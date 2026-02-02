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

    def __init__(self, use_cheap_model: bool = False, enable_evaluation: bool = True, max_retries: int = 3, quality_threshold: int = 70):
        """
        Initialize email generator.

        Args:
            use_cheap_model: If True, use cheaper model for AI generation.
            enable_evaluation: If True, evaluate emails for quality.
            max_retries: Maximum number of retry attempts with feedback (default: 3).
            quality_threshold: Minimum quality score to accept (default: 70).
        """
        self.ai_opener = AIOpener(use_cheap_model=use_cheap_model)
        self.templates = TemplateManager()
        self.evaluator = EmailEvaluator(quality_threshold=quality_threshold) if enable_evaluation else None
        self.enable_evaluation = enable_evaluation
        self.max_retries = max_retries
        self.quality_threshold = quality_threshold

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
        subject = ""
        body = ""
        evaluation_result = None
        previous_opener = None
        feedback = None

        # Cache all attempts with their scores
        cached_attempts = []

        if context.quality == ContextQuality.GOOD and context.has_usable_content:
            logger.info(f"  → Attempting AI generation for {contact.email}")
            # Try AI generation with feedback-based retries
            for attempt in range(self.max_retries + 1):
                is_retry = attempt > 0
                retry_info = f" (retry {attempt}/{self.max_retries})" if is_retry else ""
                logger.info(f"    Attempt {attempt + 1}/{self.max_retries + 1}{retry_info}")

                # Generate opener (with feedback if this is a retry)
                attempt_opener, error = self.ai_opener.generate_opener(
                    contact,
                    context,
                    prompt_variation,
                    feedback=feedback,
                    previous_opener=previous_opener
                )

                if not attempt_opener or error:
                    logger.warning(f"    AI generation failed: opener={bool(attempt_opener)}, error={error}")
                    break

                logger.info(f"    AI opener generated successfully (length: {len(attempt_opener)})")

                # Assemble email for evaluation
                attempt_subject, attempt_body = self.templates.assemble_email(contact, attempt_opener)

                # Evaluate quality if enabled
                if self.enable_evaluation and self.evaluator:
                    attempt_evaluation = self.evaluator.evaluate(attempt_body, attempt_subject)
                    logger.info(f"    Quality evaluation: score={attempt_evaluation.quality_score}, acceptable={attempt_evaluation.is_acceptable}")

                    # Cache this attempt
                    cached_attempts.append({
                        'opener': attempt_opener,
                        'subject': attempt_subject,
                        'body': attempt_body,
                        'evaluation': attempt_evaluation,
                        'score': attempt_evaluation.quality_score,
                        'attempt_number': attempt + 1
                    })

                    if attempt_evaluation.is_acceptable:
                        # Success! Use this attempt
                        opener = attempt_opener
                        subject = attempt_subject
                        body = attempt_body
                        evaluation_result = attempt_evaluation
                        used_ai = True
                        logger.info(f"  ✓ AI opener accepted for {contact.email}")
                        break
                    elif attempt < self.max_retries:
                        logger.warning(f"    Quality check failed (score: {attempt_evaluation.quality_score}/{self.quality_threshold})")
                        logger.info(f"    Preparing feedback for retry...")
                        # Save current opener and prepare feedback for next attempt
                        previous_opener = attempt_opener
                        feedback = attempt_evaluation.get_feedback_text(threshold=self.quality_threshold)
                        logger.info(f"    Feedback:\n{feedback}")
                        continue
                    else:
                        logger.warning(f"    Max retries ({self.max_retries}) reached")
                        # Use best cached attempt instead of template fallback
                        if cached_attempts:
                            best_attempt = max(cached_attempts, key=lambda x: x['score'])
                            logger.info(f"  → Using best attempt (#{best_attempt['attempt_number']}, score: {best_attempt['score']}/{self.quality_threshold})")
                            opener = best_attempt['opener']
                            subject = best_attempt['subject']
                            body = best_attempt['body']
                            evaluation_result = best_attempt['evaluation']
                            used_ai = True
                        break
                else:
                    # No evaluation, accept the opener
                    opener = attempt_opener
                    subject = attempt_subject
                    body = attempt_body
                    used_ai = True
                    logger.info(f"  ✓ AI opener accepted (evaluation disabled) for {contact.email}")
                    break
        else:
            logger.warning(f"  → Skipping AI generation for {contact.email}: quality={context.quality.value}, has_content={context.has_usable_content}")

        # Only use template fallback if AI generation completely failed or was skipped
        if not opener:
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
