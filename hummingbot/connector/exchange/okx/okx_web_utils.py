from typing import Callable, Optional
from urllib.parse import urljoin

import hummingbot.connector.exchange.okx.okx_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided REST endpoint

    :param path_url: a public REST endpoint
    :param domain: The full domain, required because it varies based on where account is registered.

    :return: the full URL to the endpoint
    """
    return urljoin(domain, path_url)


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return public_rest_url(path_url, domain)


class OKXSimulatedTradingRESTPreProcessor(RESTPreProcessorBase):
    """Injects the OKX demo (simulated) trading header into every REST request."""

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        request.headers = request.headers or {}
        request.headers.update(CONSTANTS.SIMULATED_TRADING_HEADERS)
        return request


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        use_demo_trading: bool = False) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain
    ))
    rest_pre_processors = [
        TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
    ]
    if use_demo_trading:
        rest_pre_processors.append(OKXSimulatedTradingRESTPreProcessor())
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=rest_pre_processors)
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=public_rest_url(
            path_url=CONSTANTS.OKX_SERVER_TIME_PATH,
            domain=domain
        ),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.OKX_SERVER_TIME_PATH,
    )
    server_time = float(response["data"][0]["ts"])

    return server_time
