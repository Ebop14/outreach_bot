"""Content quality assessment and context analysis."""

from outreach_bot.config import get_settings
from outreach_bot.models.context import ScrapedContext, ContextQuality, Article
from outreach_bot.models.contact import Contact
from outreach_bot.scraper.fetcher import Fetcher
from outreach_bot.scraper.blog_finder import BlogFinder
from outreach_bot.cache.sqlite_cache import SQLiteCache


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

        # Check cache first
        cached = await self.cache.get_context(domain)
        if cached:
            return cached

        # Scrape fresh context
        context = await self._scrape_context(domain)

        # Cache the result
        await self.cache.set_context(context)

        return context

    async def _scrape_context(self, domain: str) -> ScrapedContext:
        """Scrape and analyze content from a domain."""
        # Try to find blog
        blog_url = await self.blog_finder.find_blog(domain)

        if not blog_url:
            return ScrapedContext(
                domain=domain,
                quality=ContextQuality.LOW_QUALITY,
                error_message="No blog or content section found",
            )

        # Scrape articles
        articles = await self.blog_finder.scrape_articles(blog_url, max_articles=3)

        if not articles:
            return ScrapedContext(
                domain=domain,
                quality=ContextQuality.LOW_QUALITY,
                blog_url=blog_url,
                error_message="Blog found but no articles could be extracted",
            )

        # Assess quality
        quality = self._assess_quality(articles)

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
            if article.word_count >= min_words:
                return ContextQuality.GOOD

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
