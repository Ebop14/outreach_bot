"""Blog path discovery for company websites."""

import json
import logging
from typing import Optional

from openai import OpenAI

from outreach_bot.config import get_settings
from outreach_bot.scraper.fetcher import Fetcher
from outreach_bot.scraper.parser import ArticleParser
from outreach_bot.models.context import Article

logger = logging.getLogger(__name__)


class BlogFinder:
    """Find and scrape blog content from company websites."""

    # Common blog paths to try
    BLOG_PATHS = [
        "/blog",
        "/blog/",
        "/news",
        "/news/",
        "/insights",
        "/insights/",
        "/resources",
        "/resources/",
        "/articles",
        "/articles/",
        "/posts",
        "/posts/",
        "/updates",
        "/updates/",
    ]

    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher
        self.parser = ArticleParser()
        self.settings = get_settings()
        self.client = OpenAI(
            api_key=self.settings.xai_api_key,
            base_url=self.settings.xai_base_url,
        )

    async def find_blog(self, domain: str) -> Optional[str]:
        """
        Find blog URL for a domain using AI to analyze navigation links.

        Returns:
            Blog URL if found, None otherwise.
        """
        base_url = f"https://{domain}"

        # Fetch homepage
        logger.info(f"  Fetching homepage: {base_url}")
        html, error = await self.fetcher.fetch(base_url)

        if not html or error:
            logger.warning(f"  Failed to fetch homepage: {error}")
            return await self._fallback_blog_search(domain)

        # Extract navigation links
        nav_links = self.parser.extract_navigation_links(html, base_url)

        if not nav_links:
            logger.warning(f"  No navigation links found on homepage")
            return await self._fallback_blog_search(domain)

        logger.info(f"  Found {len(nav_links)} navigation links")

        # Use AI to pick the best blog/news link
        blog_url = await self._ai_pick_blog_link(nav_links, domain)

        if blog_url:
            # Verify it has articles (try flexible matching if strict fails)
            html, error = await self.fetcher.fetch(blog_url)
            if html and not error:
                articles = self.parser.parse_blog_page(html, blog_url, use_flexible_matching=True)
                if len(articles) >= 1:
                    logger.info(f"  AI selected blog URL verified: {blog_url}")
                    return blog_url
                else:
                    logger.warning(f"  AI selected URL has no articles: {blog_url}")

        # Fallback to pattern matching
        logger.info(f"  AI didn't find blog, trying pattern matching...")
        return await self._fallback_blog_search(domain)

    async def _ai_pick_blog_link(self, nav_links: list[dict], domain: str) -> Optional[str]:
        """Use AI to pick the most likely blog/news link from navigation."""
        try:
            # Format links for AI
            links_text = "\n".join([
                f"{i+1}. {link['text']} -> {link['path']}"
                for i, link in enumerate(nav_links)
            ])

            prompt = f"""Analyze these navigation links from {domain} and identify which one is most likely the blog, news, or insights section where they publish articles or company updates.

Navigation links:
{links_text}

Return a JSON object with:
{{
    "blog_link_number": <number 1-{len(nav_links)} or null if none found>,
    "confidence": <"high", "medium", "low">,
    "reason": "<brief explanation>"
}}

Look for links with text like: blog, news, insights, articles, updates, press, resources, thought leadership, perspectives, etc.
If no clear blog/news link exists, return null for blog_link_number."""

            response = self.client.chat.completions.create(
                model=self.settings.ai_model_fast,
                max_tokens=200,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing website navigation to find blog and news sections."
                    },
                    {"role": "user", "content": prompt}
                ],
            )

            result = json.loads(response.choices[0].message.content)
            link_num = result.get("blog_link_number")

            if link_num and 1 <= link_num <= len(nav_links):
                selected_link = nav_links[link_num - 1]
                logger.info(f"  AI picked: '{selected_link['text']}' ({result['confidence']} confidence)")
                logger.info(f"  Reason: {result['reason']}")
                return selected_link["url"]
            else:
                logger.info(f"  AI found no blog link: {result.get('reason', 'No reason given')}")
                return None

        except Exception as e:
            logger.warning(f"  AI blog picker failed: {e}")
            return None

    async def _fallback_blog_search(self, domain: str) -> Optional[str]:
        """Fallback to pattern matching if AI doesn't work."""
        base_url = f"https://{domain}"

        for path in self.BLOG_PATHS:
            url = f"{base_url}{path}"
            html, error = await self.fetcher.fetch(url)

            if html and not error:
                # Verify it looks like a blog page (has multiple links)
                articles = self.parser.parse_blog_page(html, url)
                if len(articles) >= 1:
                    logger.info(f"  Pattern matching found: {url}")
                    return url

        return None

    async def scrape_articles(
        self, blog_url: str, max_articles: int = 3
    ) -> list[Article]:
        """
        Scrape articles from a blog page.

        Returns:
            List of Article objects.
        """
        # Fetch blog listing page
        html, error = await self.fetcher.fetch(blog_url)
        if not html:
            return []

        # Find article links (use flexible matching)
        article_links = self.parser.parse_blog_page(html, blog_url, use_flexible_matching=True)

        # Fetch and parse individual articles
        articles = []
        for title, url in article_links[:max_articles]:
            logger.info(f"    Scraping article: {title[:60]}...")
            article_html, article_error = await self.fetcher.fetch(url)
            if article_html:
                article = self.parser.parse_article(article_html, url)
                if article and article.word_count > 0:
                    logger.info(f"      ✓ Extracted {article.word_count} words")
                    articles.append(article)
                else:
                    logger.warning(f"      ✗ No content extracted")

        return articles
