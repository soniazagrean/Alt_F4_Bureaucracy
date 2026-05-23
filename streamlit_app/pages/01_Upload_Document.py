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

st.title("Upload Document")
st.markdown("Upload PDF documents for processing and monitor their status in real-time.")

# Configuration
API_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
POLLING_INTERVAL = 3  # seconds
MAX_POLLING_TIME = 300  # 5 minutes

# ============================================================================
# SIDEBAR - Authentication & Settings
# ============================================================================

st.sidebar.markdown("## Authentication")

# Always ensure the keys exist, then restore from URL query-params if needed
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
    st.session_state.username = None

if not st.session_state.auth_token:
    _qt = st.query_params.get("token")
    _qu = st.query_params.get("user")
    if _qt:
        st.session_state.auth_token = _qt
        st.session_state.username = _qu or ""

# Login form
with st.sidebar.form("auth_form"):
    username = st.text_input("Username", placeholder="testuser")
    password = st.text_input("Password", placeholder="password", type="password")

    if st.form_submit_button("Login"):
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                st.session_state.auth_token = data.get("access_token")
                st.session_state.username = username
                st.query_params["token"] = data.get("access_token")
                st.query_params["user"] = username
                st.sidebar.success(f"Logged in as {username}")
            else:
                st.sidebar.error("Login failed")
        except Exception as e:
            st.sidebar.error(f"Connection error: {str(e)}")

# Show current user
if st.session_state.get("auth_token"):
    st.sidebar.info(f"Logged in: **{st.session_state.username}**")

    if st.sidebar.button("Logout"):
        st.session_state.auth_token = None
        st.session_state.username = None
        st.query_params.clear()
        st.rerun()
else:
    st.sidebar.warning("Please login to upload documents")

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
        st.subheader("Upload PDF")
        
        # File uploader with drag-and-drop
        uploaded_file = st.file_uploader(
            "Drag and drop your PDF here, or click to select",
            type=["pdf"],
            help="Select a PDF document to process"
        )
        
        if uploaded_file:
            st.write(f"File selected: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")
    
    with col2:
        st.subheader("Options")
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
                    
                    st.markdown("---")
                    st.subheader("Processing Status")
                    
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
