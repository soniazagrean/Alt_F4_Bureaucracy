import os

import pytest

from app.services.graph_service import (
    create_document_node,
    create_furnizor_node,
    create_dosar_node,
    link_document_to_dosar,
    get_document_node,
    get_furnizor_by_cui,
)
from app.schemas_graph import DocumentNode, DosarNode


class MockRecord:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


class MockResult:
    def __init__(self, record):
        self._record = record

    def single(self):
        return self._record


class MockTx:
    def __init__(self, executed):
        self.executed = executed

    def run(self, query, **params):
        self.executed.append((query.strip(), params))
        return MockResult(MockRecord({"node": params}))


class MockSession:
    def __init__(self, executed):
        self.executed = executed

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def execute_write(self, work):
        return work(MockTx(self.executed))

    def execute_read(self, work):
        return work(MockTx(self.executed))


@pytest.mark.skipif(
    os.environ.get("NEO4J_URI") is None,
    reason="NEO4j connection URL is not configured",
)
def test_neo4j_connectivity():
    from app.db.neo4j import init_driver, verify_connectivity, close_driver

    try:
        init_driver()
        assert verify_connectivity() is True
    except Exception as exc:
        pytest.skip(f"Neo4j not reachable: {exc}")
    finally:
        close_driver()


def test_init_constraints_is_idempotent(monkeypatch):
    from app.db.neo4j import _driver, init_constraints

    executed = []

    class DummyDriver:
        def session(self):
            return MockSession(executed)

    monkeypatch.setattr("app.db.neo4j._driver", DummyDriver())

    init_constraints()
    assert len(executed) == 5
    for query, params in executed:
        assert query.startswith("CREATE CONSTRAINT IF NOT EXISTS")


def test_create_furnizor_node_is_deduplicated(monkeypatch):
    executed = []
    session = MockSession(executed)
    monkeypatch.setattr("app.services.graph_service.get_neo4j_session", lambda: session)

    first = create_furnizor_node("RO12345678", "Supplier SRL", "RO49AAAA1B31007593840000")
    second = create_furnizor_node("RO12345678", "Supplier SRL", "RO49AAAA1B31007593840000")

    assert first["CUI"] == "RO12345678"
    assert second["CUI"] == "RO12345678"
    assert len(executed) == 2
    assert executed[0][0] == executed[1][0]


def test_link_document_to_dosar(monkeypatch):
    executed = []
    session = MockSession(executed)
    monkeypatch.setattr("app.services.graph_service.get_neo4j_session", lambda: session)

    create_document_node(DocumentNode(id="doc-1", status="PENDING"))
    create_dosar_node(DosarNode(id="dos-1", name="Achizitii/2024/IT/Alpha_SRL", nomenclator_code="III/2/b", year=2024))
    link_document_to_dosar("doc-1", "dos-1")

    assert any("MERGE (doc:Document" in q for q, _ in executed)
    assert any("MERGE (dos:Dosar" in q for q, _ in executed)
    assert any("MERGE (doc)-[r:APARTINE]->(dos)" in q for q, _ in executed)
