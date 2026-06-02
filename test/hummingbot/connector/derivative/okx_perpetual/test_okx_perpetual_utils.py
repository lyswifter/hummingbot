import unittest

from hummingbot.connector.derivative.okx_perpetual import (
    okx_perpetual_constants as CONSTANTS,
    okx_perpetual_utils as utils,
)


class OKXPerpetualWebUtilsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def test_is_exchange_information_valid(self):
        exchange_info = {
            "instType": "SWAP",
            "ctType": "linear",
            "state": "live"
        }
        self.assertTrue(utils.is_exchange_information_valid(exchange_info))
        exchange_info = {
            "instType": "FUTURES",
            "ctType": "linear",
            "state": "live"
        }
        self.assertFalse(utils.is_exchange_information_valid(exchange_info))

    def test_is_linear_perpetual(self):
        self.assertTrue(utils.is_linear_perpetual("BTC-USDT"))
        self.assertTrue(utils.is_linear_perpetual("BTC-USDC"))
        self.assertFalse(utils.is_linear_perpetual("BTC-USD"))

    def test_get_next_funding_timestamp(self):
        current_timestamp = 1626192000.0
        self.assertEqual(utils.get_next_funding_timestamp(current_timestamp), 1626220800.0)

    def test_demo_other_domain_registered(self):
        self.assertEqual([CONSTANTS.DEMO_DOMAIN], utils.OTHER_DOMAINS)
        # The domain parameter passed to the connector constructor must equal the demo domain key,
        # otherwise REST/WS URL lookups return None.
        self.assertEqual(CONSTANTS.DEMO_DOMAIN, utils.OTHER_DOMAINS_PARAMETER[CONSTANTS.DEMO_DOMAIN])
        self.assertEqual("BTC-USDT", utils.OTHER_DOMAINS_EXAMPLE_PAIR[CONSTANTS.DEMO_DOMAIN])
        self.assertIn(CONSTANTS.DEMO_DOMAIN, utils.OTHER_DOMAINS_DEFAULT_FEES)

    def test_demo_config_map_fields_map_to_parent_constructor(self):
        # AllConnectorSettings maps a sub-domain's config keys to the parent connector kwargs by replacing
        # the sub-domain name with the parent name (see ConnectorSetting.conn_init_parameters). Verify the
        # demo field names produce the exact constructor kwargs of OkxPerpetualDerivative.
        demo_keys = utils.OTHER_DOMAINS_KEYS[CONSTANTS.DEMO_DOMAIN]
        fields = [f for f in type(demo_keys).model_fields if f != "connector"]
        mapped = {f.replace(CONSTANTS.DEMO_DOMAIN, CONSTANTS.DEFAULT_DOMAIN) for f in fields}
        self.assertEqual(
            {"okx_perpetual_api_key", "okx_perpetual_secret_key", "okx_perpetual_passphrase"},
            mapped,
        )
