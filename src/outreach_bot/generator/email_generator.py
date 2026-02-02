"""Main email generation orchestrator."""

import logging
from typing import Optional

from outreach_bot.models.contact import Contact
from outreach_bot.models.context import ScrapedContext, ContextQuality
from outreach_bot.models.email import GeneratedEmail
from outreach_bot.generator.ai_opener import AIOpener
from outreach_bot.generator.templates import TemplateManager
from outreach_bot.evaluator.email_evaluator import EmailEvaluator

logger = logging.getLogger(__name__)


class EmailGenerator:
    """Orchestrates email generation from context."""

    def __init__(self, use_cheap_model: bool = False, enable_evaluation: bool = True):
        """
        Initialize email generator.

        Args:
            use_cheap_model: If True, use cheaper model for AI generation.
            enable_evaluation: If True, evaluate emails for quality.
        """
        self.ai_opener = AIOpener(use_cheap_model=use_cheap_model)
        self.templates = TemplateManager()
        self.evaluator = EmailEvaluator() if enable_evaluation else None
        self.enable_evaluation = enable_evaluation

    def generate_email(
        self,
        contact: Contact,
        context: ScrapedContext,
        prompt_variation: str = "direct_reference",
    ) -> GeneratedEmail:
        """
        Generate a complete email for a contact.

        Uses AI opener if context is good, falls back to template otherwise.
        Evaluates quality and retries if needed.
        """
        from outreach_bot.generator.prompts.variations import get_all_variation_keys

        logger.info(f"Generating email for {contact.email}")
        logger.info(f"  Context quality: {context.quality.value}")
        logger.info(f"  Has usable content: {context.has_usable_content}")
        logger.info(f"  Blog URL: {context.blog_url}")
        logger.info(f"  Summary length: {len(context.summary)} chars")
        logger.info(f"  Number of articles: {len(context.articles)}")

        used_ai = False
        opener = ""
        evaluation_result = None
        max_retries = 2
        attempted_variations = [prompt_variation]

        if context.quality == ContextQuality.GOOD and context.has_usable_content:
            logger.info(f"  → Attempting AI generation for {contact.email}")
            # Try AI generation with retries
            for attempt in range(max_retries + 1):
                logger.info(f"    Attempt {attempt + 1}/{max_retries + 1} with variation: {prompt_variation}")
                opener, error = self.ai_opener.generate_opener(
                    contact, context, prompt_variation
                )

                if not opener or error:
                    logger.warning(f"    AI generation failed: opener={bool(opener)}, error={error}")
                    break

                logger.info(f"    AI opener generated successfully (length: {len(opener)})")

                # Assemble email for evaluation
                subject, body = self.templates.assemble_email(contact, opener)

                # Evaluate quality if enabled
                if self.enable_evaluation and self.evaluator:
                    evaluation_result = self.evaluator.evaluate(body, subject)
                    logger.info(f"    Quality evaluation: score={evaluation_result.quality_score}, acceptable={evaluation_result.is_acceptable}")

                    if evaluation_result.is_acceptable:
                        used_ai = True
                        logger.info(f"  ✓ AI opener accepted for {contact.email}")
                        break
                    elif attempt < max_retries:
                        logger.warning(f"    Quality check failed, trying different variation...")
                        # Try a different prompt variation
                        all_variations = get_all_variation_keys()
                        # Find a variation we haven't tried yet
                        for var in all_variations:
                            if var not in attempted_variations:
                                prompt_variation = var
                                attempted_variations.append(var)
                                break
                        continue
                else:
                    # No evaluation, accept the opener
                    used_ai = True
                    logger.info(f"  ✓ AI opener accepted (evaluation disabled) for {contact.email}")
                    break
        else:
            logger.warning(f"  → Skipping AI generation for {contact.email}: quality={context.quality.value}, has_content={context.has_usable_content}")

        if not opener or (evaluation_result and not evaluation_result.is_acceptable):
            # Use template fallback
            logger.info(f"  → Using template fallback for {contact.email}")
            opener = self.templates.get_fallback_opener(contact)
            subject, body = self.templates.assemble_email(contact, opener)

        email = GeneratedEmail(
            to_email=contact.email,
            to_name=contact.full_name,
            company=contact.company,
            subject=subject,
            body=body,
            opener=opener,
            used_ai_opener=used_ai,
            prompt_variation=prompt_variation if used_ai else None,
        )

        # Attach evaluation result if available
        if evaluation_result:
            email.evaluation = evaluation_result

        return email

    def generate_with_all_variations(
        self,
        contact: Contact,
        context: ScrapedContext,
    ) -> list[GeneratedEmail]:
        """
        Generate emails with all prompt variations.

        Used for dry run testing.
        """
        from outreach_bot.generator.prompts.variations import get_all_variation_keys

        emails = []

        if context.quality != ContextQuality.GOOD or not context.has_usable_content:
            # Only generate one email with template fallback
            email = self.generate_email(contact, context)
            emails.append(email)
            return emails

        # Generate with each variation
        for variation_key in get_all_variation_keys():
            opener, error = self.ai_opener.generate_opener(
                contact, context, variation_key
            )

            if opener and not error:
                subject, body = self.templates.assemble_email(contact, opener)
                email = GeneratedEmail(
                    to_email=contact.email,
                    to_name=contact.full_name,
                    company=contact.company,
                    subject=subject,
                    body=body,
                    opener=opener,
                    used_ai_opener=True,
                    prompt_variation=variation_key,
                )
            else:
                # Fallback for this variation
                fallback_opener = self.templates.get_fallback_opener(contact)
                subject, body = self.templates.assemble_email(contact, fallback_opener)
                email = GeneratedEmail(
                    to_email=contact.email,
                    to_name=contact.full_name,
                    company=contact.company,
                    subject=subject,
                    body=body,
                    opener=fallback_opener,
                    used_ai_opener=False,
                    prompt_variation=variation_key,
                )

            emails.append(email)

        return emails
