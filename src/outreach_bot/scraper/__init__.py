"""Web scraping components."""

from outreach_bot.scraper.fetcher import Fetcher
from outreach_bot.scraper.parser import ArticleParser
from outreach_bot.scraper.blog_finder import BlogFinder

__all__ = ["Fetcher", "ArticleParser", "BlogFinder"]
