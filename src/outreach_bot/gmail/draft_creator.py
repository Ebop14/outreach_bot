"""Gmail draft creation."""

import base64
from email.mime.text import MIMEText
from typing import Optional

from googleapiclient.discovery import build

from outreach_bot.gmail.auth import GmailAuth
from outreach_bot.models.email import GeneratedEmail


class DraftCreator:
    """Create Gmail drafts."""

    def __init__(self, auth: Optional[GmailAuth] = None):
        self.auth = auth or GmailAuth()
        self._service = None

    def _get_service(self):
        """Get or create Gmail API service."""
        if not self._service:
            credentials = self.auth.get_credentials()
            self._service = build("gmail", "v1", credentials=credentials)
        return self._service

    def create_draft(self, email: GeneratedEmail) -> tuple[Optional[str], Optional[str]]:
        """
        Create a Gmail draft.

        Args:
            email: The generated email to create a draft for.

        Returns:
            Tuple of (draft_id, error_message). One will be None.
        """
        try:
            service = self._get_service()

            # Create MIME message
            message = MIMEText(email.body)
            message["to"] = email.to_email
            message["subject"] = email.subject

            # Encode for Gmail API
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            # Create draft
            draft = (
                service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": raw}})
                .execute()
            )

            draft_id = draft.get("id")
            return draft_id, None

        except Exception as e:
            return None, f"Failed to create draft: {str(e)}"

    def create_drafts_batch(
        self, emails: list[GeneratedEmail]
    ) -> list[tuple[Optional[str], Optional[str]]]:
        """
        Create multiple Gmail drafts.

        Returns:
            List of (draft_id, error_message) tuples.
        """
        results = []
        for email in emails:
            result = self.create_draft(email)
            results.append(result)
        return results
