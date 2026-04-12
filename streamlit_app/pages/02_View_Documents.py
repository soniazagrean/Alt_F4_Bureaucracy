"""
NV-025: Document View & Details Page

Features:
- Search & filter documents
- View full document details
- Display extracted invoice data
- Show document status timeline
- Related documents
"""

import streamlit as st
import requests
import json
from datetime import datetime

# Page config
st.set_page_config(page_title="View Documents", page_icon="📄", layout="wide")

st.title("View Documents")
st.markdown("Search, filter, and view processed documents with extracted data.")

# Configuration
API_BASE_URL = "http://fastapi:8000"

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
                
                # Header
                st.markdown(f"## {doc.get('title', 'Document')}")
                
                # Status badge
                status = doc.get("status", "UNKNOWN")
                status_color = {
                    "ARCHIVED": "🟢",
                    "PROCESSING": "🟡",
                    "ERROR": "🔴",
                    "VALIDATED": "🟢",
                }
                
                st.markdown(
                    f"{status_color.get(status, '⚪')} **Status: {status}** | "
                    f"📋 Type: {doc.get('document_type', 'N/A')} | "
                    f"📅 Created: {doc.get('created_at', 'N/A')}"
                )
                
                st.divider()
                
                # Download button for PDF
                doc_id = doc.get("id")
                if doc_id:
                    col1, col2 = st.columns([0.7, 0.3])
                    with col2:
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
                
                # Show page previews
                pages = doc.get("pages", [])
                if pages:
                    st.markdown("### Document Pages Preview")
                    
                    if len(pages) > 1:
                        # Multiple pages - show as carousel with tabs
                        page_tabs = st.tabs([f"Page {p.get('page_number', i+1)}" for i, p in enumerate(pages)])
                        for page_tab, page in zip(page_tabs, pages):
                            with page_tab:
                                page_num = page.get('page_number', 1)
                                st.markdown(f"**Page {page_num}**")
                                
                                # Show text content if available (OCR)
                                text_content = page.get("text_content", "")
                                if text_content:
                                    with st.expander(f"Text Content (Page {page_num})"):
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
                        
                        text_content = page.get("text_content", "")
                        if text_content:
                            with st.expander(f"Extracted Text Content"):
                                st.text_area(
                                    "Text content",
                                    value=text_content,
                                    height=250,
                                    disabled=True,
                                    label_visibility="collapsed"
                                )
                
                st.divider()
                
                # Main details
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Document Number", doc.get("document_number", "N/A"))
                
                with col2:
                    st.metric("Amount", f"{doc.get('amount', 'N/A')} {doc.get('currency', '')}")
                
                with col3:
                    st.metric("Document Type", doc.get("document_type", "N/A"))
                
                # Extracted data
                if doc.get("extracted_data") or doc.get("description"):
                    st.markdown("### Extracted Data")
                    
                    extracted = doc.get("extracted_data") or {}
                    
                    if isinstance(extracted, dict):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Invoice Number:** {extracted.get('nr_factura', 'N/A')}")
                            st.write(f"**Supplier:** {extracted.get('furnizor', 'N/A')}")
                            st.write(f"**Fiscal Code:** {extracted.get('cod_fiscal', 'N/A')}")
                        
                        with col2:
                            st.write(f"**Date:** {extracted.get('data', 'N/A')}")
                            st.write(f"**Total:** {extracted.get('total', 'N/A')}")
                            st.write(f"**Status:** {extracted.get('status_factura', 'N/A')}")
                    
                    if doc.get("description"):
                        st.markdown(f"**Description:** {doc.get('description')}")
                
                # Timeline
                st.markdown("### Processing Timeline")
                
                timeline_data = {
                    "Created": doc.get("created_at", "N/A"),
                    "Processed": doc.get("updated_at", "N/A"),
                    "Archived": doc.get("archived_at", "N/A"),
                }
                
                for event, timestamp in timeline_data.items():
                    if timestamp and timestamp != "N/A":
                        st.write(f"✓ **{event}:** {timestamp}")
                
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
                ["All", "ARCHIVED", "PROCESSING", "ERROR", "VALIDATED"],
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
            
            if hits:
                # Display results as clickable cards
                for doc in hits:
                    with st.container(border=True):
                        doc_id = doc.get("id", "N/A")
                        doc_id_str = str(doc_id)
                        title = doc.get("title", "Untitled")
                        status = doc.get("status", "N/A")
                        doc_type = doc.get("tip_document", "N/A")
                        
                        status_emoji = {
                            "ARCHIVED": "📦",
                            "PROCESSING": "🔄",
                            "ERROR": "❌",
                            "VALIDATED": "✓",
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
                            st.write(f"{status_emoji.get(status, '❓')} **{status}**")
                        
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
