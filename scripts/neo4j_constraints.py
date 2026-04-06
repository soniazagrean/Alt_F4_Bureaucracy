from app.db.neo4j import init_driver, init_constraints, close_driver


if __name__ == "__main__":
    init_driver()
    init_constraints()
    close_driver()
    print("Neo4j constraints ensured.")
