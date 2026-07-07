import json
import asyncio
from datetime import datetime, timedelta
import random
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types


# ─────────────────────────────────────────────
# 1.  Mock data stores
# ─────────────────────────────────────────────

MOCK_PO_DATA = {
    "PO-2024-001": {"supplier": "Oracle Corp",        "amount": 125000, "status": "Approved",  "currency": "USD", "items": 12},
    "PO-2024-002": {"supplier": "SAP SE",             "amount": 87500,  "status": "Pending",   "currency": "USD", "items": 5},
    "PO-2024-003": {"supplier": "Infosys Ltd",        "amount": 45000,  "status": "Approved",  "currency": "USD", "items": 3},
    "PO-2024-004": {"supplier": "Wipro Technologies", "amount": 62000,  "status": "Rejected",  "currency": "USD", "items": 8},
    "PO-2024-005": {"supplier": "TCS Limited",        "amount": 198000, "status": "Approved",  "currency": "USD", "items": 20},
}

EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "INR": 94,
    "AED": 3.67,
    "JPY": 149.82,
    "AUD": 1.53,
    "CAD": 1.36,
}

MOCK_PROJECTS = {
    "PRJ-CENTROID-OCI":   {"name": "OCI Accelerator", "status": "On Track",    "completion": 72, "team": 8,  "due": "2025-09-30"},
    "PRJ-ERP-AGENT":      {"name": "AI ERP Assistant", "status": "At Risk",     "completion": 45, "team": 4,  "due": "2025-08-15"},
    "PRJ-JDE-MIGRATION":  {"name": "JDE-to-OCI Migration", "status": "On Track","completion": 88, "team": 12, "due": "2025-07-31"},
    "PRJ-APEX-CHATBOT":   {"name": "APEX Chatbot v2", "status": "Completed",   "completion": 100,"team": 3,  "due": "2025-06-01"},
}


# ─────────────────────────────────────────────
# 2.  MCP Server setup
# ─────────────────────────────────────────────

server = Server("centroid-demo-mcp-server")


# ─── Tool: list_tools ────────────────────────
@server.list_tools() #Registers this function as an MCP tool so that MCP clients can discover and invoke it.
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_erp_po_summary",
            description=(
                "Retrieve Oracle Fusion purchase order data. "
                "Returns details for a specific PO number, or a summary of all POs "
                "when no PO number is provided. Simulates Oracle Fusion Cloud REST API."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "po_number": {
                        "type": "string",
                        "description": "Optional. Specific PO number e.g. 'PO-2024-001'. Leave blank for all POs."
                    },
                    "status_filter": {
                        "type": "string",
                        "enum": ["Approved", "Pending", "Rejected", "All"],
                        "description": "Filter POs by approval status. Defaults to 'All'."
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="convert_currency",
            description=(
                "Convert an amount from one currency to another. "
                "Supported currencies: USD, EUR, GBP, INR, AED, JPY, AUD, CAD."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "amount":        {"type": "number",  "description": "Amount to convert"},
                    "from_currency": {"type": "string",  "description": "Source currency code, e.g. USD"},
                    "to_currency":   {"type": "string",  "description": "Target currency code, e.g. INR"},
                },
                "required": ["amount", "from_currency", "to_currency"]
            }
        ),
        types.Tool(
            name="get_project_status",
            description=(
                "Get project health and status from the Centroid project registry. "
                "Returns completion %, team size, due date, and RAG status. "
                "Provide a project ID or leave blank for all projects."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Optional project ID, e.g. 'PRJ-CENTROID-OCI'"
                    }
                },
                "required": []
            }
        ),
    ]


# ─── Tool: call_tool ─────────────────────────
@server.call_tool()     #Registers this function as an MCP tool so that MCP clients can discover and invoke it.
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    # ── Tool 1: ERP PO Summary ────────────────
    if name == "get_erp_po_summary":
        po_number     = arguments.get("po_number", "").strip()
        status_filter = arguments.get("status_filter", "All")

        if po_number:
            po = MOCK_PO_DATA.get(po_number.upper())
            if not po:
                result = {"error": f"PO '{po_number}' not found.", "available_pos": list(MOCK_PO_DATA.keys())}
            else:
                result = {"po_number": po_number.upper(), **po}
        else:
            all_pos = [{"po_number": k, **v} for k, v in MOCK_PO_DATA.items()]
            if status_filter != "All":
                all_pos = [p for p in all_pos if p["status"] == status_filter]
            total_amount = sum(p["amount"] for p in all_pos)
            result = {
                "source":       "Oracle Fusion Cloud (Mock)",
                "retrieved_at": datetime.utcnow().isoformat() + "Z",
                "filter":       status_filter,
                "count":        len(all_pos),
                "total_value":  f"${total_amount:,.2f}",
                "purchase_orders": all_pos,
            }
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── Tool 2: Currency Converter ────────────
    elif name == "convert_currency":
        amount        = float(arguments["amount"])
        from_cur      = arguments["from_currency"].upper()
        to_cur        = arguments["to_currency"].upper()

        if from_cur not in EXCHANGE_RATES:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown currency: {from_cur}"}))]
        if to_cur not in EXCHANGE_RATES:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown currency: {to_cur}"}))]

        usd_amount     = amount / EXCHANGE_RATES[from_cur]
        converted      = usd_amount * EXCHANGE_RATES[to_cur]
        rate           = EXCHANGE_RATES[to_cur] / EXCHANGE_RATES[from_cur]

        result = {
            "input":          f"{amount:,.2f} {from_cur}",
            "output":         f"{converted:,.2f} {to_cur}",
            "exchange_rate":  round(rate, 6),
            "rate_note":      f"1 {from_cur} = {rate:.4f} {to_cur}",
            "timestamp":      datetime.now().isoformat() + "Z",
        }
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── Tool 3: Project Status ─────────────────
    elif name == "get_project_status":
        project_id = arguments.get("project_id", "").strip()

        if project_id:
            proj = MOCK_PROJECTS.get(project_id.upper())
            if not proj:
                result = {"error": f"Project '{project_id}' not found.", "available": list(MOCK_PROJECTS.keys())}
            else:
                due  = datetime.strptime(proj["due"], "%Y-%m-%d")
                days = (due - datetime.now()).days
                result = {
                    "project_id":    project_id.upper(),
                    **proj,
                    "days_remaining": days,
                    "overdue":        days < 0,
                }
        else:
            all_proj = []
            for pid, pdata in MOCK_PROJECTS.items():
                due  = datetime.strptime(pdata["due"], "%Y-%m-%d")
                days = (due - datetime.now()).days
                all_proj.append({"project_id": pid, **pdata, "days_remaining": days})

            result = {
                "source":    "Centroid Project Registry (Mock)",
                "as_of":     datetime.now().isoformat() + "Z",
                "projects":  all_proj,
                "summary": {
                    "total":     len(all_proj),
                    "on_track":  sum(1 for p in all_proj if p["status"] == "On Track"),
                    "at_risk":   sum(1 for p in all_proj if p["status"] == "At Risk"),
                    "completed": sum(1 for p in all_proj if p["status"] == "Completed"),
                }
            }
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


# ─────────────────────────────────────────────
# 3.  Entry point
# ─────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
