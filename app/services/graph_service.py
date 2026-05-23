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


def _neo4j_element_id(node: Any) -> Optional[str]:
    if node is None:
        return None
    element_id = getattr(node, "element_id", None)
    if element_id:
        return str(element_id)
    node_id = getattr(node, "id", None)
    if node_id is not None:
        return str(node_id)
    return None


def _label_from_props(props: Dict[str, Any], keys: list[str], fallback: str) -> str:
    for key in keys:
        value = props.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return fallback


def _person_label(props: Dict[str, Any], fallback: str) -> str:
    first = props.get("first_name") or props.get("firstName")
    last = props.get("last_name") or props.get("lastName")
    if first or last:
        return f"{first or ''} {last or ''}".strip()
    return _label_from_props(
        props,
        ["full_name", "name", "username", "email", "id"],
        fallback,
    )


def _company_label(props: Dict[str, Any], fallback: str) -> str:
    return _label_from_props(
        props,
        ["name", "legal_name", "company_name", "CUI", "id"],
        fallback,
    )


def _contract_label(props: Dict[str, Any], fallback: str) -> str:
    return _label_from_props(
        props,
        ["title", "contract_number", "number", "id"],
        fallback,
    )


def get_influence_network(min_admin_companies: int = 3) -> Dict[str, list[Dict[str, Any]]]:
    query = """
    MATCH (p:Person)-[:ADMINISTERS]->(c:Company)
    OPTIONAL MATCH (p)-[:ADMINISTERS]->(otherCompany:Company)
    OPTIONAL MATCH (c)-[:WON_CONTRACT]->(k:Contract)
    WITH p, c, k, count(DISTINCT otherCompany) AS admin_count
    WHERE admin_count >= $min_admin_companies
    RETURN p AS person, c AS company, k AS contract, admin_count AS admin_count
    """

    with get_neo4j_session() as session:
        records = session.execute_read(
            lambda tx: list(
                tx.run(
                    query,
                    min_admin_companies=min_admin_companies,
                    timeout=NEO4J_QUERY_TIMEOUT_SEC,
                )
            )
        )

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: Dict[tuple[str, str, str], Dict[str, Any]] = {}

    for record in records:
        person = record.get("person")
        company = record.get("company")
        contract = record.get("contract")
        admin_count = int(record.get("admin_count") or 0)

        person_id = _neo4j_element_id(person)
        company_id = _neo4j_element_id(company)
        contract_id = _neo4j_element_id(contract) if contract else None

        if person and person_id:
            person_props = _to_dict(person) or {}
            person_label = _person_label(person_props, f"Person {person_id[-6:]}")
            nodes.setdefault(
                person_id,
                {
                    "id": person_id,
                    "label": person_label,
                    "type": "Person",
                    "properties": person_props,
                    "admin_count": admin_count,
                    "risk": admin_count >= min_admin_companies,
                },
            )
            nodes[person_id]["admin_count"] = max(
                admin_count, int(nodes[person_id].get("admin_count") or 0)
            )
            nodes[person_id]["risk"] = nodes[person_id]["admin_count"] >= min_admin_companies

        if company and company_id:
            company_props = _to_dict(company) or {}
            company_label = _company_label(company_props, f"Company {company_id[-6:]}")
            nodes.setdefault(
                company_id,
                {
                    "id": company_id,
                    "label": company_label,
                    "type": "Company",
                    "properties": company_props,
                },
            )

        if contract and contract_id:
            contract_props = _to_dict(contract) or {}
            contract_label = _contract_label(contract_props, f"Contract {contract_id[-6:]}")
            nodes.setdefault(
                contract_id,
                {
                    "id": contract_id,
                    "label": contract_label,
                    "type": "Contract",
                    "properties": contract_props,
                },
            )

        if person_id and company_id:
            edge_key = (person_id, company_id, "ADMINISTERS")
            edges.setdefault(
                edge_key,
                {
                    "id": f"{person_id}->{company_id}:ADMINISTERS",
                    "source": person_id,
                    "target": company_id,
                    "type": "ADMINISTERS",
                    "label": "ADMINISTERS",
                },
            )

        if company_id and contract_id:
            edge_key = (company_id, contract_id, "WON_CONTRACT")
            edges.setdefault(
                edge_key,
                {
                    "id": f"{company_id}->{contract_id}:WON_CONTRACT",
                    "source": company_id,
                    "target": contract_id,
                    "type": "WON_CONTRACT",
                    "label": "WON_CONTRACT",
                },
            )

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }


def get_contract_network() -> Dict[str, list[Dict[str, Any]]]:
    query = """
    MATCH (doc:Document)
    OPTIONAL MATCH (doc)-[:EMIS_DE]->(f:Furnizor)
    OPTIONAL MATCH (doc)-[:APARTINE]->(dos:Dosar)
    OPTIONAL MATCH (dos)-[:IN_CATEGORY]->(n:NomenclatorEntry)
    RETURN doc AS doc, f AS furnizor, dos AS dosar, n AS nomenclator
    ORDER BY doc.id
    """

    with get_neo4j_session() as session:
        records = session.execute_read(
            lambda tx: list(
                tx.run(
                    query,
                    timeout=NEO4J_QUERY_TIMEOUT_SEC,
                )
            )
        )

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: Dict[tuple[str, str, str], Dict[str, Any]] = {}

    for record in records:
        doc = record.get("doc")
        furnizor = record.get("furnizor")
        dosar = record.get("dosar")
        nomenclator = record.get("nomenclator")

        doc_id = _neo4j_element_id(doc)
        if not doc_id:
            continue

        doc_props = _to_dict(doc) or {}
        doc_label = _label_from_props(doc_props, ["nr_factura", "title", "document_number", "id"], f"Document {doc_id[-6:]}")
        nodes.setdefault(
            doc_id,
            {
                "id": doc_id,
                "label": doc_label,
                "type": "Document",
                "properties": doc_props,
            },
        )

        if furnizor:
            furnizor_id = _neo4j_element_id(furnizor) or _clean_value(_to_dict(furnizor).get("CUI") if _to_dict(furnizor) else None)
            furnizor_props = _to_dict(furnizor) or {}
            if furnizor_id:
                nodes.setdefault(
                    furnizor_id,
                    {
                        "id": furnizor_id,
                        "label": _label_from_props(furnizor_props, ["name", "CUI", "id"], f"Furnizor {furnizor_id[-6:]}") ,
                        "type": "Furnizor",
                        "properties": furnizor_props,
                    },
                )
                edges.setdefault(
                    (doc_id, furnizor_id, REL_EMIS_DE),
                    {
                        "id": f"{doc_id}->{furnizor_id}:EMIS_DE",
                        "source": doc_id,
                        "target": furnizor_id,
                        "type": REL_EMIS_DE,
                        "label": REL_EMIS_DE,
                    },
                )

        if dosar:
            dosar_id = _neo4j_element_id(dosar)
            dosar_props = _to_dict(dosar) or {}
            if dosar_id:
                nodes.setdefault(
                    dosar_id,
                    {
                        "id": dosar_id,
                        "label": _label_from_props(dosar_props, ["name", "title", "id"], f"Dosar {dosar_id[-6:]}") ,
                        "type": "Dosar",
                        "properties": dosar_props,
                    },
                )
                edges.setdefault(
                    (doc_id, dosar_id, REL_APARTINE),
                    {
                        "id": f"{doc_id}->{dosar_id}:APARTINE",
                        "source": doc_id,
                        "target": dosar_id,
                        "type": REL_APARTINE,
                        "label": REL_APARTINE,
                    },
                )

        if dosar and nomenclator:
            dosar_id = _neo4j_element_id(dosar)
            nomen_id = _neo4j_element_id(nomenclator)
            nomen_props = _to_dict(nomenclator) or {}
            if nomen_id:
                nodes.setdefault(
                    nomen_id,
                    {
                        "id": nomen_id,
                        "label": _label_from_props(nomen_props, ["code", "name", "id"], f"Nomenclator {nomen_id[-6:]}") ,
                        "type": "NomenclatorEntry",
                        "properties": nomen_props,
                    },
                )
                edges.setdefault(
                    (dosar_id, nomen_id, REL_IN_CATEGORY),
                    {
                        "id": f"{dosar_id}->{nomen_id}:IN_CATEGORY",
                        "source": dosar_id,
                        "target": nomen_id,
                        "type": REL_IN_CATEGORY,
                        "label": REL_IN_CATEGORY,
                    },
                )

    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


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


def enrich_furnizor_with_anaf(cui: str, extracted_name: str) -> dict:
    """
    Validate a Furnizor CUI against the ANAF registry, update its Neo4j node
    with official data, and return discrepancy indicators.

    Returns:
        {
          "anaf_data": dict,
          "name_mismatch": bool,
          "inactive_company": bool,
          "name_similarity": float,
        }
    """
    from app.services.anaf_service import validate_cui, name_similarity as _sim
    from datetime import date

    anaf = validate_cui(cui)
    result: dict = {
        "anaf_data": anaf,
        "name_mismatch": False,
        "inactive_company": False,
        "name_similarity": 1.0,
    }

    if not anaf.get("found"):
        return result

    if not anaf.get("is_active", True):
        result["inactive_company"] = True

    anaf_name = anaf.get("company_name", "")
    if extracted_name and anaf_name:
        sim = _sim(extracted_name, anaf_name)
        result["name_similarity"] = sim
        result["name_mismatch"] = sim < 0.6

    # Persist official ANAF fields onto the Furnizor node in Neo4j
    props = {
        "anaf_name": anaf_name,
        "anaf_is_active": anaf.get("is_active", True),
        "anaf_address": anaf.get("address", ""),
        "anaf_last_checked": date.today().isoformat(),
    }
    update_query = """
    MERGE (f:Furnizor {CUI: $CUI})
    SET f += $props
    RETURN f
    """
    try:
        with get_neo4j_session() as session:
            session.execute_write(
                lambda tx: tx.run(update_query, CUI=str(cui), props=props).single()
            )
    except Exception as exc:
        logger.warning("Failed to enrich Furnizor %s in Neo4j: %s", cui, exc)

    return result


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
