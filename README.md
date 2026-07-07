# MCP Demo – Centroid Team Presentation

## Overview

This demo shows how **Model Context Protocol (MCP)** lets an AI agent call
real tools over a standard protocol, exactly the way USB-C standardised device
connections.

```
┌─────────────────────┐        MCP (stdio)        ┌─────────────────────┐
│   mcp_agent.py      │ ◄────────────────────────► │   mcp_server.py     │
│  (AI Agent + Claude)│                            │  (3 Business Tools) │
└─────────────────────┘                            └─────────────────────┘
         │                                                    │
   Anthropic API                                    ┌─────────┴─────────┐
  (claude-haiku-4-5)                                │ get_erp_po_summary│
                                                    │ convert_currency  │
                                                    │ get_project_status│
                                                    └───────────────────┘
```

---

## Quick Setup

```bash
# 1. Install Python dependencies
pip install anthropic mcp httpx

# 2. Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. Run the demo
python mcp_agent.py
```

---

## Files

| File | Purpose |
|------|---------|
| `mcp_server.py` | MCP server exposing 3 tools (ERP, currency, projects) |
| `mcp_agent.py`  | AI agent that discovers and calls those tools |
| `README.md`     | This file |

---

## Demo Queries to Try

```bash
# Default query (PO summary + INR conversion)
python mcp_agent.py

# Custom queries
python mcp_agent.py "What purchase orders are still pending approval?"
python mcp_agent.py "Convert 198000 USD to INR and EUR"
python mcp_agent.py "Which projects are at risk? Show me completion percentages."
python mcp_agent.py "Get the status of the AI ERP Assistant project"
python mcp_agent.py "Show me all approved POs and their total in AED"
```

---

## How It Works (Step-by-Step)

1. **Agent starts** → spawns `mcp_server.py` as a subprocess
2. **MCP handshake** → `initialize()` call establishes the session
3. **Tool discovery** → `list_tools()` returns all available tools with schemas
4. **Claude reasons** → decides which tool(s) to call based on the query
5. **Tool execution** → agent calls `session.call_tool(name, args)` via MCP
6. **Result handling** → JSON result passed back to Claude
7. **Final answer** → Claude interprets results in natural language

---

## Oracle MCP Servers (Real-World Extension)

Oracle provides official MCP servers for:
- **Oracle Database** – SQL queries via natural language
- **Oracle Analytics Cloud** – Dashboard & report generation
- **Oracle Fusion ERP** – Live REST API integration
- **OCI** – Infrastructure management

See the presentation slide on Oracle MCP for integration details.

---

## Key Concepts

| Term | What it means |
|------|--------------|
| **MCP** | Model Context Protocol – standard for AI ↔ tool communication |
| **MCP Server** | Any process that exposes tools via the MCP protocol |
| **MCP Client** | The AI agent side that discovers and calls those tools |
| **stdio transport** | Communication over stdin/stdout (simplest; no HTTP needed) |
| **SSE transport** | Server-Sent Events – used for remote/cloud MCP servers |
| **Tool schema** | JSON Schema describing a tool's inputs so Claude can call it correctly |
