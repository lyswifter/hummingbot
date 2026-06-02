from decimal import Decimal
from typing import List, Optional

import pandas_ta as ta  # noqa: F401
from pydantic import Field

from hummingbot.core.data_type.common import MarketDict, OrderType, PositionMode, PriceType, TradeType
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class SmartGridConfig(ControllerConfigBase):
    """
    A "smart" grid that reuses Hummingbot's GridExecutor (which handles spot & perpetual, the triple-barrier
    risk management and activation_bounds) and adds the three things the built-in grids lack:

      1. ATR-adaptive range  – the grid width is derived from realized volatility (NATR), not a fixed band.
      2. Trend filter        – an EMA-based regime gate decides the side and whether to trade at all.
      3. Trailing grid        – "spawn-on-empty": the executor's own barriers close it flat, then a fresh grid
                                is re-centered on the new mid price. Trailing-up falls out for free (price exits
                                above -> take-profit closes in profit -> respawn higher). Trailing-down (catching
                                a falling knife) is opt-in via `trailing_down`.

    Works for both spot (e.g. okx_demo) and perpetual (e.g. okx_perpetual_demo). Note candles must come from a
    real market-data feed (`candles_connector`, e.g. "okx"), NOT the demo trading connector which has no feed.
    """
    controller_type: str = "generic"
    controller_name: str = "smart_grid"

    # --- Trading connector (where orders go). Can be okx_demo / okx_perpetual_demo / okx / okx_perpetual ---
    connector_name: str = "okx_demo"
    trading_pair: str = "BTC-USDT"

    # --- Candles source (a real feed; the demo connector has no candles) ---
    candles_connector: str = "okx"
    interval: str = "1m"
    candles_max_records: int = 300

    # --- Account (perpetual only; ignored on spot) ---
    leverage: int = 3
    position_mode: PositionMode = PositionMode.HEDGE

    # --- Regime behaviour: "auto" (trend-driven) / "long" / "short" / "neutral" ---
    mode: str = "auto"
    allow_short: bool = False  # in a downtrend, open SELL grids (perpetual only)

    # --- Capital ---
    total_amount_quote: Decimal = Field(default=Decimal("200"), json_schema_extra={"is_updatable": True})

    # --- ATR-adaptive range ---
    atr_length: int = 14
    range_atr_mult: Decimal = Field(default=Decimal("4"), json_schema_extra={"is_updatable": True})
    min_range_pct: Decimal = Field(default=Decimal("0.01"), json_schema_extra={"is_updatable": True})

    # --- Trend filter ---
    trend_ema_length: int = 50
    trend_threshold: Decimal = Field(default=Decimal("0.004"), json_schema_extra={"is_updatable": True})

    # --- Trailing grid behaviour ---
    trailing_down: bool = Field(default=False, json_schema_extra={"is_updatable": True})
    respawn_cooldown: int = Field(default=30, json_schema_extra={"is_updatable": True})

    # --- Grid execution (passed straight to GridExecutor) ---
    min_spread_between_orders: Decimal = Field(default=Decimal("0.001"), json_schema_extra={"is_updatable": True})
    min_order_amount_quote: Decimal = Field(default=Decimal("5"), json_schema_extra={"is_updatable": True})
    max_open_orders: int = Field(default=5, json_schema_extra={"is_updatable": True})
    max_orders_per_batch: int = Field(default=1, json_schema_extra={"is_updatable": True})
    order_frequency: int = Field(default=3, json_schema_extra={"is_updatable": True})
    activation_bounds: Optional[Decimal] = Field(default=Decimal("0.01"), json_schema_extra={"is_updatable": True})

    # --- Risk barriers ---
    take_profit: Decimal = Field(default=Decimal("0.002"), json_schema_extra={"is_updatable": True})  # per grid level
    stop_loss: Decimal = Field(default=Decimal("0.05"), json_schema_extra={"is_updatable": True})      # aggregate PnL
    limit_buffer: Decimal = Field(default=Decimal("0.02"), json_schema_extra={"is_updatable": True})   # hard exit beyond range

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class SmartGrid(ControllerBase):
    def __init__(self, config: SmartGridConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self._last_active_ts: float = 0.0
        self.initialize_rate_sources()

    def initialize_rate_sources(self):
        self.market_data_provider.initialize_rate_sources(
            [ConnectorPair(connector_name=self.config.connector_name, trading_pair=self.config.trading_pair)])

    @property
    def is_perpetual(self) -> bool:
        return "perpetual" in self.config.connector_name.lower()

    def get_candles_config(self) -> List["CandlesConfig"]:  # noqa: F821
        from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
        return [CandlesConfig(
            connector=self.config.candles_connector,
            trading_pair=self.config.trading_pair,
            interval=self.config.interval,
            max_records=self.config.candles_max_records,
        )]

    def get_mid_price(self) -> Decimal:
        return self.market_data_provider.get_price_by_type(
            self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)

    def active_grids(self) -> List[ExecutorInfo]:
        return [e for e in self.executors_info if e.is_active]

    # -------------------------------------------------------------------------
    # 1) Compute volatility (NATR) + trend regime from candles every control loop
    # -------------------------------------------------------------------------
    async def update_processed_data(self):
        pair = self.config.trading_pair
        candles = self.market_data_provider.get_candles_df(
            connector_name=self.config.candles_connector,
            trading_pair=pair,
            interval=self.config.interval,
            max_records=self.config.candles_max_records,
        )
        warmup = max(self.config.atr_length, self.config.trend_ema_length) + 2
        if candles is None or len(candles) < warmup:
            self.processed_data = {"natr": None, "regime": "warmup"}
            return

        natr = float(ta.natr(candles["high"], candles["low"], candles["close"], length=self.config.atr_length).iloc[-1]) / 100.0
        ema = float(ta.ema(candles["close"], length=self.config.trend_ema_length).iloc[-1])
        mid = float(self.get_mid_price())
        deviation = (mid - ema) / ema if ema else 0.0
        threshold = float(self.config.trend_threshold)
        if deviation > threshold:
            regime = "up"
        elif deviation < -threshold:
            regime = "down"
        else:
            regime = "range"
        self.processed_data = {"natr": natr, "regime": regime, "ema": ema, "deviation": deviation, "mid": mid}

    # -------------------------------------------------------------------------
    # 2) Spawn-on-empty: one grid at a time, re-centered on the current mid price
    # -------------------------------------------------------------------------
    def determine_executor_actions(self) -> List[ExecutorAction]:
        now = self.market_data_provider.time()

        # A grid is already running -> let its own barriers close it (never force-stop a position).
        if self.active_grids():
            self._last_active_ts = now
            return []

        # Cooldown after a grid finished, to avoid thrashing right after a stop-loss/take-profit close.
        if now - self._last_active_ts < self.config.respawn_cooldown:
            return []

        if self.processed_data.get("natr") is None:
            return []  # candles not ready yet

        side = self._decide_side(self.processed_data["regime"])
        if side is None:
            return []  # gated off by the trend filter (e.g. downtrend with no shorting)

        mid = self.get_mid_price()
        natr = Decimal(str(self.processed_data["natr"]))
        half_range = max(self.config.min_range_pct, natr * self.config.range_atr_mult)
        start_price = mid * (Decimal("1") - half_range)
        end_price = mid * (Decimal("1") + half_range)
        # Hard exit line just beyond the grid in the direction that hurts.
        if side == TradeType.BUY:
            limit_price = start_price * (Decimal("1") - self.config.limit_buffer)
        else:
            limit_price = end_price * (Decimal("1") + self.config.limit_buffer)

        action = self._create_grid(side, start_price, end_price, limit_price)
        return [action] if action is not None else []

    def _decide_side(self, regime: str) -> Optional[TradeType]:
        mode = self.config.mode
        if mode == "long":
            base = TradeType.BUY
        elif mode == "short":
            base = TradeType.SELL
        elif mode == "neutral":
            base = TradeType.BUY  # v1: spot-safe neutral == centered BUY grid (perp two-sided needs HEDGE, out of scope)
        else:  # auto
            if regime == "up":
                base = TradeType.BUY
            elif regime == "down":
                base = TradeType.SELL if (self.is_perpetual and self.config.allow_short) else None
            else:  # range
                base = TradeType.BUY
        if base is None:
            return None
        # Cannot short spot.
        if base == TradeType.SELL and not self.is_perpetual:
            return None
        # Don't open a BUY grid into a downtrend (falling knife) unless explicitly trailing down.
        if base == TradeType.BUY and regime == "down" and not self.config.trailing_down:
            return None
        return base

    def _create_grid(self, side: TradeType, start_price: Decimal, end_price: Decimal,
                     limit_price: Decimal) -> Optional[CreateExecutorAction]:
        trading_rules = self.market_data_provider.get_trading_rules(self.config.connector_name, self.config.trading_pair)
        min_notional = max(self.config.min_order_amount_quote,
                           trading_rules.min_notional_size if trading_rules else Decimal("5"))
        if self.config.total_amount_quote < min_notional * Decimal("3"):
            self.logger().info(f"total_amount_quote too small for a viable grid (need >= {min_notional * 3}).")
            return None

        return CreateExecutorAction(
            controller_id=self.config.id,
            executor_config=GridExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                side=side,
                start_price=start_price,
                end_price=end_price,
                limit_price=limit_price,
                leverage=self.config.leverage,
                total_amount_quote=self.config.total_amount_quote,
                min_spread_between_orders=self.config.min_spread_between_orders,
                min_order_amount_quote=self.config.min_order_amount_quote,
                max_open_orders=self.config.max_open_orders,
                max_orders_per_batch=self.config.max_orders_per_batch,
                order_frequency=self.config.order_frequency,
                activation_bounds=self.config.activation_bounds,
                keep_position=False,  # close flat on barrier so the next grid starts clean (true trailing)
                coerce_tp_to_step=True,
                triple_barrier_config=TripleBarrierConfig(
                    take_profit=self.config.take_profit,
                    stop_loss=self.config.stop_loss,
                    open_order_type=OrderType.LIMIT_MAKER,
                    take_profit_order_type=OrderType.LIMIT_MAKER,
                    time_limit=None,
                    trailing_stop=None,
                ),
            ),
        )

    def to_format_status(self) -> List[str]:
        d = self.processed_data
        regime = d.get("regime", "n/a")
        natr = d.get("natr")
        lines = [
            f"  SmartGrid [{self.config.connector_name} {self.config.trading_pair}]  mode={self.config.mode} "
            f"{'PERP x' + str(self.config.leverage) if self.is_perpetual else 'SPOT'}",
            f"  regime: {regime} | NATR: {natr * 100:.3f}% (vol) | active grids: {len(self.active_grids())}"
            if natr is not None else f"  regime: {regime} (warming up candles...)",
        ]
        return lines
