import streamlit as st

st.set_page_config(page_title="Alt_F4_Bureaucracy", layout="wide")

st.title("🏛️ Alt_F4_Bureaucracy")
st.subheader("Hackathon Project Dashboard")

st.markdown("""
## 📋 Services Status

This is the main Streamlit dashboard for the Alt_F4_Bureaucracy hackathon project.

### Available Services:
- **FastAPI** - REST API (port 8000)
- **Celery Worker** - Background task processing
- **Celery Beat** - Task scheduling
- **PostgreSQL** - Relational database (port 5432)
- **Neo4j** - Graph database (port 7474)
- **Redis** - Cache & message broker (port 6379)
- **MinIO** - Object storage (port 9000)
- **MeiliSearch** - Search engine (port 7700)
- **Streamlit** - This dashboard (port 8501)
""")

st.success("✅ All services are running!")

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Services Running", "9")

with col2:
    st.metric("Status", "Healthy")

with col3:
    st.metric("Environment", "Development")
