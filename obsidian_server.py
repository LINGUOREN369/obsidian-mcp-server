import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("obsidian-vault")
VAULT = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "~/Obsidian")).expanduser()


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


if __name__ == "__main__":
    mcp.run(transport="stdio")
