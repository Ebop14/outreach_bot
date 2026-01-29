"""Main email generation orchestrator."""

from typing import Optional

from outreach_bot.models.contact import Contact
from outreach_bot.models.context import ScrapedContext, ContextQuality
from outreach_bot.models.email import GeneratedEmail
from outreach_bot.generator.ai_opener import AIOpener
from outreach_bot.generator.templates import TemplateManager


class EmailGenerator:
    """Orchestrates email generation from context."""

    def __init__(self, use_cheap_model: bool = False):
        """
        Initialize email generator.

        Args:
            use_cheap_model: If True, use cheaper model for AI generation.
        """
        self.ai_opener = AIOpener(use_cheap_model=use_cheap_model)
        self.templates = TemplateManager()

    def generate_email(
        self,
        contact: Contact,
        context: ScrapedContext,
        prompt_variation: str = "direct_reference",
    ) -> GeneratedEmail:
        """
        Generate a complete email for a contact.

        Uses AI opener if context is good, falls back to template otherwise.
        """
        used_ai = False
        opener = ""

        if context.quality == ContextQuality.GOOD and context.has_usable_content:
            # Try AI generation
            opener, error = self.ai_opener.generate_opener(
                contact, context, prompt_variation
            )
            if opener and not error:
                used_ai = True

        if not opener:
            # Use template fallback
            opener = self.templates.get_fallback_opener(contact)

        # Assemble the full email
        subject, body = self.templates.assemble_email(contact, opener)

        return GeneratedEmail(
            to_email=contact.email,
            to_name=contact.full_name,
            company=contact.company,
            subject=subject,
            body=body,
            opener=opener,
            used_ai_opener=used_ai,
            prompt_variation=prompt_variation if used_ai else None,
        )

    def generate_with_all_variations(
        self,
        contact: Contact,
        context: ScrapedContext,
    ) -> list[GeneratedEmail]:
        """
        Generate emails with all prompt variations.

        Used for dry run testing.
        """
        from outreach_bot.generator.prompts.variations import get_all_variation_keys

        emails = []

        if context.quality != ContextQuality.GOOD or not context.has_usable_content:
            # Only generate one email with template fallback
            email = self.generate_email(contact, context)
            emails.append(email)
            return emails

        # Generate with each variation
        for variation_key in get_all_variation_keys():
            opener, error = self.ai_opener.generate_opener(
                contact, context, variation_key
            )

            if opener and not error:
                subject, body = self.templates.assemble_email(contact, opener)
                email = GeneratedEmail(
                    to_email=contact.email,
                    to_name=contact.full_name,
                    company=contact.company,
                    subject=subject,
                    body=body,
                    opener=opener,
                    used_ai_opener=True,
                    prompt_variation=variation_key,
                )
            else:
                # Fallback for this variation
                fallback_opener = self.templates.get_fallback_opener(contact)
                subject, body = self.templates.assemble_email(contact, fallback_opener)
                email = GeneratedEmail(
                    to_email=contact.email,
                    to_name=contact.full_name,
                    company=contact.company,
                    subject=subject,
                    body=body,
                    opener=fallback_opener,
                    used_ai_opener=False,
                    prompt_variation=variation_key,
                )

            emails.append(email)

        return emails
