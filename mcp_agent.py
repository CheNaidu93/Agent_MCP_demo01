import asyncio
import json
import os
import sys
import textwrap
from pathlib import Path

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

MODEL          = "claude-haiku-4-5"           # fast & cheap for demos; swap to sonnet-4-6 for richer answers
SERVER_SCRIPT  = Path(__file__).parent / "mcp_server.py"
MAX_ITERATIONS = 5                            # safety cap on tool-call loops

SYSTEM_PROMPT = """You are an intelligent enterprise assistant for Centroid, an Oracle consulting firm.
You have access to MCP tools that can query Oracle ERP data, convert currencies, and check project health.

When the user asks a question:
1. Decide which tool(s) to call.
2. Interpret the JSON results in plain business language.
3. Be concise but complete. Use bullet points or tables where helpful.
4. Always mention data is from a demo/mock environment during the presentation.
"""


# ─────────────────────────────────────────────
# Helper: pretty-print
# ─────────────────────────────────────────────

def divider(label: str = ""):
    w = 70
    if label:
        pad = (w - len(label) - 2) // 2
        print(f"\n{'─'*pad} {label} {'─'*(w-pad-len(label)-2)}")
    else:
        print("─" * w)


def pretty_json(obj):
    """Return indented JSON string, truncated if very long."""
    text = json.dumps(obj, indent=2)
    if len(text) > 1200:
        text = text[:1200] + "\n  ... (truncated)"
    return text


# ─────────────────────────────────────────────
# Core Agent loop
# ─────────────────────────────────────────────

async def run_agent(user_query: str):
    divider("MCP AGENT  –  Centroid Demo")
    print(f"User query: {user_query}")

    # ── 1. Connect to MCP server ──────────────
    server_params = StdioServerParameters(
        command="python",
        args=[str(SERVER_SCRIPT)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ── 2. Discover tools ─────────────────
            tools_result = await session.list_tools()
            mcp_tools    = tools_result.tools

            divider("Available MCP Tools")
            for t in mcp_tools:
                print(f"  • {t.name:30s}  {t.description[:70]}")

            # ── 3. Convert MCP tools → Anthropic tool_spec format ─────────
            anthropic_tools = [
                {
                    "name":         t.name,
                    "description":  t.description,
                    "input_schema": t.inputSchema,
                }
                for t in mcp_tools
            ]

            # ── 4. Agentic loop ───────────────────
            client   = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            messages = [{"role": "user", "content": user_query}]

            for iteration in range(MAX_ITERATIONS):
                divider(f"Claude thinking (iteration {iteration + 1})")

                response = client.messages.create(
                    model=MODEL,
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    tools=anthropic_tools,
                    messages=messages,
                )

                # collect text blocks shown to user
                for block in response.content:
                    if hasattr(block, "text"):
                        print(f"\n{textwrap.fill(block.text, 80)}")

                # check stop reason
                if response.stop_reason == "end_turn":
                    divider("Final Answer")
                    for block in response.content:
                        if hasattr(block, "text"):
                            print(block.text)
                    break

                if response.stop_reason != "tool_use":
                    print(f"Unexpected stop_reason: {response.stop_reason}")
                    break

                # ── 5. Execute tool calls via MCP ─────────────────────────
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name = block.name
                    tool_args = block.input

                    divider(f"Tool Call → {tool_name}")
                    print(f"Arguments:\n{pretty_json(tool_args)}")

                    # Call the MCP tool
                    mcp_result = await session.call_tool(tool_name, arguments=tool_args)
                    result_text = mcp_result.content[0].text if mcp_result.content else "{}"

                    print(f"\nResult:\n{pretty_json(json.loads(result_text))}")

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     result_text,
                    })

                # ── 6. Feed results back to Claude ────────────────────────
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user",      "content": tool_results})

            else:
                print("\n⚠️  Reached max iterations without a final answer.")

    divider()


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable before running.")
        sys.exit(1)

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "Give me a summary of all purchase orders and tell me the total value in INR."
    )
    asyncio.run(run_agent(query))
