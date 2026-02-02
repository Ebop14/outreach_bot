"""HTML parsing and article extraction."""

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from outreach_bot.models.context import Article

logger = logging.getLogger(__name__)


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

    def extract_navigation_links(self, html: str, base_url: str) -> list[dict]:
        """
        Extract all navigation links from homepage.

        Returns:
            List of dicts with 'text', 'url', and 'path' for each link.
        """
        soup = BeautifulSoup(html, "lxml")
        links = []
        seen_urls = set()

        # Focus on navigation areas first
        nav_areas = soup.find_all(["nav", "header"]) or [soup]

        for nav in nav_areas:
            for link in nav.find_all("a", href=True):
                href = link["href"]
                full_url = urljoin(base_url, href)

                # Skip external links, anchors, and duplicates
                if not self._is_same_domain(full_url, base_url):
                    continue
                if full_url in seen_urls:
                    continue
                if full_url == base_url or full_url == base_url + "/":
                    continue

                text = link.get_text(strip=True)
                if text and len(text) > 1:  # Skip empty or single-char links
                    path = urlparse(full_url).path
                    links.append({
                        "text": text,
                        "url": full_url,
                        "path": path
                    })
                    seen_urls.add(full_url)

        return links[:20]  # Limit to first 20 links

    def parse_blog_page(
        self, html: str, base_url: str, use_flexible_matching: bool = False
    ) -> list[tuple[str, str]]:
        """
        Parse a blog listing page to find article links.

        Args:
            html: HTML content
            base_url: Base URL for resolving relative links
            use_flexible_matching: If True, use more lenient matching for article links

        Returns:
            List of (title, url) tuples for found articles.
        """
        soup = BeautifulSoup(html, "lxml")
        articles = []
        seen_urls = set()
        all_links_count = 0
        same_domain_links = []

        # Find all links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(base_url, href)
            all_links_count += 1

            # Skip external links, anchors, and duplicates
            if not self._is_same_domain(full_url, base_url):
                continue
            if full_url in seen_urls:
                continue
            if "#" in href and href.index("#") == 0:
                continue

            same_domain_links.append((link, full_url))

            # Check if link looks like an article
            if self._article_pattern.search(full_url):
                title = self._extract_link_title(link)
                if title and len(title) > 10:  # Skip very short titles
                    articles.append((title, full_url))
                    seen_urls.add(full_url)

        # If no articles found with strict matching, try flexible approach
        if len(articles) == 0 and use_flexible_matching and len(same_domain_links) > 0:
            logger.info(f"    No articles with strict matching, trying flexible approach...")
            articles = self._flexible_article_detection(same_domain_links, base_url)

        logger.info(f"    Blog page analysis: {all_links_count} total links, {len(same_domain_links)} same-domain, {len(articles)} matched article patterns")

        if len(articles) == 0 and len(same_domain_links) > 0:
            logger.info(f"    Sample same-domain links that didn't match:")
            for _, url in same_domain_links[:5]:
                logger.info(f"      {url}")

        return articles[:10]  # Limit to first 10 articles

    def _flexible_article_detection(self, links: list[tuple], base_url: str) -> list[tuple[str, str]]:
        """
        Use more flexible criteria to detect article links.

        Look for links with:
        - Long, descriptive titles (likely articles)
        - Not common navigation paths (about, contact, etc.)
        """
        articles = []
        skip_paths = [
            'about', 'contact', 'team', 'careers', 'privacy', 'terms',
            'services', 'products', 'solutions', 'pricing', 'login', 'signup'
        ]

        for link_elem, url in links:
            # Skip common navigation pages
            url_lower = url.lower()
            if any(skip in url_lower for skip in skip_paths):
                continue

            # Skip if it's just the base URL or homepage
            if url == base_url or url == base_url + '/':
                continue

            # Get link text
            title = self._extract_link_title(link_elem)

            # Look for longer titles (likely articles)
            if title and len(title) > 30 and len(title.split()) >= 4:
                articles.append((title, url))

        return articles[:10]

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
