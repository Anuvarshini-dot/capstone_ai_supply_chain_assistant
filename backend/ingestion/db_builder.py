"""
Loads all 5 raw CSVs into a SQLite database for the NL-to-SQL agent.
The database is rebuilt from scratch on every full ingestion run.
"""
import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SUPPLIERS_PATH, PRODUCTS_PATH, WAREHOUSES_PATH,
    INVENTORY_PATH, SHIPMENTS_PATH, SQLITE_DB_PATH,
)


def build_sqlite_db() -> None:
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)

    suppliers  = pd.read_csv(SUPPLIERS_PATH)
    products   = pd.read_csv(PRODUCTS_PATH)
    warehouses = pd.read_csv(WAREHOUSES_PATH)
    inventory  = pd.read_csv(INVENTORY_PATH)
    shipments  = pd.read_csv(SHIPMENTS_PATH)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    suppliers.to_sql("suppliers",   conn, if_exists="replace", index=False)
    products.to_sql("products",     conn, if_exists="replace", index=False)
    warehouses.to_sql("warehouses", conn, if_exists="replace", index=False)
    inventory.to_sql("inventory",   conn, if_exists="replace", index=False)
    shipments.to_sql("shipments",   conn, if_exists="replace", index=False)
    conn.close()

    print(f"  SQLite DB built → {SQLITE_DB_PATH}")
    print(f"  Tables: suppliers({len(suppliers)}), products({len(products)}), "
          f"warehouses({len(warehouses)}), inventory({len(inventory)}), "
          f"shipments({len(shipments)})")


if __name__ == "__main__":
    build_sqlite_db()
