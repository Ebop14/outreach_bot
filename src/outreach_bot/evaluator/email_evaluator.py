"""Email quality evaluator to detect AI-generated writing patterns."""

import re
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI
from outreach_bot.config import get_settings


@dataclass
class EvaluationResult:
    """Result of email quality evaluation."""

    is_acceptable: bool
    quality_score: float  # 0-100
    issues: list[str]
    suggestions: list[str]
    ai_indicators: list[str]
    strunk_white_violations: list[str]


class EmailEvaluator:
    """Evaluates email quality and detects AI writing patterns."""

    # Common AI writing indicators
    AI_PHRASES = [
        "I hope this email finds you well",
        "I trust this message finds you",
        "delve into",
        "it is worth noting",
        "it is important to note",
        "in today's fast-paced",
        "in this digital age",
        "in today's world",
        "paradigm shift",
        "game changer",
        "cutting-edge",
        "state-of-the-art",
        "revolutionary",
        "groundbreaking",
        "synergy",
        "leverage",
        "circle back",
        "touch base",
    ]

    # Strunk & White violations - weak qualifiers
    WEAK_QUALIFIERS = [
        "rather",
        "very",
        "little",
        "pretty",
        "quite",
        "somewhat",
        "fairly",
        "really",
        "truly",
        "basically",
        "actually",
        "literally",
    ]

    # Passive voice indicators
    PASSIVE_INDICATORS = [
        r"\bis\s+\w+ed\b",
        r"\bare\s+\w+ed\b",
        r"\bwas\s+\w+ed\b",
        r"\bwere\s+\w+ed\b",
        r"\bbeen\s+\w+ed\b",
        r"\bbe\s+\w+ed\b",
    ]

    # Generic/vague phrases
    VAGUE_PHRASES = [
        "and more",
        "and so on",
        "etc.",
        "various",
        "numerous",
        "several",
        "many",
        "a lot of",
        "a number of",
    ]

    def __init__(self):
        """Initialize the evaluator with AI model."""
        self.settings = get_settings()
        self.client = OpenAI(
            api_key=self.settings.xai_api_key,
            base_url=self.settings.xai_base_url,
        )

    def evaluate(self, email_body: str, email_subject: str) -> EvaluationResult:
        """
        Evaluate email quality using both rule-based and AI checks.

        Args:
            email_body: The email body text
            email_subject: The email subject line

        Returns:
            EvaluationResult with detailed findings
        """
        issues = []
        ai_indicators = []
        strunk_white_violations = []
        suggestions = []

        # Rule-based checks
        ai_indicators.extend(self._check_ai_phrases(email_body))
        strunk_white_violations.extend(self._check_qualifiers(email_body))
        strunk_white_violations.extend(self._check_passive_voice(email_body))
        issues.extend(self._check_vague_language(email_body))
        issues.extend(self._check_length(email_body))
        issues.extend(self._check_repetition(email_body))

        # AI-powered evaluation
        ai_result = self._ai_evaluate(email_body, email_subject)
        if ai_result:
            ai_indicators.extend(ai_result.get("ai_indicators", []))
            strunk_white_violations.extend(ai_result.get("style_issues", []))
            suggestions.extend(ai_result.get("suggestions", []))

        # Calculate quality score
        total_issues = (
            len(ai_indicators) * 3  # AI indicators weighted heavily
            + len(strunk_white_violations) * 2
            + len(issues)
        )
        quality_score = max(0, 100 - (total_issues * 5))

        # Determine if acceptable (score >= 70)
        is_acceptable = quality_score >= 70

        return EvaluationResult(
            is_acceptable=is_acceptable,
            quality_score=quality_score,
            issues=issues,
            suggestions=suggestions,
            ai_indicators=ai_indicators,
            strunk_white_violations=strunk_white_violations,
        )

    def _check_ai_phrases(self, text: str) -> list[str]:
        """Check for common AI-generated phrases."""
        found = []
        text_lower = text.lower()
        for phrase in self.AI_PHRASES:
            if phrase.lower() in text_lower:
                found.append(f"AI phrase detected: '{phrase}'")
        return found

    def _check_qualifiers(self, text: str) -> list[str]:
        """Check for weak qualifiers (Strunk & White rule)."""
        found = []
        words = re.findall(r'\b\w+\b', text.lower())
        for qualifier in self.WEAK_QUALIFIERS:
            count = words.count(qualifier)
            if count > 0:
                found.append(f"Weak qualifier used {count}x: '{qualifier}'")
        return found

    def _check_passive_voice(self, text: str) -> list[str]:
        """Check for passive voice constructions."""
        found = []
        for pattern in self.PASSIVE_INDICATORS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                found.append(f"Passive voice detected: {len(matches)} instance(s)")
                break  # Only report once
        return found

    def _check_vague_language(self, text: str) -> list[str]:
        """Check for vague or non-specific language."""
        found = []
        text_lower = text.lower()
        for phrase in self.VAGUE_PHRASES:
            if phrase in text_lower:
                found.append(f"Vague language: '{phrase}'")
        return found

    def _check_length(self, text: str) -> list[str]:
        """Check for appropriate email length (not too long)."""
        issues = []
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Check for overly long sentences
        long_sentences = [s for s in sentences if len(s.split()) > 25]
        if long_sentences:
            issues.append(
                f"{len(long_sentences)} sentence(s) too long (>25 words)"
            )

        # Check total length
        word_count = len(text.split())
        if word_count > 150:
            issues.append(f"Email too long ({word_count} words, aim for <150)")

        return issues

    def _check_repetition(self, text: str) -> list[str]:
        """Check for repetitive words or phrases."""
        issues = []
        words = re.findall(r'\b\w{4,}\b', text.lower())  # Words 4+ chars
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1

        # Check for words used too frequently
        frequent = [
            (word, count)
            for word, count in word_counts.items()
            if count > 3 and word not in ['that', 'with', 'your', 'have']
        ]
        if frequent:
            for word, count in frequent:
                issues.append(f"Repetitive: '{word}' used {count}x")

        return issues

    def _ai_evaluate(
        self, email_body: str, email_subject: str
    ) -> Optional[dict]:
        """Use AI to evaluate writing quality."""
        try:
            prompt = f"""Evaluate this cold outreach email for quality issues.

Subject: {email_subject}

Body:
{email_body}

Check for:
1. Signs of AI-generated writing (generic phrases, overly formal tone, unnatural phrasing)
2. Strunk & White violations (wordiness, passive voice, weak qualifiers)
3. Lack of specificity or personality
4. Sales-y or inauthentic language

Return a JSON object with:
{{
    "ai_indicators": ["list of AI writing patterns found"],
    "style_issues": ["list of style/grammar issues"],
    "suggestions": ["brief suggestions for improvement"]
}}

Be strict but fair. Only list actual problems found."""

            response = self.client.chat.completions.create(
                model=self.settings.ai_model,
                max_tokens=500,
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert writing evaluator focused on detecting AI-generated text and applying Strunk & White principles.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            import json

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            # If AI evaluation fails, continue with rule-based checks
            return None
