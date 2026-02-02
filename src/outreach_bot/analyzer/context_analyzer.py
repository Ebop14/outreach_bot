"""Content quality assessment and context analysis."""

import logging

from outreach_bot.config import get_settings
from outreach_bot.models.context import ScrapedContext, ContextQuality, Article
from outreach_bot.models.contact import Contact
from outreach_bot.scraper.fetcher import Fetcher
from outreach_bot.scraper.blog_finder import BlogFinder
from outreach_bot.cache.sqlite_cache import SQLiteCache

logger = logging.getLogger(__name__)


class ContextAnalyzer:
    """Analyze and assess content quality for contacts."""

    def __init__(self, fetcher: Fetcher, cache: SQLiteCache):
        self.fetcher = fetcher
        self.cache = cache
        self.blog_finder = BlogFinder(fetcher)
        self.settings = get_settings()

    async def get_context(self, contact: Contact) -> ScrapedContext:
        """
        Get or scrape context for a contact.

        Checks cache first, then scrapes if needed.
        """
        domain = contact.domain
        logger.info(f"Getting context for domain: {domain}")

        # Check cache first
        cached = await self.cache.get_context(domain)
        if cached:
            logger.info(f"  Using cached context (quality: {cached.quality.value})")
            return cached

        # Scrape fresh context
        logger.info(f"  No cache found, scraping fresh content...")
        context = await self._scrape_context(domain)

        # Cache the result
        await self.cache.set_context(context)

        return context

    async def _scrape_context(self, domain: str) -> ScrapedContext:
        """Scrape and analyze content from a domain."""
        # Try to find blog
        logger.info(f"  Searching for blog on {domain}...")
        blog_url = await self.blog_finder.find_blog(domain)

        if not blog_url:
            logger.warning(f"  ✗ No blog found for {domain}")
            return ScrapedContext(
                domain=domain,
                quality=ContextQuality.LOW_QUALITY,
                error_message="No blog or content section found",
            )

        logger.info(f"  ✓ Found blog: {blog_url}")

        # Scrape articles
        logger.info(f"  Scraping articles from {blog_url}...")
        articles = await self.blog_finder.scrape_articles(blog_url, max_articles=3)

        if not articles:
            logger.warning(f"  ✗ No articles extracted from {blog_url}")
            return ScrapedContext(
                domain=domain,
                quality=ContextQuality.LOW_QUALITY,
                blog_url=blog_url,
                error_message="Blog found but no articles could be extracted",
            )

        logger.info(f"  ✓ Extracted {len(articles)} articles")

        # Assess quality
        quality = self._assess_quality(articles)
        logger.info(f"  Content quality assessed as: {quality.value}")

        # Build summary for AI prompt
        summary = self._build_summary(articles)

        return ScrapedContext(
            domain=domain,
            quality=quality,
            blog_url=blog_url,
            articles=articles,
            summary=summary,
        )

    def _assess_quality(self, articles: list[Article]) -> ContextQuality:
        """
        Assess content quality.

        GOOD = at least 1 article with 100+ words
        LOW_QUALITY = no substantial content
        """
        min_words = self.settings.min_article_words

        for article in articles:
            logger.info(f"    Article: '{article.title}' - {article.word_count} words")
            if article.word_count >= min_words:
                logger.info(f"    ✓ Article meets minimum word count ({min_words} words)")
                return ContextQuality.GOOD

        logger.warning(f"    ✗ No articles meet minimum word count ({min_words} words)")
        return ContextQuality.LOW_QUALITY

    def _build_summary(self, articles: list[Article]) -> str:
        """
        Build a summary of articles for the AI prompt.

        Truncates to max_article_content_chars.
        """
        max_chars = self.settings.max_article_content_chars
        parts = []

        for article in articles:
            part = f"Title: {article.title}\n{article.content[:500]}"
            parts.append(part)

        summary = "\n\n---\n\n".join(parts)

        # Truncate if needed
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "..."

        return summary
