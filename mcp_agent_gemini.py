import asyncio
import json
import os
import sys
import textwrap
from pathlib import Path

import google.genai as genai
import google.genai.types as gtypes

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

MODEL         = "gemini-2.0-flash"          # free tier, supports function calling
SERVER_SCRIPT = Path(__file__).parent / "mcp_server.py"
MAX_ITERATIONS = 6                          # safety cap on tool-call loops

SYSTEM_PROMPT = (
    "You are an intelligent enterprise assistant for Centroid, an Oracle consulting firm. "
    "You have access to tools that can query Oracle ERP data, convert currencies, and check project health. "
    "When the user asks a question: "
    "1. Decide which tool(s) to call. "
    "2. Interpret the JSON results in plain business language. "
    "3. Be concise but complete. Use bullet points or tables where helpful. "
    "4. Always mention data is from a demo/mock environment during the presentation."
)


# ─────────────────────────────────────────────
# Helper utilities
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


def mcp_schema_to_gemini_tool(mcp_tools) -> list[gtypes.Tool]:
    """
    Convert MCP tool definitions → a single Gemini Tool object containing
    a list of FunctionDeclarations.

    MCP gives us a JSON Schema in t.inputSchema.
    Gemini's FunctionDeclaration accepts that directly via parameters_json_schema.
    """
    declarations = []
    for t in mcp_tools:
        schema = t.inputSchema or {}
        # Gemini requires "type": "object" at the top level
        if schema.get("type") != "object":
            schema = {"type": "object", "properties": {}}

        declarations.append(
            gtypes.FunctionDeclaration(
                name=t.name,
                description=t.description or "",
                parameters_json_schema=schema,
            )
        )
    return [gtypes.Tool(function_declarations=declarations)]


# ─────────────────────────────────────────────
# Core Agent loop
# ─────────────────────────────────────────────

async def run_agent(user_query: str):
    divider("MCP AGENT (Gemini)  –  Centroid Demo")
    print(f"Model:      {MODEL}")
    print(f"User query: {user_query}")

    # ── 1. Connect to MCP server ──────────────
    server_params = StdioServerParameters(
        command="python",
        args=[str(SERVER_SCRIPT)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ── 2. Discover tools via MCP ─────────────────────────
            tools_result = await session.list_tools()
            mcp_tools    = tools_result.tools

            divider("Available MCP Tools")
            for t in mcp_tools:
                print(f"  • {t.name:30s}  {t.description[:70]}")

            # ── 3. Convert MCP tools → Gemini FunctionDeclarations ─
            gemini_tools = mcp_schema_to_gemini_tool(mcp_tools)

            # ── 4. Set up Gemini client ────────────────────────────
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

            # Conversation history for multi-turn
            # Gemini uses a list of Content objects
            contents: list[gtypes.Content] = [
                gtypes.Content(
                    role="user",
                    parts=[gtypes.Part(text=user_query)],
                )
            ]

            # ── 5. Agentic loop ────────────────────────────────────
            for iteration in range(MAX_ITERATIONS):
                divider(f"Gemini thinking (iteration {iteration + 1})")

                response = client.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=gtypes.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=gemini_tools,
                        temperature=0.1,
                    ),
                )

                candidate   = response.candidates[0]
                finish      = candidate.finish_reason
                parts       = candidate.content.parts or []

                # Print any text parts Gemini returned this turn
                for part in parts:
                    if part.text:
                        print(f"\n{textwrap.fill(part.text, 80)}")

                # Check if Gemini is done (no function calls)
                function_calls = [p for p in parts if p.function_call]

                if not function_calls:
                    divider("Final Answer")
                    for part in parts:
                        if part.text:
                            print(part.text)
                    break

                # ── 6. Execute each function call via MCP ──────────
                # Add Gemini's response (with function_call parts) to history
                contents.append(candidate.content)

                # Build the function_response parts
                function_response_parts = []

                for part in function_calls:
                    fc        = part.function_call
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}

                    divider(f"Tool Call → {tool_name}")
                    print(f"Arguments:\n{pretty_json(tool_args)}")

                    # Call the MCP tool
                    mcp_result  = await session.call_tool(tool_name, arguments=tool_args)
                    result_text = mcp_result.content[0].text if mcp_result.content else "{}"

                    print(f"\nResult:\n{pretty_json(json.loads(result_text))}")

                    # Wrap result as Gemini FunctionResponse
                    function_response_parts.append(
                        gtypes.Part(
                            function_response=gtypes.FunctionResponse(
                                name=tool_name,
                                response={"result": result_text},
                            )
                        )
                    )

                # ── 7. Feed results back to Gemini ─────────────────
                contents.append(
                    gtypes.Content(
                        role="user",
                        parts=function_response_parts,
                    )
                )

            else:
                print("\n⚠️  Reached max iterations without a final answer.")

    divider()


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if "GEMINI_API_KEY" not in os.environ:
        print("ERROR: Set the GEMINI_API_KEY environment variable before running.")
        print("       Get a free key at: https://aistudio.google.com/apikey")
        sys.exit(1)

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "Give me a summary of all purchase orders and tell me the total value in INR."
    )
    asyncio.run(run_agent(query))
