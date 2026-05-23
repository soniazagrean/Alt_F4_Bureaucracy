"""
NexusVault — Main Dashboard
"""
import os
import requests
import streamlit as st

st.set_page_config(
    page_title="NexusVault",
    page_icon="\U0001f3db",
    layout="wide",
)

API_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")

st.markdown("""
<style>
/* ── Service cards ── */
.svc-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 14px 18px;
    margin-bottom: 8px;
}
.svc-card .name  { font-size: 15px; font-weight: 700; color: #e2e8f0; }
.svc-card .desc  { font-size: 12px; color: #94a3b8; margin-top: 2px; }
.svc-card .dot   { display:inline-block; width:10px; height:10px;
                   border-radius:50%; margin-right:6px; }
.dot-ok   { background:#22c55e; }
.dot-down { background:#ef4444; }
.dot-unkn { background:#f59e0b; }
/* ── Stat metric ── */
.stat-box {
    background: #0f172a; border: 1px solid #1e3a5f;
    border-radius: 12px; padding: 16px;
    text-align: center;
}
.stat-box .val  { font-size: 32px; font-weight: 800; color: #38bdf8; }
.stat-box .lbl  { font-size: 12px; color: #64748b; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# ── Header ──────────────────────────────────────────────────────────────────────
st.title("\U0001f3db️ NexusVault")
st.caption("Automated document intake, classification, and archival platform.")

st.divider()

# ── Service health ───────────────────────────────────────────────────────────────
def _ping(url: str, timeout: float = 2.0) -> bool:
    try:
        return requests.get(url, timeout=timeout).status_code < 500
    except Exception:
        return False

SERVICES = [
    ("FastAPI",     f"{API_BASE_URL}/health",           "REST API — document processing & auth"),
    ("Database",    f"{API_BASE_URL}/db/status",        "PostgreSQL — relational store"),
    ("Neo4j",       None,                               "Graph DB — document & supplier relations"),
    ("Redis",       None,                               "Cache & Celery broker"),
    ("MinIO",       None,                               "Object storage for PDFs & images"),
    ("MeiliSearch", None,                               "Full-text search index"),
    ("Celery",      None,                               "Async worker for PDF processing"),
]

st.subheader("⚙️ Service Status")

svc_cols = st.columns(3)
for idx, (name, url, desc) in enumerate(SERVICES):
    if url:
        ok = _ping(url)
        dot_cls = "dot-ok" if ok else "dot-down"
        status_text = "Online" if ok else "Unreachable"
    else:
        dot_cls = "dot-unkn"
        status_text = "Configured"

    with svc_cols[idx % 3]:
        st.markdown(
            f'<div class="svc-card">'
            f'<div class="name"><span class="dot {dot_cls}"></span>{name}'
            f'<span style="font-size:11px;color:#64748b;font-weight:400;margin-left:8px">{status_text}</span>'
            f'</div>'
            f'<div class="desc">{desc}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.divider()

# ── Quick stats (from API if reachable) ──────────────────────────────────────────
st.subheader("\U0001f4ca Quick Stats")

stats = {"Total documents": None, "Pending review": None, "Archived": None, "Errors": None}

token = st.session_state.get("auth_token")
if token:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/documents/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": 1},
            timeout=4,
        )
        if resp.ok:
            data = resp.json()
            stats["Total documents"] = data.get("total_hits", "—")
    except Exception:
        pass

stat_cols = st.columns(4)
for i, (label, value) in enumerate(stats.items()):
    with stat_cols[i]:
        val_str = str(value) if value is not None else "—"
        st.markdown(
            f'<div class="stat-box">'
            f'<div class="val">{val_str}</div>'
            f'<div class="lbl">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

if not token:
    st.caption("\U0001f512 Log in via Upload Document or View Documents to see live stats.")

st.divider()

# ── Navigation shortcuts ──────────────────────────────────────────────────────────
st.subheader("\U0001f9ed Navigation")
nav_col1, nav_col2, nav_col3 = st.columns(3)

with nav_col1:
    st.markdown("""
    #### \U0001f4c4 Upload Document
    Upload and process new PDF documents.  
    Monitor processing status in real-time.
    """)

with nav_col2:
    st.markdown("""
    #### \U0001f4c2 View Documents
    Search, filter, and review processed documents.  
    Approve, archive, or return for correction.
    """)

with nav_col3:
    st.markdown("""
    #### \U0001f578 Graph Intelligence
    Visualise supplier and contract networks.  
    Detect influence patterns and anomalies.
    """)

st.divider()
st.caption("Alt_F4_Bureaucracy · Hackathon 2026")
