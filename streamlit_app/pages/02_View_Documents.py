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

st.title("View Documents")
st.markdown("Search, filter, and view processed documents with extracted data.")

st.markdown(
    """
    <style>
    .doc-hero {
        background: linear-gradient(135deg, #f7f4ed 0%, #eef6f2 100%);
        border: 1px solid #e4dccf;
        border-radius: 18px;
        padding: 16px 18px;
        margin-bottom: 16px;
    }
    .status-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .status-pill.good { background: #d9f5e5; color: #0b5f3b; border: 1px solid #a7e2c3; }
    .status-pill.warn { background: #fff4cc; color: #8a5b00; border: 1px solid #f5d08b; }
    .status-pill.bad { background: #ffe1df; color: #8a1f17; border: 1px solid #f4b1aa; }
    .meta-chip {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        border: 1px solid #e6e1d5;
        background: #fffdf7;
        font-size: 12px;
        color: #5a5447;
        margin-right: 6px;
        margin-top: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# SIDEBAR - Authentication & Filters
# ============================================================================

st.sidebar.markdown("## Authentication")

# Check if token exists in session
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
    st.session_state.username = None

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
                st.sidebar.success(f"Logged in as {username}")
            else:
                st.sidebar.error("Login failed")
        except Exception as e:
            st.sidebar.error(f"Connection error: {str(e)}")

# Show current user
if st.session_state.auth_token:
    st.sidebar.info(f"Logged in: **{st.session_state.username}**")
    
    if st.sidebar.button("Logout"):
        st.session_state.auth_token = None
        st.session_state.username = None
        st.rerun()
else:
    st.sidebar.warning("Please login to view documents")

# ============================================================================
# MAIN CONTENT
# ============================================================================

if st.session_state.auth_token:
    headers = {
        "Authorization": f"Bearer {st.session_state.auth_token}"
    }
    
    # Initialize session state for search results
    if "search_results" not in st.session_state:
        st.session_state.search_results = None
    if "selected_doc_id" not in st.session_state:
        st.session_state.selected_doc_id = None
    
    st.divider()
    
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
                        <div style="font-size: 20px; font-weight: 700;">{doc_title}</div>
                        <div style="margin-top: 6px;">
                            <span class="status-pill {status_class}">{status_upper}</span>
                            <span style="margin-left: 10px; color: #6b7280;">Created: {doc.get('created_at', 'N/A')}</span>
                        </div>
                        <div style="margin-top: 8px; color: #4b5563;">
                            Type: {doc.get('document_type', 'N/A')} · Document ID: {doc_id if doc_id is not None else 'N/A'}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.divider()

                preview_col, meta_col = st.columns([1.1, 1.9])

                with preview_col:
                    st.markdown("### Preview rapid")
                    preview_url = doc.get("preview_url")
                    mime_type = doc.get("mime_type") or ""
                    if preview_url and "pdf" in mime_type.lower():
                        components.html(
                            f"""
                            <iframe
                                src="{preview_url}"
                                width="100%"
                                height="480"
                                style="border: 1px solid #e5e7eb; border-radius: 12px;"
                            ></iframe>
                            """,
                            height=500,
                        )
                        st.caption("Preview link is time-limited and may expire.")
                    elif preview_url and "image" in mime_type.lower():
                        st.image(preview_url, use_container_width=True, caption="Preview")
                    else:
                        pages = doc.get("pages", [])
                        first_page_num = None
                        if pages:
                            first_page_num = sorted(pages, key=lambda p: p.get("page_number", 1))[0].get("page_number", 1)
                        if doc_id and first_page_num:
                            try:
                                img_response = requests.get(
                                    f"{API_BASE_URL}/documents/{doc_id}/page-image/{first_page_num}",
                                    headers=headers,
                                    timeout=10,
                                )
                                if img_response.status_code == 200:
                                    st.image(img_response.content, use_container_width=True, caption="Page 1")
                                else:
                                    st.info("Preview not available yet (processing in progress).")
                            except Exception:
                                st.info("Preview not available yet (processing in progress).")
                        else:
                            st.info("Preview not available yet (processing in progress).")

                with meta_col:
                    st.markdown("### Metadata & workflow")

                    meta_left, meta_right = st.columns(2)
                    with meta_left:
                        st.metric("Document Number", doc.get("document_number", "N/A"))
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

                    st.markdown("#### Cale arhiva sugerata")
                    archive_hint = None
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

                    if archive_hint:
                        st.code(archive_hint, language=None)
                    else:
                        st.info("Nu exista inca o sugestie de arhivare.")

                    st.markdown("#### Workflow operator")
                    nomenclator_confirmed = doc.get("nomenclator_confirmed", False)
                    if status_upper == "REVIEW":
                        action_cols = st.columns([1, 1])

                        with action_cols[0]:
                            if not nomenclator_confirmed:
                                if st.button("✓ Confirma nomenclator", use_container_width=True, type="primary"):
                                    try:
                                        confirm_response = requests.post(
                                            f"{API_BASE_URL}/documents/{doc_id}/confirm-nomenclator",
                                            headers=headers,
                                            json={"confirmed": True},
                                            timeout=10,
                                        )
                                        if confirm_response.status_code in [200, 202]:
                                            st.success("Nomenclator confirmat!")
                                            st.rerun()
                                        else:
                                            st.error(f"Confirmation failed: {confirm_response.status_code}")
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")
                            else:
                                st.success("Nomenclator confirmat")

                        with action_cols[1]:
                            if st.button("✅ Aproba document", use_container_width=True):
                                try:
                                    approve_response = requests.post(
                                        f"{API_BASE_URL}/documents/{doc_id}/approve",
                                        headers=headers,
                                        timeout=10,
                                    )
                                    if approve_response.status_code in [200, 202]:
                                        st.success("Document aprobat!")
                                        st.rerun()
                                    else:
                                        st.error(f"Approve failed: {approve_response.status_code}")
                                except Exception as e:
                                    st.error(f"Error: {str(e)}")

                        correction_reason = st.text_area(
                            "Motiv corectie (optional)",
                            key=f"correction_reason_{doc_id}",
                            height=90,
                            placeholder="Ex: lipsesc date din factura sau suma nu corespunde.",
                        )

                        if st.button("↩️ Trimite la corectie", use_container_width=True):
                            try:
                                correction_response = requests.post(
                                    f"{API_BASE_URL}/documents/{doc_id}/request-manual-correction",
                                    headers=headers,
                                    json={"reason": correction_reason or None},
                                    timeout=10,
                                )
                                if correction_response.status_code in [200, 202]:
                                    st.success("Document trimis la corectie!")
                                    st.rerun()
                                else:
                                    st.error(f"Correction failed: {correction_response.status_code}")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    else:
                        st.info("Actiunile operatorului sunt disponibile doar in status REVIEW.")
                
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
                                                    st.image(image_data, use_container_width=True, caption=f"Page {page_num} Preview")
                                                elif image_data.startswith('data:image'):
                                                    st.image(image_data, use_container_width=True, caption=f"Page {page_num} Preview")
                                                else:
                                                    st.image(base64.b64decode(image_data), use_container_width=True, caption=f"Page {page_num} Preview")
                                            else:
                                                st.image(image_data, use_container_width=True, caption=f"Page {page_num} Preview")
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
                                                st.image(img_response.content, use_container_width=True, caption=f"Page {page_num} Preview")
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
                                            st.image(image_data, use_container_width=True, caption=f"Page {page_num} Preview")
                                        elif image_data.startswith('data:image'):
                                            st.image(image_data, use_container_width=True, caption=f"Page {page_num} Preview")
                                        else:
                                            st.image(base64.b64decode(image_data), use_container_width=True, caption=f"Page {page_num} Preview")
                                    else:
                                        st.image(image_data, use_container_width=True, caption=f"Page {page_num} Preview")
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
                                        st.image(img_response.content, use_container_width=True, caption=f"Page {page_num} Preview")
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
                    st.markdown("### Informații Extrase")
                    
                    # Panel 1: Invoice Data Extraction
                    with st.expander("📋 Date Extrase Factură", expanded=True):
                        if isinstance(extracted, dict) and extracted:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Numărul Facturii:** `{extracted.get('nr_factura', 'N/A')}`")
                                st.write(f"**Furnizor:** {extracted.get('furnizor', 'N/A')}")
                                st.write(f"**Cod Fiscal Furnizor:** {extracted.get('cod_fiscal', 'N/A')}")
                                st.write(f"**Serie Factură:** {extracted.get('serie_factura', 'N/A')}")
                            
                            with col2:
                                st.write(f"**Data Facturii:** {extracted.get('data', 'N/A')}")
                                st.write(f"**Total:** {extracted.get('total', 'N/A')}")
                                st.write(f"**Monedă:** {extracted.get('moneda', 'RON')}")
                                st.write(f"**Status Factură:** {extracted.get('status_factura', 'N/A')}")
                            
                            # Additional invoice details
                            if extracted.get('descriere'):
                                st.write(f"**Descriere:** {extracted.get('descriere')}")
                        else:
                            st.info("Nu au fost extrase date de factură")
                    
                    # Panel 2: Document Classification
                    with st.expander("🏷️ Clasificare Document"):
                        if isinstance(classification, dict) and classification:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Tip Document:** {classification.get('tip_document', 'N/A')}")
                                st.write(f"**Sub-tip:** {classification.get('subtip', 'N/A')}")
                                st.write(f"**Categorie:** {classification.get('categorie', 'N/A')}")
                            
                            with col2:
                                confidence = classification.get('confidence', 0)
                                confidence = confidence if confidence is not None else 0
                                st.metric("Încredere Clasificare", f"{confidence*100:.1f}%")
                                st.write(f"**Model:** {classification.get('model', 'AI')}")
                            
                            if classification.get('caracteristici'):
                                st.write(f"**Caracteristici:** {', '.join(classification.get('caracteristici', []))}")
                        else:
                            st.info("Nu au fost completate date de clasificare")
                    
                    # Panel 3: Nomenclator Suggestions
                    with st.expander("💡 Sugestii Nomenclator"):
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
                                st.write(f"**Cod Nomenclator Sugerat:** `{suggested_code or 'N/A'}`")
                                st.write(f"**Descriere:** {nomenclator_data.get('descriere', 'N/A')}")
                                if suggested_dosar:
                                    st.write(f"**Dosar propus:** {suggested_dosar}")
                                st.write(f"**Incidenţă (%):** {nomenclator_data.get('incidenta', '0')} %")
                            
                            with col2:
                                confidence = nomenclator_data.get('confidence', 0)
                                confidence = confidence if confidence is not None else 0
                                st.metric("Încredere Sugestie", f"{confidence*100:.1f}%")
                            
                            # Alternate suggestions
                            alternatives = nomenclator_data.get('alternative', [])
                            if alternatives:
                                st.write("**Alte Sugestii:**")
                                for alt in alternatives:
                                    alt_confidence = alt.get('confidence', 0)
                                    alt_confidence = alt_confidence if alt_confidence is not None else 0
                                    st.write(f"- `{alt.get('cod')}` - {alt.get('descriere')} ({alt_confidence*100:.1f}%)")
                        else:
                            st.info("Nu sunt disponibile sugestii de nomenclator încă")
                    
                    st.divider()
                
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
                            st.info("Nu exista inca evenimente de audit pentru acest document.")
                    else:
                        st.warning("Audit trail indisponibil momentan.")
                except Exception:
                    st.warning("Audit trail indisponibil momentan.")
                
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
        # SEARCH VIEW
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_query = st.text_input(
                "Search",
                placeholder="Search by title, number, supplier...",
                help="Full-text search across documents"
            )
        
        with col2:
            doc_type = st.selectbox(
                "Type",
                ["All", "INVOICE", "CONTRACT", "REPORT", "OTHER"],
                help="Filter by document type"
            )
        
        with col3:
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
        
        # Search parameters
        search_params = {
            "limit": 20,
            "offset": 0,
        }
        
        if search_query:
            search_params["q"] = search_query
        if doc_type != "All":
            search_params["tip_document"] = doc_type
        if doc_status != "All":
            search_params["status"] = doc_status
        
        # Perform search
        if st.button("Search", type="primary", use_container_width=True):
            try:
                with st.spinner("Searching documents..."):
                    query_string = "&".join([f"{k}={v}" for k, v in search_params.items()])
                    response = requests.get(
                        f"{API_BASE_URL}/documents/search?{query_string}",
                        headers=headers,
                        timeout=10
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
        
        # Display cached search results
        if st.session_state.search_results:
            hits = st.session_state.search_results.get("hits", [])
            total = st.session_state.search_results.get("total_hits", 0)
            
            st.markdown(f"### Results: {len(hits)} of {total} documents")
            
            # Debug info
            with st.expander("🔍 Debug Search Info"):
                st.write(f"**Query:** {search_params}")
                st.write(f"**Total found:** {total}")
                st.write(f"**Shown:** {len(hits)}")
                if not hits:
                    st.warning("Try broader search or check that documents are indexed in Meilisearch")
            
            if hits:
                # Display results as clickable cards
                for doc in hits:
                    with st.container(border=True):
                        doc_id = doc.get("id", "N/A")
                        doc_id_str = str(doc_id)
                        title = doc.get("title", "Untitled")
                        status = doc.get("status", "N/A")
                        status_upper = str(status).upper()
                        doc_type = doc.get("tip_document", "N/A")
                        
                        status_emoji = {
                            "ARCHIVED": "📦",
                            "APPROVED": "✅",
                            "REVIEW": "🕵️",
                            "RETURNED": "↩️",
                            "PROCESSING": "🔄",
                            "CLASSIFIED": "🏷️",
                            "EXTRACTED": "🧾",
                            "VALIDATED": "✓",
                            "PENDING": "⏳",
                            "ERROR": "❌",
                        }
                        
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            if st.button(
                                f"Document: {title}",
                                key=f"view_{doc_id_str}",
                                use_container_width=True,
                                type="secondary"
                            ):
                                # Store as string, will be converted in detail view
                                st.session_state.selected_doc_id = str(doc_id)
                                st.rerun()
                        
                        with col2:
                            st.write(f"{status_emoji.get(status_upper, '❓')} **{status_upper}**")
                        
                        with col3:
                            st.write(f"**{doc_type}**")
            else:
                st.info("No documents found matching your search criteria")

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
