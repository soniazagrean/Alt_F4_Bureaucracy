"""
Graph Intelligence — NV-028
Visualise the contract network or the influence graph stored in Neo4j.
Semantic Search filters the visible graph to nodes matching your keyword
and their immediate (1-hop) neighbours.
"""

import os
from typing import Any

import requests
import streamlit as st
from streamlit_agraph import agraph, Config, Edge, Node

API_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")

# ── Colour palette ──────────────────────────────────────────────────────────────
COL = {
    "Person":           "#9CA3AF",
    "Person_risk":      "#EF4444",
    "Company":          "#3B82F6",
    "Contract":         "#22C55E",
    "Furnizor":         "#A78BFA",
    "Dosar":            "#FBBF24",
    "NomenclatorEntry": "#FB923C",
    "Document":         "#60A5FA",
    "default":          "#9CA3AF",
    "match":            "#F97316",
    "edge":             "#64748B",
}
NODE_SIZE = {
    "Person": 22, "Company": 26, "Contract": 20,
    "Furnizor": 22, "Dosar": 22, "NomenclatorEntry": 18, "Document": 20,
}

# ── Page setup ──────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Graph Intelligence", page_icon="\U0001f578", layout="wide")

st.markdown("""
<style>
.legend-row { display:flex; flex-wrap:wrap; gap:6px; margin:6px 0 0; }
.legend-item {
    display:inline-flex; align-items:center; gap:6px;
    background:#1e293b; border:1px solid #334155;
    border-radius:20px; padding:3px 10px;
    font-size:12px; color:#e2e8f0;
}
.legend-dot { width:10px; height:10px; border-radius:50%; flex-shrink:0; }
.search-banner {
    background: linear-gradient(90deg, #1e3a5f 0%, #1e293b 100%);
    border: 1px solid #3b82f6; border-radius: 10px;
    padding: 8px 16px; margin-bottom: 12px;
    color: #bfdbfe; font-size: 14px;
}
</style>
""", unsafe_allow_html=True)

st.title("\U0001f578 Graph Intelligence")
st.caption(
    "Inspect the **Contract network** or **Influence graph** from Neo4j. "
    "Type a keyword in **Semantic Search** to focus on matching nodes and their neighbours."
)

# ── Auth guard ──────────────────────────────────────────────────────────────────
if not st.session_state.get("auth_token"):
    st.info("\U0001f512 Please log in via the **View Documents** page, then come back here.")
    st.stop()

headers: dict[str, str] = {"Authorization": f"Bearer {st.session_state['auth_token']}"}

# ── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("\u2699\ufe0f Controls")
    graph_mode = st.radio("Graph mode", ["Contracts", "Influence"], index=0)

    st.markdown("---")
    st.subheader("\U0001f50d Semantic Search")
    search_query = st.text_input(
        "Search nodes",
        placeholder="e.g. supplier name, person, contract\u2026",
        help=(
            "Filters the graph to nodes whose label or properties contain this keyword, "
            "plus their direct neighbours (1-hop)."
        ),
    ).strip()
    if search_query:
        st.caption(f"Showing matches for **{search_query}** + neighbours.")

    st.markdown("---")
    st.subheader("Filters")
    min_connections = st.slider("Min connections", 1, 10, 1)
    min_admin_companies = st.slider("Risk threshold (admin \u2265)", 1, 10, 3)

    st.markdown("---")
    st.subheader("Legend")
    if graph_mode == "Influence":
        legend_items = [
            (COL["Person"], "Person"),
            (COL["Person_risk"], "Person (\u26a0 risk)"),
            (COL["Company"], "Company"),
            (COL["Contract"], "Contract"),
        ]
    else:
        legend_items = [
            (COL["Document"], "Document"),
            (COL["Furnizor"], "Supplier"),
            (COL["Dosar"], "Folder"),
            (COL["NomenclatorEntry"], "Nomenclator"),
        ]
    if search_query:
        legend_items.append((COL["match"], "Search match"))

    leg_html = '<div class="legend-row">' + "".join(
        f'<span class="legend-item"><span class="legend-dot" style="background:{c}"></span>{lbl}</span>'
        for c, lbl in legend_items
    ) + "</div>"
    st.markdown(leg_html, unsafe_allow_html=True)


# ── Data fetch helpers ──────────────────────────────────────────────────────────

def _fetch_influence_network(min_admin: int) -> dict[str, Any]:
    r = requests.get(
        f"{API_BASE_URL}/api/v1/graph/influence-network",
        params={"min_admin_companies": min_admin},
        headers=headers, timeout=10,
    )
    if r.status_code != 200:
        raise RuntimeError(f"API error {r.status_code}: {r.text[:200]}")
    return r.json()


def _fetch_contract_network() -> dict[str, Any]:
    r = requests.get(
        f"{API_BASE_URL}/api/v1/graph/contract-network",
        headers=headers, timeout=10,
    )
    if r.status_code != 200:
        raise RuntimeError(f"API error {r.status_code}: {r.text[:200]}")
    return r.json()


# ── Graph helpers ───────────────────────────────────────────────────────────────

def _apply_min_degree(
    nodes: list[dict], edges: list[dict], min_deg: int
) -> tuple[list[dict], list[dict]]:
    if min_deg <= 1:
        return nodes, edges
    degree: dict[str, int] = {}
    for e in edges:
        for k in ("source", "target"):
            nid = str(e[k])
            degree[nid] = degree.get(nid, 0) + 1
    allowed = {n["id"] for n in nodes if degree.get(str(n["id"]), 0) >= min_deg}
    return (
        [n for n in nodes if n["id"] in allowed],
        [e for e in edges if e["source"] in allowed and e["target"] in allowed],
    )


def _semantic_search(
    nodes: list[dict], edges: list[dict], query: str
) -> tuple[list[dict], list[dict], set[str]]:
    """
    Return (filtered_nodes, filtered_edges, matched_ids).
    matched_ids are the directly-matching nodes (shown in orange).
    Matched nodes + their 1-hop neighbours are included in the result.
    """
    if not query:
        return nodes, edges, set()

    q = query.lower()
    matched_ids: set[str] = set()

    for node in nodes:
        label = str(node.get("label", "")).lower()
        ntype = str(node.get("type", "")).lower()
        props = node.get("properties") or {}

        if q in label or q in ntype:
            matched_ids.add(str(node["id"]))
            continue
        if any(q in str(v).lower() for v in props.values() if v):
            matched_ids.add(str(node["id"]))

    if not matched_ids:
        return [], [], set()

    # Expand to 1-hop neighbours
    shown: set[str] = set(matched_ids)
    for e in edges:
        s, t = str(e["source"]), str(e["target"])
        if s in matched_ids or t in matched_ids:
            shown.add(s)
            shown.add(t)

    fn = [n for n in nodes if str(n["id"]) in shown]
    fe = [e for e in edges if str(e["source"]) in shown and str(e["target"]) in shown]
    return fn, fe, matched_ids


def _build_nodes(nodes: list[dict], matched_ids: set[str]) -> list[Node]:
    result: list[Node] = []
    for node in nodes:
        nid   = str(node["id"])
        ntype = node.get("type", "")
        label = str(node.get("label") or nid)
        risk  = bool(node.get("risk"))

        if ntype == "Person" and risk:
            label = f"{label} ⚠️"
            color = COL["Person_risk"]
            size  = 34
        elif nid in matched_ids:
            color = COL["match"]
            size  = 30
        else:
            color = COL.get(ntype, COL["default"])
            size  = NODE_SIZE.get(ntype, 22)

        node_font_color = "#E2E8F0" 
        
        result.append(Node(
            id=nid, 
            label=label, 
            color=color, 
            size=size,
            font={"color": node_font_color, "size": 14} 
        ))
        
    return result


def _build_edges(edges: list[dict]) -> list[Edge]:
    return [
        Edge(
            source=str(e["source"]),
            target=str(e["target"]),
            label=str(e.get("label") or e.get("type") or ""),
            color=COL["edge"],
        )
        for e in edges
    ]


# ── Load data ───────────────────────────────────────────────────────────────────
try:
    if graph_mode == "Influence":
        with st.spinner("Loading influence network\u2026"):
            payload = _fetch_influence_network(min_admin_companies)
    else:
        with st.spinner("Loading contract graph\u2026"):
            payload = _fetch_contract_network()
except requests.exceptions.ConnectionError:
    st.error("\u274c Cannot reach the API server. Is FastAPI running?")
    st.stop()
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

raw_nodes = payload.get("nodes", [])
raw_edges = payload.get("edges", [])

if graph_mode == "Influence":
    raw_nodes, raw_edges = _apply_min_degree(raw_nodes, raw_edges, min_connections)

# Apply semantic search filter
nodes, edges, matched_ids = _semantic_search(raw_nodes, raw_edges, search_query)

# ── Stats bar ───────────────────────────────────────────────────────────────────
if search_query:
    st.markdown(
        f'<div class="search-banner">\U0001f50d Semantic search: <strong>{search_query}</strong> \u2014 ' +
        f'<strong>{len(matched_ids)}</strong> direct match(es), <strong>{len(nodes)}</strong> node(s) shown ' +
        f'(including 1-hop neighbours), <strong>{len(edges)}</strong> edge(s)</div>',
        unsafe_allow_html=True,
    )

col_a, col_b, col_c = st.columns(3)
col_a.metric("\U0001f4cd Nodes", len(nodes),
             delta=f"-{len(raw_nodes)-len(nodes)}" if search_query and len(raw_nodes) != len(nodes) else None)
col_b.metric("\U0001f517 Edges", len(edges))
risk_count = sum(1 for n in nodes if n.get("type") == "Person" and n.get("risk"))
col_c.metric("\u26a0\ufe0f Risk flags", risk_count if graph_mode == "Influence" else "—")

if search_query and not nodes:
    st.warning(f'No nodes matched "{search_query}". Try a broader keyword.')
    st.stop()
elif not nodes:
    st.info("No graph data for the current filters." if graph_mode == "Influence" else "No contract graph data yet.")
    st.stop()

# ── Graph visualisation ─────────────────────────────────────────────────────────
agraph(
    nodes=_build_nodes(nodes, matched_ids),
    edges=_build_edges(edges),
    config=Config(
        width=1200,
        height=680,
        directed=True,
        physics=True,
        nodeHighlightBehavior=True,
        highlightColor="#FBBF24",
        collapsible=True,
    ),
)

# ── Search results table (only when searching) ──────────────────────────────────
if search_query and matched_ids:
    st.markdown("---")
    st.subheader(f"\U0001f50e Matched nodes ({len(matched_ids)})")
    st.caption("These are the nodes whose label or properties contained your search term.")

    rows = []
    for node in nodes:
        if str(node["id"]) not in matched_ids:
            continue
        props = node.get("properties") or {}
        row: dict = {
            "Label":  node.get("label", ""),
            "Type":   node.get("type", ""),
            "ID":     str(node["id"])[:16],
        }
        # Add up to 3 useful properties
        for k, v in list(props.items())[:3]:
            if v is not None:
                row[k] = str(v)[:50]
        rows.append(row)

    if rows:
        try:
            import pandas as pd
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )
        except ImportError:
            for row in rows:
                st.write(row)
