import asyncio
import json
import os
import sys
import textwrap
from pathlib import Path

from groq import Groq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

MODEL         = "llama-3.1-8b-instant"         #"llama-3.3-70b-versatile"
SERVER_SCRIPT = Path(__file__).parent / "mcp_server.py"
MAX_ITERATIONS = 6

SYSTEM_PROMPT = (
    "You are an intelligent enterprise assistant for Centroid, an Oracle consulting firm. "
    "You have access to tools that can query Oracle ERP data, convert currencies, and check project health. "
    "When the user asks a question:\n"
    "1. Decide which tool(s) to call based on what the user needs.\n"
    "2. Interpret the JSON results clearly in plain business language.\n"
    "3. Be concise but complete. Use bullet points or tables where helpful.\n"
    "4. Always mention that data is from a demo/mock environment."
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def divider(label: str = ""):
    w = 70
    if label:
        pad = (w - len(label) - 2) // 2
        print(f"\n{'─'*pad} {label} {'─'*(w - pad - len(label) - 2)}")
    else:
        print("─" * w)


def pretty_json(obj):
    text = json.dumps(obj, indent=2)
    if len(text) > 1200:
        text = text[:1200] + "\n  ... (truncated)"
    return text


def mcp_tools_to_groq_tools(mcp_tools) -> list[dict]:
    """Convert MCP tool definitions → Groq/OpenAI function-calling format."""
    groq_tools = []
    for t in mcp_tools:
        schema = dict(t.inputSchema) if t.inputSchema else {}
        if schema.get("type") != "object":
            schema = {"type": "object", "properties": {}}
        groq_tools.append({
            "type": "function",
            "function": {
                "name":        t.name,
                "description": t.description or "",
                "parameters":  schema,
            }
        })
    return groq_tools


# ─────────────────────────────────────────────
# Core Agent loop
# ─────────────────────────────────────────────

async def run_agent(user_query: str, status_callback=None) -> str:
    """
    Run the MCP agent and return the final answer as a plain string.

    Parameters
    ----------
    user_query      : natural-language question from the user
    status_callback : optional callable(str) for live status updates
                      (used by the Streamlit UI to show progress)

    Returns
    -------
    str  – the model's final natural-language answer
    """

    def status(msg: str):
        """Print to terminal AND forward to UI if a callback is registered."""
        print(msg)
        if status_callback:
            status_callback(msg)

    status(f"⚙️  Connecting to MCP server...")

    server_params = StdioServerParameters(
        command="python",
        args=[str(SERVER_SCRIPT)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover tools
            tools_result = await session.list_tools()
            mcp_tools    = tools_result.tools
            tool_names   = [t.name for t in mcp_tools]
            status(f"🔧 Tools available: {', '.join(tool_names)}")

            groq_tools = mcp_tools_to_groq_tools(mcp_tools)

            client = Groq(api_key=os.environ["GROQ_API_KEY"]) #to be set with the env variable GROQ_API_KEY

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_query},
            ]

            for iteration in range(MAX_ITERATIONS):
                status(f"🤖 Llama thinking... (step {iteration + 1})")

                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=groq_tools,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=2048,
                )

                msg           = response.choices[0].message
                finish_reason = response.choices[0].finish_reason

                # Terminal trace
                if msg.content:
                    print(f"\n{textwrap.fill(msg.content, 80)}")

                # No tool calls → final answer
                if finish_reason == "stop" or not msg.tool_calls:
                    final_answer = msg.content or "No answer returned."
                    divider("Final Answer")
                    print(final_answer)
                    return final_answer

                # Execute tool calls via MCP
                messages.append(msg)

                for tool_call in msg.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments or "{}")

                    status(f"🔨 Calling tool: {tool_name}...")
                    divider(f"Tool Call → {tool_name}")
                    print(f"Arguments:\n{pretty_json(tool_args)}")

                    mcp_result  = await session.call_tool(tool_name, arguments=tool_args)
                    result_text = mcp_result.content[0].text if mcp_result.content else "{}"

                    print(f"\nResult:\n{pretty_json(json.loads(result_text))}")

                    messages.append({
                        "role":         "tool",
                        "tool_call_id": tool_call.id,
                        "name":         tool_name,
                        "content":      result_text,
                    })

            # Safety fallback
            fallback = "⚠️ Reached max iterations without a final answer."
            print(fallback)
            return fallback


# ─────────────────────────────────────────────
# Entry point (terminal use)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if "GROQ_API_KEY" not in os.environ:
        print("ERROR: GROQ_API_KEY is not set.")
        print("\n  1. Go to https://console.groq.com")
        print("  2. Sign up free → API Keys → Create API Key")
        print("  3. Windows CMD:        set GROQ_API_KEY=gsk_...")
        print("     Windows PowerShell: $env:GROQ_API_KEY=\"gsk_...\"")
        print("     Mac/Linux:          export GROQ_API_KEY=\"gsk_...\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "Give me a summary of all purchase orders and their total value in INR."
    )
    asyncio.run(run_agent(query))
