"""xAI Grok API integration for generating personalized openers."""

from typing import Optional

from openai import OpenAI

from outreach_bot.config import get_settings
from outreach_bot.models.contact import Contact
from outreach_bot.models.context import ScrapedContext
from outreach_bot.generator.prompts.variations import (
    get_prompt,
    get_all_variation_keys,
    SYSTEM_PROMPT,
)


class AIOpener:
    """Generate personalized email openers using Grok."""

    def __init__(self, use_cheap_model: bool = False):
        """
        Initialize AI opener.

        Args:
            use_cheap_model: If True, use faster model for cheaper generation (dry run).
        """
        self.settings = get_settings()
        self.client = OpenAI(
            api_key=self.settings.xai_api_key,
            base_url=self.settings.xai_base_url,
        )
        self.model = (
            self.settings.ai_model_dry_run if use_cheap_model else self.settings.ai_model
        )

    def generate_opener(
        self,
        contact: Contact,
        context: ScrapedContext,
        variation_key: str = "direct_reference",
    ) -> tuple[str, Optional[str]]:
        """
        Generate a personalized opener using Grok.

        Args:
            contact: The contact to generate for.
            context: Scraped context about the company.
            variation_key: Which prompt variation to use.

        Returns:
            Tuple of (opener_text, error_message). One will be None.
        """
        if not context.has_usable_content:
            return "", "Context not usable for AI generation"

        try:
            system_prompt, user_prompt = get_prompt(variation_key, contact, context)

            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.settings.ai_max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            opener = response.choices[0].message.content.strip()

            # Clean up the opener
            opener = self._clean_opener(opener)

            return opener, None

        except Exception as e:
            return "", f"Generation error: {str(e)}"

    async def generate_opener_async(
        self,
        contact: Contact,
        context: ScrapedContext,
        variation_key: str = "direct_reference",
    ) -> tuple[str, Optional[str]]:
        """
        Async version of generate_opener for parallel execution.

        Note: Uses sync client internally as openai SDK handles this well.
        """
        return self.generate_opener(contact, context, variation_key)

    def generate_all_variations(
        self,
        contact: Contact,
        context: ScrapedContext,
    ) -> dict[str, tuple[str, Optional[str]]]:
        """
        Generate openers for all prompt variations.

        Returns:
            Dict mapping variation_key to (opener, error) tuple.
        """
        results = {}
        for key in get_all_variation_keys():
            results[key] = self.generate_opener(contact, context, key)
        return results

    def _clean_opener(self, opener: str) -> str:
        """Clean and validate the generated opener."""
        # Remove quotes if the model wrapped the output
        if opener.startswith('"') and opener.endswith('"'):
            opener = opener[1:-1]
        if opener.startswith("'") and opener.endswith("'"):
            opener = opener[1:-1]

        # Remove common prefixes the model might add
        prefixes_to_remove = [
            "Here's an opener:",
            "Opener:",
            "Email opener:",
            "Here is",
        ]
        for prefix in prefixes_to_remove:
            if opener.lower().startswith(prefix.lower()):
                opener = opener[len(prefix) :].strip()

        return opener.strip()
