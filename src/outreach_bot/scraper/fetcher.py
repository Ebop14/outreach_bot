"""HTTP fetching with rate limiting and connection pooling."""

import asyncio
from datetime import datetime
from typing import Optional

import httpx
from aiolimiter import AsyncLimiter

from outreach_bot.config import get_settings


class Fetcher:
    """Async HTTP fetcher with rate limiting."""

    def __init__(self):
        settings = get_settings()
        self._rate_limiter = AsyncLimiter(
            settings.rate_limit_requests_per_second, 1.0
        )
        self._domain_delay = settings.rate_limit_domain_delay_seconds
        self._timeout = settings.scrape_timeout_seconds
        self._last_domain_access: dict[str, datetime] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "Fetcher":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self._client:
            await self._client.aclose()

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL for rate limiting."""
        if "://" in url:
            url = url.split("://", 1)[1]
        return url.split("/", 1)[0].lower()

    async def _wait_for_domain(self, domain: str):
        """Ensure minimum delay between requests to same domain."""
        if domain in self._last_domain_access:
            elapsed = (datetime.utcnow() - self._last_domain_access[domain]).total_seconds()
            if elapsed < self._domain_delay:
                await asyncio.sleep(self._domain_delay - elapsed)
        self._last_domain_access[domain] = datetime.utcnow()

    async def fetch(
        self, url: str, max_retries: int = 3
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Fetch URL content with rate limiting and retries.

        Returns:
            Tuple of (html_content, error_message). One will be None.
        """
        if not self._client:
            raise RuntimeError("Fetcher must be used as async context manager")

        # Ensure URL has protocol
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        domain = self._extract_domain(url)

        for attempt in range(max_retries):
            try:
                # Apply rate limiting
                async with self._rate_limiter:
                    await self._wait_for_domain(domain)

                    response = await self._client.get(url)
                    response.raise_for_status()

                    # Check content type
                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type and "text/plain" not in content_type:
                        return None, f"Non-HTML content type: {content_type}"

                    return response.text, None

            except httpx.TimeoutException:
                if attempt == max_retries - 1:
                    return None, f"Timeout after {max_retries} attempts"
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None, "Page not found (404)"
                if e.response.status_code in (429, 503):
                    # Rate limited or service unavailable - wait longer
                    if attempt == max_retries - 1:
                        return None, f"HTTP {e.response.status_code} after {max_retries} attempts"
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    return None, f"HTTP error: {e.response.status_code}"

            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    return None, f"Request error: {str(e)}"
                await asyncio.sleep(2 ** attempt)

        return None, "Max retries exceeded"
