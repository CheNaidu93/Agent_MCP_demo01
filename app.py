import asyncio
import os

import streamlit as st

from mcp_agent_groq import run_agent


# ─────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Centroid MCP Agent",
    page_icon="🤖",
    layout="centered",
)


# ─────────────────────────────────────────────────────────────
# Styling
# ─────────────────────────────────────────────────────────────

st.markdown("""
<style>
.stApp { background-color: #0F1117; }

.header-bar {
    background: linear-gradient(90deg, #FFA500, #0F2044);
    padding: 18px 24px;
    border-radius: 10px;
    margin-bottom: 20px;
}
.header-bar h1 { color: #fff; margin: 0; font-size: 1.55rem; }
.header-bar p  { color: #CCFBF1; margin: 4px 0 0 0; font-size: 0.88rem; }

.bubble-user {
    background: #0D9488;
    color: #fff;
    padding: 12px 16px;
    border-radius: 18px 18px 4px 18px;
    margin: 8px 0 8px 18%;
    font-size: 0.93rem;
    line-height: 1.5;
}
.bubble-bot {
    background: #1E293B;
    color: #E2E8F0;
    padding: 14px 18px;
    border-radius: 18px 18px 18px 4px;
    margin: 8px 18% 8px 0;
    font-size: 0.93rem;
    line-height: 1.65;
}

.step-log {
    background: #0F172A;
    border-left: 3px solid #0D9488;
    padding: 8px 12px;
    border-radius: 0 6px 6px 0;
    margin-bottom: 10px;
    font-size: 0.78rem;
    color: #7DD3FC;
    font-family: monospace;
}

.demo-badge {
    background: #1E293B;
    color: #94A3B8;
    font-size: 0.75rem;
    padding: 4px 10px;
    border-radius: 6px;
    display: inline-block;
    margin-bottom: 18px;
}

div[data-testid="stTextInput"] input {
    background: #1E293B !important;
    color: #E2E8F0 !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #0D9488 !important;
    box-shadow: 0 0 0 2px rgba(13,148,136,0.25) !important;
}

button[kind="primary"], .stButton button {
    background-color: #0D9488 !important;
    color: white !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 600 !important;
}
button[kind="primary"]:hover, .stButton button:hover {
    background-color: #0F766E !important;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────

st.markdown("""
<div class="header-bar">
  <h1>🤖 Centroid MCP Agent</h1>
  <p>Llama 3.3 70B · Oracle ERP, Projects &amp; Currency Tools via MCP</p>
</div>
<div class="demo-badge">⚠️ Demo environment — all ERP/project data is mock/simulated</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# API key guard
# ─────────────────────────────────────────────────────────────

if "GROQ_API_KEY" not in os.environ:
    st.error(
        "**GROQ_API_KEY is not set.** Get a free key at https://console.groq.com\n\n"
        "Then restart:\n"
        "- **Windows CMD:** `set GROQ_API_KEY=gsk_...` → `streamlit run app.py`\n"
        "- **PowerShell:** `$env:GROQ_API_KEY=\"gsk_...\"` → `streamlit run app.py`\n"
        "- **Mac/Linux:** `export GROQ_API_KEY=gsk_...` → `streamlit run app.py`"
    )
    st.stop()


# ─────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    # Each item: {"role": "user"|"assistant", "content": str, "steps": list[str]}
    st.session_state.messages = []


# ─────────────────────────────────────────────────────────────
# Async runner — avoids "event loop already running" in Streamlit
# ─────────────────────────────────────────────────────────────

def run_agent_sync(query: str, steps: list) -> str:
    """
    Run the async agent in a brand-new event loop.
    Streamlit's thread may already own a loop, so we create a fresh one.
    The steps list is mutated in-place via status_callback so the caller
    can show live progress.
    """
    def on_status(msg: str):
        steps.append(msg)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_agent(query, status_callback=on_status))
    finally:
        loop.close()


# ─────────────────────────────────────────────────────────────
# Render chat history
# ─────────────────────────────────────────────────────────────

def render_history():
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="bubble-user">👤&nbsp; {msg["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            # Show agent steps in a collapsible block
            steps_html = ""
            if msg.get("steps"):
                lines = "<br>".join(msg["steps"])
                steps_html = (
                    f'<details><summary style="color:#64748B;font-size:0.8rem;'
                    f'cursor:pointer;margin-bottom:6px">🔧 Agent steps '
                    f'({len(msg["steps"])})</summary>'
                    f'<div class="step-log">{lines}</div></details>'
                )
            content_html = msg["content"].replace("\n", "<br>")
            st.markdown(
                f'<div class="bubble-bot">{steps_html}{content_html}</div>',
                unsafe_allow_html=True,
            )


render_history()


# ─────────────────────────────────────────────────────────────
# Suggested starters (shown only on empty chat)
# ─────────────────────────────────────────────────────────────

SUGGESTIONS = [
    "Summarise all POs with total in INR",
    "Which projects are at risk?",
    "Show only pending purchase orders",
    "Convert the TCS PO value to AED",
    "Completion % of the JDE migration?",
    "List all approved POs and their suppliers",
]

if not st.session_state.messages:
    st.markdown("<br>**💡 Try asking:**", unsafe_allow_html=True)
    cols = st.columns(3)
    for i, s in enumerate(SUGGESTIONS):
        if cols[i % 3].button(s, key=f"sug_{i}"):
            st.session_state["prefill"] = s
            st.rerun()


# ─────────────────────────────────────────────────────────────
# Input row
# ─────────────────────────────────────────────────────────────

prefill = st.session_state.pop("prefill", "")

col_q, col_send, col_clear = st.columns([7, 1.3, 1.3])

with col_q:
    question = st.text_input(
        label="q",
        label_visibility="collapsed",
        placeholder="Ask about POs, projects, currencies…  (press Enter or click Send)",
        value=prefill,
        key="q_input",
    )

with col_send:
    send_clicked = st.button("Send ➤", use_container_width=True)

with col_clear:
    if st.button("🗑 Clear", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# ─────────────────────────────────────────────────────────────
# Submit logic
# ─────────────────────────────────────────────────────────────

# Trigger on button click OR Enter key (text_input submits on Enter
# which causes a rerun — we detect it via a changed value in prefill
# or by checking question vs last user message)
trigger = send_clicked or bool(prefill)

if trigger and question.strip():
    user_text = question.strip()

    # Don't re-process if identical to the last user message
    last_user = next(
        (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"),
        None,
    )
    if user_text == last_user and len(st.session_state.messages) % 2 == 0:
        # Already answered
        st.stop()

    # Append user bubble immediately
    st.session_state.messages.append({"role": "user", "content": user_text, "steps": []})

    # Run agent with live status
    steps: list[str] = []
    with st.spinner("🤖 Agent is thinking…"):
        try:
            answer = run_agent_sync(user_text, steps)
        except Exception as exc:
            answer = (
                f"❌ **Error:** {exc}\n\n"
                "Make sure `mcp_server.py` is in the same folder as `app.py` "
                "and your `GROQ_API_KEY` is valid."
            )

    # Append assistant bubble with steps
    st.session_state.messages.append({
        "role":    "assistant",
        "content": answer,
        "steps":   steps,
    })

    st.rerun()
