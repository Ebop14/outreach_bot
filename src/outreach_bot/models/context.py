"""Scraped context data model."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ContextQuality(Enum):
    """Quality assessment of scraped context."""

    GOOD = "good"  # At least 1 article with 100+ words
    LOW_QUALITY = "low_quality"  # No blog or empty content
    ERROR = "error"  # Failed to scrape


@dataclass
class Article:
    """Represents a scraped article."""

    title: str
    url: str
    content: str
    word_count: int

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        """Create Article from dictionary."""
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            content=data.get("content", ""),
            word_count=data.get("word_count", 0),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "word_count": self.word_count,
        }


@dataclass
class ScrapedContext:
    """Contains scraped website context for a contact."""

    domain: str
    quality: ContextQuality
    blog_url: Optional[str] = None
    articles: list[Article] = field(default_factory=list)
    summary: str = ""  # Truncated content for AI prompt (max 2000 chars)
    error_message: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def has_usable_content(self) -> bool:
        """Check if context has enough content for AI generation."""
        return self.quality == ContextQuality.GOOD and len(self.summary) > 50

    def to_dict(self) -> dict:
        """Convert to dictionary for caching."""
        return {
            "domain": self.domain,
            "quality": self.quality.value,
            "blog_url": self.blog_url,
            "articles": [a.to_dict() for a in self.articles],
            "summary": self.summary,
            "error_message": self.error_message,
            "scraped_at": self.scraped_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScrapedContext":
        """Create from dictionary (cache retrieval)."""
        return cls(
            domain=data["domain"],
            quality=ContextQuality(data["quality"]),
            blog_url=data.get("blog_url"),
            articles=[Article.from_dict(a) for a in data.get("articles", [])],
            summary=data.get("summary", ""),
            error_message=data.get("error_message"),
            scraped_at=datetime.fromisoformat(data["scraped_at"]),
        )
