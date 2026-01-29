"""HTML parsing and article extraction."""

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from outreach_bot.models.context import Article


class ArticleParser:
    """Parse HTML to extract articles and content."""

    # Common blog article link patterns
    ARTICLE_LINK_PATTERNS = [
        r"/blog/",
        r"/post/",
        r"/article/",
        r"/news/",
        r"/insights/",
        r"/\d{4}/\d{2}/",  # Date-based URLs like /2024/01/
    ]

    # Tags that typically contain main article content
    CONTENT_TAGS = ["article", "main", "div.post", "div.article", "div.content"]

    # Tags to remove from content
    REMOVE_TAGS = [
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "iframe",
        "noscript",
    ]

    def __init__(self):
        self._article_pattern = re.compile(
            "|".join(self.ARTICLE_LINK_PATTERNS), re.IGNORECASE
        )

    def parse_blog_page(
        self, html: str, base_url: str
    ) -> list[tuple[str, str]]:
        """
        Parse a blog listing page to find article links.

        Returns:
            List of (title, url) tuples for found articles.
        """
        soup = BeautifulSoup(html, "lxml")
        articles = []
        seen_urls = set()

        # Find all links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(base_url, href)

            # Skip external links, anchors, and duplicates
            if not self._is_same_domain(full_url, base_url):
                continue
            if full_url in seen_urls:
                continue
            if "#" in href and href.index("#") == 0:
                continue

            # Check if link looks like an article
            if self._article_pattern.search(full_url):
                title = self._extract_link_title(link)
                if title and len(title) > 10:  # Skip very short titles
                    articles.append((title, full_url))
                    seen_urls.add(full_url)

        return articles[:10]  # Limit to first 10 articles

    def parse_article(self, html: str, url: str) -> Optional[Article]:
        """
        Parse an article page to extract content.

        Returns:
            Article object if content found, None otherwise.
        """
        soup = BeautifulSoup(html, "lxml")

        # Remove unwanted elements
        for tag_name in self.REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Try to find title
        title = self._extract_title(soup)

        # Try to find main content
        content = self._extract_content(soup)

        if not content:
            return None

        # Clean and count words
        clean_content = self._clean_text(content)
        word_count = len(clean_content.split())

        return Article(
            title=title or "Untitled",
            url=url,
            content=clean_content,
            word_count=word_count,
        )

    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are on the same domain."""
        try:
            domain1 = urlparse(url1).netloc.lower()
            domain2 = urlparse(url2).netloc.lower()
            # Remove www prefix for comparison
            domain1 = domain1.removeprefix("www.")
            domain2 = domain2.removeprefix("www.")
            return domain1 == domain2
        except Exception:
            return False

    def _extract_link_title(self, link: Tag) -> str:
        """Extract title from a link element."""
        # Try text content
        text = link.get_text(strip=True)
        if text:
            return text

        # Try title attribute
        if link.get("title"):
            return link["title"]

        # Try aria-label
        if link.get("aria-label"):
            return link["aria-label"]

        # Try finding heading inside link
        heading = link.find(["h1", "h2", "h3", "h4"])
        if heading:
            return heading.get_text(strip=True)

        return ""

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract page title."""
        # Try h1 first
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        # Try meta og:title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"]

        # Try title tag
        title = soup.find("title")
        if title:
            return title.get_text(strip=True)

        return None

    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract main content from page."""
        # Try article tag
        article = soup.find("article")
        if article:
            return article.get_text(separator="\n", strip=True)

        # Try main tag
        main = soup.find("main")
        if main:
            return main.get_text(separator="\n", strip=True)

        # Try common content class names
        for class_name in ["post-content", "article-content", "entry-content", "content"]:
            content_div = soup.find(class_=class_name)
            if content_div:
                return content_div.get_text(separator="\n", strip=True)

        # Try role="main"
        main_role = soup.find(attrs={"role": "main"})
        if main_role:
            return main_role.get_text(separator="\n", strip=True)

        # Fallback to body with paragraph extraction
        paragraphs = soup.find_all("p")
        if paragraphs:
            text = "\n".join(p.get_text(strip=True) for p in paragraphs)
            if len(text) > 200:  # Only if substantial content
                return text

        return None

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
