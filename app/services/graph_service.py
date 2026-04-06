from typing import Any, Dict, Optional

from app.db.neo4j import get_neo4j_session
from app.schemas_graph import DocumentNode, DosarNode, FurnizorNode, NomenclatorEntryNode

REL_APARTINE = "APARTINE"
REL_EMIS_DE = "EMIS_DE"
REL_IN_CATEGORY = "IN_CATEGORY"
REL_RELATED_TO = "RELATED_TO"


def _to_dict(node: Any) -> Optional[Dict[str, Any]]:
    if node is None:
        return None
    try:
        return dict(node)
    except Exception:
        return {k: node[k] for k in node}


def _prepare_props(data: Any, keys_to_pop: Optional[list[str]] = None) -> Dict[str, Any]:
    if isinstance(data, (DocumentNode, DosarNode, FurnizorNode, NomenclatorEntryNode)):
        payload = data.dict(exclude_none=True)
    elif isinstance(data, dict):
        payload = {k: v for k, v in data.items() if v is not None}
    else:
        payload = dict(data)

    if keys_to_pop:
        for key in keys_to_pop:
            payload.pop(key, None)
    return payload


def create_document_node(doc_data: Any) -> Dict[str, Any]:
    payload = _prepare_props(doc_data, keys_to_pop=["id"])
    document_id = str(doc_data["id"] if isinstance(doc_data, dict) else getattr(doc_data, "id"))
    query = """
    MERGE (doc:Document {id: $id})
    SET doc += $props
    RETURN doc AS node
    """

    with get_neo4j_session() as session:
        result = session.execute_write(lambda tx: tx.run(query, id=document_id, props=payload).single())
        return _to_dict(result.get("node"))


def create_furnizor_node(cui: str, name: str, iban: Optional[str] = None) -> Dict[str, Any]:
    query = """
    MERGE (f:Furnizor {CUI: $CUI})
    SET f.name = $name, f.iban = $iban
    RETURN f AS node
    """

    with get_neo4j_session() as session:
        result = session.execute_write(
            lambda tx: tx.run(query, CUI=cui, name=name, iban=iban).single()
        )
        return _to_dict(result.get("node"))


def create_dosar_node(dosar_data: Any) -> Dict[str, Any]:
    payload = _prepare_props(dosar_data, keys_to_pop=["id"])
    dosar_id = str(dosar_data["id"] if isinstance(dosar_data, dict) else getattr(dosar_data, "id"))
    query = """
    MERGE (d:Dosar {id: $id})
    SET d += $props
    RETURN d AS node
    """

    with get_neo4j_session() as session:
        result = session.execute_write(lambda tx: tx.run(query, id=dosar_id, props=payload).single())
        return _to_dict(result.get("node"))


def create_nomenclator_node(entry_data: Any) -> Dict[str, Any]:
    payload = _prepare_props(entry_data, keys_to_pop=["code"])
    code = str(entry_data["code"] if isinstance(entry_data, dict) else getattr(entry_data, "code"))
    query = """
    MERGE (n:NomenclatorEntry {code: $code})
    SET n += $props
    RETURN n AS node
    """

    with get_neo4j_session() as session:
        result = session.execute_write(lambda tx: tx.run(query, code=code, props=payload).single())
        return _to_dict(result.get("node"))


def link_document_to_dosar(doc_id: str, dosar_id: str) -> Optional[Dict[str, Any]]:
    query = """
    MERGE (doc:Document {id: $doc_id})
    MERGE (dos:Dosar {id: $dosar_id})
    MERGE (doc)-[r:APARTINE]->(dos)
    RETURN r AS node
    """

    with get_neo4j_session() as session:
        result = session.execute_write(
            lambda tx: tx.run(query, doc_id=str(doc_id), dosar_id=str(dosar_id)).single()
        )
        return _to_dict(result.get("node"))


def link_document_to_furnizor(doc_id: str, cui: str) -> Optional[Dict[str, Any]]:
    query = """
    MERGE (doc:Document {id: $doc_id})
    MERGE (f:Furnizor {CUI: $CUI})
    MERGE (doc)-[r:EMIS_DE]->(f)
    RETURN r AS node
    """

    with get_neo4j_session() as session:
        result = session.execute_write(
            lambda tx: tx.run(query, doc_id=str(doc_id), CUI=cui).single()
        )
        return _to_dict(result.get("node"))


def get_document_node(doc_id: str) -> Optional[Dict[str, Any]]:
    query = """
    MATCH (doc:Document {id: $id})
    RETURN doc AS node
    LIMIT 1
    """

    with get_neo4j_session() as session:
        result = session.execute_read(lambda tx: tx.run(query, id=str(doc_id)).single())
        record = result
        return _to_dict(record.get("node") if record else None)


def get_furnizor_by_cui(cui: str) -> Optional[Dict[str, Any]]:
    query = """
    MATCH (f:Furnizor {CUI: $CUI})
    RETURN f AS node
    LIMIT 1
    """

    with get_neo4j_session() as session:
        result = session.execute_read(lambda tx: tx.run(query, CUI=cui).single())
        record = result
        return _to_dict(record.get("node") if record else None)
