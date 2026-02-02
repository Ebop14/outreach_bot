"""Static email templates and template management."""

from typing import Optional
from outreach_bot.models.contact import Contact


class TemplateManager:
    """Manage email templates and static content."""

    # Fallback openers when AI generation isn't possible
    FALLBACK_OPENERS = [
        "I came across {company} while researching firms in your space.",
        "Been following {company}'s work and thought I'd reach out.",
        "{company} caught my attention recently.",
    ]

    # Value propositions to include in emails
    VALUE_PROPS = """
I recently left Ramp, where my work saved $3M annually with an internal workflow. My co-founder built an sales tool that turned a 12-month process into a 2 day one. 
""".strip()

    # Email subject templates
    SUBJECT_TEMPLATES = [
        "AI opportunities for {company}",
        "Quick question about {company}'s AI strategy",
        "Helping {company} with AI automation",
    ]

    # Closing template (placeholders will be replaced with CSV values if available)
    CLOSING_TEMPLATE = """
Let me know if you'd like to chat. I think we could save a lot of time and money for your team.

Best,
{sender_name}
{sender_company}
""".strip()

    def get_fallback_opener(self, contact: Contact, variation: int = 0) -> str:
        """Get a fallback opener when AI generation isn't available."""
        template = self.FALLBACK_OPENERS[variation % len(self.FALLBACK_OPENERS)]
        return template.format(
            company=contact.company,
            first_name=contact.first_name,
        )

    def get_subject(self, contact: Contact, variation: int = 0) -> str:
        """Get an email subject line."""
        template = self.SUBJECT_TEMPLATES[variation % len(self.SUBJECT_TEMPLATES)]
        return template.format(company=contact.company)

    def get_value_props(self) -> str:
        """Get the value propositions section."""
        return self.VALUE_PROPS

    def get_closing(self, contact: Contact) -> str:
        """Get the email closing with sender info from contact."""
        sender_name = contact.sender_name or "[Your Name]"
        sender_company = contact.sender_company or "Snaptask"

        return self.CLOSING_TEMPLATE.format(
            sender_name=sender_name,
            sender_company=sender_company
        )

    def assemble_email(
        self,
        contact: Contact,
        opener: str,
        subject: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Assemble a complete email from components.

        Returns:
            Tuple of (subject, body).
        """
        if not subject:
            subject = self.get_subject(contact)

        # Build the email body
        greeting = f"Hi {contact.first_name},"

        body_parts = [
            greeting,
            "",
            opener,
            "",
            self.get_value_props(),
            "",
            self.get_closing(contact),
        ]

        body = "\n".join(body_parts)

        return subject, body
