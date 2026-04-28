import os
from typing import Any

import requests
import streamlit as st
from streamlit_agraph import agraph, Config, Edge, Node

API_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")

COLOR_PERSON = "#9CA3AF"
COLOR_PERSON_RISK = "#EF4444"
COLOR_COMPANY = "#3B82F6"
COLOR_CONTRACT = "#22C55E"
COLOR_EDGE = "#94A3B8"


st.set_page_config(page_title="Visual Graph Intelligence", layout="wide")

st.title("Visual Graph Intelligence")
st.caption("Detect influence networks and potential conflicts of interest.")


def _fetch_influence_network(min_admin_companies: int, headers: dict[str, str]) -> dict[str, Any]:
    response = requests.get(
        f"{API_BASE_URL}/api/v1/graph/influence-network",
        params={"min_admin_companies": min_admin_companies},
        headers=headers,
        timeout=10,
    )
    if response.status_code != 200:
        raise RuntimeError(f"API error {response.status_code}: {response.text[:200]}")
    return response.json()


def _apply_min_degree_filter(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    min_connections: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if min_connections <= 1:
        return nodes, edges

    degree: dict[str, int] = {}
    for edge in edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        degree[source] = degree.get(source, 0) + 1
        degree[target] = degree.get(target, 0) + 1

    allowed = {node["id"] for node in nodes if degree.get(str(node["id"]), 0) >= min_connections}
    filtered_nodes = [node for node in nodes if node["id"] in allowed]
    filtered_edges = [
        edge
        for edge in edges
        if edge.get("source") in allowed and edge.get("target") in allowed
    ]
    return filtered_nodes, filtered_edges


def _build_agraph_nodes(nodes: list[dict[str, Any]]) -> list[Node]:
    result: list[Node] = []
    for node in nodes:
        node_id = str(node.get("id"))
        node_type = node.get("type")
        label = str(node.get("label") or node_id)
        risk = bool(node.get("risk"))

        if node_type == "Person" and risk:
            label = f"{label} \u26a0\ufe0f"

        color = COLOR_PERSON
        size = 22
        if node_type == "Company":
            color = COLOR_COMPANY
            size = 24
        elif node_type == "Contract":
            color = COLOR_CONTRACT
            size = 20
        elif node_type == "Person" and risk:
            color = COLOR_PERSON_RISK
            size = 36

        result.append(Node(id=node_id, label=label, color=color, size=size))
    return result


def _build_agraph_edges(edges: list[dict[str, Any]]) -> list[Edge]:
    result: list[Edge] = []
    for edge in edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        label = str(edge.get("label") or edge.get("type") or "")
        result.append(Edge(source=source, target=target, label=label, color=COLOR_EDGE))
    return result


st.sidebar.header("Filters")
min_connections = st.sidebar.slider("Minimum connections", 1, 10, 1)
min_admin_companies = st.sidebar.slider("Risk threshold (administers >=)", 1, 10, 3)

headers: dict[str, str] = {}
if token := st.session_state.get("auth_token"):
    headers["Authorization"] = f"Bearer {token}"
else:
    st.sidebar.info("Login in the documents view to access protected data.")

try:
    with st.spinner("Loading influence network..."):
        payload = _fetch_influence_network(min_admin_companies, headers)
except requests.exceptions.ConnectionError:
    st.error("Cannot reach the API server.")
    st.stop()
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

nodes = payload.get("nodes", [])
edges = payload.get("edges", [])

nodes, edges = _apply_min_degree_filter(nodes, edges, min_connections)

risk_count = sum(1 for node in nodes if node.get("type") == "Person" and node.get("risk"))

col1, col2, col3 = st.columns(3)
col1.metric("Nodes", str(len(nodes)))
col2.metric("Edges", str(len(edges)))
col3.metric("Risk flags", str(risk_count))

if not nodes:
    st.info("No influence network data available for the current filters.")
    st.stop()

agraph(
    nodes=_build_agraph_nodes(nodes),
    edges=_build_agraph_edges(edges),
    config=Config(
        width=1200,
        height=650,
        directed=True,
        physics=True,
        nodeHighlightBehavior=True,
        highlightColor="#F59E0B",
        collapsible=True,
    ),
)
