import aiohttp
import asyncio
import base64
import logging
import nest_asyncio
from typing import Dict, Optional, Any, AsyncGenerator
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_log, retry_if_not_exception_type
from functools import wraps
from aiohttp import ClientError, ClientTimeout, ClientResponseError

# Apply nest_asyncio to handle nested event loops (e.g., Jupyter)
nest_asyncio.apply()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NonRetryableError(Exception):
    """Custom exception for non-retryable errors like 400 Bad Request."""
    pass

def with_retry_strategy(cls):
    """Decorator to apply retry strategy to class methods post-definition."""
    retry_decorator = cls._get_retry_strategy()
    cls.get = retry_decorator(cls.get)
    cls.get_streamed = retry_decorator(cls.get_streamed)
    cls.post = retry_decorator(cls.post)
    return cls

class Dhis2:
    """An asynchronous DHIS2 API client optimized for scalability and ease of use with improved timeout and retry handling."""
    # Define class attributes
    max_retries = 3
    backoff_factor = 1.0
    rate_limit_per_second = 200
    default_timeout = 30

    def __init__(self, username: str, password: str, url: str = "https://dhis-country_here.icap.columbia.edu/api/", rate_limit_per_second: int = 200):
        """
        Initialize the DHIS2 client with authentication and async session management.

        Args:
            username (str): DHIS2 username.
            password (str): DHIS2 password.
            url (str): Base URL for the DHIS2 API.
            rate_limit_per_second (int): Maximum requests per second.
        """
        self.username = username
        self.password = password
        self.base_url = url.rstrip('/') + '/api/' if not url.endswith('/api/') else url.rstrip('/') + '/'
        self._headers = self._get_auth_headers()
        self._semaphore = asyncio.Semaphore(rate_limit_per_second)
        self._session = None

    def _get_auth_headers(self) -> Dict[str, str]:
        """Generate authentication headers using Basic Auth."""
        user_pass = f"{self.username}:{self.password}"
        token = base64.b64encode(user_pass.encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    @classmethod
    def _get_retry_strategy(cls):
        """Configure and return the retry strategy for async requests."""
        return retry(
            stop=stop_after_attempt(cls.max_retries),
            wait=wait_exponential(multiplier=cls.backoff_factor, min=1, max=10),
            retry=retry_if_exception_type((ClientError, asyncio.TimeoutError, aiohttp.ClientTimeout)) &
                  retry_if_not_exception_type((NonRetryableError, ClientResponseError)),  # Exclude 400 errors
            before_sleep=before_log(logger, logging.WARNING),
            before=lambda retry_state: logger.debug(f"Retrying {retry_state.fn.__name__} - Attempt {retry_state.attempt_number}/{cls.max_retries}, "
                                                  f"last exception: {str(retry_state.outcome.exception()) if retry_state.outcome and retry_state.outcome.failed else 'None'}")
        )

    async def _init_session(self) -> aiohttp.ClientSession:
        """Initialize the async session with optimized settings."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self._headers,
                connector=aiohttp.TCPConnector(limit=200),
                timeout=aiohttp.ClientTimeout(total=self.default_timeout, connect=5)
            )
        return self._session

    async def close(self):
        """Close the async session to free resources, called only at shutdown."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    @staticmethod
    async def _handle_response(response):
        """Handle response parsing with error checking and raise custom exceptions."""
        try:
            response.raise_for_status()
            text = await response.text()
            if not text.strip():
                raise ClientError("Empty response received from the server")
            return await response.json()
        except ClientResponseError as e:
            if e.status == 400:
                logger.error(f"Bad request error {e.status} for URL {e.request_info.url}: {str(e)}")
                raise NonRetryableError(f"Bad request: {str(e)}") from e
            elif e.status >= 500:
                logger.warning(f"Server error {e.status} for URL {e.request_info.url}: {str(e)}")
                raise
            else:
                logger.error(f"Non-retryable HTTP error {e.status} for URL {e.request_info.url}: {str(e)}")
                raise NonRetryableError(f"HTTP error {e.status}: {str(e)}") from e
        except (ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network or timeout error for URL {response.url if 'response' in locals() else 'unknown'}: {str(e)}")
            raise

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: Optional[int] = None) -> Dict:
        """Perform an asynchronous GET request to the DHIS2 API with retry and custom timeout."""
        url = f"{self.base_url}{endpoint.lstrip('/')}"
        logger.debug(f"Constructed URL: {url} with params: {params}")
        session = await self._init_session()
        custom_timeout = aiohttp.ClientTimeout(total=timeout if timeout is not None else self.default_timeout)
        async with self._semaphore:
            try:
                async with session.get(url, params=params, timeout=custom_timeout) as response:
                    return await self._handle_response(response)
            except (ClientError, asyncio.TimeoutError) as e:
                logger.error(f"GET request failed for {url}: {str(e)}")
                raise

    async def get_streamed(self, endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Perform an asynchronous GET request with streaming response."""
        url = f"{self.base_url}{endpoint.lstrip('/')}"
        session = await self._init_session()
        custom_timeout = aiohttp.ClientTimeout(total=timeout if timeout is not None else self.default_timeout)
        async with self._semaphore:
            try:
                async with session.get(url, params=params, timeout=custom_timeout) as response:
                    response.raise_for_status()
                    async for chunk in response.content.iter_chunked(1024):
                        yield chunk.decode('utf-8')
            except (ClientError, asyncio.TimeoutError) as e:
                logger.error(f"Streamed GET request failed for {url}: {str(e)}")
                raise

    async def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, timeout: Optional[int] = None) -> Dict:
        """Perform an asynchronous POST request to the DHIS2 API."""
        url = f"{self.base_url}{endpoint.lstrip('/')}"
        session = await self._init_session()
        custom_timeout = aiohttp.ClientTimeout(total=timeout if timeout is not None else self.default_timeout)
        async with self._semaphore:
            try:
                async with session.post(url, json=data, timeout=custom_timeout) as response:
                    return await self._handle_response(response)
            except (ClientError, asyncio.TimeoutError) as e:
                logger.error(f"POST request failed for {url}: {e}")
                raise

    async def __aenter__(self):
        """Support async context manager by initializing the session."""
        await self._init_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Do not close session automatically; defer to explicit close."""
        pass

Dhis2 = with_retry_strategy(Dhis2)

def run_async(coro):
    """
    Run an async coroutine in a way that works in both script and interactive environments.

    Args:
        coro: The coroutine to run.

    Returns:
        The result of the coroutine.
    """
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            return asyncio.ensure_future(coro)
    except RuntimeError:
        return asyncio.run(coro)
    return asyncio.run(coro)