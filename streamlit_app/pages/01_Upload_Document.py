"""
NV-024: Document Upload & Status Monitoring Page

Features:
- Drag-and-drop PDF upload
- Real-time status monitoring (3s polling)
- Progress indicators with status messages
- Document details display
"""

import os
import streamlit as st
import requests
import time
from datetime import datetime
import json

# Page config
st.set_page_config(page_title="Upload Document", page_icon="📄", layout="wide")

st.markdown("""
<style>
@keyframes fadeInUp   { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
@keyframes pulse-ring { 0%,100%{box-shadow:0 0 0 0 rgba(56,189,248,.4)} 60%{box-shadow:0 0 0 10px rgba(56,189,248,0)} }
@keyframes spin       { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
@keyframes bar-fill   { from{width:0} to{width:100%} }
@keyframes blink      { 0%,100%{opacity:1} 50%{opacity:.3} }

/* Page header card */
.page-hero {
    background: linear-gradient(135deg,#0f172a 0%,#1e3a5f 60%,#0f172a 100%);
    border:1px solid #1e40af; border-radius:18px;
    padding:24px 28px; margin-bottom:20px;
    animation: fadeInUp .5s ease;
}
.page-hero-title { font-size:26px; font-weight:800; color:#f1f5f9; margin:0; }
.page-hero-sub   { font-size:13px; color:#94a3b8; margin-top:4px; }

/* Status pill */
.status-pill {
    display:inline-block; padding:3px 12px; border-radius:20px;
    font-size:11px; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
}
.pill-processing { background:#1e3a5f; color:#7dd3fc; border:1px solid #2563eb; animation:blink 1.5s ease infinite; }
.pill-done       { background:#052e16; color:#4ade80; border:1px solid #16a34a; }
.pill-error      { background:#450a0a; color:#f87171; border:1px solid #b91c1c; }
.pill-review     { background:#422006; color:#fb923c; border:1px solid #c2410c; }

/* Polling step row */
.step-row { display:flex; align-items:center; gap:10px; padding:5px 0; font-size:13px; color:#94a3b8; }
.step-row.done    { color:#4ade80; }
.step-row.current { color:#38bdf8; }
.step-icon { font-size:16px; width:22px; text-align:center; }

/* Animated progress track */
.prog-track {
    height:6px; background:#1e293b; border-radius:999px; overflow:hidden; margin:8px 0 4px;
}
.prog-fill {
    height:100%; border-radius:999px;
    background:linear-gradient(90deg,#3b82f6,#38bdf8,#3b82f6);
    background-size:200% 100%;
    animation:bar-fill .6s ease forwards, shimmer 2s linear infinite;
}
@keyframes shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }

/* Streamlit tweaks */
section[data-testid="stSidebar"] { background:#0f172a !important; }
section[data-testid="stSidebar"] * { color:#cbd5e1 !important; }
.stButton > button {
    border-radius:10px !important; font-weight:600 !important;
    transition:transform .15s, box-shadow .15s !important;
}
.stButton > button:hover { transform:translateY(-1px) !important; box-shadow:0 4px 14px rgba(0,0,0,.4) !important; }
div[data-testid="stFileUploader"] {
    border:2px dashed #334155 !important; border-radius:14px !important;
    background:#0f172a !important; transition:border-color .2s !important;
}
div[data-testid="stFileUploader"]:hover { border-color:#3b82f6 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-hero">
  <div class="page-hero-title">📄 Upload Document</div>
  <div class="page-hero-sub">
    Drag &amp; drop a PDF — AI will classify it, extract key fields, suggest an archive folder,
    and route it for operator approval automatically.
  </div>
</div>
""", unsafe_allow_html=True)

# Configuration
API_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
POLLING_INTERVAL = 3  # seconds
MAX_POLLING_TIME = 300  # 5 minutes

# ============================================================================
# SIDEBAR - Authentication & Settings
# ============================================================================

st.sidebar.markdown("### 🔑 Authentication")

if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
    st.session_state.username = None

_upload_err = st.session_state.get("_login_error_upload", "")
_upload_locked = "locked" in _upload_err.lower()

if st.session_state.auth_token:
    st.sidebar.success(f"✅ **{st.session_state.username}**")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.auth_token = None
        st.session_state.username = None
        st.session_state.pop("_login_error_upload", None)
        st.rerun()
else:
    # --- lockout / error banner shown ABOVE the form ---
    if _upload_locked:
        st.sidebar.warning(_upload_err)
        st.sidebar.caption(
            "⏳ Your account is temporarily locked. "
            "Wait for the lockout period to expire, then try again."
        )
    elif _upload_err:
        st.sidebar.error(_upload_err)

    # Login form — disabled while account is locked
    with st.sidebar.form("login_form_upload"):
        username = st.text_input("Username", placeholder="admin", disabled=_upload_locked)
        password = st.text_input("Password", type="password", disabled=_upload_locked)
        _btn_label = "🔒 Account Locked" if _upload_locked else "Login"
        submitted = st.form_submit_button(
            _btn_label, use_container_width=True, disabled=_upload_locked,
        )

    if submitted and not _upload_locked:
        st.session_state.pop("_login_error_upload", None)
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
                st.session_state["_login_error_upload"] = "🔒 " + response.json().get("detail", "Account locked.")
                st.rerun()
            else:
                st.session_state["_login_error_upload"] = response.json().get("detail", "Login failed.")
                st.rerun()
        except Exception as e:
            st.session_state["_login_error_upload"] = f"Connection error: {e}"
            st.rerun()

# ============================================================================
# MAIN CONTENT - Upload Form
# ============================================================================

if st.session_state.auth_token:
    # Headers for API requests
    headers = {
        "Authorization": f"Bearer {st.session_state.auth_token}"
    }
    
    st.divider()
    
    # Upload section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**📄 Upload PDF**")

        # File uploader with drag-and-drop
        uploaded_file = st.file_uploader(
            "Drag and drop your PDF here, or click to select",
            type=["pdf"],
            help="Select a PDF document to process"
        )
        
        if uploaded_file:
            st.markdown(
                f'<div style="background:#052e16;border:1px solid #16a34a;border-radius:10px;'
                f'padding:8px 14px;font-size:13px;color:#4ade80;margin-top:4px">'
                f'📄 <strong>{uploaded_file.name}</strong> &nbsp;\u00b7\u00a0 {uploaded_file.size/1024:.1f} KB'
                f'</div>',
                unsafe_allow_html=True,
            )
    
    with col2:
        st.markdown("**⚙️ Options**")
        auto_archive = st.checkbox("Auto-archive after processing", value=True)
        create_node = st.checkbox("Create graph node", value=True)
    
    st.divider()
    
    # Upload button
    if uploaded_file and st.button("Upload & Process", type="primary", use_container_width=True):
        
        try:
            with st.spinner("Uploading document..."):
                # Upload file
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                response = requests.post(
                    f"{API_BASE_URL}/documents/upload",
                    files=files,
                    data={"auto_archive": str(auto_archive).lower()},
                    headers=headers,
                    timeout=30
                )
            
            if response.status_code not in [200, 201, 202]:
                st.error(f"Upload failed: {response.status_code}")
                st.write(response.text)
            else:
                upload_data = response.json()
                document_id = upload_data.get("id") or upload_data.get("document_id")
                
                if not document_id:
                    st.error("No document ID returned from server")
                else:
                    st.success("File uploaded successfully!")
                    
                    # ====================================================================
                    # STATUS MONITORING - Polling Section
                    # ====================================================================

                    st.markdown("""
<div style="background:linear-gradient(135deg,#0f172a,#1e293b);border:1px solid #334155;
border-radius:14px;padding:16px 20px;margin:16px 0 8px;animation:fadeInUp .4s ease">
  <div style="font-size:16px;font-weight:700;color:#f1f5f9">🔄 Processing Status</div>
  <div style="font-size:12px;color:#64748b;margin-top:3px">Polling every 3s — updates automatically</div>
</div>""", unsafe_allow_html=True)

                    # Create placeholders for dynamic updates
                    status_placeholder = st.empty()
                    progress_placeholder = st.empty()
                    details_placeholder = st.empty()

                    # Status mapping
                    status_colors = {
                        "PROCESSING": "🔄 blue",
                        "CLASSIFIED": "📊 blue",
                        "EXTRACTED": "✂️ blue",
                        "VALIDATED": "✓ green",
                        "REVIEW": "📝 yellow",
                        "APPROVED": "✅ green",
                        "ARCHIVED": "📦 green",
                        "RETURNED": "↩️ red",
                        "ERROR": "❌ red",
                    }
                    
                    # Polling loop
                    start_time = time.time()
                    poll_count = 0
                    
                    while True:
                        elapsed = time.time() - start_time
                        poll_count += 1
                        
                        # Check timeout
                        if elapsed > MAX_POLLING_TIME:
                            status_placeholder.warning(
                                f"Polling timeout after {MAX_POLLING_TIME}s. "
                                f"Document may still be processing in the background."
                            )
                            break
                        
                        try:
                            # Fetch document status
                            response = requests.get(
                                f"{API_BASE_URL}/documents/{document_id}",
                                headers=headers,
                                timeout=10
                            )
                            
                            if response.status_code not in [200, 202]:
                                status_placeholder.error(
                                    f"Failed to fetch status: {response.status_code}\n\n"
                                    f"Response: {response.text[:500]}"
                                )
                                break
                            
                            doc = response.json()
                            status = doc.get("status", "UNKNOWN")
                            
                            # Display status
                            with status_placeholder.container():
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("Document ID", document_id)
                                with col2:
                                    st.metric("Status", status)
                                with col3:
                                    st.metric("Polling", f"{poll_count}x")
                                with col4:
                                    st.metric("Elapsed", f"{elapsed:.0f}s")
                            
                            # Progress visualization
                            status_stages = {
                                "PROCESSING": 25,
                                "CLASSIFIED": 50,
                                "EXTRACTED": 75,
                                "VALIDATED": 85,
                                "REVIEW": 90,
                                "APPROVED": 95,
                                "ARCHIVED": 100,
                                "RETURNED": 40,
                                "ERROR": 0,
                                "PENDING": 10,
                                "UPLOADED": 15,
                            }
                            
                            progress = status_stages.get(status.upper(), 0)
                            
                            with progress_placeholder.container():
                                st.progress(
                                    min(progress / 100, 1.0),
                                    text=f"{status} ({progress}%)"
                                )
                            
                            # Document details
                            with details_placeholder.container():
                                st.markdown("### 📋 Document Details")
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
                                
                                detail_cols = st.columns(3)
                                
                                with detail_cols[0]:
                                    st.write(f"**Title:** {doc.get('title', 'N/A')}")
                                    st.write(f"**Type:** {doc.get('document_type', 'N/A')}")
                                
                                with detail_cols[1]:
                                    st.write(f"**{number_label}:** {number_value}")
                                    st.write(f"**Document Number (internal):** {doc.get('document_number', 'N/A')}")
                                    st.write(f"**Amount:** {doc.get('amount', 'N/A')} {doc.get('currency', '')}")
                                
                                with detail_cols[2]:
                                    created = doc.get('created_at', 'N/A')
                                    st.write(f"**Created:** {created}")
                                    archived = doc.get('archived_at')
                                    if archived:
                                        st.write(f"**Archived:** {archived}")
                            
                            # Check if done / review requires operator action
                            if status in ["ARCHIVED", "ERROR", "REVIEW"]:
                                if status == "ARCHIVED":
                                    st.success("Document processing completed successfully!")
                                    st.balloons()
                                elif status == "REVIEW":
                                    details_placeholder.info(
                                        "Documentul este in REVIEW. Daca auto-archive este activ, trebuie sa existe dosar/nomenclator setat."
                                    )
                                    if st.button(
                                        "Open in View Documents",
                                        use_container_width=True,
                                        key=f"open_view_{document_id}",
                                    ):
                                        st.session_state.selected_doc_id = str(document_id)
                                        st.switch_page("pages/02_View_Documents.py")
                                else:
                                    error_msg = doc.get("error_message", "Unknown error")
                                    st.error(f"Processing failed: {error_msg}")

                                # ── ANAF result after processing ────────────────
                                _anaf_up = doc.get("anaf_validation") or {}
                                _ext_up  = doc.get("extracted_data_map") or {}
                                _cui_up  = _ext_up.get("cui") or _ext_up.get("cod_fiscal")
                                if _cui_up or _anaf_up.get("found") is not None:
                                    st.markdown("---")
                                    st.markdown("#### 🏛️ ANAF Supplier Validation")
                                    _an_name = (_anaf_up.get("company_name") or "").strip()
                                    _an_addr = (_anaf_up.get("address") or "").strip()
                                    if _anaf_up.get("error") and not _anaf_up.get("found"):
                                        st.caption(f"ANAF service unavailable: {_anaf_up.get('error','')}")
                                    elif not _anaf_up.get("found"):
                                        st.warning(f"⚠️ CUI `{_cui_up}` not found in the ANAF registry")
                                    elif not _anaf_up.get("is_active"):
                                        st.error(f"🚨 **COMPANY INACTIVE** — {_an_name}  \nCUI: {_cui_up}")
                                    else:
                                        st.success(f"✅ **Active supplier** — {_an_name}  \nCUI: {_cui_up}")
                                        _furnizor_up = (_ext_up.get("furnizor") or "").strip()
                                        if _furnizor_up and _an_name:
                                            from difflib import SequenceMatcher as _SM2
                                            _sim2 = _SM2(None, _furnizor_up.upper(), _an_name.upper()).ratio()
                                            if _sim2 < 0.6:
                                                st.warning(
                                                    f"⚠️ Name mismatch: document `{_furnizor_up}` "
                                                    f"vs ANAF `{_an_name}` ({int(_sim2*100)}% match)"
                                                )
                                    if _an_addr:
                                        st.caption(f"📍 {_an_addr}")
                                # ────────────────────────────────────────────────
                                break
                            
                            # Wait before next poll
                            time.sleep(POLLING_INTERVAL)
                        
                        except requests.exceptions.Timeout:
                            status_placeholder.error("Request timeout - retrying...")
                            time.sleep(POLLING_INTERVAL)
                        except requests.exceptions.ConnectionError:
                            status_placeholder.error("Connection error - retrying...")
                            time.sleep(POLLING_INTERVAL)
                        except Exception as e:
                            status_placeholder.error(f"Error: {str(e)}")
                            break
        
        except requests.exceptions.Timeout:
            st.error("Upload timeout - please try again")
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to API - is it running?")
        except Exception as e:
            st.error(f"Error: {str(e)}")

else:
    st.warning("Please login first to upload documents")
    st.info("Use the sidebar to enter your credentials")

# ============================================================================
# FOOTER
# ============================================================================

st.divider()
st.markdown("""
### Help
- **Drag & Drop:** Click the upload area or drag your PDF onto it
- **Polling:** Status is checked every 3 seconds automatically
- **Status Times:** 
  - PROCESSING → CLASSIFIED: ~5-10s (PDF → images, classification)
  - CLASSIFIED → EXTRACTED: ~5-15s (invoice extraction)
    - EXTRACTED → REVIEW: ~2-5s (nomenclator suggestion, graph population)
    - REVIEW → APPROVED/ARCHIVED: manual (confirmare + aprobare + arhivare)

### Related
- [API Documentation](http://localhost:8000/docs)
- [Main Dashboard](/)
""")
