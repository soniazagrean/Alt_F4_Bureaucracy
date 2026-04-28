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
                    st.markdown("### Quick Preview")
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

                    try:
                        alert_resp = requests.get(f"{API_BASE_URL}/documents/{doc_id}/alerts", headers=headers)
                        if alert_resp.status_code == 200:
                            alerts = alert_resp.json()
                            if alerts:
                                for alert in alerts:
                                    # Folosim un expander roșu pentru alerte critice
                                    with st.expander(f"⚠️ Anomaly: {alert['anomaly_type']}", expanded=True):
                                        st.write(f"**Description:** {alert['description']}")
                                        st.write(f"**Risk Level:** {alert['risk_level'].upper()}")
                            else:
                                st.success("No suspicious anomalies detected.")
                    except:
                        st.caption("Alerts service is currently down.")

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
                            for related_doc in related_items:
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
                                            key=f"related_open_{doc_id}_{related_doc.get('id')}",
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
        search_tab, archive_tab = st.tabs(["Document Search", "Archive Browser"])

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

            if st.button("Search", type="primary", use_container_width=True):
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
                st.markdown(f"### Results: {len(hits)} of {total} documents")

                with st.expander("🔍 Debug Search Info"):
                    st.write(f"**Search params:** {search_params}")
                    st.write(f"**Total found:** {total}")
                    st.write(f"**Shown:** {len(hits)}")
                    if not hits:
                        st.warning("Try broader search or check that documents are indexed in Meilisearch")

                if hits:
                    for doc in hits:
                        with st.container(border=True):
                            doc_id = doc.get("id", "N/A")
                            doc_id_str = str(doc_id)
                            title = doc.get("title", "Untitled")
                            status = doc.get("status", "N/A")
                            status_upper = str(status).upper()
                            doc_type = doc.get("tip_document", "N/A")
                            f_val = doc.get("fraud_score", 0.0) or 0.0
                            if f_val > 0.7 or status_upper == "RETURNED":
                                alert_text = "🚨 High risk of fraud" if f_val > 0.7 else "↩ Returned for correction"
                                st.markdown(f"<p style='color:#ff4b4b; font-weight:bold; margin-bottom:5px;'>{alert_text}</p>", unsafe_allow_html=True)
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
                                    type="secondary",
                                ):
                                    st.session_state.selected_doc_id = str(doc_id)
                                    st.rerun()
                                detail_bits = []
                                doc_number = doc.get("invoice_number") or doc.get("nr_factura") or doc.get("document_number")
                                if doc_number:
                                    detail_bits.append(f"Invoice: {doc_number}")
                                if doc.get("furnizor"):
                                    detail_bits.append(f"Furnizor: {doc.get('furnizor')}")
                                if doc.get("data"):
                                    detail_bits.append(str(doc.get("data")))
                                if detail_bits:
                                    st.caption(" · ".join(detail_bits))
                            with col2:
                                st.write(f"{status_emoji.get(status_upper, '❓')} **{status_upper}**")
                            with col3:
                                st.write(f"**{doc_type}**")
                else:
                    st.info("No documents found matching your search criteria")

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
