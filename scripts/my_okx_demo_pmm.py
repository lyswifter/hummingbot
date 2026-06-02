import logging
import os
from decimal import Decimal
from typing import Dict, List

from pydantic import Field

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import MarketDict, OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


# =============================================================================
# 1) 配置类:决定 `create --v2-config` 会问你哪些参数,以及默认值
#    每个 Field(...) 就是一个可配置项。带默认值,所以也能直接用默认跑。
# =============================================================================
class MyOkxDemoPMMConfig(StrategyV2ConfigBase):
    # 这两行是 V2 脚本的固定样板:声明自己是哪个脚本文件、不挂任何 controller
    script_file_name: str = os.path.basename(__file__)
    controllers_config: List[str] = []

    exchange: str = Field("okx_demo")          # 交易所连接器:OKX 现货模拟盘
    trading_pair: str = Field("BTC-USDT")      # 交易对
    order_amount: Decimal = Field(Decimal("0.001"))   # 每单数量(基础币 BTC)
    bid_spread: Decimal = Field(Decimal("0.005"))     # 买单挂在中间价下方 0.5%
    ask_spread: Decimal = Field(Decimal("0.005"))     # 卖单挂在中间价上方 0.5%
    order_refresh_time: int = Field(20)        # 每 20 秒撤单重挂一次

    # 框架启动时调用,告诉引擎"我要订阅哪个交易所的哪个交易对的行情"
    def update_markets(self, markets: MarketDict) -> MarketDict:
        markets[self.exchange] = markets.get(self.exchange, set()) | {self.trading_pair}
        return markets


# =============================================================================
# 2) 策略类:真正的交易逻辑
# =============================================================================
class MyOkxDemoPMM(StrategyV2Base):
    """
    最小做市(Pure Market Making)起步脚本。
    每个 order_refresh_time:撤掉所有挂单 -> 在中间价两侧按点差各挂一个限价单。
    成交后在日志/界面打印一条提示。
    """

    create_timestamp = 0  # 记录"下次该重新挂单的时间戳"

    def __init__(self, connectors: Dict[str, ConnectorBase], config: MyOkxDemoPMMConfig):
        super().__init__(connectors, config)
        self.config = config

    # on_tick 每秒被框架调用一次 —— 这是策略的"心跳"
    def on_tick(self):
        # 还没到重挂时间就什么都不做,直接返回
        if self.create_timestamp > self.current_timestamp:
            return
        self.cancel_all_orders()                                  # 1. 撤掉旧单
        proposal = self.create_proposal()                         # 2. 算出想挂的单
        proposal = self.adjust_proposal_to_budget(proposal)       # 3. 按余额裁剪(钱不够就不挂)
        self.place_orders(proposal)                               # 4. 下单
        self.create_timestamp = self.config.order_refresh_time + self.current_timestamp  # 5. 定下次时间

    # 根据中间价 + 点差,构造一个买单和一个卖单
    def create_proposal(self) -> List[OrderCandidate]:
        mid_price = self.connectors[self.config.exchange].get_price_by_type(
            self.config.trading_pair, PriceType.MidPrice)
        buy_price = mid_price * (Decimal("1") - self.config.bid_spread)
        sell_price = mid_price * (Decimal("1") + self.config.ask_spread)

        buy = OrderCandidate(
            trading_pair=self.config.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
            order_side=TradeType.BUY, amount=self.config.order_amount, price=buy_price)
        sell = OrderCandidate(
            trading_pair=self.config.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
            order_side=TradeType.SELL, amount=self.config.order_amount, price=sell_price)
        return [buy, sell]

    # 让框架按当前余额自动裁剪订单(余额不足时整单丢弃,避免下出会被拒的单)
    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        return self.connectors[self.config.exchange].budget_checker.adjust_candidates(
            proposal, all_or_none=True)

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            if order.order_side == TradeType.BUY:
                self.buy(self.config.exchange, order.trading_pair, order.amount,
                         order.order_type, order.price)
            else:
                self.sell(self.config.exchange, order.trading_pair, order.amount,
                          order.order_type, order.price)

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.config.exchange):
            self.cancel(self.config.exchange, order.trading_pair, order.client_order_id)

    # 任何一单成交时框架自动回调这里
    def did_fill_order(self, event: OrderFilledEvent):
        msg = (f"成交 {event.trade_type.name} {event.amount} {event.trading_pair} "
               f"@ {event.price} ({self.config.exchange})")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)   # 在 TUI 顶部弹一条提示
