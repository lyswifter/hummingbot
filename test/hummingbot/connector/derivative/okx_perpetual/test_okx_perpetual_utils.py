import unittest

from hummingbot.connector.derivative.okx_perpetual import okx_perpetual_utils as utils


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

    def test_other_domains_expose_demo(self):
        self.assertIn("okx_perpetual_demo", utils.OTHER_DOMAINS)
        self.assertEqual("okx_perpetual_demo", utils.OTHER_DOMAINS_PARAMETER["okx_perpetual_demo"])
        self.assertIn("okx_perpetual_demo", utils.OTHER_DOMAINS_KEYS)
        self.assertIn("okx_perpetual_demo", utils.OTHER_DOMAINS_DEFAULT_FEES)
        self.assertIn("okx_perpetual_demo", utils.OTHER_DOMAINS_EXAMPLE_PAIR)

    def test_demo_config_map_key_fields_remap_to_parent_connector(self):
        # OTHER_DOMAINS strips the connector name prefix to feed the parent __init__,
        # so the field names must be the parent params prefixed with "okx_perpetual_demo".
        config_map = utils.OTHER_DOMAINS_KEYS["okx_perpetual_demo"]
        demo_fields = type(config_map).model_fields
        parent_fields = utils.OkxPerpetualConfigMap.model_fields
        for field in ("okx_perpetual_demo_api_key",
                      "okx_perpetual_demo_secret_key",
                      "okx_perpetual_demo_passphrase"):
            self.assertIn(field, demo_fields)
            parent_field = field.replace("okx_perpetual_demo", "okx_perpetual")
            self.assertIn(parent_field, parent_fields)
