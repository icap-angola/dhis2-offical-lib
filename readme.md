# Dhis2 Python Library

An asynchronous Python library for interacting with the DHIS2 API, designed for scalability, ease of use, and robust error handling. This library provides a comprehensive set of tools for data and metadata import/export, rate limiting, and streaming responses, optimized for DHIS2 versions >= 2.25.

---

## 🧭 Overview

The `dhis2` library wraps the `aiohttp` library to provide an asynchronous client for the DHIS2 API. It supports authentication, retry mechanisms for network issues, rate limiting, and both synchronous and streaming data retrieval. Ideal for developers building applications that integrate with DHIS2 instances.

---

## 🚀 Features

- **Asynchronous API Calls**: Leverage Python's `asyncio` for non-blocking requests.
- **Retry Mechanism**: Automatically retries failed requests (e.g., network errors) up to 3 times with exponential backoff.
- **Rate Limiting**: Enforces a configurable limit (default: 200 requests/second) to comply with DHIS2 API policies.
- **Streaming Responses**: Retrieve large datasets in chunks for memory-efficient processing.
- **Error Handling**: Custom handling for non-retryable errors (e.g., HTTP 400) and retryable server errors (e.g., HTTP 500).
- **Context Manager Support**: Use with `async with` for session management.
- **JSON Support**: Native handling of JSON data for metadata and data value operations.

---

## 📦 Installation

Install the library using pip:

```bash
pip install dhis2-async


# ✅ Prerequisites
    -   Python 3.6 or higher

    -   aiohttp, tenacity, and nest_asyncio (installed automatically with the package)

# Usage

# Basic example
`
import asyncio
from dhis2 import Dhis2, run_async

async def main():
    # Initialize the client
    dhis2_client = Dhis2(
        username="your_username",
        password="your_password",
        url="https://your-dhis2-instance/api/"
    )

    try:
        # Fetch organization units
        response = await dhis2_client.get("organisationUnits", params={"fields": "id,name"})
        print(response)

        # Post metadata
        metadata = {"dataElements": [{"name": "Test Element", "id": "test123"}]}
        post_response = await dhis2_client.post("metadata", data=metadata)
        print(post_response)
    finally:
        await dhis2_client.close()

if __name__ == "__main__":
    run_async(main())



`

# Streaming example

`
async def stream_data():
    dhis2_client = Dhis2(username="your_username", password="your_password")
    async for chunk in dhis2_client.get_streamed("dataValues", params={"orgUnit": "OU123"}):
        print(chunk)
    await dhis2_client.close()

run_async(stream_data())


`

# API Documentation

`
Dhis2(
    username: str,
    password: str,
    url: str = "https://dhis-ao.icap.columbia.edu/api/",
    rate_limit_per_second: int = 200
)


`

-   username: DHIS2 username

-   password: DHIS2 password

-   url: Base DHIS2 API URL (defaults to ICAP instance)

-   rate_limit_per_second: Maximum requests per second (default: 200)

# 🧩 Methods
    `
    get(endpoint: str, params: Dict = None, timeout: int = None) -> Dict
    Performs a GET request with retry logic.
    `
    `
    endpoint: API endpoint (e.g., tracker/enrollments)
    `
    `
    params: Query parameters
    `
    `
    timeout: Custom timeout in seconds (default: 30)

    `


`
    get_streamed(endpoint: str, params: Dict = None, timeout: int = None) -> AsyncGenerator[str, None]
    Streams GET request responses in chunks.

    Yields decoded UTF-8 chunks as they arrive.

    post(endpoint: str, data: Dict = None, timeout: int = None) -> Dict
    Performs a POST request with JSON data.

    data: JSON payload

    close()
    Closes the async session to free resources.

    __aenter__ and __aexit__
    Supports async with context manager for clean session handling.

    ❗ Error Handling
    NonRetryableError: Raised for HTTP 400 and other non-retryable errors.

    Retries are automatically attempted for network or server errors (e.g., HTTP 500) using exponential backoff.

`

# 🤝 Contributing
    Contributions are welcome! Please follow these steps:

    Fork the repository on GitHub.

    Create a new branch for your feature or bug fix.

    Submit a pull request with a clear description of changes.

    Ensure tests pass and add new tests if applicable.

    Please open an issue for bugs or feature requests.


#  📬 Contact
For support or questions, please open an issue on the GitHub repository or contact the maintainers via email at sfc2128@cumc.columbia.edu