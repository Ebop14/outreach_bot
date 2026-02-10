"""Static email templates and template management."""

from typing import Optional
from outreach_bot.models.contact import Contact


class TemplateManager:
    """Manage email templates and static content."""

    # Fallback openers when AI generation isn't possible (T1)
    FALLBACK_OPENERS = [
        "I came across {company} while researching PE firms focused on operation efficiency, and thought I'd reach out..",
    ]

    # Follow-up fallback openers for T2+
    FOLLOWUP_OPENERS = {
        2: [
            "I wanted to follow up on my previous email. I think there's a real opportunity for {company} to leverage AI to drive efficiency across your portfolio.",
            "Bumping this to the top of your inbox. I'd love to explore how AI automation could benefit {company}'s operations.",
        ],
        3: [
            "I know you're busy, so I'll keep this short. I still think AI automation could be a game-changer for {company}'s portfolio companies.",
            "Following up one last time. If the timing isn't right, no worries at all -- but I'd hate for {company} to miss out on what we're building.",
        ],
    }

    # Value propositions to include in emails
    VALUE_PROPS = """

I recently left Ramp, where my work saved the sales team 1,250 hours/week and $3M annually by automating manual follow-up emails.
My co-founder, Brian Ng created a sales tool that transformed a 12-month prospecting process into a 2 day one.

""".strip()

    # Email subject templates (T1)
    SUBJECT_TEMPLATES = [
        "AI opportunities for {company}",
        "Quick question about {company}'s AI strategy",
        "Saving {company} $3M annually",
    ]

    # Follow-up subject templates for T2+
    FOLLOWUP_SUBJECT_TEMPLATES = {
        2: [
            "Re: AI opportunities for {company}",
            "Following up -- {company} + AI",
        ],
        3: [
            "Re: AI opportunities for {company}",
            "One more thought for {company}",
        ],
    }

    # Closing template (placeholders will be replaced with CSV values if available)
    CLOSING_TEMPLATE = """
Let me know if you'd like to chat. I'd love to see if I can bring the same efficiency gains to your portfolio companies.

Best,
{sender_name}
{sender_company}
""".strip()

    def get_fallback_opener(self, contact: Contact, variation: int = 0) -> str:
        """Get a fallback opener when AI generation isn't available."""
        if contact.touch_number > 1:
            return self.get_followup_fallback_opener(contact, variation)
        template = self.FALLBACK_OPENERS[variation % len(self.FALLBACK_OPENERS)]
        return template.format(
            company=contact.company,
            first_name=contact.first_name,
        )

    def get_followup_fallback_opener(self, contact: Contact, variation: int = 0) -> str:
        """Get a follow-up fallback opener for T2+ touches."""
        # Use the highest available touch template, capped at what we have
        touch = min(contact.touch_number, max(self.FOLLOWUP_OPENERS.keys()))
        templates = self.FOLLOWUP_OPENERS[touch]
        template = templates[variation % len(templates)]
        return template.format(
            company=contact.company,
            first_name=contact.first_name,
        )

    def get_subject(self, contact: Contact, variation: int = 0) -> str:
        """Get an email subject line."""
        if contact.touch_number > 1:
            return self.get_followup_subject(contact, variation)
        template = self.SUBJECT_TEMPLATES[variation % len(self.SUBJECT_TEMPLATES)]
        return template.format(company=contact.company)

    def get_followup_subject(self, contact: Contact, variation: int = 0) -> str:
        """Get a follow-up subject line for T2+ touches."""
        touch = min(contact.touch_number, max(self.FOLLOWUP_SUBJECT_TEMPLATES.keys()))
        templates = self.FOLLOWUP_SUBJECT_TEMPLATES[touch]
        template = templates[variation % len(templates)]
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

        For T1 (first touch): full email with value props.
        For T2+ (follow-ups): shorter bump email without repeating value props.

        Returns:
            Tuple of (subject, body).
        """
        if not subject:
            subject = self.get_subject(contact)

        greeting = f"Hey {contact.first_name},"

        if contact.touch_number > 1:
            # Follow-up emails are shorter -- no value props repeat
            body_parts = [
                greeting,
                "",
                opener,
                "",
                self.get_closing(contact),
            ]
        else:
            # First touch: full email with value props
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
