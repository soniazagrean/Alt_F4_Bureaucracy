from typing import Optional, Any
import logging

try:
    from neo4j import GraphDatabase
    from neo4j import Driver, Session
except ImportError:  # pragma: no cover
    GraphDatabase = None  # type: ignore
    Driver = Any  # type: ignore
    Session = Any  # type: ignore

from app.config import settings

logger = logging.getLogger(__name__)
_driver: Optional[Driver] = None


def init_driver() -> Driver:
    global _driver
    if _driver is None:
        if GraphDatabase is None:
            raise ImportError(
                "Neo4j driver package is not installed. Install 'neo4j' to use Neo4j integration."
            )
        logger.info("Initializing Neo4j driver for %s", settings.NEO4J_URI)
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
    return _driver


def get_neo4j_driver() -> Driver:
    if _driver is None:
        return init_driver()
    return _driver


def get_neo4j_session(database: str = None) -> Session:
    driver = get_neo4j_driver()
    if database:
        return driver.session(database=database)
    return driver.session()


def verify_connectivity() -> bool:
    driver = get_neo4j_driver()
    driver.verify_connectivity()
    logger.info("Neo4j connectivity verified")
    return True


def init_constraints() -> None:
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Furnizor) REQUIRE n.CUI IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Document) REQUIRE n.nr_factura IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:NomenclatorEntry) REQUIRE n.code IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Dosar) REQUIRE n.id IS UNIQUE",
    ]

    with get_neo4j_session() as session:
        for query in constraints:
            session.execute_write(lambda tx, q=query: tx.run(q))
            logger.info("Ensured Neo4j constraint: %s", query)


def close_driver() -> None:
    global _driver
    if _driver is not None:
        logger.info("Closing Neo4j driver")
        _driver.close()
        _driver = None
