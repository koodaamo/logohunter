#!/usr/bin/env python3
"""
LogoHunt CLI - Command-line tool for discovering and analyzing website logos.

Usage:
    uv run logohunt <domain_name> [options]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.tree import Tree
from rich.text import Text
from rich.columns import Columns
from rich.align import Align

from logohunter import LogoHunter, Icon


def setup_logging(verbose: bool = False) -> None:
    """Set up minimal logging configuration."""
    level = logging.WARNING  # Only show warnings and errors
    logging.basicConfig(level=level, handlers=[logging.NullHandler()])

    # Suppress all HTTP logging
    logging.getLogger("httpx").setLevel(logging.CRITICAL)
    logging.getLogger("logo_hunter").setLevel(logging.WARNING)


def create_scoring_tree(icon: Icon) -> Tree:
    """Create a rich tree showing scoring breakdown."""
    if not icon.rule_details:
        return Tree("No detailed scoring available")

    tree = Tree(f"[bold]Score: {icon.score}[/bold]")

    for rule_label, score_contribution in icon.rule_details:
        if score_contribution > 0:
            tree.add(f"[green]+{score_contribution}[/green] {rule_label}")
        elif score_contribution < 0:
            tree.add(f"[red]{score_contribution}[/red] {rule_label}")
        else:
            tree.add(f"[dim]0[/dim] {rule_label}")

    return tree


def create_candidate_panel(icon: Icon, rank: int) -> Panel:
    """Create a rich panel for a single candidate."""
    # Format dimensions
    dimensions = ""
    if icon.width and icon.height:
        dimensions = f" ({icon.width}×{icon.height})"
    elif icon.width or icon.height:
        dimensions = f" ({icon.width or '?'}×{icon.height or '?'})"

    # Main info
    title = f"#{rank} • Score: {icon.score} • {icon.format.upper()}{dimensions}"

    # URL (truncated if too long)
    url = icon.url
    if len(url) > 80:
        url = url[:40] + "..." + url[-37:]

    content = f"[link]{url}[/link]"

    # Add context if available
    context_parts = []
    if icon.alt_text:
        context_parts.append(f"Alt: [italic]{icon.alt_text}[/italic]")
    if icon.css_classes:
        context_parts.append(f"Classes: [dim]{icon.css_classes}[/dim]")

    if context_parts:
        content += "\n" + " • ".join(context_parts)

    # Color based on score
    if icon.score >= 200:
        border_style = "green"
    elif icon.score >= 100:
        border_style = "yellow"
    elif icon.score >= 0:
        border_style = "blue"
    else:
        border_style = "red"

    return Panel(content, title=title, border_style=border_style, padding=(0, 1))


async def discover_logos(domain: str, console: Console) -> List[Icon]:
    """Discover logos for a domain and return the list of candidates."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Discovering logos for {domain}...", total=None)

        hunter = LogoHunter()
        logo_candidates = await hunter.find_logo_candidates(domain)

    return logo_candidates


def display_candidates(candidates: List[Icon], console: Console) -> None:
    """Display all candidates with rich formatting."""
    if not candidates:
        console.print("[red]❌ No logo candidates found[/red]")
        return

    console.print(
        f"\n[bold blue]📊 Found {len(candidates)} logo candidates[/bold blue]"
    )

    # Create panels for each candidate
    panels = []
    for i, icon in enumerate(candidates[:10], 1):  # Show top 10
        panels.append(create_candidate_panel(icon, i))

    # Display in columns if we have multiple candidates
    if len(panels) > 1:
        console.print(Columns(panels, equal=True, expand=True))
    elif panels:
        console.print(panels[0])

    # Show remaining count if truncated
    if len(candidates) > 10:
        console.print(f"\n[dim]... and {len(candidates) - 10} more candidates[/dim]")


def display_detailed_scoring(
    candidates: List[Icon], console: Console, show_all: bool = False
) -> None:
    """Display detailed scoring for top candidates."""
    if not candidates:
        return

    console.print(f"\n[bold yellow]🎯 Detailed Scoring Analysis[/bold yellow]")

    # Show detailed scoring for top 3 (or all if requested)
    show_count = len(candidates) if show_all else min(3, len(candidates))

    for i in range(show_count):
        icon = candidates[i]
        tree = create_scoring_tree(icon)

        # Truncate URL for display
        display_url = icon.url
        if len(display_url) > 60:
            display_url = display_url[:30] + "..." + display_url[-27:]

        panel = Panel(tree, title=f"#{i + 1} {display_url}", border_style="cyan")
        console.print(panel)


async def fetch_best_logo(
    candidates: List[Icon], domain: str, save_dir: str | None, console: Console
) -> None:
    """Fetch and optionally save the best logo."""
    if not candidates:
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Fetching best logo...", total=None)

        # Get URLs from top candidates (highest score first)
        candidate_urls = [icon.url for icon in candidates]

        hunter = LogoHunter()
        best_logo = await hunter.fetch_best_logo(candidate_urls)

    if not best_logo:
        console.print("[red]❌ Could not fetch any of the candidate logos[/red]")
        return

    # Success message
    console.print(f"\n[bold green]✅ Successfully fetched logo[/bold green]")

    # Show details - handle both PIL Image and SVG string
    details_table = Table(show_header=False, box=None, padding=(0, 1))

    if isinstance(best_logo, str):
        # SVG string
        details_table.add_row("[cyan]Type:[/cyan]", "SVG")
        details_table.add_row("[cyan]Format:[/cyan]", "Vector")
        details_table.add_row("[cyan]Size:[/cyan]", f"{len(best_logo)} bytes")
    else:
        # PIL Image
        details_table.add_row(
            "[cyan]Size:[/cyan]", f"{best_logo.size[0]}×{best_logo.size[1]}"
        )
        details_table.add_row("[cyan]Format:[/cyan]", best_logo.format)

    details_table.add_row(
        "[cyan]Selected:[/cyan]", f"Candidate #1 (score: {candidates[0].score})"
    )

    console.print(Panel(details_table, title="Logo Details", border_style="green"))

    if save_dir:
        # Process and save the image
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Saving logo...", total=None)

            # Determine output directory
            if save_dir:
                output_dir = Path(save_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                output_dir = Path(".")

            if isinstance(best_logo, str):
                # For SVG, save as logo.svg
                output_path = output_dir / "logo.svg"
                output_path.write_text(best_logo, encoding="utf-8")
            else:
                # For PIL images, determine extension from format
                ext = best_logo.format.lower() if best_logo.format else "png"
                if ext == "jpeg":
                    ext = "jpg"
                output_path = output_dir / f"logo.{ext}"
                best_logo.save(output_path)

        console.print(
            f"[bold green]💾 Saved to:[/bold green] [link]{output_path.absolute()}[/link]"
        )


async def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Discover and analyze website logos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run logohunt github.com
  uv run logohunt reddit.com --save
  uv run logohunt discord.com --verbose
  uv run logohunt openai.com --save logos/ --all-scores
        """,
    )

    parser.add_argument(
        "domain", help="Domain name to search for logos (e.g., github.com)"
    )

    parser.add_argument(
        "--save",
        nargs="?",
        const=".",
        metavar="DIR",
        help="Save the best logo as 'logo.ext' in current directory or specified directory",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed debug information"
    )

    parser.add_argument(
        "--all-scores",
        action="store_true",
        help="Show detailed scoring for all candidates",
    )

    args = parser.parse_args()

    # Set up logging and console
    setup_logging(verbose=args.verbose)
    console = Console()

    # Header
    console.print(
        Panel.fit(
            f"[bold blue]LogoHunt[/bold blue] • Analyzing [cyan]{args.domain}[/cyan]",
            border_style="blue",
        )
    )

    try:
        # Discover logo candidates
        candidates = await discover_logos(args.domain, console)

        if not candidates:
            console.print("[red]❌ No logo candidates found[/red]")
            return

        # Display candidates
        display_candidates(candidates, console)

        # Show detailed scoring
        if args.verbose or args.all_scores:
            display_detailed_scoring(candidates, console, show_all=args.all_scores)

        # Fetch and optionally save the best logo
        await fetch_best_logo(candidates, args.domain, args.save, console)

    except KeyboardInterrupt:
        console.print("\n[red]❌ Operation cancelled by user[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        if args.verbose:
            console.print_exception()
        sys.exit(1)


def cli_entry() -> None:
    """Sync entry point for CLI script."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_entry()
