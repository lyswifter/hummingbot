import unittest

from hummingbot.connector.exchange.okx import okx_utils


class OkxUtilsTests(unittest.TestCase):

    def _config(self, **overrides):
        params = dict(
            okx_api_key="someKey",
            okx_secret_key="someSecret",
            okx_passphrase="somePassphrase",
        )
        params.update(overrides)
        return okx_utils.OKXConfigMap(**params)

    def test_use_demo_trading_defaults_to_false(self):
        config = self._config()
        self.assertFalse(config.okx_use_demo_trading)

    def test_use_demo_trading_can_be_enabled(self):
        config = self._config(okx_use_demo_trading=True)
        self.assertTrue(config.okx_use_demo_trading)

    def test_use_demo_trading_is_a_connect_key(self):
        # The flag must be part of the connect flow so it is persisted with the keys.
        field = okx_utils.OKXConfigMap.model_fields["okx_use_demo_trading"]
        self.assertTrue(field.json_schema_extra.get("is_connect_key"))


if __name__ == "__main__":
    unittest.main()
