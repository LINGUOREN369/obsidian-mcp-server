import os
import re
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("obsidian-vault")
VAULT = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "~/Obsidian")).expanduser()

MOC_FOLDER = "5. Index"
MOC_RULES_FILE = "MOC Organization Rules.md.md"
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
EXCLUDED_FOLDERS = {"5. Index", "4. Templates", "copilot"}


def _resolve(file_path: str) -> Path:
    """Resolve and validate a path is inside the vault."""
    full = (VAULT / file_path).resolve()
    if not str(full).startswith(str(VAULT.resolve())):
        raise ValueError(f"Path escapes vault: {file_path}")
    return full


@mcp.tool()
async def read_note(file_path: str) -> str:
    """Read a markdown file from the vault.

    Args:
        file_path: Relative path like 'projects/my-note.md'
    """
    p = _resolve(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Not found: {file_path}")
    return p.read_text(encoding="utf-8")


@mcp.tool()
async def search_notes(query: str) -> str:
    """Search vault files for a string (case-insensitive).

    Args:
        query: The search term
    """
    hits = []
    for md in VAULT.rglob("*.md"):
        try:
            text = md.read_text(encoding="utf-8")
        except Exception:
            continue
        if query.lower() in text.lower():
            rel = md.relative_to(VAULT)
            hits.append(str(rel))
    if not hits:
        return "No matches."
    return "\n".join(hits[:20])


@mcp.tool()
async def write_note(file_path: str, content: str) -> str:
    """Write or overwrite a markdown file in the vault.

    Args:
        file_path: Relative path like 'inbox/new-note.md'
        content: Markdown content to write
    """
    p = _resolve(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {file_path}"


@mcp.tool()
async def list_folder(directory: str = "") -> str:
    """List files and subfolders in a vault directory.

    Args:
        directory: Relative path, empty string for vault root
    """
    target = _resolve(directory) if directory else VAULT
    items = sorted(target.iterdir())
    lines = []
    for item in items:
        if item.name.startswith("."):
            continue
        prefix = "dir " if item.is_dir() else "    "
        lines.append(f"{prefix}{item.name}")
    return "\n".join(lines) or "(empty)"


def _extract_wikilinks(text: str) -> list[str]:
    """Extract all wikilink targets from text, handling aliases."""
    links = []
    for match in WIKILINK_RE.finditer(text):
        name = match.group(1).split("|")[0].strip()
        if name:
            links.append(name)
    return links


def _parse_moc_sections(text: str) -> list[tuple[str, list[str]]]:
    """Parse MOC text into [(section_name, [link_targets])]."""
    sections = []
    current_section = None
    current_links = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current_section is not None:
                sections.append((current_section, current_links))
            current_section = line[3:].strip()
            current_links = []
        elif current_section is not None:
            for match in WIKILINK_RE.finditer(line):
                name = match.group(1).split("|")[0].strip()
                if name:
                    current_links.append(name)
    if current_section is not None:
        sections.append((current_section, current_links))
    return sections


def _collect_all_moc_links() -> set[str]:
    """Collect all wikilink targets from all MOC files."""
    moc_dir = _resolve(MOC_FOLDER)
    if not moc_dir.exists():
        return set()
    linked = set()
    for moc_file in moc_dir.glob("*.md"):
        try:
            text = moc_file.read_text(encoding="utf-8")
        except Exception:
            continue
        for match in WIKILINK_RE.finditer(text):
            name = match.group(1).split("|")[0].strip()
            if name:
                linked.add(name.lower())
    return linked


def _is_excluded(rel_path: Path) -> bool:
    """Check if a path should be excluded from unlinked note scanning."""
    parts = rel_path.parts
    if any(p.startswith(".") for p in parts):
        return True
    if parts and parts[0] in EXCLUDED_FOLDERS:
        return True
    return False


@mcp.tool()
async def get_all_mocs() -> str:
    """Return all MOCs from 5. Index/ with their sections and links.

    Reads every MOC file in the Index folder and returns a structured
    summary showing each MOC's sections and the notes linked within.
    """
    moc_dir = _resolve(MOC_FOLDER)
    if not moc_dir.exists():
        raise FileNotFoundError(f"MOC folder '{MOC_FOLDER}' not found")

    output = []
    for moc_file in sorted(moc_dir.glob("*.md")):
        if moc_file.name == MOC_RULES_FILE:
            continue
        try:
            text = moc_file.read_text(encoding="utf-8")
        except Exception:
            output.append(f"=== {moc_file.stem} === (unreadable)")
            continue
        sections = _parse_moc_sections(text)
        output.append(f"=== {moc_file.stem} ===")
        if not sections:
            output.append("  (no sections)")
        for sec_name, links in sections:
            output.append(f"## {sec_name} ({len(links)} links)")
            for link in links:
                output.append(f"  - {link}")

    return "\n".join(output)


@mcp.tool()
async def find_unlinked_notes(folder: str = "", include_rough_notes: bool = True) -> str:
    """Find notes not linked in any MOC.

    Scans .md files and returns those not referenced in any MOC in 5. Index/.

    Args:
        folder: Restrict scan to this subfolder (e.g. '6. Zettelkasten'). Empty = all.
        include_rough_notes: Include 1. Rough Notes/ in the scan. Default True.
    """
    linked = _collect_all_moc_links()

    scan_root = _resolve(folder) if folder else VAULT
    if not scan_root.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    unlinked = {}
    total = 0

    for md_file in sorted(scan_root.rglob("*.md")):
        rel = md_file.relative_to(VAULT)
        if _is_excluded(rel):
            continue
        if not include_rough_notes and str(rel).startswith("1. Rough Notes"):
            continue
        total += 1
        stem = md_file.stem
        if stem.lower() not in linked:
            folder_name = str(rel.parent) if str(rel.parent) != "." else "(vault root)"
            unlinked.setdefault(folder_name, []).append(rel.name)

    count = sum(len(v) for v in unlinked.values())
    if count == 0:
        return f"All {total} notes are linked in MOCs."

    lines = [f"Found {count} unlinked notes (out of {total} scanned):"]
    for folder_name in sorted(unlinked):
        notes = unlinked[folder_name]
        lines.append(f"\n## {folder_name} ({len(notes)} unlinked)")
        for note in sorted(notes)[:50]:
            lines.append(f"  - {note}")
        if len(notes) > 50:
            lines.append(f"  ... and {len(notes) - 50} more")

    return "\n".join(lines)


@mcp.tool()
async def add_to_moc(moc_name: str, section: str, note_name: str, description: str = "") -> str:
    """Add a note link to a specific section of a MOC file.

    Inserts '- [[note_name]]' (with optional description) into the given section
    of the specified MOC. Safer than write_note as it appends rather than overwrites.

    Args:
        moc_name: MOC filename, e.g. 'Deep Learning MOC' or 'Deep Learning MOC.md'
        section: Section heading to insert under, e.g. 'Fundamentals & Theory'
        note_name: Note to link (without brackets), e.g. 'My New Note'
        description: Optional brief description appended after the link
    """
    if not moc_name.endswith(".md"):
        moc_name += ".md"
    moc_path = _resolve(f"{MOC_FOLDER}/{moc_name}")
    if not moc_path.exists():
        moc_dir = _resolve(MOC_FOLDER)
        available = [f.stem for f in sorted(moc_dir.glob("*MOC.md"))]
        raise FileNotFoundError(
            f"MOC '{moc_name}' not found. Available: {', '.join(available)}"
        )

    text = moc_path.read_text(encoding="utf-8")

    if f"[[{note_name}]]".lower() in text.lower():
        return f"'{note_name}' is already linked in {moc_name}"

    lines = text.splitlines()
    section_start = None
    next_section = None

    for i, line in enumerate(lines):
        if line.strip() == f"## {section}":
            section_start = i
        elif section_start is not None and line.startswith("## "):
            next_section = i
            break

    if section_start is None:
        available_sections = [l[3:].strip() for l in lines if l.startswith("## ")]
        raise ValueError(
            f"Section '{section}' not found in {moc_name}. "
            f"Available: {', '.join(available_sections)}"
        )

    boundary = next_section if next_section else len(lines)
    insert_at = section_start + 1
    for j in range(boundary - 1, section_start, -1):
        if lines[j].strip().startswith("- "):
            insert_at = j + 1
            break

    new_line = f"- [[{note_name}]]"
    if description:
        new_line += f" - {description}"

    lines.insert(insert_at, new_line)
    moc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return f"Added [[{note_name}]] to '{section}' in {moc_name}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
