"""NexusVault — Main Dashboard"""
import os
import requests
import streamlit as st

st.set_page_config(page_title="NexusVault", page_icon="🏛️", layout="wide")

API_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")

st.markdown("""
<style>
@keyframes fadeInUp   { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
@keyframes slideInLeft{ from{opacity:0;transform:translateX(-20px)} to{opacity:1;transform:translateX(0)} }
@keyframes pulse-dot  { 0%,100%{box-shadow:0 0 0 0 rgba(34,197,94,.5)} 50%{box-shadow:0 0 0 6px rgba(34,197,94,0)} }
@keyframes shimmer    { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
@keyframes spin-slow  { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
@keyframes glow-blue  { 0%,100%{box-shadow:0 0 0 rgba(56,189,248,0)} 50%{box-shadow:0 0 24px rgba(56,189,248,.35)} }

/* Hero banner */
.hero-banner {
    background: linear-gradient(135deg,#0f172a 0%,#1e3a5f 40%,#0f172a 100%);
    background-size: 200% 200%;
    animation: shimmer 6s ease infinite, fadeInUp .6s ease;
    border: 1px solid #1e40af;
    border-radius: 20px;
    padding: 32px 36px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.hero-banner::before {
    content: "";
    position: absolute; inset: 0;
    background: radial-gradient(ellipse at 70% 50%, rgba(56,189,248,.08) 0%, transparent 70%);
    pointer-events: none;
}
.hero-title  { font-size:36px; font-weight:800; color:#f8fafc; margin:0; letter-spacing:-.5px; }
.hero-sub    { font-size:15px; color:#94a3b8; margin-top:6px; }
.hero-badge  {
    display:inline-block; background:rgba(56,189,248,.12);
    border:1px solid rgba(56,189,248,.3); border-radius:20px;
    padding:4px 14px; font-size:12px; color:#38bdf8;
    margin-top:12px; font-weight:600;
}

/* Service cards */
.svc-card {
    background: linear-gradient(135deg,#1e293b 0%,#0f172a 100%);
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 14px 18px;
    margin-bottom: 8px;
    transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
    animation: fadeInUp .4s ease both;
    cursor: default;
}
.svc-card:hover {
    transform: translateY(-3px);
    border-color: #3b82f6;
    box-shadow: 0 8px 24px rgba(59,130,246,.15);
}
.svc-name { font-size:14px; font-weight:700; color:#e2e8f0; }
.svc-desc { font-size:11px; color:#64748b; margin-top:3px; }
.dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:8px; flex-shrink:0; }
.dot-ok   { background:#22c55e; animation: pulse-dot 2s ease infinite; }
.dot-down { background:#ef4444; }
.dot-unkn { background:#f59e0b; }

/* Stat boxes */
.stat-box {
    background: linear-gradient(135deg,#0f172a 0%,#1e293b 100%);
    border: 1px solid #1e3a5f;
    border-radius: 14px;
    padding: 20px 16px;
    text-align: center;
    transition: transform .2s, box-shadow .2s;
    animation: glow-blue 4s ease infinite, fadeInUp .5s ease both;
}
.stat-box:hover { transform: translateY(-2px); box-shadow:0 8px 20px rgba(56,189,248,.1); }
.stat-val { font-size:36px; font-weight:800; color:#38bdf8; }
.stat-lbl { font-size:12px; color:#64748b; margin-top:4px; text-transform:uppercase; letter-spacing:.06em; }

/* Nav cards */
.nav-card {
    background: linear-gradient(135deg,#1e293b 0%,#0f172a 100%);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 20px 22px;
    height: 100%;
    transition: transform .2s, border-color .2s, box-shadow .2s;
    animation: slideInLeft .5s ease both;
}
.nav-card:hover {
    transform: translateY(-4px);
    border-color: #38bdf8;
    box-shadow: 0 12px 32px rgba(56,189,248,.12);
}
.nav-icon { font-size:28px; margin-bottom:8px; }
.nav-title{ font-size:16px; font-weight:700; color:#e2e8f0; margin-bottom:4px; }
.nav-desc { font-size:13px; color:#94a3b8; line-height:1.5; }

/* Streamlit overrides */
section[data-testid="stSidebar"] { background: #0f172a !important; }
section[data-testid="stSidebar"] * { color: #cbd5e1 !important; }
.stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: transform .15s, box-shadow .15s !important;
}
.stButton > button:hover { transform: translateY(-1px) !important; box-shadow: 0 4px 12px rgba(0,0,0,.3) !important; }
</style>
""", unsafe_allow_html=True)

# ── Hero ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
  <div class="hero-title">🏛️ NexusVault</div>
  <div class="hero-sub">Automated document intake, AI classification & archival platform</div>
  <span class="hero-badge">⚡ Hackathon 2026 · Counter Errorists</span>
</div>
""", unsafe_allow_html=True)

# ── Service health ────────────────────────────────────────────────────────────────
def _ping(url: str, t: float = 2.0) -> bool:
    try:
        return requests.get(url, timeout=t).status_code < 500
    except Exception:
        return False

SERVICES = [
    ("FastAPI",     f"{API_BASE_URL}/health",  "REST API · document processing & auth"),
    ("Database",    f"{API_BASE_URL}/db/status","PostgreSQL · relational store"),
    ("Neo4j",       None,                       "Graph DB · supplier & contract links"),
    ("Redis",       None,                       "Cache & Celery message broker"),
    ("MinIO",       None,                       "Object storage for PDFs & images"),
    ("MeiliSearch", None,                       "Full-text & faceted search index"),
    ("Celery",      None,                       "Async workers · PDF processing pipeline"),
]

st.markdown("### ⚙️ Service Status")
cols = st.columns(3)
for i, (name, url, desc) in enumerate(SERVICES):
    dot_cls    = ("dot-ok" if _ping(url) else "dot-down") if url else "dot-unkn"
    status_txt = ("Online" if _ping(url) else "Unreachable") if url else "Configured"
    delay = f"animation-delay:{i*0.07:.2f}s"
    with cols[i % 3]:
        st.markdown(f"""
        <div class="svc-card" style="{delay}">
          <div class="svc-name"><span class="dot {dot_cls}"></span>{name}
            <span style="font-size:11px;color:#475569;font-weight:400;margin-left:6px">{status_txt}</span>
          </div>
          <div class="svc-desc">{desc}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── Quick stats ───────────────────────────────────────────────────────────────────
st.markdown("### 📊 Quick Stats")
token = st.session_state.get("auth_token")
total_docs = "—"
if token:
    try:
        r = requests.get(f"{API_BASE_URL}/documents/search",
                         headers={"Authorization": f"Bearer {token}"},
                         params={"limit": 1}, timeout=4)
        if r.ok:
            total_docs = str(r.json().get("total_hits", "—"))
    except Exception:
        pass

stats = [("Total Documents", total_docs, "📄"),
         ("Pending Review",  "—",         "🕵️"),
         ("Archived",        "—",         "📦"),
         ("Processing",      "—",         "⚙️")]

sc = st.columns(4)
for i, (lbl, val, icon) in enumerate(stats):
    with sc[i]:
        st.markdown(f"""
        <div class="stat-box" style="animation-delay:{i*0.1:.1f}s">
          <div style="font-size:22px">{icon}</div>
          <div class="stat-val">{val}</div>
          <div class="stat-lbl">{lbl}</div>
        </div>""", unsafe_allow_html=True)

if not token:
    st.caption("🔑 Log in via Upload Document or View Documents to see live stats.")

st.markdown("---")

# ── Navigation ────────────────────────────────────────────────────────────────────
st.markdown("### 🧭 Navigation")
nc = st.columns(3)
nav_items = [
    ("📄", "Upload Document", "Upload new PDF documents and monitor AI processing in real-time.", "0s"),
    ("📂", "View Documents",  "Search, review, approve, archive or return documents.", "0.1s"),
    ("🕸️", "Graph Intelligence","Visualise supplier and contract networks. Detect influence anomalies.", "0.2s"),
]
for col, (icon, title, desc, delay) in zip(nc, nav_items):
    with col:
        st.markdown(f"""
        <div class="nav-card" style="animation-delay:{delay}">
          <div class="nav-icon">{icon}</div>
          <div class="nav-title">{title}</div>
          <div class="nav-desc">{desc}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.caption("Counter Errorists · Hackathon 2026 · Powered by FastAPI + Neo4j + Streamlit")
