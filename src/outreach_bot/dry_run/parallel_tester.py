"""Parallel prompt testing for dry run mode."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from outreach_bot.config import get_settings
from outreach_bot.models.contact import Contact
from outreach_bot.models.context import ScrapedContext
from outreach_bot.models.email import GeneratedEmail
from outreach_bot.generator.ai_opener import AIOpener
from outreach_bot.generator.templates import TemplateManager
from outreach_bot.generator.prompts.variations import (
    PROMPT_VARIATIONS,
    get_all_variation_keys,
)


class ParallelTester:
    """Test all prompt variations in parallel."""

    def __init__(self):
        self.settings = get_settings()
        self.console = Console()
        # Use cheap model for dry run
        self.ai_opener = AIOpener(use_cheap_model=True)
        self.templates = TemplateManager()

    async def test_all_variations(
        self,
        contact: Contact,
        context: ScrapedContext,
    ) -> list[dict]:
        """
        Test all prompt variations in parallel.

        Returns:
            List of result dictionaries.
        """
        if not context.has_usable_content:
            self.console.print(
                "[yellow]Warning: Context quality is low. "
                "AI generation may not produce good results.[/yellow]"
            )

        variation_keys = get_all_variation_keys()

        # Run all variations in parallel using thread pool
        # (anthropic SDK is sync but thread-safe)
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=10) as executor:
            tasks = [
                loop.run_in_executor(
                    executor,
                    self._generate_single,
                    key,
                    contact,
                    context,
                )
                for key in variation_keys
            ]
            results = await asyncio.gather(*tasks)

        return results

    def _generate_single(
        self,
        variation_key: str,
        contact: Contact,
        context: ScrapedContext,
    ) -> dict:
        """Generate a single variation."""
        variation_info = PROMPT_VARIATIONS[variation_key]

        opener, error = self.ai_opener.generate_opener(
            contact, context, variation_key
        )

        return {
            "variation_key": variation_key,
            "variation_name": variation_info["name"],
            "variation_description": variation_info["description"],
            "opener": opener,
            "error": error,
            "success": bool(opener and not error),
        }

    def display_results(
        self,
        results: list[dict],
        contact: Contact,
        context: ScrapedContext,
    ):
        """Display results in a formatted table."""
        # Header panel
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Dry Run Results[/bold]\n"
                f"Contact: {contact.full_name} ({contact.email})\n"
                f"Company: {contact.company}\n"
                f"Domain: {contact.domain}\n"
                f"Context Quality: {context.quality.value}",
                title="Test Summary",
            )
        )

        # Results table
        table = Table(title="Prompt Variations", show_lines=True)
        table.add_column("Variation", style="cyan", width=20)
        table.add_column("Generated Opener", width=60)
        table.add_column("Status", width=10)

        for result in results:
            status = "[green]OK[/green]" if result["success"] else "[red]FAIL[/red]"
            opener = result["opener"] if result["success"] else f"[red]{result['error']}[/red]"

            table.add_row(
                f"{result['variation_name']}\n[dim]{result['variation_description']}[/dim]",
                opener,
                status,
            )

        self.console.print(table)

        # Summary
        success_count = sum(1 for r in results if r["success"])
        self.console.print(
            f"\n[bold]Summary:[/bold] {success_count}/{len(results)} variations successful"
        )

    def save_results(
        self,
        results: list[dict],
        contact: Contact,
        context: ScrapedContext,
        output_dir: Optional[Path] = None,
    ) -> Path:
        """Save results to JSON file."""
        if output_dir is None:
            output_dir = self.settings.dry_run_output_dir

        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"dry_run_{contact.domain}_{timestamp}.json"
        output_path = output_dir / filename

        output_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "contact": {
                "email": contact.email,
                "name": contact.full_name,
                "company": contact.company,
                "domain": contact.domain,
            },
            "context": {
                "quality": context.quality.value,
                "blog_url": context.blog_url,
                "summary_preview": context.summary[:500] if context.summary else None,
            },
            "results": results,
        }

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        return output_path
