"""Data models for the outreach bot."""

from outreach_bot.models.contact import Contact
from outreach_bot.models.context import ScrapedContext, ContextQuality
from outreach_bot.models.email import GeneratedEmail

__all__ = ["Contact", "ScrapedContext", "ContextQuality", "GeneratedEmail"]
