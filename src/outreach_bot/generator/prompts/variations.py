"""Prompt variations for AI opener generation."""

from outreach_bot.models.contact import Contact
from outreach_bot.models.context import ScrapedContext


# Base system prompt
SYSTEM_PROMPT = """You are an expert at writing personalized cold email openers for an AI consultancy. Your openers should:
- Be 1-2 sentences maximum
- Reference something specific from the company's content
- Feel genuine and not salesy
- Create a natural bridge to discussing AI solutions
- Never use generic phrases like "I was impressed by" or "I noticed that"

Output ONLY the opener text, nothing else."""


# 10 prompt variations for dry run testing
PROMPT_VARIATIONS = {
    "direct_reference": {
        "name": "Direct Reference",
        "description": "Directly reference a specific article or topic",
        "template": """Write a cold email opener for {first_name} at {company}.

Their recent content discusses:
{summary}

Reference something specific from their content that relates to AI/automation opportunities.""",
    },
    "problem_focused": {
        "name": "Problem Focused",
        "description": "Focus on a problem or challenge they might face",
        "template": """Write a cold email opener for {first_name} at {company}.

Based on their content:
{summary}

Identify a challenge they might face that AI could solve, and reference it naturally.""",
    },
    "compliment_insight": {
        "name": "Compliment + Insight",
        "description": "Compliment their work then add an insight",
        "template": """Write a cold email opener for {first_name} at {company}.

Their recent content:
{summary}

Start with a specific compliment about their content, then add a brief insight about AI potential.""",
    },
    "question_based": {
        "name": "Question Based",
        "description": "Open with a thoughtful question",
        "template": """Write a cold email opener for {first_name} at {company}.

Context from their blog:
{summary}

Ask a thoughtful question based on their content that leads to AI/automation discussion.""",
    },
    "shared_interest": {
        "name": "Shared Interest",
        "description": "Establish common ground",
        "template": """Write a cold email opener for {first_name} at {company}.

Their content covers:
{summary}

Find common ground between their focus areas and AI solutions. Make it feel like a peer reaching out.""",
    },
    "trend_connection": {
        "name": "Trend Connection",
        "description": "Connect their work to broader trends",
        "template": """Write a cold email opener for {first_name} at {company}.

Recent content:
{summary}

Connect something from their content to a broader industry trend involving AI/automation.""",
    },
    "specific_quote": {
        "name": "Specific Quote",
        "description": "Reference or paraphrase something specific",
        "template": """Write a cold email opener for {first_name} at {company}.

From their blog:
{summary}

Reference or paraphrase a specific point from their content and connect it to AI opportunities.""",
    },
    "future_focused": {
        "name": "Future Focused",
        "description": "Focus on future possibilities",
        "template": """Write a cold email opener for {first_name} at {company}.

Their content:
{summary}

Based on where they seem to be heading, mention an AI-related opportunity for their future.""",
    },
    "contrarian": {
        "name": "Contrarian Angle",
        "description": "Offer a slightly different perspective",
        "template": """Write a cold email opener for {first_name} at {company}.

Their recent writing:
{summary}

Offer a thoughtful, slightly different perspective on something they wrote about, related to AI.""",
    },
    "minimalist": {
        "name": "Minimalist",
        "description": "Ultra-concise, one sentence only",
        "template": """Write a ONE SENTENCE cold email opener for {first_name} at {company}.

Context:
{summary}

Be extremely concise - just one punchy sentence that references their content and hints at AI value.""",
    },
}


def get_prompt(
    variation_key: str,
    contact: Contact,
    context: ScrapedContext,
) -> tuple[str, str]:
    """
    Get a formatted prompt for a specific variation.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    if variation_key not in PROMPT_VARIATIONS:
        raise ValueError(f"Unknown prompt variation: {variation_key}")

    variation = PROMPT_VARIATIONS[variation_key]

    user_prompt = variation["template"].format(
        first_name=contact.first_name,
        company=contact.company,
        summary=context.summary,
    )

    return SYSTEM_PROMPT, user_prompt


def get_all_variation_keys() -> list[str]:
    """Get all prompt variation keys."""
    return list(PROMPT_VARIATIONS.keys())
