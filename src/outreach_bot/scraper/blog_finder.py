"""Blog path discovery for company websites."""

from typing import Optional

from outreach_bot.scraper.fetcher import Fetcher
from outreach_bot.scraper.parser import ArticleParser
from outreach_bot.models.context import Article


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

    async def find_blog(self, domain: str) -> Optional[str]:
        """
        Find blog URL for a domain.

        Returns:
            Blog URL if found, None otherwise.
        """
        base_url = f"https://{domain}"

        for path in self.BLOG_PATHS:
            url = f"{base_url}{path}"
            html, error = await self.fetcher.fetch(url)

            if html and not error:
                # Verify it looks like a blog page (has multiple links)
                articles = self.parser.parse_blog_page(html, url)
                if len(articles) >= 1:
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

        # Find article links
        article_links = self.parser.parse_blog_page(html, blog_url)

        # Fetch and parse individual articles
        articles = []
        for title, url in article_links[:max_articles]:
            article_html, article_error = await self.fetcher.fetch(url)
            if article_html:
                article = self.parser.parse_article(article_html, url)
                if article and article.word_count > 0:
                    articles.append(article)

        return articles
