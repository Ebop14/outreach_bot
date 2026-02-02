"""Gmail OAuth authentication."""

import json
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from outreach_bot.config import get_settings


# Only need compose scope for creating drafts
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


class GmailAuth:
    """Handle Gmail OAuth authentication."""

    def __init__(self):
        self.settings = get_settings()
        self._credentials: Optional[Credentials] = None

    def get_credentials(self) -> Credentials:
        """
        Get valid OAuth credentials.

        Loads from cache or initiates OAuth flow.
        """
        if self._credentials and self._credentials.valid:
            return self._credentials

        # Try to load from token file
        token_path = self.settings.gmail_token_path
        if token_path.exists():
            self._credentials = Credentials.from_authorized_user_file(
                str(token_path), SCOPES
            )

        # Refresh if expired
        if self._credentials and self._credentials.expired and self._credentials.refresh_token:
            try:
                self._credentials.refresh(Request())
                self._save_credentials()
                return self._credentials
            except Exception:
                # Token refresh failed, need new auth
                self._credentials = None

        if not self._credentials or not self._credentials.valid:
            raise RuntimeError(
                "Gmail not authenticated. Run 'outreach setup-gmail' first."
            )

        return self._credentials

    def setup_oauth(self) -> bool:
        """
        Run the OAuth flow to get credentials.

        Returns:
            True if successful.
        """
        credentials_path = self.settings.gmail_credentials_path

        if not credentials_path.exists():
            raise FileNotFoundError(
                f"Gmail credentials file not found at {credentials_path}. "
                "Download it from Google Cloud Console."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path), SCOPES
        )

        self._credentials = flow.run_local_server(port=0)
        self._save_credentials()

        return True

    def _save_credentials(self):
        """Save credentials to token file."""
        token_path = self.settings.gmail_token_path
        token_path.parent.mkdir(parents=True, exist_ok=True)

        with open(token_path, "w", encoding="utf-8") as f:
            f.write(self._credentials.to_json())

    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        try:
            self.get_credentials()
            return True
        except Exception:
            return False

    def clear_credentials(self):
        """Remove stored credentials."""
        token_path = self.settings.gmail_token_path
        if token_path.exists():
            token_path.unlink()
        self._credentials = None
