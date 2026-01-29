"""Contact data model."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Contact:
    """Represents a contact from the CSV input."""

    email: str
    first_name: str
    last_name: str
    company: str
    website: str
    title: Optional[str] = None
    row_index: int = 0

    @property
    def full_name(self) -> str:
        """Get the full name of the contact."""
        return f"{self.first_name} {self.last_name}"

    @property
    def domain(self) -> str:
        """Extract domain from website URL."""
        url = self.website.lower()
        # Remove protocol
        if "://" in url:
            url = url.split("://", 1)[1]
        # Remove path
        url = url.split("/", 1)[0]
        # Remove www prefix
        if url.startswith("www."):
            url = url[4:]
        return url

    @classmethod
    def from_dict(cls, data: dict, row_index: int = 0) -> "Contact":
        """Create Contact from dictionary (CSV row)."""
        # Handle various column name formats
        def get_field(names: list[str], default: str = "") -> str:
            for name in names:
                if name in data and data[name]:
                    return str(data[name]).strip()
                # Try case-insensitive match
                for key in data:
                    if key.lower() == name.lower() and data[key]:
                        return str(data[key]).strip()
            return default

        return cls(
            email=get_field(["email", "Email", "EMAIL", "e-mail"]),
            first_name=get_field(["first_name", "First Name", "FirstName", "first"]),
            last_name=get_field(["last_name", "Last Name", "LastName", "last"]),
            company=get_field(["company", "Company", "COMPANY", "organization"]),
            website=get_field(["website", "Website", "WEBSITE", "url", "URL", "domain"]),
            title=get_field(["title", "Title", "TITLE", "job_title", "position"]) or None,
            row_index=row_index,
        )
