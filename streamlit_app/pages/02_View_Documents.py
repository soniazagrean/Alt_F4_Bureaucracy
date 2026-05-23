"""
NV-025: Document View & Details Page

Features:
- Search & filter documents
- View full document details
- Display extracted invoice data
- Show document status timeline
- Related documents
"""

import os
import streamlit as st
import streamlit.components.v1 as components
import requests
import json
from datetime import datetime
import base64

# Page config
st.set_page_config(page_title="View Documents", page_icon="📄", layout="wide")

# Configuration
API_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")

st.markdown(
    """
    <style>
    @keyframes fadeInUp   { from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:translateY(0)} }
    @keyframes slideIn    { from{opacity:0;transform:translateX(-10px)} to{opacity:1;transform:translateX(0)} }
    @keyframes pulse-dot  { 0%,100%{box-shadow:0 0 0 0 rgba(34,197,94,.5)} 60%{box-shadow:0 0 0 8px rgba(34,197,94,0)} }
    @keyframes shimmer    { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
    @keyframes blink      { 0%,100%{opacity:1} 50%{opacity:.35} }

    /* Page hero */
    .page-hero {
        background: linear-gradient(135deg,#0f172a 0%,#1e3a5f 55%,#0f172a 100%);
        border:1px solid #1e40af; border-radius:18px;
        padding:22px 28px; margin-bottom:18px;
        animation: fadeInUp .5s ease;
    }
    .page-hero-title { font-size:24px; font-weight:800; color:#f1f5f9; margin:0; }
    .page-hero-sub   { font-size:13px; color:#94a3b8; margin-top:4px; }

    /* Document hero card (detail view) */
    .doc-hero {
        background: linear-gradient(135deg, #f7f4ed 0%, #eef6f2 100%);
        border: 1px solid #e4dccf;
        border-radius: 18px;
        padding: 18px 20px;
        margin-bottom: 14px;
        animation: fadeInUp .4s ease;
    }
    .doc-hero { color: #1f2937 !important; }
    .doc-hero * { color: #1f2937 !important; }

    /* Status pills */
    .status-pill {
        display:inline-block; padding:4px 12px; border-radius:999px;
        font-size:11px; font-weight:700; letter-spacing:.05em; text-transform:uppercase;
    }
    .status-pill.good { background:#d1fae5; color:#065f46; border:1px solid #6ee7b7; }
    .status-pill.warn { background:#fef3c7; color:#92400e; border:1px solid #fcd34d; animation:blink 2s ease infinite; }
    .status-pill.bad  { background:#fee2e2; color:#991b1b; border:1px solid #fca5a5; }
    .status-pill.info { background:#dbeafe; color:#1e40af; border:1px solid #93c5fd; animation:blink 1.5s ease infinite; }

    /* Search result cards */
    .doc-card {
        border-radius:12px; padding:14px 16px;
        background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);
        border:1px solid #334155; margin-bottom:6px;
        transition:transform .18s ease, border-color .18s ease, box-shadow .18s ease;
        animation: fadeInUp .35s ease both;
    }
    .doc-card:hover {
        transform:translateY(-2px);
        border-color:#3b82f6;
        box-shadow:0 6px 20px rgba(59,130,246,.15);
    }
    .doc-card-title  { font-size:15px; font-weight:700; color:#f1f5f9; }
    .doc-card-meta   { font-size:12px; color:#64748b; margin-top:3px; }
    .doc-card-badges { margin-top:6px; display:flex; flex-wrap:wrap; gap:5px; }
    .badge {
        display:inline-block; padding:2px 9px; border-radius:8px;
        font-size:11px; font-weight:600;
    }
    .badge-type     { background:#1e3a5f; color:#7dd3fc; border:1px solid #2563eb; }
    .badge-archived { background:#052e16; color:#4ade80; border:1px solid #16a34a; }
    .badge-review   { background:#422006; color:#fb923c; border:1px solid #c2410c; }
    .badge-returned { background:#450a0a; color:#f87171; border:1px solid #b91c1c; }
    .badge-default  { background:#1e293b; color:#94a3b8; border:1px solid #475569; }
    .badge-fraud    { background:#450a0a; color:#fca5a5; border:1px solid #b91c1c; }

    /* Meta chips */
    .meta-chip {
        display:inline-block; padding:2px 8px; border-radius:10px;
        border:1px solid #e6e1d5; background:#fffdf7;
        font-size:12px; color:#5a5447; margin-right:6px; margin-top:6px;
    }

    /* ANAF cards */
    .anaf-card { border-radius:10px; padding:12px 15px; margin:8px 0 12px; border-left:5px solid; }
    .anaf-card.active   { background:#d9f5e5; border-color:#22c55e; color:#064e2b; }
    .anaf-card.inactive { background:#ffe1df; border-color:#ef4444; color:#7f1d1d; }
    .anaf-card.notfound { background:#fef9c3; border-color:#eab308; color:#713f12; }
    .anaf-card.unavail  { background:#f3f4f6; border-color:#9ca3af; color:#4b5563; }
    .anaf-title { font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.07em; margin-bottom:5px; opacity:.75; }
    .anaf-main  { font-size:14px; font-weight:700; margin-bottom:4px; }
    .anaf-field { font-size:12px; margin:2px 0; opacity:.85; }

    /* Result search row accent */
    .result-risk   { border-left:3px solid #ef4444; padding-left:10px; }
    .result-review { border-left:3px solid #f59e0b; padding-left:10px; }
    .result-ok     { border-left:3px solid #22c55e; padding-left:10px; }

    /* Streamlit global tweaks */
    section[data-testid="stSidebar"] { background:#0f172a !important; }
    section[data-testid="stSidebar"] * { color:#cbd5e1 !important; }
    .stButton > button {
        border-radius:10px !important; font-weight:600 !important;
        transition:transform .15s, box-shadow .15s !important;
    }
    .stButton > button:hover { transform:translateY(-1px) !important; box-shadow:0 4px 12px rgba(0,0,0,.35) !important; }
    .stTabs [data-baseweb="tab"] { font-weight:600 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("""
<div class="page-hero">
  <div class="page-hero-title">\U0001f4c2 View Documents</div>
  <div class="page-hero-sub">Search, filter, review and archive processed documents. Open a document for the full detail view.</div>
</div>
""", unsafe_allow_html=True)

# Helper functions

def _format_dosar_label(dosar: dict) -> str:
    code = dosar.get("nomenclator_code") or dosar.get("nomenclator_name") or "Unknown"
    title = dosar.get("title") or "Untitled"
    if dosar.get("is_suggestion"):
        return f"{code} / {title} (Create suggested folder)"

    number = dosar.get("dosar_number") or "N/A"
    count = dosar.get("documents_count", 0)
    return f"{code} / {number} · {title} ({count} docs)"


def _dosar_matches_search(dosar: dict, query: str) -> bool:
    if not query:
        return True
    text = " ".join(
        str(dosar.get(key, ""))
        for key in ["dosar_number", "title", "description", "nomenclator_code", "nomenclator_name"]
        if dosar.get(key)
    )
    return query.lower() in text.lower()


def _render_archive_node(node: dict, search_query: str, selected_dosar_id: str, level=0):
    indent = "&nbsp;" * (level * 8)
    label = f"📁 {node.get('code', 'N/A')} — {node.get('name', 'Unnamed Category')}"
    
    st.markdown(f"{indent}**{label}**", unsafe_allow_html=True)
    
    dosare = [dosar for dosar in node.get("dosare", []) if _dosar_matches_search(dosar, search_query)]
    if dosare:
        for dosar in dosare:
            dosar_label = _format_dosar_label(dosar)
            cols = st.columns([0.1, 4.9, 1])
            with cols[1]:
                st.markdown(f"{indent}&nbsp;&nbsp;&nbsp;&nbsp;📄 {dosar_label}", unsafe_allow_html=True)
            if cols[2].button("Open folder", key=f"open_dosar_{dosar['id']}"):
                st.session_state.selected_dosar_id = str(dosar["id"])
                st.session_state.archive_dosar_details = None
                st.rerun()

    for child in node.get("children", []):
        if _node_has_matching_content(child, search_query):
            _render_archive_node(child, search_query, selected_dosar_id, level + 1)


def _collect_dosare(node: dict) -> list[dict]:
    dosare = list(node.get("dosare", []) or [])
    for child in node.get("children", []) or []:
        dosare.extend(_collect_dosare(child))
    return dosare


def _flatten_dosare_from_tree(roots: list[dict]) -> list[dict]:
    all_dosare: list[dict] = []
    for root in roots or []:
        all_dosare.extend(_collect_dosare(root))
    return all_dosare


def _node_has_matching_content(node: dict, query: str) -> bool:
    if not query:
        return True

    text = " ".join(
        str(node.get(key, ""))
        for key in ["code", "name", "description"]
        if node.get(key)
    )
    if query.lower() in text.lower():
        return True

    for dosar in node.get("dosare", []):
        if _dosar_matches_search(dosar, query):
            return True

    return any(_node_has_matching_content(child, query) for child in node.get("children", []))


def _filter_documents(documents: list[dict], year: str, supplier: str, doc_type: str) -> list[dict]:
    filtered = []
    for doc in documents:
        if year != "All":
            doc_date = doc.get("data") or doc.get("document_date") or doc.get("created_at")
            if doc_date:
                try:
                    if str(datetime.fromisoformat(doc_date).year) != str(year):
                        continue
                except Exception:
                    continue
        if supplier and supplier.lower() not in str(doc.get("title", "")).lower() and supplier.lower() not in str(doc.get("description", "")).lower() and supplier.lower() not in str(doc.get("document_number", "")).lower():
            # also check extracted supplier fields when available
            extracted = doc.get("extracted_data_map") or {}
            if supplier.lower() not in str(extracted.get("furnizor", "")).lower():
                continue
        if doc_type != "All" and str(doc.get("document_type", "")).upper() != doc_type:
            continue
        filtered.append(doc)
    return filtered


def _format_relation_label(relation_type: str) -> str:
    labels = {
        "same_dosar": "Same folder",
        "same_furnizor": "Same supplier",
    }
    return labels.get(relation_type, relation_type.replace("_", " ").title())

# ============================================================================
# SIDEBAR - Authentication & Filters
# ============================================================================

st.sidebar.markdown("### 🔑 Authentication")

if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
    st.session_state.username = None

_view_err = st.session_state.get("_login_error", "")
_view_locked = "locked" in _view_err.lower()

if st.session_state.auth_token:
    st.sidebar.success(f"✅ **{st.session_state.username}**")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.auth_token = None
        st.session_state.username = None
        st.session_state.pop("_login_error", None)
        st.rerun()
else:
    # --- lockout / error banner shown ABOVE the form ---
    if _view_locked:
        st.sidebar.warning(_view_err)
        st.sidebar.caption(
            "⏳ Your account is temporarily locked. "
            "Wait for the lockout period to expire, then try again."
        )
    elif _view_err:
        st.sidebar.error(_view_err)

    # Login form — disabled while account is locked
    with st.sidebar.form("login_form_view"):
        username = st.text_input("Username", placeholder="admin", disabled=_view_locked)
        password = st.text_input("Password", type="password", disabled=_view_locked)
        _btn_label = "🔒 Account Locked" if _view_locked else "Login"
        submitted = st.form_submit_button(
            _btn_label, use_container_width=True, disabled=_view_locked,
        )

    if submitted and not _view_locked:
        st.session_state.pop("_login_error", None)
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                st.session_state.auth_token = data.get("access_token")
                st.session_state.username = username
                st.rerun()
            elif response.status_code == 429:
                st.session_state["_login_error"] = f"🔒 {response.json().get('detail', 'Account locked.')}"
                st.rerun()
            else:
                st.session_state["_login_error"] = response.json().get("detail", "Login failed.")
                st.rerun()
        except Exception as e:
            st.session_state["_login_error"] = f"Connection error: {e}"
            st.rerun()

# ============================================================================
# MAIN CONTENT
# ============================================================================

if st.session_state.auth_token:
    headers = {
        "Authorization": f"Bearer {st.session_state.auth_token}"
    }
    
    # Initialize session state for search results and archive browsing
    if "search_results" not in st.session_state:
        st.session_state.search_results = None
    if "search_autoloaded" not in st.session_state:
        st.session_state.search_autoloaded = False
    if "selected_doc_id" not in st.session_state:
        st.session_state.selected_doc_id = None
    if "archive_tree" not in st.session_state:
        st.session_state.archive_tree = None
    if "selected_dosar_id" not in st.session_state:
        st.session_state.selected_dosar_id = None
    if "archive_dosar_details" not in st.session_state:
        st.session_state.archive_dosar_details = None
    if "delete_confirm_doc_id" not in st.session_state:
        st.session_state.delete_confirm_doc_id = None
    
    st.divider()
    
    # Auto-load recent documents for first visit
    if not st.session_state.search_results and not st.session_state.search_autoloaded:
        try:
            recent_params = {
                "limit": 20,
                "offset": 0,
            }
            recent_response = requests.get(
                f"{API_BASE_URL}/documents/search",
                headers=headers,
                params=recent_params,
                timeout=10,
            )
            if recent_response.status_code == 200:
                st.session_state.search_results = recent_response.json()
        except Exception:
            pass
        finally:
            st.session_state.search_autoloaded = True

    # Show detail view or search based on state
    if st.session_state.selected_doc_id:
        # DETAIL VIEW
        doc_id = st.session_state.selected_doc_id
        
        if st.button("← Back to Search"):
            st.session_state.selected_doc_id = None
            st.rerun()
        
        st.markdown("---")
        
        try:
            with st.spinner(f"Loading document..."):
                response = requests.get(
                    f"{API_BASE_URL}/documents/{doc_id}",
                    headers=headers,
                    timeout=10
                )
            
            if response.status_code in [200, 202]:
                doc = response.json()
                
                doc_id = doc.get("id")
                doc_title = doc.get("title", "Document")
                status_raw = doc.get("status", "unknown")
                status_upper = str(status_raw).upper()

                status_class = "warn"
                if status_upper in {"ARCHIVED", "APPROVED", "VALIDATED"}:
                    status_class = "good"
                elif status_upper in {"ERROR", "REJECTED", "RETURNED"}:
                    status_class = "bad"

                extracted = doc.get("extracted_data_map") or doc.get("extracted_data") or {}
                if isinstance(extracted, list):
                    extracted = {
                        str(item.get("field_name")): item.get("field_value")
                        for item in extracted
                        if isinstance(item, dict) and item.get("field_name")
                    }
                classification = doc.get("classification") or {}

                st.markdown(
                    f"""
                    <div class="doc-hero">
                        <div style="font-size: 20px; font-weight: 700; color: #111827;">{doc_title}</div>
                        <div style="margin-top: 6px;">
                            <span class="status-pill {status_class}">{status_upper}</span>
                            <span style="margin-left: 10px; color: #4b5563;">Created: {doc.get('created_at', 'N/A')}</span>
                        </div>
                        <div style="margin-top: 8px; color: #4b5563;">
                            Type: {doc.get('document_type', 'N/A')} · Document ID: {doc_id if doc_id is not None else 'N/A'}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # ── ANAF banner – full width, visible immediately ──────────
                _anaf = doc.get("anaf_validation") or {}
                _extracted_map = doc.get("extracted_data_map") or {}
                # Schema stores CUI uppercase (Pydantic model); fall back to lowercase
                _cui_val = (_extracted_map.get("CUI") or _extracted_map.get("cui")
                            or _extracted_map.get("COD_FISCAL") or _extracted_map.get("cod_fiscal"))
                _furnizor_doc = (_extracted_map.get("furnizor") or _extracted_map.get("Furnizor") or "").strip()
                _anaf_name = (_anaf.get("company_name") or "").strip()
                _anaf_addr = (_anaf.get("address") or "").strip()
                _anaf_reg  = (_anaf.get("registration_date") or "").strip()

                if _cui_val or _anaf.get("found") is not None:
                    from difflib import SequenceMatcher as _SM

                    if _anaf.get("error") and not _anaf.get("found"):
                        _cls = "unavail"; _icon = "⚠️"; _status_lbl = "ANAF UNAVAILABLE"
                        _main = f"Service error: {_anaf.get('error','')}"
                    elif not _anaf.get("found"):
                        _cls = "notfound"; _icon = "❓"; _status_lbl = "NOT IN ANAF REGISTRY"
                        _main = f"CUI {_cui_val} returned no results"
                    elif not _anaf.get("is_active"):
                        _cls = "inactive"; _icon = "🚨"; _status_lbl = "COMPANY INACTIVE"
                        _main = _anaf_name or "Unknown company"
                    else:
                        _cls = "active"; _icon = "✅"; _status_lbl = "ACTIVE"
                        _main = _anaf_name or "—"

                    _cui_html  = f'<span class="anaf-field">&nbsp;·&nbsp;🔢 CUI: <b>{_cui_val}</b></span>' if _cui_val else ""
                    _addr_html = f'<span class="anaf-field">&nbsp;·&nbsp;📍 {_anaf_addr}</span>' if _anaf_addr else ""
                    _reg_html  = f'<span class="anaf-field">&nbsp;·&nbsp;📅 since {_anaf_reg}</span>' if _anaf_reg else ""

                    st.markdown(
                        f"""
                        <div class="anaf-card {_cls}" style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;">
                            <span class="anaf-title" style="margin:0;margin-right:8px;">🏛️ ANAF · {_status_lbl}</span>
                            <span class="anaf-main" style="margin:0;">{_icon} {_main}</span>
                            {_cui_html}{_addr_html}{_reg_html}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Name-mismatch warning
                    if _cls == "active" and _furnizor_doc and _anaf_name:
                        _sim = _SM(None, _furnizor_doc.upper(), _anaf_name.upper()).ratio()
                        if _sim < 0.6:
                            st.warning(
                                f"⚠️ **Name mismatch** — document: `{_furnizor_doc}` "
                                f"vs ANAF: `{_anaf_name}` ({int(_sim * 100)}% match)"
                            )

                    # Sidebar summary
                    st.sidebar.markdown("---")
                    st.sidebar.markdown("### 🏛️ ANAF Registry")
                    if _cls == "active":
                        st.sidebar.success(f"✅ Active  \n{_anaf_name[:35] or '—'}")
                    elif _cls == "inactive":
                        st.sidebar.error(f"🚨 INACTIVE  \n{_anaf_name[:35] or '—'}")
                    elif _cls == "notfound":
                        st.sidebar.warning("❓ Not found in registry")
                    else:
                        st.sidebar.caption("⚠️ ANAF service unavailable")
                    if _cui_val:
                        st.sidebar.caption(f"CUI: {_cui_val}")
                    if _anaf_addr:
                        st.sidebar.caption(f"📍 {_anaf_addr[:60]}")
                # ────────────────────────────────────────────────────────────

                st.divider()

                preview_col, meta_col = st.columns([1.1, 1.9])

                with preview_col:
                    st.markdown("### Quick Preview")
                    # Always use the FastAPI page-image proxy rather than a direct
                    # MinIO presigned URL. The proxy fetches via the internal Docker
                    # hostname (minio:9000) and streams PNG bytes — no browser-to-MinIO
                    # direct connection needed, which fixes the "random text" iframe issue.
                    _pages = doc.get("pages", [])
                    _preview_shown = False

                    _IN_PROGRESS_STATUSES = {
                        "pending", "uploaded", "processing", "classified", "extracted"
                    }
                    _preview_err = None

                    if doc_id and _pages:
                        _pages_with_img = sorted(
                            [p for p in _pages if p.get("image_path")],
                            key=lambda p: p.get("page_number", 99),
                        )
                        if _pages_with_img:
                            _pnum = _pages_with_img[0].get("page_number", 0)
                            try:
                                _img_resp = requests.get(
                                    f"{API_BASE_URL}/documents/{doc_id}/page-image/{_pnum}",
                                    headers=headers,
                                    timeout=10,
                                )
                                if _img_resp.status_code == 200:
                                    st.image(
                                        _img_resp.content,
                                        use_column_width=True,
                                        caption=f"Page {_pnum + 1} preview",
                                    )
                                    _preview_shown = True
                                else:
                                    _preview_err = f"Image endpoint returned {_img_resp.status_code}"
                            except Exception as _pe:
                                _preview_err = str(_pe)

                    if not _preview_shown:
                        _doc_status = (doc.get("status") or "").lower()
                        if _doc_status in _IN_PROGRESS_STATUSES:
                            st.info(f"⏳ Document is still being processed ({_doc_status.upper()}) — preview will appear once ready.")
                        elif _preview_err:
                            st.error(f"Preview error: {_preview_err}")
                            if st.button("⚙️ Reprocess Document", key=f"reprocess_{doc_id}"):
                                _rp = requests.post(
                                    f"{API_BASE_URL}/documents/{doc_id}/process",
                                    headers=headers, timeout=15,
                                )
                                if _rp.status_code in (200, 202):
                                    st.success("✅ Reprocessing started! Refresh in ~30 seconds.")
                                else:
                                    st.error(f"Failed ({_rp.status_code})")
                        else:
                            st.warning("🔄 No preview available. This document may need to be reprocessed.")
                            if st.button("⚙️ Reprocess Document", key=f"reprocess_{doc_id}"):
                                _rp = requests.post(
                                    f"{API_BASE_URL}/documents/{doc_id}/process",
                                    headers=headers, timeout=15,
                                )
                                if _rp.status_code in (200, 202):
                                    st.success("✅ Reprocessing started! Refresh in ~30 seconds.")
                                else:
                                    st.error(f"Failed ({_rp.status_code})")

                    # Download button for the original PDF
                    if doc_id:
                        try:
                            _pdf_dl = requests.get(
                                f"{API_BASE_URL}/documents/{doc_id}/download",
                                headers=headers,
                                timeout=30,
                            )
                            if _pdf_dl.status_code == 200:
                                st.download_button(
                                    label="⬇️ Download original PDF",
                                    data=_pdf_dl.content,
                                    file_name=f"{doc.get('title', 'document')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                )
                        except Exception:
                            pass

                with meta_col:
                    st.markdown("### Metadata & Workflow")
                    doc_type_value = str(doc.get("document_type", "")).lower()
                    extracted_map = doc.get("extracted_data_map") or {}

                    if doc_type_value == "invoice":
                        number_label = "Invoice Number (extracted)"
                        number_value = doc.get("invoice_number") or extracted_map.get("nr_factura") or "N/A"
                    elif doc_type_value == "contract":
                        number_label = "Contract Number (extracted)"
                        number_value = (
                            extracted_map.get("contract_number")
                            or extracted_map.get("nr_contract")
                            or extracted_map.get("numar_contract")
                            or "N/A"
                        )
                    elif doc_type_value == "report":
                        number_label = "Report Number (extracted)"
                        number_value = (
                            extracted_map.get("report_number")
                            or extracted_map.get("nr_raport")
                            or extracted_map.get("numar_raport")
                            or "N/A"
                        )
                    else:
                        number_label = "Document Number (extracted)"
                        number_value = (
                            extracted_map.get("document_number")
                            or extracted_map.get("numar_document")
                            or "N/A"
                        )

                    meta_left, meta_right = st.columns(2)
                    with meta_left:
                        st.metric(number_label, number_value)
                        st.metric("Document Number (internal)", doc.get("document_number", "N/A"))
                        st.metric("Document Date", doc.get("document_date", "N/A"))

                    with meta_right:
                        amount = doc.get("amount", "N/A")
                        currency = doc.get("currency", "")
                        st.metric("Amount", f"{amount} {currency}".strip())
                        st.metric("Document Type", doc.get("document_type", "N/A"))

                    st.markdown(
                        f"""
                        <span class="meta-chip">Status: {status_upper}</span>
                        <span class="meta-chip">Pages: {doc.get('page_count', 'N/A')}</span>
                        <span class="meta-chip">Size: {doc.get('file_size', 'N/A')} bytes</span>
                        """,
                        unsafe_allow_html=True,
                    )

                    st.markdown("---")
                    st.markdown("#### 🔍 Forensics & Fraud Analysis")
                    
                    f_score = doc.get("fraud_score", 0.0) or 0.0
                    st.progress(f_score, text=f"Overall Fraud Score: {f_score*100:.1f}%")

                    # ── ANAF Supplier Validation card ─────────────────────
                    _anaf = doc.get("anaf_validation") or {}
                    _extracted_map = doc.get("extracted_data_map") or {}
                    _cui_val = _extracted_map.get("cui") or _extracted_map.get("cod_fiscal")
                    _furnizor_doc = (_extracted_map.get("furnizor") or "").strip()
                    _anaf_name = (_anaf.get("company_name") or "").strip()
                    _anaf_addr = (_anaf.get("address") or "").strip()
                    _anaf_reg  = (_anaf.get("registration_date") or "").strip()

                    if _cui_val or _anaf:
                        from difflib import SequenceMatcher as _SM

                        if _anaf.get("error") and not _anaf.get("found"):
                            _cls = "unavail"; _icon = "⚠️"; _status_lbl = "ANAF UNAVAILABLE"
                            _main = f"Service error: {_anaf.get('error','')}"
                        elif not _anaf.get("found"):
                            _cls = "notfound"; _icon = "❓"; _status_lbl = "NOT IN ANAF REGISTRY"
                            _main = f"CUI {_cui_val} returned no results"
                        elif not _anaf.get("is_active"):
                            _cls = "inactive"; _icon = "🚨"; _status_lbl = "COMPANY INACTIVE"
                            _main = _anaf_name or "Unknown company"
                        else:
                            _cls = "active"; _icon = "✅"; _status_lbl = "ACTIVE"
                            _main = _anaf_name or "—"

                        _cui_html  = f'<div class="anaf-field">🔢 CUI: <b>{_cui_val}</b></div>' if _cui_val else ""
                        _addr_html = f'<div class="anaf-field">📍 {_anaf_addr}</div>' if _anaf_addr else ""
                        _reg_html  = f'<div class="anaf-field">📅 Active since: {_anaf_reg}</div>' if _anaf_reg else ""

                        st.markdown(
                            f"""
                            <div class="anaf-card {_cls}">
                                <div class="anaf-title">🏛️ ANAF Romania · {_status_lbl}</div>
                                <div class="anaf-main">{_icon} {_main}</div>
                                {_cui_html}{_addr_html}{_reg_html}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        # Name-mismatch warning (only when company is active)
                        if _cls == "active" and _furnizor_doc and _anaf_name:
                            _sim = _SM(None, _furnizor_doc.upper(), _anaf_name.upper()).ratio()
                            if _sim < 0.6:
                                st.warning(
                                    f"⚠️ **Name mismatch** — document: `{_furnizor_doc}` "
                                    f"vs ANAF: `{_anaf_name}` ({int(_sim * 100)}% match)"
                                )

                        # ── Sidebar ANAF summary (visible while this doc is open) ──
                        st.sidebar.markdown("---")
                        st.sidebar.markdown("### 🏛️ ANAF Registry")
                        if _cls == "active":
                            st.sidebar.success(f"✅ Active  \n{_anaf_name[:35] or '—'}")
                        elif _cls == "inactive":
                            st.sidebar.error(f"🚨 INACTIVE  \n{_anaf_name[:35] or '—'}")
                        elif _cls == "notfound":
                            st.sidebar.warning("❓ Not found in registry")
                        else:
                            st.sidebar.caption("⚠️ ANAF service unavailable")
                        if _cui_val:
                            st.sidebar.caption(f"CUI: {_cui_val}")
                        if _anaf_addr:
                            st.sidebar.caption(f"📍 {_anaf_addr[:60]}")
                    # ──────────────────────────────────────────────────────

                    try:
                        alert_resp = requests.get(
                            f"{API_BASE_URL}/documents/{doc_id}/alerts",
                            headers=headers,
                            timeout=10,
                        )
                        if alert_resp.status_code == 200:
                            alerts = alert_resp.json()
                            if alerts:
                                for alert in alerts:
                                    # API returns 'type'/'risk'; also accept legacy key names
                                    _atype = alert.get("type") or alert.get("anomaly_type") or "unknown"
                                    _arisk = (alert.get("risk") or alert.get("risk_level") or "").upper()
                                    _ascore = float(alert.get("score") or alert.get("fraud_score") or 0.0)
                                    with st.expander(
                                        f"⚠️ {_atype.replace('_', ' ').title()} · risk: {_arisk}",
                                        expanded=True,
                                    ):
                                        st.write(f"**Description:** {alert.get('description', '—')}")
                                        st.write(f"**Risk Level:** {_arisk}")
                                        st.write(f"**Fraud Score:** {_ascore*100:.1f}%")
                                        if alert.get("detected_at"):
                                            st.caption(f"Detected: {alert['detected_at']}")
                            else:
                                st.success("✅ No suspicious anomalies detected.")
                        else:
                            st.caption(f"Alerts unavailable ({alert_resp.status_code})")
                    except Exception as _ae:
                        st.caption(f"Alerts error: {_ae}")

                    if doc_id:
                        try:
                            pdf_response = requests.get(
                                f"{API_BASE_URL}/documents/{doc_id}/download",
                                headers=headers,
                                timeout=30
                            )
                            if pdf_response.status_code == 200:
                                st.download_button(
                                    label="Download PDF",
                                    data=pdf_response.content,
                                    file_name=f"{doc.get('title', 'document')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                            else:
                                st.warning(f"PDF not available ({pdf_response.status_code})")
                        except Exception as e:
                            st.warning(f"Could not download PDF: {str(e)}")

                    # Dangerous action: delete document
                    st.markdown("#### ⚠️ Delete Document")
                    if st.button("🗑️ Delete Document", key=f"del_init_{doc_id}"):
                        st.session_state.delete_confirm_doc_id = str(doc_id)
                        st.rerun()

                    if st.session_state.get("delete_confirm_doc_id") == str(doc_id):
                        st.warning("Are you sure? This will permanently delete the document and its related data.")
                        confirm_col1, confirm_col2 = st.columns([1, 1])
                        with confirm_col1:
                            if st.button("Confirm Delete", key=f"del_confirm_{doc_id}"):
                                try:
                                    del_resp = requests.delete(
                                        f"{API_BASE_URL}/documents/{doc_id}",
                                        headers=headers,
                                        timeout=20,
                                    )
                                    if del_resp.status_code in [200, 202, 204]:
                                        st.success("Document deleted.")
                                        st.session_state.selected_doc_id = None
                                        st.session_state.search_results = None
                                        st.session_state.delete_confirm_doc_id = None
                                        st.rerun()
                                    else:
                                        st.error(f"Delete failed: {del_resp.status_code} {del_resp.text[:200]}")
                                except Exception as e:
                                    st.error(f"Error deleting document: {str(e)}")
                        with confirm_col2:
                            if st.button("Cancel", key=f"del_cancel_{doc_id}"):
                                st.session_state.delete_confirm_doc_id = None
                                st.rerun()

                    st.markdown("#### Suggested Archive Path")
                    archive_hint = None
                    suggested_dosar = None
                    suggested_code = None
                    dosar_id = doc.get("dosar_id")
                    if dosar_id:
                        try:
                            dosar_response = requests.get(
                                f"{API_BASE_URL}/archive/dosar/{dosar_id}",
                                headers=headers,
                                timeout=10,
                            )
                            if dosar_response.status_code == 200:
                                dosar_data = dosar_response.json()
                                nomenclator_code = dosar_data.get("nomenclator_code")
                                dosar_number = dosar_data.get("dosar_number")
                                dosar_title = dosar_data.get("title")
                                archive_hint = " / ".join(
                                    [
                                        part
                                        for part in [nomenclator_code, dosar_number, dosar_title]
                                        if part
                                    ]
                                )
                        except Exception:
                            archive_hint = None

                    if not archive_hint:
                        nomenclator_suggestion = doc.get("nomenclator_suggestion") or {}
                        suggested_dosar = (
                            nomenclator_suggestion.get("dosar_propus")
                            or nomenclator_suggestion.get("dosar")
                            or extracted.get("dosar_propus")
                            or extracted.get("dosar")
                        )
                        suggested_code = (
                            nomenclator_suggestion.get("cod")
                            or nomenclator_suggestion.get("cod_nomenclator")
                            or (doc.get("nomenclator") or {}).get("code")
                        )
                        if suggested_dosar or suggested_code:
                            archive_hint = " / ".join(
                                [part for part in [suggested_code, suggested_dosar] if part]
                            )
                    else:
                        nomenclator_suggestion = doc.get("nomenclator_suggestion") or {}
                        suggested_dosar = (
                            nomenclator_suggestion.get("dosar_propus")
                            or nomenclator_suggestion.get("dosar")
                            or extracted.get("dosar_propus")
                            or extracted.get("dosar")
                        )
                        suggested_code = (
                            nomenclator_suggestion.get("cod")
                            or nomenclator_suggestion.get("cod_nomenclator")
                            or (doc.get("nomenclator") or {}).get("code")
                        )

                    if archive_hint:
                        st.code(archive_hint, language=None)
                    else:
                        st.info("No archive suggestion available yet.")

                    st.markdown("#### Operator Workflow")
                    nomenclator_confirmed = doc.get("nomenclator_confirmed", False)
                    if status_upper == "REVIEW":
                        if "archive_tree_cache" not in st.session_state:
                            st.session_state.archive_tree_cache = None

                        st.markdown("**Step 1: Confirm nomenclator/folder**")
                        refresh_archive = st.button(
                            "Refresh archive list",
                            use_container_width=True,
                            key=f"refresh_archive_{doc_id}",
                        )
                        if refresh_archive or st.session_state.archive_tree_cache is None:
                            try:
                                tree_response = requests.get(
                                    f"{API_BASE_URL}/archive/tree",
                                    headers=headers,
                                    timeout=10,
                                )
                                if tree_response.status_code == 200:
                                    st.session_state.archive_tree_cache = tree_response.json()
                                else:
                                    st.warning("Archive tree could not be loaded.")
                                    st.session_state.archive_tree_cache = None
                            except Exception:
                                st.session_state.archive_tree_cache = None

                        dosare_options = []
                        archive_tree = st.session_state.archive_tree_cache or {}
                        roots = archive_tree.get("roots", [])
                        if roots:
                            dosare_options = _flatten_dosare_from_tree(roots)

                        if not any(
                            d.get("nomenclator_code") == suggested_code and d.get("title") == suggested_dosar
                            for d in dosare_options
                        ) and (suggested_code or suggested_dosar):
                            dosare_options.append({
                                "id": None,
                                "dosar_number": None,
                                "title": suggested_dosar or "Suggested Folder",
                                "description": "Create folder from suggested nomenclator",
                                "nomenclator_id": None,
                                "nomenclator_code": suggested_code,
                                "nomenclator_name": suggested_code,
                                "documents_count": 0,
                                "is_suggestion": True,
                            })

                        selected_dosar = None
                        if dosare_options:
                            labels = [_format_dosar_label(dosar) for dosar in dosare_options]
                            default_index = 0
                            current_dosar_id = doc.get("dosar_id")
                            if current_dosar_id:
                                for idx, dosar in enumerate(dosare_options):
                                    if str(dosar.get("id")) == str(current_dosar_id):
                                        default_index = idx
                                        break
                            selected_label = st.selectbox(
                                "Suggested / Selected Folder",
                                labels,
                                index=default_index,
                                key=f"dosar_select_{doc_id}",
                            )
                            for dosar, label in zip(dosare_options, labels):
                                if label == selected_label:
                                    selected_dosar = dosar
                                    break
                        else:
                            st.info("No folders available. Create one in Archive Browser.")

                        if not nomenclator_confirmed:
                            confirm_payload = {"confirmed": True}
                            if selected_dosar:
                                if selected_dosar.get("is_suggestion"):
                                    confirm_payload["create_dosar_from_suggestion"] = True
                                    confirm_payload["suggested_nomenclator_code"] = selected_dosar.get("nomenclator_code")
                                    confirm_payload["suggested_dosar_title"] = selected_dosar.get("title")
                                else:
                                    confirm_payload["dosar_id"] = selected_dosar.get("id")
                                    confirm_payload["nomenclator_id"] = selected_dosar.get("nomenclator_id")
                            elif doc.get("dosar_id") and doc.get("nomenclator_id"):
                                confirm_payload["dosar_id"] = doc.get("dosar_id")
                                confirm_payload["nomenclator_id"] = doc.get("nomenclator_id")

                            confirm_disabled = not (
                                confirm_payload.get("dosar_id") and confirm_payload.get("nomenclator_id")
                            ) and not confirm_payload.get("create_dosar_from_suggestion")

                            if st.button(
                                "✓ Confirm Nomenclator",
                                use_container_width=True,
                                type="primary",
                                disabled=confirm_disabled,
                            ):
                                try:
                                    confirm_response = requests.post(
                                        f"{API_BASE_URL}/documents/{doc_id}/confirm-nomenclator",
                                        headers=headers,
                                        json=confirm_payload,
                                        timeout=10,
                                    )
                                    if confirm_response.status_code in [200, 202]:
                                        st.success("Nomenclator confirmed!")
                                        st.rerun()
                                    else:
                                        st.error(f"Confirmation failed: {confirm_response.status_code}")
                                except Exception as e:
                                    st.error(f"Error: {str(e)}")
                            if confirm_disabled:
                                st.caption("Select a folder to confirm.")
                        else:
                            st.success("✅ Nomenclator confirmed.")

                        st.markdown("---")
                        st.markdown("**Step 2: Approve / Return**")
                        if st.button(
                            "✅ Approve Document",
                            use_container_width=True,
                            type="primary",
                            disabled=not nomenclator_confirmed,
                        ):
                            try:
                                approve_response = requests.post(
                                    f"{API_BASE_URL}/documents/{doc_id}/approve",
                                    headers=headers,
                                    timeout=10,
                                )
                                if approve_response.status_code in [200, 202]:
                                    st.success("Document approved!")
                                    st.rerun()
                                else:
                                    st.error(f"Approve failed: {approve_response.status_code}")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")

                        correction_reason = st.text_area(
                            "Correction Reason (optional)",
                            key=f"correction_reason_{doc_id}",
                            height=90,
                            placeholder="e.g., missing data or incorrect amount.",
                        )

                        if st.button("↩️ Send to Correction", use_container_width=True):
                            try:
                                correction_response = requests.post(
                                    f"{API_BASE_URL}/documents/{doc_id}/request-manual-correction",
                                    headers=headers,
                                    json={"reason": correction_reason or None},
                                    timeout=10,
                                )
                                if correction_response.status_code in [200, 202]:
                                    st.success("Document sent back for correction!")
                                    st.rerun()
                                else:
                                    st.error(f"Correction failed: {correction_response.status_code}")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")

                    elif status_upper == "APPROVED":
                        if st.button("📦 Archive Document", use_container_width=True, type="primary"):
                            try:
                                archive_response = requests.post(
                                    f"{API_BASE_URL}/documents/{doc_id}/archive",
                                    headers=headers,
                                    timeout=10,
                                )
                                if archive_response.status_code in [200, 202]:
                                    st.success("Document archived!")
                                    st.rerun()
                                else:
                                    st.error(f"Archive failed: {archive_response.status_code}")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")

                    elif status_upper == "ARCHIVED":
                        st.success("✅ Document archived.")
                        if not nomenclator_confirmed:
                            st.info("Nomenclator is not confirmed.")
                        else:
                            st.success("✅ Nomenclator confirmed.")

                    elif status_upper == "RETURNED":
                        st.info(
                            "Document returned for correction. Edit the document details below and submit. "
                            "If the submission changes any field, status will return to REVIEW."
                        )

                        with st.form(key=f"returned_document_form_{doc_id}"):
                            st.subheader("Edit Returned Document")
                            title_input = st.text_input(
                                "Title",
                                value=doc.get("title", "") or "",
                                key=f"returned_title_{doc_id}",
                            )
                            description_input = st.text_area(
                                "Description",
                                value=doc.get("description", "") or "",
                                key=f"returned_description_{doc_id}",
                                height=120,
                            )
                            document_number_input = st.text_input(
                                "Document Number",
                                value=doc.get("document_number", "") or "",
                                key=f"returned_document_number_{doc_id}",
                            )
                            amount_value = doc.get("amount")
                            amount_input = st.number_input(
                                "Amount",
                                value=float(amount_value) if amount_value is not None else 0.0,
                                min_value=0.0,
                                format="%.2f",
                                key=f"returned_amount_{doc_id}",
                            )
                            currency_input = st.text_input(
                                "Currency",
                                value=doc.get("currency", "RON") or "RON",
                                max_chars=3,
                                key=f"returned_currency_{doc_id}",
                            )
                            document_type_options = [
                                "invoice",
                                "contract",
                                "report",
                                "correspondence",
                                "decision",
                                "protocol",
                                "other",
                                "adresa",
                                "cerere",
                                "hcl",
                                "deviz",
                            ]
                            current_type = doc.get("document_type") or "other"
                            type_index = document_type_options.index(current_type) if current_type in document_type_options else 0
                            document_type_input = st.selectbox(
                                "Document Type",
                                document_type_options,
                                index=type_index,
                                key=f"returned_document_type_{doc_id}",
                            )
                            document_date_value = doc.get("document_date")
                            try:
                                document_date_default = datetime.fromisoformat(document_date_value).date() if document_date_value else datetime.now().date()
                            except Exception:
                                document_date_default = datetime.now().date()
                            document_date_input = st.date_input(
                                "Document Date",
                                value=document_date_default,
                                key=f"returned_document_date_{doc_id}",
                            )

                            submit_returned = st.form_submit_button("Submit Corrections")

                        if submit_returned:
                            document_date_iso = document_date_input.isoformat() + "T00:00:00"
                            payload = {
                                "title": title_input,
                                "description": description_input,
                                "document_number": document_number_input,
                                "amount": amount_input,
                                "currency": currency_input.strip().upper() if currency_input else None,
                                "document_type": document_type_input,
                                "document_date": document_date_iso,
                            }
                            try:
                                update_response = requests.put(
                                    f"{API_BASE_URL}/documents/{doc_id}",
                                    headers=headers,
                                    json=payload,
                                    timeout=10,
                                )
                                if update_response.status_code in [200, 202]:
                                    st.success("Corrections submitted. Document returned to REVIEW.")
                                    st.rerun()
                                else:
                                    st.error(f"Update failed: {update_response.status_code}")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")

                    else:
                        st.info(f"Current status: {status_upper}. No operator actions available.")
                
                # Show full page previews
                pages = doc.get("pages", [])
                if pages:
                    with st.expander("📄 Document Pages Preview", expanded=False):
                        if len(pages) > 1:
                            # Multiple pages - show as carousel with tabs
                            page_tabs = st.tabs([f"Page {p.get('page_number', i+1)}" for i, p in enumerate(pages)])
                            for page_tab, page in zip(page_tabs, pages):
                                with page_tab:
                                    page_num = page.get('page_number', 1)
                                    st.markdown(f"**Page {page_num}**")
                                    
                                    # Show page image/preview if available
                                    image_data = page.get("image_data") or page.get("page_image")
                                    image_path = page.get("image_path")
                                    
                                    if image_data:
                                        try:
                                            # Handle base64 or URL from image_data field
                                            if isinstance(image_data, str):
                                                if image_data.startswith(('http://', 'https://')):
                                                    st.image(image_data, use_column_width=True, caption=f"Page {page_num} Preview")
                                                elif image_data.startswith('data:image'):
                                                    st.image(image_data, use_column_width=True, caption=f"Page {page_num} Preview")
                                                else:
                                                    st.image(base64.b64decode(image_data), use_column_width=True, caption=f"Page {page_num} Preview")
                                            else:
                                                st.image(image_data, use_column_width=True, caption=f"Page {page_num} Preview")
                                        except Exception as e:
                                            st.warning(f"Could not display image for page {page_num}: {str(e)}")
                                    elif image_path:
                                        # Try to download image from MinIO via presigned URL
                                        try:
                                            img_response = requests.get(
                                                f"{API_BASE_URL}/documents/{doc_id}/page-image/{page_num}",
                                                headers=headers,
                                                timeout=10
                                            )
                                            if img_response.status_code == 200:
                                                st.image(img_response.content, use_column_width=True, caption=f"Page {page_num} Preview")
                                            else:
                                                st.info(f"Page {page_num} image not available yet (processing...)")
                                        except Exception as e:
                                            st.info(f"Page {page_num} image not available yet (still processing...)")
                                    else:
                                        st.info(f"No preview image available for page {page_num} (processing...)")
                                    
                                    # Show text content if available (OCR)
                                    text_content = page.get("text_content", "")
                                    if text_content:
                                        with st.expander(f"📝 Text Content (Page {page_num})"):
                                            st.text_area(
                                                f"Text from page {page_num}",
                                                value=text_content,
                                                height=200,
                                                disabled=True,
                                                label_visibility="collapsed"
                                            )
                        else:
                            # Single page
                            page = pages[0]
                            page_num = page.get('page_number', 1)
                            st.markdown(f"**Page {page_num}**")
                            
                            # Show page image/preview if available
                            image_data = page.get("image_data") or page.get("page_image")
                            image_path = page.get("image_path")
                            
                            if image_data:
                                try:
                                    # Handle base64 or URL from image_data field
                                    if isinstance(image_data, str):
                                        if image_data.startswith(('http://', 'https://')):
                                            st.image(image_data, use_column_width=True, caption=f"Page {page_num} Preview")
                                        elif image_data.startswith('data:image'):
                                            st.image(image_data, use_column_width=True, caption=f"Page {page_num} Preview")
                                        else:
                                            st.image(base64.b64decode(image_data), use_column_width=True, caption=f"Page {page_num} Preview")
                                    else:
                                        st.image(image_data, use_column_width=True, caption=f"Page {page_num} Preview")
                                except Exception as e:
                                    st.warning(f"Could not display image: {str(e)}")
                            elif image_path:
                                # Try to download image from MinIO via presigned URL
                                try:
                                    img_response = requests.get(
                                        f"{API_BASE_URL}/documents/{doc_id}/page-image/{page_num}",
                                        headers=headers,
                                        timeout=10
                                    )
                                    if img_response.status_code == 200:
                                        st.image(img_response.content, use_column_width=True, caption=f"Page {page_num} Preview")
                                    else:
                                        st.info("Page image not available yet (processing...)")
                                except Exception as e:
                                    st.info("Page image not available yet (still processing...)")
                            else:
                                st.info("No preview image available (processing...)")
                            
                            text_content = page.get("text_content", "")
                            if text_content:
                                with st.expander(f"📝 Extracted Text Content"):
                                    st.text_area(
                                        "Text content",
                                        value=text_content,
                                        height=250,
                                        disabled=True,
                                        label_visibility="collapsed"
                                    )
                
                st.divider()

                # ============================================================================
                # EXTRACTED DATA - Collapsible Panels
                # ============================================================================
                
                if isinstance(extracted, dict) or isinstance(classification, dict):
                    st.markdown("### Extracted Information")
                    
                    # Panel 1: Invoice Data Extraction
                    with st.expander("📋 Extracted Invoice Data", expanded=True):
                        if isinstance(extracted, dict) and extracted:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Invoice Number:** `{extracted.get('nr_factura', 'N/A')}`")
                                st.write(f"**Supplier:** {extracted.get('furnizor', 'N/A')}")
                                st.write(f"**Supplier Tax ID:** {extracted.get('cod_fiscal', 'N/A')}")
                                st.write(f"**Invoice Series:** {extracted.get('serie_factura', 'N/A')}")
                            
                            with col2:
                                st.write(f"**Invoice Date:** {extracted.get('data', 'N/A')}")
                                st.write(f"**Total:** {extracted.get('total', 'N/A')}")
                                st.write(f"**Currency:** {extracted.get('moneda', 'RON')}")
                                st.write(f"**Invoice Status:** {extracted.get('status_factura', 'N/A')}")
                            
                            # Additional invoice details
                            if extracted.get('descriere'):
                                st.write(f"**Description:** {extracted.get('descriere')}")
                        else:
                            st.info("No invoice data extracted.")
                    
                    # Panel 2: Document Classification
                    with st.expander("🏷️ Document Classification"):
                        if isinstance(classification, dict) and classification:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Document Type:** {classification.get('tip_document', 'N/A')}")
                                st.write(f"**Subtype:** {classification.get('subtip', 'N/A')}")
                                st.write(f"**Category:** {classification.get('categorie', 'N/A')}")
                            
                            with col2:
                                confidence = classification.get('confidence', 0)
                                confidence = confidence if confidence is not None else 0
                                st.metric("Classification Confidence", f"{confidence*100:.1f}%")
                                st.write(f"**Model:** {classification.get('model', 'AI')}")
                            
                            if classification.get('caracteristici'):
                                st.write(f"**Features:** {', '.join(classification.get('caracteristici', []))}")
                        else:
                            st.info("No classification data available.")
                    
                    # Panel 3: Nomenclator Suggestions
                    with st.expander("💡 Nomenclator Suggestions"):
                        nomenclator_data = doc.get("nomenclator_suggestion") or {}
                        
                        if isinstance(nomenclator_data, dict) and nomenclator_data:
                            col1, col2 = st.columns([2, 1])
                            suggested_code = (
                                nomenclator_data.get("cod")
                                or nomenclator_data.get("cod_nomenclator")
                                or (doc.get("nomenclator") or {}).get("code")
                            )
                            suggested_dosar = nomenclator_data.get("dosar_propus") or nomenclator_data.get("dosar")
                            
                            with col1:
                                st.write(f"**Suggested Nomenclator Code:** `{suggested_code or 'N/A'}`")
                                st.write(f"**Description:** {nomenclator_data.get('descriere', 'N/A')}")
                                if suggested_dosar:
                                    st.write(f"**Suggested Folder:** {suggested_dosar}")
                                st.write(f"**Relevance (%):** {nomenclator_data.get('incidenta', '0')} %")
                            
                            with col2:
                                confidence = nomenclator_data.get('confidence', 0)
                                confidence = confidence if confidence is not None else 0
                                st.metric("Suggestion Confidence", f"{confidence*100:.1f}%")
                            
                            # Alternate suggestions
                            alternatives = nomenclator_data.get('alternative', [])
                            if alternatives:
                                st.write("**Other Suggestions:**")
                                for alt in alternatives:
                                    alt_confidence = alt.get('confidence', 0)
                                    alt_confidence = alt_confidence if alt_confidence is not None else 0
                                    st.write(f"- `{alt.get('cod')}` - {alt.get('descriere')} ({alt_confidence*100:.1f}%)")
                        else:
                            st.info("No nomenclator suggestions yet.")
                    
                    st.divider()

                # =========================================================================
                # RELATED DOCUMENTS (Neo4j)
                # =========================================================================

                st.markdown("### Related Documents")
                related_filters = st.columns([2, 1, 1])

                with related_filters[0]:
                    relation_filter = st.selectbox(
                        "Relation type",
                        ["All", "Same folder", "Same supplier"],
                        key=f"related_filter_{doc_id}",
                    )

                with related_filters[1]:
                    related_page_size = st.selectbox(
                        "Results per page",
                        [5, 10, 20],
                        index=1,
                        key=f"related_page_size_{doc_id}",
                    )

                with related_filters[2]:
                    related_page = st.number_input(
                        "Page",
                        min_value=1,
                        value=1,
                        step=1,
                        key=f"related_page_{doc_id}",
                    )

                relation_type_map = {
                    "All": None,
                    "Same folder": "same_dosar",
                    "Same supplier": "same_furnizor",
                }
                relation_type = relation_type_map.get(relation_filter)

                try:
                    with st.spinner("Loading related documents..."):
                        related_params = {
                            "page": int(related_page),
                            "page_size": int(related_page_size),
                        }
                        if relation_type:
                            related_params["relation_type"] = relation_type

                        related_response = requests.get(
                            f"{API_BASE_URL}/documents/{doc_id}/related",
                            headers=headers,
                            params=related_params,
                            timeout=10,
                        )

                    if related_response.status_code == 200:
                        related_payload = related_response.json()
                        related_items = related_payload.get("related", [])
                        total_related = related_payload.get("total_count", 0)
                        total_pages = related_payload.get("total_pages", 0)

                        st.caption(
                            f"Total: {total_related} · Page {related_payload.get('page', 1)} of {total_pages or 1}"
                        )

                        if not related_items:
                            st.info("No related documents for the selected filter.")
                        else:
                            # De-duplicate: same doc can appear with multiple relation types
                            _seen_related_ids: set = set()
                            _deduped_related = []
                            for _rd in related_items:
                                _rid = _rd.get("id")
                                if _rid not in _seen_related_ids:
                                    _seen_related_ids.add(_rid)
                                    _deduped_related.append(_rd)
                            for _rel_idx, related_doc in enumerate(_deduped_related):
                                with st.container(border=True):
                                    left_col, right_col = st.columns([3, 1])

                                    with left_col:
                                        doc_label = related_doc.get("nr_factura") or f"Document #{related_doc.get('id')}"
                                        st.markdown(f"**{doc_label}**")

                                        meta_bits = []
                                        if related_doc.get("tip_document"):
                                            meta_bits.append(str(related_doc.get("tip_document")).upper())
                                        if related_doc.get("data"):
                                            meta_bits.append(str(related_doc.get("data")))
                                        if related_doc.get("total") is not None:
                                            meta_bits.append(f"Total: {related_doc.get('total')}")
                                        if related_doc.get("status"):
                                            meta_bits.append(str(related_doc.get("status")).upper())
                                        if meta_bits:
                                            st.caption(" · ".join(meta_bits))

                                        if related_doc.get("furnizor"):
                                            st.markdown(
                                                f"<span class='meta-chip'>Supplier: {related_doc.get('furnizor')}</span>",
                                                unsafe_allow_html=True,
                                            )
                                        if related_doc.get("dosar"):
                                            st.markdown(
                                                f"<span class='meta-chip'>Folder: {related_doc.get('dosar')}</span>",
                                                unsafe_allow_html=True,
                                            )

                                        relation_types = related_doc.get("relation_types") or []
                                        if relation_types:
                                            relation_badges = " ".join(
                                                f"<span class='meta-chip'>{_format_relation_label(rel)}</span>"
                                                for rel in relation_types
                                            )
                                            st.markdown(relation_badges, unsafe_allow_html=True)

                                    with right_col:
                                        if st.button(
                                            "Open details",
                                            key=f"related_open_{doc_id}_{related_doc.get('id')}_{_rel_idx}",
                                            use_container_width=True,
                                        ):
                                            st.session_state.selected_doc_id = str(related_doc.get("id"))
                                            st.rerun()
                    elif related_response.status_code == 503:
                        st.warning("Neo4j is temporarily unavailable. Please try again later.")
                    else:
                        st.warning(
                            f"Could not load related documents: {related_response.status_code}"
                        )
                except requests.exceptions.ConnectionError:
                    st.warning("Cannot reach the Neo4j service right now.")
                except Exception as e:
                    st.warning(f"Error loading related documents: {str(e)}")

                # Timeline
                st.markdown("### Processing Timeline")

                timeline_items = [
                    ("Created", doc.get("created_at")),
                    ("Processed", doc.get("updated_at")),
                    ("Nomenclator Confirmed", doc.get("nomenclator_confirmed_at")),
                    ("Approved / Archived", doc.get("archived_at")),
                ]

                for label, timestamp in timeline_items:
                    if timestamp and timestamp != "N/A":
                        st.write(f"✓ **{label}:** {timestamp}")

                st.markdown("### Audit Trail")
                try:
                    audit_response = requests.get(
                        f"{API_BASE_URL}/audit-trail/{doc_id}",
                        headers=headers,
                        timeout=10,
                    )
                    if audit_response.status_code == 200:
                        audit_payload = audit_response.json()
                        audit_items = audit_payload.get("items", [])
                        if audit_items:
                            for entry in audit_items:
                                actor = entry.get("actor") or {}
                                actor_name = actor.get("full_name") or actor.get("username") or "System"
                                actor_role = actor.get("role") or ""
                                action = str(entry.get("action", "")).upper()
                                timestamp = entry.get("timestamp", "N/A")
                                details = entry.get("details")

                                with st.container(border=True):
                                    st.markdown(f"**{action}** · {timestamp}")
                                    st.caption(f"{actor_name} {f'({actor_role})' if actor_role else ''}")
                                    if details:
                                        st.write(details)
                                    if entry.get("changes"):
                                        with st.expander("Changes"):
                                            st.json(entry.get("changes"))
                        else:
                            st.info("No audit events yet for this document.")
                    else:
                        st.warning("Audit trail is currently unavailable.")
                except Exception:
                    st.warning("Audit trail is currently unavailable.")
                
                # Raw JSON (expandable)
                with st.expander("Raw JSON Data"):
                    st.json(doc)
            
            elif response.status_code == 404:
                st.error("Document not found")
            
            else:
                st.error(f"Failed to fetch document: {response.status_code}\n\n{response.text[:500]}")
        
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to API")
        except Exception as e:
            st.error(f"Error: {str(e)}")
    
    else:
        search_tab, archive_tab = st.tabs(["🔍 Document Search", "📁 Archive Browser"])

        with search_tab:
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                search_query = st.text_input(
                    "Search",
                    placeholder="Search by title, number, supplier...",
                    help="Full-text search across documents"
                )
            with col2:
                doc_type = st.selectbox(
                    "Type",
                    ["All", "INVOICE", "CONTRACT", "REPORT", "CORRESPONDENCE", "DECISION", "PROTOCOL", "OTHER"],
                    help="Filter by document type"
                )
            with col3:
                supplier_query = st.text_input(
                    "Supplier",
                    placeholder="Supplier name",
                    help="Filter by supplier name (exact match)"
                )
            with col4:
                doc_status = st.selectbox(
                    "Status",
                    [
                        "All",
                        "REVIEW",
                        "APPROVED",
                        "RETURNED",
                        "ARCHIVED",
                        "PROCESSING",
                        "CLASSIFIED",
                        "EXTRACTED",
                        "VALIDATED",
                        "PENDING",
                        "ERROR",
                    ],
                    help="Filter by processing status"
                )

            year_options = ["All"] + [str(y) for y in range(datetime.now().year, 2019, -1)]
            year = st.selectbox("Year", year_options, index=0, help="Filter by document year")

            search_params = {
                "limit": 20,
                "offset": 0,
            }
            if search_query:
                search_params["q"] = search_query
            if doc_type != "All":
                search_params["tip_document"] = doc_type.lower()
            if supplier_query:
                search_params["furnizor"] = supplier_query
            if doc_status != "All":
                search_params["status"] = doc_status.lower()
            if year != "All":
                search_params["data_start"] = f"{year}-01-01"
                search_params["data_end"] = f"{year}-12-31"

            if st.button("🔍 Search Documents", type="primary", use_container_width=True):
                try:
                    with st.spinner("Searching documents..."):
                        response = requests.get(
                            f"{API_BASE_URL}/documents/search",
                            headers=headers,
                            params=search_params,
                            timeout=10,
                        )

                    if response.status_code == 200:
                        search_result = response.json()
                        st.session_state.search_results = search_result
                        st.success("Search completed")
                    else:
                        st.error(f"Search failed: {response.status_code}")
                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to API")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

            if st.session_state.search_results:
                hits = st.session_state.search_results.get("hits", [])
                total = st.session_state.search_results.get("total_hits", 0)
                st.markdown(f"### 📄 {len(hits)} of {total} documents found")



                _TYPE_ICON = {
                    "invoice":"🧾","contract":"📋","report":"📊",
                    "correspondence":"✉️","decision":"⚖️",
                    "protocol":"📝","adresa":"📨","hcl":"📜",
                }
                _STATUS_BADGE = {
                    "ARCHIVED":"badge-archived","APPROVED":"badge-archived",
                    "REVIEW":"badge-review","RETURNED":"badge-returned",
                    "ERROR":"badge-returned",
                }

                if hits:
                    for _ci, doc in enumerate(hits):
                        doc_id       = doc.get("id","N/A")
                        doc_id_str   = str(doc_id)
                        title        = doc.get("title") or "Untitled"
                        status_upper = str(doc.get("status","N/A")).upper()
                        dtype_raw    = str(doc.get("tip_document","other") or "other").lower()
                        f_val        = float(doc.get("fraud_score") or 0.0)

                        doc_number = (doc.get("invoice_number") or doc.get("nr_factura")
                                      or doc.get("document_number") or "")
                        furnizor   = doc.get("furnizor") or ""
                        doc_date   = doc.get("data") or ""
                        amount_str = f"{doc['total']} RON" if doc.get("total") is not None else ""

                        meta_parts = [x for x in [doc_number, furnizor, doc_date, amount_str] if x]
                        meta_str   = " · ".join(meta_parts) or "No metadata"

                        type_icon   = _TYPE_ICON.get(dtype_raw, "📄")
                        status_cls  = _STATUS_BADGE.get(status_upper, "badge-default")
                        fraud_badge = ('<span class="badge badge-fraud">🚨 Fraud risk</span>'
                                       if f_val > 0.7 else "")

                        st.markdown(
                            f'<div class="doc-card" style="animation-delay:{_ci*0.04:.2f}s">'
                            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
                            f'  <span style="font-size:20px">{type_icon}</span>'
                            f'  <span class="doc-card-title">{title}</span>'
                            f'</div>'
                            f'<div class="doc-card-badges">'
                            f'  <span class="badge badge-type">{dtype_raw.upper()}</span>'
                            f'  <span class="badge {status_cls}">{status_upper}</span>'
                            f'  {fraud_badge}'
                            f'</div>'
                            f'<div class="doc-card-meta">{meta_str}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        _btn_c, _del_c = st.columns([5, 1])
                        with _btn_c:
                            if st.button(
                                f"📂  {title[:70]}",
                                key=f"view_{doc_id_str}",
                                use_container_width=True,
                                type="primary",
                            ):
                                st.session_state.selected_doc_id = str(doc_id)
                                st.rerun()
                        with _del_c:
                            if st.button("🗑", key=f"del_init_hit_{doc_id_str}",
                                         use_container_width=True, help="Delete"):
                                st.session_state.delete_confirm_doc_id = str(doc_id)
                                st.rerun()
                            if st.session_state.get("delete_confirm_doc_id") == str(doc_id):
                                st.warning("Delete permanently?")
                                if st.button("Confirm", key=f"del_confirm_hit_{doc_id_str}"):
                                    try:
                                        del_resp = requests.delete(
                                            f"{API_BASE_URL}/documents/{doc_id}",
                                            headers=headers, timeout=15,
                                        )
                                        if del_resp.status_code in [200, 202, 204]:
                                            st.success("Deleted.")
                                            st.session_state.search_results = None
                                            st.session_state.delete_confirm_doc_id = None
                                            st.rerun()
                                        else:
                                            st.error(f"Delete failed: {del_resp.status_code}")
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")
                else:
                    st.info("🔍 No documents found. Try a broader search or clear the filters.")

        with archive_tab:
            st.markdown("### Archive Folder Browser")
            st.info(
                "Browse archived dossiers by hierarchical nomenclator categories, then open documents from the selected folder."
            )

            archive_search_query = st.text_input(
                "Archive Search",
                placeholder="Search folder names, codes, or dossier titles...",
                help="Filter the archive hierarchy and dossier labels",
                key="archive_search_query",
            )

            filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
            selected_department = "All"
            if st.session_state.archive_tree:
                category_options = ["All"]
                roots = st.session_state.archive_tree.get("roots", [])
                for root in roots:
                    category_options.append(root.get("code") or root.get("name") or "Unnamed")
                with filter_col1:
                    selected_department = st.selectbox(
                        "Department / Category",
                        category_options,
                        help="Show only dossiers from a top-level archive category",
                        key="archive_department",
                    )
            else:
                with filter_col1:
                    selected_department = st.selectbox(
                        "Department / Category",
                        ["All"],
                        help="Show only dossiers from a top-level archive category",
                        key="archive_department",
                    )
            with filter_col2:
                archive_year = st.selectbox(
                    "Year",
                    ["All"] + [str(y) for y in range(datetime.now().year, 2019, -1)],
                    index=0,
                    help="Filter documents by year when a dossier is selected",
                    key="archive_year",
                )
            with filter_col3:
                supplier_filter = st.text_input(
                    "Supplier",
                    placeholder="Supplier name or keyword",
                    help="Filter documents in the selected dossier by supplier",
                    key="archive_supplier",
                )
            with filter_col4:
                archive_doc_type = st.selectbox(
                    "Document Type",
                    ["All", "INVOICE", "CONTRACT", "REPORT", "CORRESPONDENCE", "DECISION", "PROTOCOL", "OTHER"],
                    key="archive_doc_type",
                    help="Filter documents in the selected dossier by document type",
                )

            if st.button("Refresh archive tree", type="secondary", use_container_width=True):
                st.session_state.archive_tree = None
                st.session_state.archive_dosar_details = None
                st.session_state.selected_dosar_id = None
                st.experimental_rerun()

            if st.session_state.archive_tree is None:
                try:
                    with st.spinner("Loading archive hierarchy..."):
                        response = requests.get(
                            f"{API_BASE_URL}/archive/tree",
                            headers=headers,
                            timeout=10,
                        )
                    if response.status_code == 200:
                        st.session_state.archive_tree = response.json()
                    else:
                        st.error(f"Unable to load archive tree: {response.status_code}")
                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to API")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

            archive_tree = st.session_state.archive_tree
            if archive_tree:
                roots = archive_tree.get("roots", [])
                if selected_department != "All":
                    roots = [root for root in roots if root.get("code") == selected_department or root.get("name") == selected_department]

                if not roots:
                    st.warning("No archive folders match the selected department. Refresh the tree or choose All.")
                else:
                    for root in roots:
                        _render_archive_node(root, st.session_state.get("archive_search_query", ""), st.session_state.selected_dosar_id)

            if st.session_state.selected_dosar_id:
                try:
                    if not st.session_state.archive_dosar_details or st.session_state.archive_dosar_details.get("id") != int(st.session_state.selected_dosar_id):
                        with st.spinner("Loading dossier details..."):
                            dosar_response = requests.get(
                                f"{API_BASE_URL}/archive/dosar/{st.session_state.selected_dosar_id}",
                                headers=headers,
                                timeout=10,
                            )
                        if dosar_response.status_code == 200:
                            st.session_state.archive_dosar_details = dosar_response.json()
                        else:
                            st.error(f"Unable to load dossier details: {dosar_response.status_code}")

                    if st.session_state.archive_dosar_details:
                        dosar = st.session_state.archive_dosar_details
                        st.markdown(f"#### Selected Dossier: {dosar.get('nomenclator_code', 'N/A')} / {dosar.get('dosar_number', 'N/A')} - {dosar.get('title', '')}")
                        st.write(dosar.get("description", "No description available."))

                        documents = dosar.get("documents", [])
                        filtered_docs = _filter_documents(documents, archive_year, supplier_filter, archive_doc_type)

                        st.markdown(f"**Documents in dossier:** {len(filtered_docs)} of {len(documents)}")
                        if not filtered_docs:
                            st.info("No documents match the current filters in this dossier.")
                        else:
                            for doc in filtered_docs:
                                with st.container(border=True):
                                    doc_cols = st.columns([4, 1, 1, 1])
                                    archive_invoice_number = doc.get("invoice_number") or doc.get("document_number", "")
                                    doc_cols[0].markdown(f"**{doc.get('title', 'Untitled')}**\n- {archive_invoice_number}")
                                    doc_cols[1].markdown(f"_{(doc.get('document_type') or '').upper()}_")
                                    doc_cols[2].markdown(f"{doc.get('status', 'N/A').upper()}")
                                    if doc_cols[3].button(
                                        "Open details",
                                        key=f"archive_open_doc_{doc.get('id')}",
                                        use_container_width=True,
                                    ):
                                        st.session_state.selected_doc_id = str(doc.get('id'))
                                        st.rerun()
                                    # Delete button for archive listing
                                    if doc_cols[3].button(
                                        "🗑️ Delete",
                                        key=f"archive_del_{doc.get('id')}",
                                        use_container_width=True,
                                    ):
                                        st.session_state.delete_confirm_doc_id = str(doc.get('id'))
                                        st.rerun()
                                    if st.session_state.get("delete_confirm_doc_id") == str(doc.get('id')):
                                        if doc_cols[3].button("Confirm Delete", key=f"archive_del_confirm_{doc.get('id')}"):
                                            try:
                                                del_resp = requests.delete(
                                                    f"{API_BASE_URL}/documents/{doc.get('id')}",
                                                    headers=headers,
                                                    timeout=15,
                                                )
                                                if del_resp.status_code in [200, 202, 204]:
                                                    st.success("Document deleted.")
                                                    st.session_state.archive_dosar_details = None
                                                    st.session_state.delete_confirm_doc_id = None
                                                    st.rerun()
                                                else:
                                                    st.error(f"Delete failed: {del_resp.status_code} {del_resp.text[:200]}")
                                            except Exception as e:
                                                st.error(f"Error deleting document: {str(e)}")
                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to API")
                except Exception as e:
                    st.error(f"Error loading dossier details: {str(e)}")

else:
    st.warning("Please login first to view documents")
    st.info("Use the sidebar to enter your credentials")

# ============================================================================
# FOOTER
# ============================================================================

st.divider()
st.markdown("""
### Help
- **Search:** Use keywords to find documents by title, number, or supplier
- **Filter:** Narrow results by type or status
- **Details:** Click on a document to view full extracted data
- **Timeline:** See the processing history of each document

### Related
- [Upload Document](01_Upload_Document)
- [API Documentation](http://localhost:8000/docs)
- [Main Dashboard](/)
""")
