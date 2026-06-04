import pandas as pd
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SUPPLIERS_PATH, PRODUCTS_PATH, WAREHOUSES_PATH,
    INVENTORY_PATH, SHIPMENTS_PATH,
    PROCESSED_DATA_PATH, CLEANED_RECORDS_PATH,
)


def _count_jsonl_lines(path: str) -> int:
    if not os.path.exists(path):
        return 0
    count = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def _write_jsonl(path: str, records: list, mode: str = "w"):
    with open(path, mode, encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _safe_float(val, default=0.0) -> float:
    try:
        if pd.isna(val):
            return default
        return float(val)
    except Exception:
        return default


def _safe_int(val, default=0) -> int:
    try:
        if pd.isna(val):
            return default
        return int(val)
    except Exception:
        return default


def _safe_str(val, default="unknown") -> str:
    try:
        if pd.isna(val):
            return default
        return str(val).strip()
    except Exception:
        return default


def _clean_row(i: int, rec: dict) -> dict:
    return {
        "id":                   str(i),
        # Shipment
        "shipment_id":          _safe_str(rec.get("shipment_id"), f"SHP-{i}"),
        "shipment_status":      _safe_str(rec.get("status"), "unknown").lower().replace(" ", "_"),
        "order_date":           _safe_str(rec.get("order_date")),
        "scheduled_delivery":   _safe_str(rec.get("scheduled_delivery_date")),
        "actual_delivery":      _safe_str(rec.get("actual_delivery_date")),
        "delay_days":           _safe_float(rec.get("delay_days")),
        "shipping_mode":        _safe_str(rec.get("shipping_mode")),
        "carrier":              _safe_str(rec.get("carrier")),
        "quantity_units":       _safe_float(rec.get("quantity_units")),
        "shipment_cost_usd":    _safe_float(rec.get("shipment_cost_usd")),
        "is_late":              _safe_int(rec.get("is_late")),
        "late_delivery_risk":   _safe_float(rec.get("late_delivery_risk")),
        "severity":             _safe_str(rec.get("severity"), "low"),
        "risk_score":           _safe_float(rec.get("risk_score")),
        "origin_city":          _safe_str(rec.get("origin_city")),
        "origin_country":       _safe_str(rec.get("origin_country")),
        "destination_city":     _safe_str(rec.get("destination_city")),
        "destination_country":  _safe_str(rec.get("destination_country")),
        # Supplier
        "supplier_id":          _safe_str(rec.get("supplier_id")),
        "supplier_name":        _safe_str(rec.get("supplier_name")),
        "supplier_category":    _safe_str(rec.get("supplier_category")),
        "supplier_region":      _safe_str(rec.get("supplier_region")),
        "risk_tier":            _safe_str(rec.get("risk_tier"), "medium"),
        "on_time_delivery_rate":_safe_float(rec.get("on_time_delivery_rate"), 0.5),
        "defect_rate":          _safe_float(rec.get("defect_rate"), 0.05),
        "reliability_score":    _safe_float(rec.get("reliability_score"), 0.7),
        # Product
        "product_id":           _safe_str(rec.get("product_id")),
        "product_name":         _safe_str(rec.get("product_name")),
        "product_category":     _safe_str(rec.get("product_category")),
        "unit_cost_usd":        _safe_float(rec.get("unit_cost_usd")),
        "weight_kg":            _safe_float(rec.get("weight_kg"), 1.0),
        # Warehouse
        "warehouse_id":         _safe_str(rec.get("destination_warehouse_id")),
        "warehouse_name":       _safe_str(rec.get("warehouse_name")),
        "warehouse_city":       _safe_str(rec.get("warehouse_city")),
        "warehouse_region":     _safe_str(rec.get("warehouse_region")),
        # Inventory (left-joined — may be NaN)
        "stock_level_units":    _safe_float(rec.get("stock_level_units")),
        "days_of_supply":       _safe_float(rec.get("days_of_supply")),
        "stockout_count_30d":   _safe_int(rec.get("stockout_count_30d")),
        "inventory_status":     _safe_str(rec.get("inventory_status"), "unknown"),
        "timestamp":            _safe_str(rec.get("order_date")),
    }


def load_and_clean(mode: str = "incremental") -> list:
    # Read all 5 tables
    suppliers  = pd.read_csv(SUPPLIERS_PATH)
    products   = pd.read_csv(PRODUCTS_PATH)
    warehouses = pd.read_csv(WAREHOUSES_PATH)
    inventory  = pd.read_csv(INVENTORY_PATH)
    shipments  = pd.read_csv(SHIPMENTS_PATH)

    print(f"  Loaded: {len(suppliers)} suppliers, {len(products)} products, "
          f"{len(warehouses)} warehouses, {len(inventory)} inventory, "
          f"{len(shipments)} shipments")

    # Rename before merge to avoid column conflicts
    suppliers = suppliers.rename(columns={
        "category": "supplier_category",
        "country":  "supplier_country",
        "region":   "supplier_region",
    })
    products = products.rename(columns={
        "category": "product_category",
    })
    warehouses = warehouses.rename(columns={
        "warehouse_id": "destination_warehouse_id",
        "city":         "warehouse_city",
        "country":      "warehouse_country",
        "region":       "warehouse_region",
    })
    inventory = inventory.rename(columns={
        "status":       "inventory_status",
        "warehouse_id": "inv_warehouse_id",
    })

    # Join: shipments → suppliers → products → warehouses
    df = shipments.merge(suppliers[["supplier_id","supplier_name","supplier_category",
                                     "supplier_region","on_time_delivery_rate","defect_rate",
                                     "avg_lead_time_days","risk_tier","reliability_score"]],
                         on="supplier_id", how="left")

    df = df.merge(products[["product_id","product_name","product_category",
                              "unit_cost_usd","unit_price_usd","weight_kg"]],
                  on="product_id", how="left")

    df = df.merge(warehouses[["destination_warehouse_id","warehouse_name",
                                "warehouse_city","warehouse_country","warehouse_region"]],
                  on="destination_warehouse_id", how="left")

    # Join inventory on product + warehouse
    inv_slim = inventory[["product_id","inv_warehouse_id","stock_level_units",
                           "days_of_supply","stockout_count_30d","inventory_status"]].copy()
    inv_slim = inv_slim.rename(columns={"inv_warehouse_id": "destination_warehouse_id"})

    df = df.merge(inv_slim, on=["product_id","destination_warehouse_id"], how="left")

    print(f"  Joined dataframe: {len(df)} rows, {len(df.columns)} columns")

    # Incremental: skip already processed
    already_processed = _count_jsonl_lines(CLEANED_RECORDS_PATH)
    if mode == "incremental" and already_processed > 0:
        print(f"  Incremental: skipping {already_processed:,} already processed rows...")
        df = df.iloc[already_processed:]

    if df.empty:
        print("  No new rows to process.")
        return []

    records = df.to_dict(orient="records")
    cleaned = []
    for i, rec in enumerate(records):
        start_id = already_processed if mode == "incremental" else 0
        cleaned.append(_clean_row(start_id + i, rec))

    os.makedirs(PROCESSED_DATA_PATH, exist_ok=True)
    write_mode = "a" if mode == "incremental" else "w"
    _write_jsonl(CLEANED_RECORDS_PATH, cleaned, mode=write_mode)

    total = _count_jsonl_lines(CLEANED_RECORDS_PATH)
    print(f"  {len(cleaned):,} records written  (total in file: {total:,})")
    return cleaned


if __name__ == "__main__":
    load_and_clean(mode="full")
