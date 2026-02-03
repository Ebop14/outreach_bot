"""Typer CLI entry point."""

import asyncio
import hashlib
import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.logging import RichHandler

from outreach_bot.models.contact import Contact
from outreach_bot.scraper.fetcher import Fetcher
from outreach_bot.cache.sqlite_cache import SQLiteCache
from outreach_bot.analyzer.context_analyzer import ContextAnalyzer
from outreach_bot.generator.email_generator import EmailGenerator
from outreach_bot.gmail.auth import GmailAuth
from outreach_bot.dry_run.parallel_tester import ParallelTester

app = typer.Typer(
    name="outreach",
    help="AI-powered outreach email automation system",
    no_args_is_help=True,
)
console = Console()


def load_contacts(csv_path: Path) -> list[Contact]:
    """Load contacts from CSV file."""
    df = pd.read_csv(csv_path, encoding='utf-8')
    contacts = []
    for idx, row in df.iterrows():
        contact = Contact.from_dict(row.to_dict(), row_index=idx)
        if contact.email and contact.website:
            contacts.append(contact)
    return contacts


def get_csv_hash(csv_path: Path) -> str:
    """Get hash of CSV file for progress tracking."""
    content = csv_path.read_bytes()
    return hashlib.md5(content).hexdigest()


@app.command()
def run(
    csv_path: Path = typer.Argument(..., help="Path to contacts CSV file"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Process only first N contacts"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output CSV path (default: input_with_emails.csv)"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume from last progress"),
    skip_evaluation: bool = typer.Option(False, "--skip-evaluation", help="Skip quality evaluation"),
    max_retries: int = typer.Option(3, "--max-retries", "-r", help="Max retries with feedback for quality improvement (default: 3)"),
    quality_threshold: int = typer.Option(70, "--quality-threshold", "-q", help="Minimum quality score 0-100 to accept (default: 70)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """Process contacts and generate emails, writing results to CSV."""
    if not csv_path.exists():
        console.print(f"[red]Error: CSV file not found: {csv_path}[/red]")
        raise typer.Exit(1)

    # Configure logging - always enabled, verbose adds more detail
    log_level = logging.DEBUG if verbose else logging.WARNING

    # Clear any existing handlers and configure fresh
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)

    # Create RichHandler that works with Progress context
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=True if verbose else False,
        show_path=verbose,
        markup=True,
    )
    rich_handler.setLevel(log_level)
    root_logger.addHandler(rich_handler)

    # Ensure logs are flushed immediately
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(line_buffering=True)

    # Default output path
    if output is None:
        output = csv_path.parent / f"{csv_path.stem}_with_emails.csv"

    console.print("\n[bold cyan]🤖 Outreach Bot Starting...[/bold cyan]\n")
    console.print(f"[dim]Input:[/dim]  {csv_path}")
    console.print(f"[dim]Output:[/dim] {output}")
    console.print(f"[dim]Quality threshold:[/dim] {quality_threshold}/100")
    console.print(f"[dim]Max retries:[/dim] {max_retries}")
    if skip_evaluation:
        console.print(f"[yellow]⚠ Quality evaluation disabled[/yellow]")
    console.print()

    asyncio.run(_run_async(csv_path, limit, output, resume, skip_evaluation, max_retries, quality_threshold, verbose))


async def _run_async(csv_path: Path, limit: Optional[int], output_path: Path, resume: bool, skip_evaluation: bool, max_retries: int, quality_threshold: int, verbose: bool):
    """Async implementation of run command."""
    logger = logging.getLogger(__name__)
    # Load original CSV as DataFrame to preserve all columns
    console.print("[cyan]📂 Loading contacts...[/cyan]")
    df = pd.read_csv(csv_path, encoding='utf-8')

    # Load contacts
    contacts = load_contacts(csv_path)
    if not contacts:
        console.print("[red]Error: No valid contacts found in CSV[/red]")
        return

    if limit:
        contacts = contacts[:limit]
        df = df.iloc[:limit].copy()
        console.print(f"[dim]Limiting to first {limit} contacts[/dim]")

    console.print(f"[green]✓ Loaded {len(contacts)} contacts[/green]\n")

    csv_hash = get_csv_hash(csv_path)

    # Initialize new columns if they don't exist
    if "generated_subject" not in df.columns:
        df["generated_subject"] = ""
    if "generated_body" not in df.columns:
        df["generated_body"] = ""
    if "ai_generated" not in df.columns:
        df["ai_generated"] = ""
    if "quality_score" not in df.columns:
        df["quality_score"] = ""
    if "quality_acceptable" not in df.columns:
        df["quality_acceptable"] = ""
    if "quality_issues" not in df.columns:
        df["quality_issues"] = ""

    # Initialize components
    async with SQLiteCache() as cache:
        # Check for resume point
        start_index = 0
        if resume:
            progress = await cache.get_progress(csv_hash)
            if progress:
                start_index = progress[0] + 1
                if start_index >= len(contacts):
                    console.print("[green]All contacts already processed![/green]")
                    return
                console.print(f"[yellow]Resuming from contact {start_index + 1}/{len(contacts)}[/yellow]")

        async with Fetcher() as fetcher:
            analyzer = ContextAnalyzer(fetcher, cache)
            generator = EmailGenerator(
                enable_evaluation=not skip_evaluation,
                max_retries=max_retries,
                quality_threshold=quality_threshold
            )

            # Process contacts
            results_summary = {
                "success": 0,
                "flagged": 0,
                "errors": 0,
                "quality_passed": 0,
                "quality_failed": 0,
            }

            # Use Progress bar only when not verbose (verbose mode shows detailed logs instead)
            progress_ctx = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) if not verbose else None

            if progress_ctx:
                progress_ctx.start()
                task = progress_ctx.add_task(
                    "Processing contacts...",
                    total=len(contacts) - start_index,
                )

            try:
                for i, contact in enumerate(contacts[start_index:], start=start_index):
                    if progress_ctx:
                        progress_ctx.update(
                            task,
                            description=f"Processing {contact.company}...",
                        )

                    try:
                        console.print(f"\n[bold]━━━ Contact {i+1}/{len(contacts)}: {contact.company} ({contact.email}) ━━━[/bold]")

                        # Get context
                        console.print(f"[cyan]🌐 Fetching website content from {contact.website}...[/cyan]")
                        context = await analyzer.get_context(contact)
                        console.print(f"[dim]   Context quality: {context.quality.value}[/dim]")
                        if context.blog_url:
                            console.print(f"[dim]   Blog found: {context.blog_url}[/dim]")
                            console.print(f"[dim]   Articles found: {len(context.articles)}[/dim]")

                        # Generate email
                        console.print(f"[cyan]✍️  Generating personalized email...[/cyan]")
                        email = generator.generate_email(contact, context)

                        # Show generation result
                        if email.used_ai_opener:
                            console.print(f"[green]   ✓ AI-generated email[/green]")
                        else:
                            console.print(f"[yellow]   ⚠ Template fallback used[/yellow]")

                        # Show quality if evaluated
                        if email.evaluation:
                            score = email.evaluation.quality_score
                            acceptable = email.evaluation.is_acceptable
                            status_icon = "✓" if acceptable else "✗"
                            status_color = "green" if acceptable else "yellow"
                            console.print(f"[{status_color}]   {status_icon} Quality score: {score}/{quality_threshold}[/{status_color}]")

                        # Write to DataFrame
                        df.at[contact.row_index, "generated_subject"] = email.subject
                        df.at[contact.row_index, "generated_body"] = email.body
                        df.at[contact.row_index, "ai_generated"] = str(email.used_ai_opener)

                        # Add evaluation results if available
                        if email.evaluation:
                            df.at[contact.row_index, "quality_score"] = str(email.evaluation.quality_score)
                            df.at[contact.row_index, "quality_acceptable"] = str(email.evaluation.is_acceptable)
                            df.at[contact.row_index, "quality_issues"] = str(len(email.evaluation.issues))

                            # Track quality stats
                            if email.evaluation.is_acceptable:
                                results_summary["quality_passed"] += 1
                            else:
                                results_summary["quality_failed"] += 1

                        if email.is_flagged:
                            results_summary["flagged"] += 1
                        else:
                            results_summary["success"] += 1

                        # Save email record to cache
                        await cache.save_email(contact.email, email.to_dict())

                        # Update progress
                        await cache.set_progress(csv_hash, i, len(contacts))

                        # Save CSV after each contact for safety
                        console.print(f"[dim]💾 Saved to {output_path}[/dim]")
                        df.to_csv(output_path, index=False, encoding='utf-8-sig')

                    except Exception as e:
                        console.print(f"[red]✗ Error processing {contact.email}: {e}[/red]")
                        if verbose:
                            import traceback
                            console.print(f"[red]{traceback.format_exc()}[/red]")
                        results_summary["errors"] += 1

                    if progress_ctx:
                        progress_ctx.advance(task)
            finally:
                if progress_ctx:
                    progress_ctx.stop()

            # Clear progress on completion
            await cache.clear_progress(csv_hash)

            # Print summary
            console.print("\n[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
            console.print("[bold cyan]📊 Processing Complete![/bold cyan]\n")

            console.print(f"[green]✓ Successfully processed:[/green] {results_summary['success']}")
            if results_summary['flagged'] > 0:
                console.print(f"[yellow]⚠ Flagged for review:[/yellow] {results_summary['flagged']}")
            if results_summary['errors'] > 0:
                console.print(f"[red]✗ Errors:[/red] {results_summary['errors']}")

            if not skip_evaluation:
                console.print(f"\n[bold]Quality Results:[/bold]")
                console.print(f"[green]  Passed ({quality_threshold}+):[/green] {results_summary['quality_passed']}")
                console.print(f"[yellow]  Below threshold:[/yellow] {results_summary['quality_failed']}")

                if results_summary['quality_passed'] + results_summary['quality_failed'] > 0:
                    pass_rate = (results_summary['quality_passed'] / (results_summary['quality_passed'] + results_summary['quality_failed'])) * 100
                    console.print(f"[dim]  Pass rate: {pass_rate:.1f}%[/dim]")

            console.print(f"\n[bold]Output saved to:[/bold] [cyan]{output_path}[/cyan]")
            console.print("[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]\n")

    # Final save
    console.print(f"[dim]💾 Final save to {output_path}[/dim]")
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    # Summary
    console.print()
    console.print("[bold]Processing Complete![/bold]")
    console.print(f"  Output saved to: {output_path}")
    console.print(f"  AI-generated openers: {results_summary['success']}")
    console.print(f"  Template fallbacks: {results_summary['flagged']}")
    console.print(f"  Errors: {results_summary['errors']}")

    if not skip_evaluation and (results_summary["quality_passed"] + results_summary["quality_failed"]) > 0:
        console.print()
        console.print("[bold]Quality Evaluation:[/bold]")
        console.print(f"  Passed: {results_summary['quality_passed']}")
        console.print(f"  Failed: {results_summary['quality_failed']}")
        pass_rate = (
            results_summary['quality_passed']
            / (results_summary['quality_passed'] + results_summary['quality_failed'])
            * 100
        )
        console.print(f"  Pass rate: {pass_rate:.1f}%")


@app.command("dry-run")
def dry_run(
    csv_path: Path = typer.Argument(..., help="Path to contacts CSV file"),
    row_index: int = typer.Option(0, "--row-index", "-r", help="Row index to test (0-based)"),
):
    """Test all prompt variations on a single contact."""
    if not csv_path.exists():
        console.print(f"[red]Error: CSV file not found: {csv_path}[/red]")
        raise typer.Exit(1)

    asyncio.run(_dry_run_async(csv_path, row_index))


async def _dry_run_async(csv_path: Path, row_index: int):
    """Async implementation of dry-run command."""
    # Load contacts
    contacts = load_contacts(csv_path)
    if not contacts:
        console.print("[red]Error: No valid contacts found in CSV[/red]")
        return

    if row_index >= len(contacts):
        console.print(f"[red]Error: Row index {row_index} out of range (max: {len(contacts) - 1})[/red]")
        return

    contact = contacts[row_index]
    console.print(f"[cyan]Testing contact: {contact.full_name} at {contact.company}[/cyan]")

    async with SQLiteCache() as cache:
        async with Fetcher() as fetcher:
            analyzer = ContextAnalyzer(fetcher, cache)

            # Get context
            with console.status("Scraping website..."):
                context = await analyzer.get_context(contact)

            console.print(f"Context quality: {context.quality.value}")
            if context.blog_url:
                console.print(f"Blog URL: {context.blog_url}")

            # Run parallel tests
            tester = ParallelTester()
            with console.status("Running prompt variations in parallel..."):
                results = await tester.test_all_variations(contact, context)

            # Display and save results
            tester.display_results(results, contact, context)
            output_path = tester.save_results(results, contact, context)
            console.print(f"\n[dim]Results saved to: {output_path}[/dim]")


@app.command("setup-gmail")
def setup_gmail():
    """Set up Gmail OAuth authentication."""
    console.print("[cyan]Setting up Gmail authentication...[/cyan]")

    try:
        auth = GmailAuth()
        auth.setup_oauth()
        console.print("[green]Gmail authentication successful![/green]")
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        console.print("\n[yellow]To set up Gmail:[/yellow]")
        console.print("1. Go to Google Cloud Console")
        console.print("2. Create OAuth 2.0 credentials (Desktop app)")
        console.print("3. Download the JSON file")
        console.print("4. Save it as data/credentials.json")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    csv_path: Path = typer.Argument(..., help="Path to contacts CSV file"),
):
    """Show processing status for a CSV file."""
    if not csv_path.exists():
        console.print(f"[red]Error: CSV file not found: {csv_path}[/red]")
        raise typer.Exit(1)

    asyncio.run(_status_async(csv_path))


async def _status_async(csv_path: Path):
    """Async implementation of status command."""
    contacts = load_contacts(csv_path)
    csv_hash = get_csv_hash(csv_path)

    async with SQLiteCache() as cache:
        progress = await cache.get_progress(csv_hash)
        stats = await cache.get_stats()

        table = Table(title="Processing Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value")

        table.add_row("CSV File", str(csv_path))
        table.add_row("Total Contacts", str(len(contacts)))

        if progress:
            table.add_row("Last Processed", str(progress[0] + 1))
            table.add_row("Remaining", str(len(contacts) - progress[0] - 1))
        else:
            table.add_row("Progress", "Not started or completed")

        table.add_row("Cached Contexts", str(stats["cached_contexts"]))
        table.add_row("Generated Emails", str(stats["generated_emails"]))

        console.print(table)


@app.command("clear-cache")
def clear_cache(
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Clear all cached data."""
    if not confirm:
        confirm = typer.confirm("Are you sure you want to clear all cached data?")

    if confirm:
        asyncio.run(_clear_cache_async())
        console.print("[green]Cache cleared successfully![/green]")
    else:
        console.print("[yellow]Cancelled[/yellow]")


async def _clear_cache_async():
    """Async implementation of clear-cache command."""
    async with SQLiteCache() as cache:
        await cache.clear_all()


if __name__ == "__main__":
    app()
