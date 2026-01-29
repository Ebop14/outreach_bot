"""Static email templates and template management."""

from typing import Optional
from outreach_bot.models.contact import Contact


class TemplateManager:
    """Manage email templates and static content."""

    # Fallback openers when AI generation isn't possible
    FALLBACK_OPENERS = [
        "I came across {company} and was impressed by your work in the industry.",
        "I've been following {company}'s growth and wanted to reach out.",
        "I noticed {company} is doing interesting things in your space.",
    ]

    # Value propositions to include in emails
    VALUE_PROPS = """
I run an AI consultancy that helps companies like yours:
• Build custom AI solutions tailored to your specific workflows
• Reduce operational costs through intelligent automation
• Gain competitive advantage with cutting-edge ML capabilities

We've helped companies achieve 40%+ efficiency gains in their core processes.
""".strip()

    # Email subject templates
    SUBJECT_TEMPLATES = [
        "AI opportunities for {company}",
        "Quick question about {company}'s AI strategy",
        "Helping {company} with AI automation",
    ]

    # Closing template
    CLOSING = """
Would you be open to a 15-minute call to explore if there's a fit?

Best regards,
[Your Name]
[Your Company]
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

    def get_closing(self) -> str:
        """Get the email closing."""
        return self.CLOSING

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
            self.get_closing(),
        ]

        body = "\n".join(body_parts)

        return subject, body
