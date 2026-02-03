"""Static email templates and template management."""

from typing import Optional
from outreach_bot.models.contact import Contact


class TemplateManager:
    """Manage email templates and static content."""

    # Fallback openers when AI generation isn't possible
    FALLBACK_OPENERS = [
        "I came across {company} while researching PE firms focused on operation efficiency, and thought I'd reach out..",
    ]

    # Value propositions to include in emails
    VALUE_PROPS = """
Our co-founder Ethan Child recently left Ramp, where his work saved the sales team 1,250 hours/week and $3M annuallyi by automating manual follow-up emails. 
Brian Ng created a sales tool that transformed a 12-month prospecting process into a 2 day one. 
""".strip()

    # Email subject templates
    SUBJECT_TEMPLATES = [
        "AI opportunities for {company}",
        "Quick question about {company}'s AI strategy",
        "Saving {company} $3M annually",
    ]

    # Closing template (placeholders will be replaced with CSV values if available)
    CLOSING_TEMPLATE = """
Let me know if you'd like to chat with either of our co-founders. I think that a partnership could be mutually beneficial.  

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
