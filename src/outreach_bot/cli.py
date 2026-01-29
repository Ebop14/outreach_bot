"""Typer CLI entry point."""

import asyncio
import hashlib
from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from outreach_bot.config import get_settings
from outreach_bot.models.contact import Contact
from outreach_bot.models.context import ContextQuality
from outreach_bot.scraper.fetcher import Fetcher
from outreach_bot.cache.sqlite_cache import SQLiteCache
from outreach_bot.analyzer.context_analyzer import ContextAnalyzer
from outreach_bot.generator.email_generator import EmailGenerator
from outreach_bot.gmail.auth import GmailAuth
from outreach_bot.gmail.draft_creator import DraftCreator
from outreach_bot.dry_run.parallel_tester import ParallelTester

app = typer.Typer(
    name="outreach",
    help="AI-powered outreach email automation system",
    no_args_is_help=True,
)
console = Console()


def load_contacts(csv_path: Path) -> list[Contact]:
    """Load contacts from CSV file."""
    df = pd.read_csv(csv_path)
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
    skip_gmail: bool = typer.Option(False, "--skip-gmail", help="Generate emails without creating drafts"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume from last progress"),
):
    """Process contacts and create Gmail drafts."""
    if not csv_path.exists():
        console.print(f"[red]Error: CSV file not found: {csv_path}[/red]")
        raise typer.Exit(1)

    asyncio.run(_run_async(csv_path, limit, skip_gmail, resume))


async def _run_async(csv_path: Path, limit: Optional[int], skip_gmail: bool, resume: bool):
    """Async implementation of run command."""
    settings = get_settings()

    # Load contacts
    contacts = load_contacts(csv_path)
    if not contacts:
        console.print("[red]Error: No valid contacts found in CSV[/red]")
        return

    if limit:
        contacts = contacts[:limit]

    csv_hash = get_csv_hash(csv_path)

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
            generator = EmailGenerator()

            # Gmail setup if needed
            draft_creator = None
            if not skip_gmail:
                auth = GmailAuth()
                if not auth.is_authenticated():
                    console.print("[red]Gmail not authenticated. Run 'outreach setup-gmail' first.[/red]")
                    return
                draft_creator = DraftCreator(auth)

            # Process contacts
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Processing contacts...",
                    total=len(contacts) - start_index,
                )

                results_summary = {"success": 0, "flagged": 0, "errors": 0}

                for i, contact in enumerate(contacts[start_index:], start=start_index):
                    progress.update(
                        task,
                        description=f"Processing {contact.company}...",
                    )

                    try:
                        # Get context
                        context = await analyzer.get_context(contact)

                        # Generate email
                        email = generator.generate_email(contact, context)

                        # Create draft if not skipping
                        if draft_creator:
                            draft_id, error = draft_creator.create_draft(email)
                            if error:
                                console.print(f"[red]Draft error for {contact.email}: {error}[/red]")
                                results_summary["errors"] += 1
                            else:
                                email.draft_id = draft_id
                                if email.is_flagged:
                                    results_summary["flagged"] += 1
                                else:
                                    results_summary["success"] += 1
                        else:
                            # Just count as success if skipping gmail
                            if email.is_flagged:
                                results_summary["flagged"] += 1
                            else:
                                results_summary["success"] += 1

                        # Save email record
                        await cache.save_email(contact.email, email.to_dict())

                        # Update progress
                        await cache.set_progress(csv_hash, i, len(contacts))

                    except Exception as e:
                        console.print(f"[red]Error processing {contact.email}: {e}[/red]")
                        results_summary["errors"] += 1

                    progress.advance(task)

            # Clear progress on completion
            await cache.clear_progress(csv_hash)

    # Summary
    console.print()
    console.print("[bold]Processing Complete![/bold]")
    console.print(f"  AI-generated openers: {results_summary['success']}")
    console.print(f"  Template fallbacks: {results_summary['flagged']}")
    console.print(f"  Errors: {results_summary['errors']}")


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
