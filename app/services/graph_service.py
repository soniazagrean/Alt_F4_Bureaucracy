from typing import Any, Dict, Optional
import logging

from app.db.database import SessionLocal
from app.db.neo4j import get_neo4j_session
from app.schemas_graph import DocumentNode, DosarNode, FurnizorNode, NomenclatorEntryNode

logger = logging.getLogger(__name__)

REL_APARTINE = "APARTINE"
REL_EMIS_DE = "EMIS_DE"
REL_IN_CATEGORY = "IN_CATEGORY"
REL_RELATED_TO = "RELATED_TO"
NEO4J_QUERY_TIMEOUT_SEC = 5


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


def link_dosar_to_nomenclator(dosar_id: str, code: str) -> Optional[Dict[str, Any]]:
    query = """
    MERGE (dos:Dosar {id: $dosar_id})
    MERGE (n:NomenclatorEntry {code: $code})
    MERGE (dos)-[r:IN_CATEGORY]->(n)
    RETURN r AS node
    """

    with get_neo4j_session() as session:
        result = session.execute_write(
            lambda tx: tx.run(query, dosar_id=str(dosar_id), code=str(code)).single()
        )
        return _to_dict(result.get("node"))


def _normalize_extracted_data(entries: list) -> Dict[str, Any]:
    extracted = {}
    for entry in entries:
        key = getattr(entry, "field_name", None)
        if not key:
            continue
        extracted[key.lower()] = getattr(entry, "field_value", None)
    return extracted


def _clean_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return str(value)


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def populate_graph_for_document(document_id: str) -> None:
    from app.models.document import Document, ExtractedData

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.warning("populate_graph_for_document: document %s not found", document_id)
            return

        extracted_entries = (
            db.query(ExtractedData)
            .filter(ExtractedData.document_id == document_id)
            .all()
        )
        extracted = _normalize_extracted_data(extracted_entries)

        doc_type = (
            doc.document_type.value
            if getattr(doc, "document_type", None) is not None and hasattr(doc.document_type, "value")
            else (str(doc.document_type) if doc.document_type is not None else None)
        )
        status = (
            doc.status.value
            if getattr(doc, "status", None) is not None and hasattr(doc.status, "value")
            else (str(doc.status) if doc.status is not None else None)
        )

        invoice_number = extracted.get("nr_factura") or doc.invoice_number or doc.document_number
        invoice_date = (
            doc.document_date.isoformat()
            if getattr(doc, "document_date", None)
            else extracted.get("data")
        )
        total_value = doc.amount if doc.amount is not None else _coerce_float(extracted.get("total"))

        document_node = DocumentNode(
            id=str(doc.id),
            nr_factura=invoice_number,
            tip_document=doc_type,
            data=invoice_date,
            total=total_value,
            status=status,
            fraud_score=getattr(doc, "fraud_score", None),
        )

        create_document_node(document_node)

        cui = _clean_value(extracted.get("cui"))
        furnizor_name = _clean_value(extracted.get("furnizor"))
        iban = _clean_value(extracted.get("iban"))

        if cui:
            create_furnizor_node(cui, furnizor_name or "", iban)
            link_document_to_furnizor(str(doc.id), cui)

        cod_nomenclator = _clean_value(extracted.get("cod_nomenclator"))
        termen_pastrare = _clean_value(extracted.get("termen_pastrare"))
        if cod_nomenclator:
            create_nomenclator_node({"code": cod_nomenclator, "termen_pastrare": termen_pastrare})

        dosar_propus = _clean_value(extracted.get("dosar_propus"))
        if dosar_propus:
            dosar_payload = {"id": dosar_propus, "name": dosar_propus}
            if cod_nomenclator:
                dosar_payload["nomenclator_code"] = cod_nomenclator

            create_dosar_node(dosar_payload)
            link_document_to_dosar(str(doc.id), dosar_propus)

            if cod_nomenclator:
                link_dosar_to_nomenclator(dosar_propus, cod_nomenclator)

    except Exception as exc:
        logger.exception("populate_graph_for_document(%s) failed: %s", document_id, exc)
    finally:
        db.close()


def _related_record_to_dict(record: Any) -> Dict[str, Any]:
    doc_node = _to_dict(record.get("doc"))
    relation_types = list(record.get("relation_types") or [])
    return {
        "id": doc_node.get("id") if doc_node else None,
        "nr_factura": doc_node.get("nr_factura") if doc_node else None,
        "tip_document": doc_node.get("tip_document") if doc_node else None,
        "data": doc_node.get("data") if doc_node else None,
        "total": doc_node.get("total") if doc_node else None,
        "status": doc_node.get("status") if doc_node else None,
        "furnizor": record.get("furnizor"),
        "dosar": record.get("dosar"),
        "relation_types": relation_types,
    }


def get_related_by_dosar(doc_id: str, skip: int, limit: int) -> tuple[list[dict], int]:
    data_query = """
    MATCH (doc:Document {id: $id})-[:APARTINE]->(:Dosar)<-[:APARTINE]-(related:Document)
    WHERE related.id <> $id
    OPTIONAL MATCH (related)-[:EMIS_DE]->(f:Furnizor)
    OPTIONAL MATCH (related)-[:APARTINE]->(d:Dosar)
    RETURN related AS doc, ["same_dosar"] AS relation_types, f.name AS furnizor, d.id AS dosar
    ORDER BY related.id
    SKIP $skip
    LIMIT $limit
    """

    count_query = """
    MATCH (doc:Document {id: $id})-[:APARTINE]->(:Dosar)<-[:APARTINE]-(related:Document)
    WHERE related.id <> $id
    RETURN count(DISTINCT related) AS total_count
    """

    with get_neo4j_session() as session:
        records = session.execute_read(
            lambda tx: list(
                tx.run(
                    data_query,
                    id=str(doc_id),
                    skip=skip,
                    limit=limit,
                    timeout=NEO4J_QUERY_TIMEOUT_SEC,
                )
            )
        )
        count_record = session.execute_read(
            lambda tx: tx.run(
                count_query,
                id=str(doc_id),
                timeout=NEO4J_QUERY_TIMEOUT_SEC,
            ).single()
        )

    results = [_related_record_to_dict(record) for record in records]
    total_count = int(count_record.get("total_count") if count_record else 0)
    return results, total_count


def get_related_by_furnizor(doc_id: str, skip: int, limit: int) -> tuple[list[dict], int]:
    data_query = """
    MATCH (doc:Document {id: $id})-[:EMIS_DE]->(:Furnizor)<-[:EMIS_DE]-(related:Document)
    WHERE related.id <> $id
    OPTIONAL MATCH (related)-[:EMIS_DE]->(f:Furnizor)
    OPTIONAL MATCH (related)-[:APARTINE]->(d:Dosar)
    RETURN related AS doc, ["same_furnizor"] AS relation_types, f.name AS furnizor, d.id AS dosar
    ORDER BY related.id
    SKIP $skip
    LIMIT $limit
    """

    count_query = """
    MATCH (doc:Document {id: $id})-[:EMIS_DE]->(:Furnizor)<-[:EMIS_DE]-(related:Document)
    WHERE related.id <> $id
    RETURN count(DISTINCT related) AS total_count
    """

    with get_neo4j_session() as session:
        records = session.execute_read(
            lambda tx: list(
                tx.run(
                    data_query,
                    id=str(doc_id),
                    skip=skip,
                    limit=limit,
                    timeout=NEO4J_QUERY_TIMEOUT_SEC,
                )
            )
        )
        count_record = session.execute_read(
            lambda tx: tx.run(
                count_query,
                id=str(doc_id),
                timeout=NEO4J_QUERY_TIMEOUT_SEC,
            ).single()
        )

    results = [_related_record_to_dict(record) for record in records]
    total_count = int(count_record.get("total_count") if count_record else 0)
    return results, total_count


def get_all_related(doc_id: str, skip: int, limit: int) -> tuple[list[dict], int]:
    data_query = """
    CALL {
        MATCH (doc:Document {id: $id})-[:APARTINE]->(:Dosar)<-[:APARTINE]-(related:Document)
        WHERE related.id <> $id
        RETURN related AS doc, "same_dosar" AS rel_type
        UNION
        MATCH (doc:Document {id: $id})-[:EMIS_DE]->(:Furnizor)<-[:EMIS_DE]-(related:Document)
        WHERE related.id <> $id
        RETURN related AS doc, "same_furnizor" AS rel_type
    }
    WITH doc, collect(DISTINCT rel_type) AS relation_types
    OPTIONAL MATCH (doc)-[:EMIS_DE]->(f:Furnizor)
    OPTIONAL MATCH (doc)-[:APARTINE]->(d:Dosar)
    RETURN doc, relation_types, f.name AS furnizor, d.id AS dosar
    ORDER BY doc.id
    SKIP $skip
    LIMIT $limit
    """

    count_query = """
    CALL {
        MATCH (doc:Document {id: $id})-[:APARTINE]->(:Dosar)<-[:APARTINE]-(related:Document)
        WHERE related.id <> $id
        RETURN related AS doc
        UNION
        MATCH (doc:Document {id: $id})-[:EMIS_DE]->(:Furnizor)<-[:EMIS_DE]-(related:Document)
        WHERE related.id <> $id
        RETURN related AS doc
    }
    RETURN count(DISTINCT doc) AS total_count
    """

    with get_neo4j_session() as session:
        records = session.execute_read(
            lambda tx: list(
                tx.run(
                    data_query,
                    id=str(doc_id),
                    skip=skip,
                    limit=limit,
                    timeout=NEO4J_QUERY_TIMEOUT_SEC,
                )
            )
        )
        count_record = session.execute_read(
            lambda tx: tx.run(
                count_query,
                id=str(doc_id),
                timeout=NEO4J_QUERY_TIMEOUT_SEC,
            ).single()
        )

    results = [_related_record_to_dict(record) for record in records]
    total_count = int(count_record.get("total_count") if count_record else 0)
    return results, total_count
