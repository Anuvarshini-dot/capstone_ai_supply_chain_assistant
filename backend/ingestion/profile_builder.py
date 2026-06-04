"""
Builds aggregated profile documents for suppliers and warehouses.
These are embedded alongside shipment events so agents can answer
entity-level questions (e.g. "who is the most reliable supplier?")
from pre-aggregated summaries rather than sampling random shipments.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SUPPLIERS_PATH, PRODUCTS_PATH, WAREHOUSES_PATH,
    INVENTORY_PATH, SHIPMENTS_PATH,
)


# ── Supplier profiles ─────────────────────────────────────────────────────────

def _supplier_profile_text(row: pd.Series, shipments: pd.DataFrame, inventory: pd.DataFrame) -> str:
    sid   = row["supplier_id"]
    sname = row["supplier_name"]

    s = shipments[shipments["supplier_id"] == sid]
    total     = len(s)
    delayed   = int((s["delay_days"] > 0).sum())
    cancelled = int((s["status"].str.lower() == "cancelled").sum())
    on_time   = total - delayed - cancelled
    avg_delay = round(s["delay_days"].mean(), 1) if total > 0 else 0
    max_delay = int(s["delay_days"].max()) if total > 0 else 0
    delay_pct = round(delayed / total * 100, 1) if total > 0 else 0

    mode_counts = s["shipping_mode"].value_counts()
    top_mode    = mode_counts.index[0] if len(mode_counts) > 0 else "N/A"

    top_wh = s["destination_warehouse_id"].value_counts().head(3).index.tolist()

    # Inventory impact — inventory records for products supplied by this supplier
    products_of_supplier = shipments[shipments["supplier_id"] == sid]["product_id"].unique()
    inv_records = inventory[inventory["product_id"].isin(products_of_supplier)]
    total_inv   = len(inv_records)
    at_risk_inv = int((inv_records["status"].isin(["critical", "stockout"])).sum())
    inv_pct     = round(at_risk_inv / total_inv * 100, 1) if total_inv > 0 else 0
    avg_days_supply = round(inv_records["days_of_supply"].mean(), 1) if total_inv > 0 else 0

    return (
        f"SUPPLIER PROFILE: {sname} ({sid})\n"
        f"Category: {row['category']} | Region: {row['region']} | "
        f"Risk Tier: {row['risk_tier'].upper()}\n"
        f"Reliability Score: {row['reliability_score']} | "
        f"On-Time Rate: {row['on_time_delivery_rate']} | "
        f"Defect Rate: {row['defect_rate']}\n\n"
        f"SHIPMENT PERFORMANCE ({total} total shipments):\n"
        f"  On-Time: {on_time} ({round(on_time/total*100,1) if total else 0}%) | "
        f"Delayed: {delayed} ({delay_pct}%) | Cancelled: {cancelled}\n"
        f"  Average Delay: {avg_delay} days | Maximum Delay: {max_delay} days\n"
        f"  Most Used Shipping Mode: {top_mode}\n"
        f"  Top Destination Warehouses: {', '.join(top_wh) if top_wh else 'N/A'}\n\n"
        f"INVENTORY IMPACT:\n"
        f"  Products supplied: {len(products_of_supplier)}\n"
        f"  Destination inventory at risk (critical/stockout): {at_risk_inv} of {total_inv} ({inv_pct}%)\n"
        f"  Average days of supply at destination: {avg_days_supply} days"
    )


def build_supplier_profiles() -> list:
    suppliers  = pd.read_csv(SUPPLIERS_PATH)
    shipments  = pd.read_csv(SHIPMENTS_PATH)
    inventory  = pd.read_csv(INVENTORY_PATH)

    chunks = []
    for _, row in suppliers.iterrows():
        text = _supplier_profile_text(row, shipments, inventory)
        chunks.append({
            "id":   f"profile_supplier_{row['supplier_id']}",
            "text": text,
            "metadata": {
                "doc_type":           "supplier_profile",
                "supplier_id":        str(row["supplier_id"]),
                "supplier_name":      str(row["supplier_name"]),
                "supplier_category":  str(row["category"]),
                "supplier_region":    str(row["region"]),
                "risk_tier":          str(row["risk_tier"]),
                "reliability_score":  float(row["reliability_score"]),
                "on_time_rate":       float(row["on_time_delivery_rate"]),
                "defect_rate":        float(row["defect_rate"]),
            }
        })

    print(f"  Built {len(chunks)} supplier profile documents")
    return chunks


# ── Warehouse + inventory profiles ───────────────────────────────────────────

def _warehouse_profile_text(row: pd.Series, inventory: pd.DataFrame,
                             shipments: pd.DataFrame, suppliers: pd.DataFrame,
                             products: pd.DataFrame) -> str:
    wid   = row["warehouse_id"]
    wname = row["warehouse_name"]

    inv = inventory[inventory["warehouse_id"] == wid]
    total_products = len(inv)
    healthy  = int((inv["status"] == "healthy").sum())
    low      = int((inv["status"] == "low").sum())
    critical = int((inv["status"] == "critical").sum())
    stockout = int((inv["status"] == "stockout").sum())
    avg_days = round(inv["days_of_supply"].mean(), 1) if total_products > 0 else 0
    total_stockouts_30d = int(inv["stockout_count_30d"].sum())

    at_risk = inv[inv["status"].isin(["critical", "stockout"])].sort_values("days_of_supply")
    at_risk_names = []
    for _, ir in at_risk.head(5).iterrows():
        pname = products[products["product_id"] == ir["product_id"]]["product_name"].values
        name  = pname[0] if len(pname) > 0 else ir["product_id"]
        at_risk_names.append(
            f"{name} — {ir['status'].upper()} ({ir['days_of_supply']:.0f} days supply, "
            f"{ir['stockout_count_30d']} stockouts in 30d)"
        )

    incoming = shipments[shipments["destination_warehouse_id"] == wid]
    total_incoming = len(incoming)
    incoming_suppliers = incoming["supplier_id"].unique()
    sup_risk = suppliers[suppliers["supplier_id"].isin(incoming_suppliers)]["risk_tier"]
    high_risk_count = int((sup_risk == "high").sum())
    avg_incoming_delay = round(incoming["delay_days"].mean(), 1) if total_incoming > 0 else 0
    delayed_count = int((incoming["delay_days"] > 0).sum())

    at_risk_block = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(at_risk_names)) or "  None"

    return (
        f"WAREHOUSE PROFILE: {wname} ({wid})\n"
        f"Region: {row['region']} | City: {row['city']}, {row['country']}\n"
        f"Capacity: {row['capacity_units']:,} units | "
        f"Utilization: {round(row['current_utilization_pct']*100, 0):.0f}%\n\n"
        f"INVENTORY STATUS ({total_products} products stocked):\n"
        f"  Healthy: {healthy} | Low: {low} | Critical: {critical} | Stockout: {stockout}\n"
        f"  Average Days of Supply: {avg_days} days\n"
        f"  Total Stockout Incidents (last 30d): {total_stockouts_30d}\n\n"
        f"MOST AT-RISK PRODUCTS:\n{at_risk_block}\n\n"
        f"INCOMING SUPPLY QUALITY ({total_incoming} shipments):\n"
        f"  Unique Suppliers: {len(incoming_suppliers)} | "
        f"High-Risk Suppliers: {high_risk_count}\n"
        f"  Delayed Shipments: {delayed_count} | "
        f"Average Incoming Delay: {avg_incoming_delay} days"
    )


def build_warehouse_profiles() -> list:
    warehouses = pd.read_csv(WAREHOUSES_PATH)
    inventory  = pd.read_csv(INVENTORY_PATH)
    shipments  = pd.read_csv(SHIPMENTS_PATH)
    suppliers  = pd.read_csv(SUPPLIERS_PATH)
    products   = pd.read_csv(PRODUCTS_PATH)   # read once, passed to every row

    chunks = []
    for _, row in warehouses.iterrows():
        text = _warehouse_profile_text(row, inventory, shipments, suppliers, products)
        inv  = inventory[inventory["warehouse_id"] == row["warehouse_id"]]
        chunks.append({
            "id":   f"profile_warehouse_{row['warehouse_id']}",
            "text": text,
            "metadata": {
                "doc_type":           "warehouse_profile",
                "warehouse_id":       str(row["warehouse_id"]),
                "warehouse_name":     str(row["warehouse_name"]),
                "warehouse_city":     str(row["city"]),
                "warehouse_region":   str(row["region"]),
                "critical_count":     int((inv["status"] == "critical").sum()),
                "stockout_count":     int((inv["status"] == "stockout").sum()),
                "avg_days_of_supply": round(float(inv["days_of_supply"].mean()), 1) if len(inv) > 0 else 0.0,
                "total_products":     int(len(inv)),
            }
        })

    print(f"  Built {len(chunks)} warehouse profile documents")
    return chunks
