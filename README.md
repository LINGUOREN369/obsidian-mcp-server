# obsidian-mcp-server

A local MCP (Model Context Protocol) server that gives AI clients (Claude Desktop, Claude Code, Cursor) direct read/search/write access to your Obsidian vault.

## How it works

```
┌─────────────────┐        stdio (JSON-RPC)        ┌─────────────────────┐
│   AI Client     │◄──────────────────────────────►│  obsidian_server.py  │
│  (Claude Code,  │                                 │                     │
│  Claude Desktop,│   Tools exposed:                │  Reads/writes your  │
│   Cursor, etc.) │   • read_note                   │  vault's .md files  │
│                 │   • search_notes                │  directly on disk   │
└─────────────────┘   • write_note                  └─────────────────────┘
                      • list_folder                          │
                                                             ▼
                                                   ┌─────────────────────┐
                                                   │  Your Obsidian Vault │
                                                   │  (folder of .md)    │
                                                   └─────────────────────┘
```

The AI client spawns this server as a subprocess. They communicate over stdin/stdout using JSON-RPC 2.0 (the MCP standard). The server never touches the network — it only reads and writes files in the vault directory you configure.

## Repository structure

```
obsidian-mcp-server/
├── obsidian_server.py   # The MCP server — all tool definitions live here
├── pyproject.toml       # Python project config (dependency: mcp[cli])
├── .env                 # Your local vault path (git-ignored)
├── .env.example         # Template for .env
├── .gitignore           # Ignores .venv, .env, __pycache__
├── .python-version      # Python version pin
└── uv.lock              # Locked dependency versions
```

## Tools provided

| Tool | What it does |
|------|--------------|
| `read_note` | Read any `.md` file by relative path |
| `search_notes` | Case-insensitive substring search across all `.md` files, returns up to 20 matching paths |
| `write_note` | Create or overwrite a `.md` file (creates parent folders if needed) |
| `list_folder` | List files and subfolders in a directory |

All tools enforce path validation — they reject any path that would escape your vault directory.

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

Install uv if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install dependencies

```bash
cd /path/to/obsidian-mcp-server
uv sync
```

### Configure your vault path

```bash
cp .env.example .env
```

Edit `.env` and set `OBSIDIAN_VAULT_PATH` to the absolute path of your Obsidian vault:

```
OBSIDIAN_VAULT_PATH=/Users/yourname/path/to/your/vault
```

## Connecting to an AI client

### Claude Code

Register the server (one-time):

```bash
claude mcp add -t stdio \
  -e "OBSIDIAN_VAULT_PATH=/Users/yourname/path/to/vault" \
  -s user \
  obsidian uv -- --directory /path/to/obsidian-mcp-server run obsidian_server.py
```

Verify it's connected:

```
/mcp
```

You should see `obsidian` listed with 4 tools.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/obsidian-mcp-server",
        "run", "obsidian_server.py"
      ],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/Users/yourname/path/to/vault"
      }
    }
  }
}
```

Then fully quit Claude Desktop (Cmd+Q) and relaunch it.

### Cursor / other MCP-compatible editors

Most editors that support MCP accept the same config format as Claude Desktop. Check your editor's MCP documentation for where to place the config.

## Usage

Once connected, you just talk to Claude normally. Examples:

- "List all folders in my vault"
- "Search my notes for 'machine learning'"
- "Read the file at projects/thesis-outline.md"
- "Create a new note at inbox/meeting-notes-2025-01-15.md with these bullet points: ..."
- "Find all notes that mention 'Python' and summarize them"

Claude will automatically call the appropriate tools. You don't need to name the tools explicitly — just describe what you want.

## Security notes

- The server only accesses files inside your configured vault path. Path traversal attempts (e.g., `../../etc/passwd`) are rejected.
- The `.env` file containing your vault path is git-ignored and never committed.
- The server runs locally over stdio — no network ports are opened, no data leaves your machine.
- The `write_note` tool will overwrite files without confirmation. If you want a safety net, make sure your vault is backed up or version-controlled.

## Extending the server

To add new tools, define an async function with the `@mcp.tool()` decorator in `obsidian_server.py`:

```python
@mcp.tool()
async def my_new_tool(param: str) -> str:
    """Description of what this tool does (shown to the AI).

    Args:
        param: Description of the parameter
    """
    # your logic here
    return "result"
```

The function's docstring becomes the tool description, and type hints become the input schema. Restart the server (or reconnect) to pick up changes.
