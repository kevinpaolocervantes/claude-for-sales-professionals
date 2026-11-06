#!/usr/bin/env python3
"""
sales-claude — a CLI that runs the 10 Sales Claude Prompts against the Anthropic API.

Usage:
    sales-claude list
    sales-claude show <prompt_id>
    sales-claude run <prompt_id> --input key=value [--input key=value ...]
    sales-claude run <prompt_id> --interactive
    sales-claude run <prompt_id> --input-file inputs.json

Environment:
    ANTHROPIC_API_KEY must be set (either in the shell or in a .env file).
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

try:
    from anthropic import Anthropic
except ImportError:
    print("Missing dependency: anthropic. Run: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

load_dotenv()

app = typer.Typer(
    add_completion=False,
    help="Run the 10 Sales Claude Prompts against the Anthropic API.",
    no_args_is_help=True,
)
console = Console()

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "prompts"

DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 4096

# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

VARIABLE_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


@dataclass
class PromptSpec:
    """A parsed prompt template."""

    id: str
    path: Path
    title: str
    category: str
    best_model: str
    inputs_required: list[str]
    body: str  # the full markdown of the prompt

    @property
    def variables(self) -> list[str]:
        """All {{variable}} names referenced in the body, in order of first appearance."""
        seen: list[str] = []
        for match in VARIABLE_RE.finditer(self.body):
            name = match.group(1)
            if name not in seen:
                seen.append(name)
        return seen


def _parse_prompt_header(text: str) -> dict:
    """Pull Title / Category / Best model / Inputs required from the prompt markdown header."""
    header: dict = {"title": "", "category": "", "best_model": DEFAULT_MODEL, "inputs_required": []}

    first_line = text.splitlines()[0] if text else ""
    if first_line.startswith("# "):
        header["title"] = first_line[2:].strip()

    for raw in text.splitlines()[1:30]:
        line = raw.strip()
        if line.startswith("**Category:**"):
            header["category"] = line.replace("**Category:**", "").strip()
        elif line.startswith("**Best model:**"):
            # best model is backticked, strip ticks
            value = line.replace("**Best model:**", "").strip()
            header["best_model"] = value.strip("`").split()[0] if value else DEFAULT_MODEL
        elif line.startswith("**Inputs required:**"):
            value = line.replace("**Inputs required:**", "").strip()
            # pull out `backticked` names
            header["inputs_required"] = re.findall(r"`([^`]+)`", value)

    return header


def load_prompt(prompt_id: str) -> PromptSpec:
    """Load a prompt by its ID (e.g. '01', '1', 'icp', or filename stem)."""
    candidates = sorted(PROMPTS_DIR.glob("*.md"))
    if not candidates:
        raise FileNotFoundError(f"No prompt files found in {PROMPTS_DIR}")

    needle = prompt_id.lower().strip()
    # Try numeric match first (01, 1, 10)
    try:
        n = int(needle)
        for p in candidates:
            if p.stem.startswith(f"{n:02d}_"):
                return _spec_from_path(p)
    except ValueError:
        pass

    # Try substring match on stem
    matches = [p for p in candidates if needle in p.stem.lower()]
    if len(matches) == 1:
        return _spec_from_path(matches[0])
    if len(matches) > 1:
        names = ", ".join(p.stem for p in matches)
        raise ValueError(f"Ambiguous prompt id '{prompt_id}'. Matches: {names}")

    raise FileNotFoundError(f"No prompt matching '{prompt_id}'. Try `sales-claude list`.")


def _spec_from_path(path: Path) -> PromptSpec:
    text = path.read_text(encoding="utf-8")
    header = _parse_prompt_header(text)
    return PromptSpec(
        id=path.stem,
        path=path,
        title=header["title"],
        category=header["category"],
        best_model=header["best_model"],
        inputs_required=header["inputs_required"],
        body=text,
    )


def list_prompts() -> list[PromptSpec]:
    return [_spec_from_path(p) for p in sorted(PROMPTS_DIR.glob("*.md"))]


# ---------------------------------------------------------------------------
# Variable substitution
# ---------------------------------------------------------------------------

def substitute(body: str, values: dict[str, str]) -> tuple[str, list[str]]:
    """Substitute {{var}} placeholders. Returns (rendered, missing_vars)."""
    missing: list[str] = []

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name not in values:
            if name not in missing:
                missing.append(name)
            return m.group(0)
        return str(values[name])

    rendered = VARIABLE_RE.sub(repl, body)
    return rendered, missing


def parse_input_flags(pairs: list[str]) -> dict[str, str]:
    """Parse --input key=value pairs. Supports @file.txt to load value from a file."""
    out: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise typer.BadParameter(f"--input must be key=value, got: {pair}")
        key, value = pair.split("=", 1)
        key = key.strip()
        if value.startswith("@"):
            fp = Path(value[1:]).expanduser()
            if not fp.exists():
                raise typer.BadParameter(f"Input file does not exist: {fp}")
            value = fp.read_text(encoding="utf-8")
        out[key] = value
    return out


def prompt_interactive(missing: list[str]) -> dict[str, str]:
    """Prompt the user interactively for missing variables. Multi-line via '.' sentinel."""
    collected: dict[str, str] = {}
    console.print("\n[bold cyan]Interactive input[/bold cyan] — enter a single line per variable.")
    console.print("For multi-line input, end your value with a line containing just [bold]:end[/bold].\n")
    for name in missing:
        console.print(f"[bold]{name}[/bold]:")
        first = typer.prompt("", default="", show_default=False)
        if first == ":end":
            collected[name] = ""
            continue
        if first.strip() == ":multi":
            lines: list[str] = []
            while True:
                line = typer.prompt("...", default="", show_default=False)
                if line == ":end":
                    break
                lines.append(line)
            collected[name] = "\n".join(lines)
        else:
            collected[name] = first
    return collected


# ---------------------------------------------------------------------------
# Anthropic call
# ---------------------------------------------------------------------------

def call_claude(
    rendered_prompt: str,
    *,
    model: str,
    max_tokens: int,
    stream: bool,
    system: Optional[str] = None,
) -> str:
    """Call the Anthropic API. Returns the full response text."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]ANTHROPIC_API_KEY is not set.[/red] Add it to your shell or a .env file.")
        raise typer.Exit(code=2)

    client = Anthropic(api_key=api_key)

    messages = [{"role": "user", "content": rendered_prompt}]
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    if stream:
        collected: list[str] = []
        with client.messages.stream(**kwargs) as s:
            for event_text in s.text_stream:
                console.print(event_text, end="", soft_wrap=True, highlight=False)
                collected.append(event_text)
            console.print()
        return "".join(collected)

    resp = client.messages.create(**kwargs)
    text = "".join(block.text for block in resp.content if hasattr(block, "text"))
    console.print(text)
    return text


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command("list")
def cmd_list() -> None:
    """List all available prompts."""
    specs = list_prompts()
    if not specs:
        console.print(f"[yellow]No prompts found in {PROMPTS_DIR}[/yellow]")
        raise typer.Exit(code=1)

    table = Table(title="Sales Claude Prompts", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Category", style="dim")
    table.add_column("Required inputs", style="green")

    for spec in specs:
        number = spec.id.split("_", 1)[0]
        table.add_row(
            number,
            spec.title,
            spec.category,
            ", ".join(spec.inputs_required) or "—",
        )
    console.print(table)
    console.print(
        "\nRun one with: [bold]sales-claude run <ID> --input key=value[/bold]  "
        "(use [bold]--interactive[/bold] to be prompted)."
    )


@app.command("show")
def cmd_show(prompt_id: str = typer.Argument(..., help="Prompt ID (e.g. '03' or 'objection')")) -> None:
    """Show the full markdown of a prompt."""
    spec = load_prompt(prompt_id)
    console.print(Markdown(spec.body))


@app.command("vars")
def cmd_vars(prompt_id: str = typer.Argument(..., help="Prompt ID")) -> None:
    """List the {{variables}} a prompt expects."""
    spec = load_prompt(prompt_id)
    console.print(f"[bold]{spec.title}[/bold]  ({spec.id})")
    console.print(f"Required: {', '.join(spec.inputs_required) or '—'}")
    console.print(f"All variables referenced in body: {', '.join(spec.variables) or '—'}")


@app.command("run")
def cmd_run(
    prompt_id: str = typer.Argument(..., help="Prompt ID (e.g. '03' or 'objection')"),
    input_pairs: list[str] = typer.Option(
        [], "--input", "-i",
        help="key=value pairs for prompt variables. Use @filename to load value from file.",
    ),
    input_file: Optional[Path] = typer.Option(
        None, "--input-file", "-f",
        help="JSON file mapping variable names to values.",
    ),
    interactive: bool = typer.Option(
        False, "--interactive",
        help="Prompt for any missing variables interactively.",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help=f"Anthropic model id. Defaults to the prompt's suggested model, else {DEFAULT_MODEL}.",
    ),
    max_tokens: int = typer.Option(
        DEFAULT_MAX_TOKENS, "--max-tokens",
        help="Max output tokens.",
    ),
    stream: bool = typer.Option(
        True, "--stream/--no-stream",
        help="Stream the response as it is generated.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Render the prompt with variables substituted but do not call the API.",
    ),
    save: Optional[Path] = typer.Option(
        None, "--save",
        help="Save the model's output to this file.",
    ),
) -> None:
    """Run a prompt against Claude."""
    spec = load_prompt(prompt_id)

    values: dict[str, str] = {}
    if input_file is not None:
        if not input_file.exists():
            console.print(f"[red]Input file not found: {input_file}[/red]")
            raise typer.Exit(code=2)
        try:
            values.update(json.loads(input_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON in {input_file}: {e}[/red]")
            raise typer.Exit(code=2)

    values.update(parse_input_flags(input_pairs))

    rendered, missing = substitute(spec.body, values)

    if missing and interactive:
        extra = prompt_interactive(missing)
        values.update(extra)
        rendered, missing = substitute(spec.body, values)

    if missing:
        console.print(
            f"[yellow]Missing variables:[/yellow] {', '.join(missing)}\n"
            f"Pass them with --input name=value, --input-file inputs.json, or --interactive."
        )
        raise typer.Exit(code=2)

    chosen_model = model or spec.best_model or DEFAULT_MODEL

    if dry_run:
        console.print(f"[dim]# model: {chosen_model}[/dim]")
        console.print(f"[dim]# prompt: {spec.id}[/dim]")
        console.print("[dim]# --- rendered prompt below ---[/dim]\n")
        console.print(rendered)
        return

    console.print(f"[dim]running {spec.id} on {chosen_model}...[/dim]\n")
    output = call_claude(
        rendered,
        model=chosen_model,
        max_tokens=max_tokens,
        stream=stream,
    )

    if save:
        save.parent.mkdir(parents=True, exist_ok=True)
        save.write_text(output, encoding="utf-8")
        console.print(f"\n[green]Saved to {save}[/green]")


@app.command("render")
def cmd_render(
    prompt_id: str = typer.Argument(..., help="Prompt ID"),
    input_pairs: list[str] = typer.Option([], "--input", "-i"),
    input_file: Optional[Path] = typer.Option(None, "--input-file", "-f"),
) -> None:
    """Render a prompt with variables substituted and print it (no API call)."""
    spec = load_prompt(prompt_id)
    values: dict[str, str] = {}
    if input_file is not None and input_file.exists():
        values.update(json.loads(input_file.read_text(encoding="utf-8")))
    values.update(parse_input_flags(input_pairs))
    rendered, missing = substitute(spec.body, values)
    if missing:
        console.print(f"[yellow]# Missing variables: {', '.join(missing)}[/yellow]")
    console.print(rendered)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
