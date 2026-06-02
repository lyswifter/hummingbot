import asyncio
import unittest
from typing import Awaitable

from hummingbot.connector.exchange.okx import okx_constants as CONSTANTS, okx_utils as utils, okx_web_utils as web_utils
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class OKXWebUtilsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.new_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    # --- Demo (paper trading) URL routing ---------------------------------------------------------

    def test_demo_rest_base_url_uses_production_host(self):
        # Demo Trading REST shares the production host; only the header differentiates it.
        self.assertEqual("https://www.okx.com/", CONSTANTS.get_okx_base_url(CONSTANTS.DEMO_SUB_DOMAIN))

    def test_demo_websocket_urls(self):
        self.assertEqual("wss://wspap.okx.com:8443", CONSTANTS.get_ws_url(CONSTANTS.DEMO_SUB_DOMAIN))
        self.assertEqual(
            "wss://wspap.okx.com:8443/ws/v5/public?brokerId=9999",
            CONSTANTS.get_okx_ws_uri_public(CONSTANTS.DEMO_SUB_DOMAIN),
        )
        self.assertEqual(
            "wss://wspap.okx.com:8443/ws/v5/private?brokerId=9999",
            CONSTANTS.get_okx_ws_uri_private(CONSTANTS.DEMO_SUB_DOMAIN),
        )

    def test_production_websocket_urls_unchanged(self):
        self.assertEqual("wss://ws.okx.com:8443/ws/v5/public", CONSTANTS.get_okx_ws_uri_public("www"))
        self.assertEqual("wss://wsus.okx.com:8443/ws/v5/private", CONSTANTS.get_okx_ws_uri_private("app"))

    # --- Simulated trading header injection -------------------------------------------------------

    def test_simulated_trading_pre_processor_adds_header(self):
        pre_processor = web_utils.SimulatedTradingRESTPreProcessor(simulated_trading=True)
        request = RESTRequest(method=RESTMethod.GET, url="/api/v5/account/balance")
        result = self.async_run_with_timeout(pre_processor.pre_process(request))
        self.assertEqual("1", result.headers["x-simulated-trading"])

    def test_simulated_trading_pre_processor_omits_header_when_disabled(self):
        pre_processor = web_utils.SimulatedTradingRESTPreProcessor(simulated_trading=False)
        request = RESTRequest(method=RESTMethod.GET, url="/api/v5/account/balance")
        result = self.async_run_with_timeout(pre_processor.pre_process(request))
        self.assertTrue(result.headers is None or "x-simulated-trading" not in result.headers)

    def test_build_api_factory_with_simulated_trading(self):
        api_factory = web_utils.build_api_factory(time_provider=lambda: None, simulated_trading=True)
        self.assertIsInstance(api_factory, WebAssistantsFactory)
        sim_pre_processors = [
            p for p in api_factory._rest_pre_processors
            if isinstance(p, web_utils.SimulatedTradingRESTPreProcessor)
        ]
        self.assertEqual(1, len(sim_pre_processors))
        self.assertTrue(sim_pre_processors[0]._simulated_trading)

    def test_build_api_factory_defaults_to_production(self):
        api_factory = web_utils.build_api_factory(time_provider=lambda: None)
        sim_pre_processors = [
            p for p in api_factory._rest_pre_processors
            if isinstance(p, web_utils.SimulatedTradingRESTPreProcessor)
        ]
        self.assertEqual(1, len(sim_pre_processors))
        self.assertFalse(sim_pre_processors[0]._simulated_trading)

    # --- OTHER_DOMAINS (okx_demo) registration ----------------------------------------------------

    def test_demo_other_domain_registered(self):
        self.assertEqual(["okx_demo"], utils.OTHER_DOMAINS)
        self.assertEqual(CONSTANTS.DEMO_SUB_DOMAIN, utils.OTHER_DOMAINS_PARAMETER["okx_demo"])
        self.assertEqual("BTC-USDT", utils.OTHER_DOMAINS_EXAMPLE_PAIR["okx_demo"])
        self.assertIn("okx_demo", utils.OTHER_DOMAINS_DEFAULT_FEES)

    def test_demo_config_map_fields_map_to_parent_constructor(self):
        # AllConnectorSettings maps a sub-domain's config keys to the parent connector kwargs by replacing
        # the sub-domain name with the parent name. Verify the demo field names produce OkxExchange kwargs.
        demo_keys = utils.OTHER_DOMAINS_KEYS["okx_demo"]
        fields = [f for f in type(demo_keys).model_fields if f != "connector"]
        mapped = {f.replace("okx_demo", "okx") for f in fields}
        self.assertEqual({"okx_api_key", "okx_secret_key", "okx_passphrase"}, mapped)


if __name__ == "__main__":
    unittest.main()
