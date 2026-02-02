"""Generated email data model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from outreach_bot.evaluator.email_evaluator import EvaluationResult


@dataclass
class GeneratedEmail:
    """Represents a generated outreach email."""

    to_email: str
    to_name: str
    company: str
    subject: str
    body: str
    opener: str  # The personalized or template opener
    used_ai_opener: bool  # True if AI-generated, False if template fallback
    prompt_variation: Optional[str] = None  # For dry run tracking
    draft_id: Optional[str] = None  # Gmail draft ID once created
    evaluation: Optional["EvaluationResult"] = None  # Quality evaluation results
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_flagged(self) -> bool:
        """Email is flagged if it used template fallback."""
        return not self.used_ai_opener

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "to_email": self.to_email,
            "to_name": self.to_name,
            "company": self.company,
            "subject": self.subject,
            "body": self.body,
            "opener": self.opener,
            "used_ai_opener": self.used_ai_opener,
            "prompt_variation": self.prompt_variation,
            "draft_id": self.draft_id,
            "created_at": self.created_at.isoformat(),
            "is_flagged": self.is_flagged,
        }

        # Add evaluation results if available
        if self.evaluation:
            result["quality_score"] = self.evaluation.quality_score
            result["quality_acceptable"] = self.evaluation.is_acceptable
            result["quality_issues"] = len(self.evaluation.issues)
            result["ai_indicators"] = len(self.evaluation.ai_indicators)

        return result
