import asyncio
import unittest
from typing import Awaitable

from hummingbot.connector.exchange.okx import okx_constants as CONSTANTS, okx_web_utils as web_utils
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class OkxWebUtilsTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    # --- WebSocket URLs: live vs demo ---
    def test_public_ws_url_live(self):
        self.assertEqual(
            "wss://ws.okx.com:8443/ws/v5/public",
            CONSTANTS.get_okx_ws_uri_public("www"),
        )

    def test_public_ws_url_demo(self):
        self.assertEqual(
            "wss://wspap.okx.com:8443/ws/v5/public?brokerId=9999",
            CONSTANTS.get_okx_ws_uri_public("www", use_demo_trading=True),
        )

    def test_private_ws_url_live(self):
        self.assertEqual(
            "wss://ws.okx.com:8443/ws/v5/private",
            CONSTANTS.get_okx_ws_uri_private("www"),
        )

    def test_private_ws_url_demo(self):
        self.assertEqual(
            "wss://wspap.okx.com:8443/ws/v5/private?brokerId=9999",
            CONSTANTS.get_okx_ws_uri_private("www", use_demo_trading=True),
        )

    def test_demo_ws_url_ignores_registration_subdomain(self):
        # Demo trading always routes through the dedicated wspap host regardless of subdomain.
        self.assertEqual(
            CONSTANTS.get_okx_ws_uri_private("www", use_demo_trading=True),
            CONSTANTS.get_okx_ws_uri_private("app", use_demo_trading=True),
        )

    # --- REST base URL stays on the live domain for demo (only the header differs) ---
    def test_rest_base_url_unchanged(self):
        self.assertEqual("https://www.okx.com/", CONSTANTS.get_okx_base_url("www"))

    # --- build_api_factory wires the simulated-trading pre-processor only when enabled ---
    def test_build_api_factory_live_has_no_simulated_pre_processor(self):
        api_factory = web_utils.build_api_factory(
            time_synchronizer=TimeSynchronizer(),
            time_provider=lambda: None,
        )
        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertFalse(
            any(isinstance(p, web_utils.OKXSimulatedTradingRESTPreProcessor)
                for p in api_factory._rest_pre_processors)
        )

    def test_build_api_factory_demo_adds_simulated_pre_processor(self):
        api_factory = web_utils.build_api_factory(
            time_synchronizer=TimeSynchronizer(),
            time_provider=lambda: None,
            use_demo_trading=True,
        )
        self.assertTrue(
            any(isinstance(p, web_utils.OKXSimulatedTradingRESTPreProcessor)
                for p in api_factory._rest_pre_processors)
        )

    # --- the pre-processor injects the simulated-trading header ---
    def test_simulated_trading_pre_processor_injects_header(self):
        pre_processor = web_utils.OKXSimulatedTradingRESTPreProcessor()
        request = RESTRequest(method=RESTMethod.GET, url="/TEST_URL")
        result = self.async_run_with_timeout(pre_processor.pre_process(request))
        self.assertEqual("1", result.headers["x-simulated-trading"])

    def test_simulated_trading_pre_processor_preserves_existing_headers(self):
        pre_processor = web_utils.OKXSimulatedTradingRESTPreProcessor()
        request = RESTRequest(
            method=RESTMethod.GET, url="/TEST_URL", headers={"Content-Type": "application/json"})
        result = self.async_run_with_timeout(pre_processor.pre_process(request))
        self.assertEqual("application/json", result.headers["Content-Type"])
        self.assertEqual("1", result.headers["x-simulated-trading"])


if __name__ == "__main__":
    unittest.main()
