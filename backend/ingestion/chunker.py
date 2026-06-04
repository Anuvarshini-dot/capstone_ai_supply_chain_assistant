import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PROCESSED_DATA_PATH, CLEANED_RECORDS_PATH, CHUNKS_PATH


def _read_jsonl(path: str) -> list:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _write_jsonl(path: str, records: list, mode: str = "w"):
    with open(path, mode, encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def record_to_chunk(rec: dict) -> str:
    """Convert one joined supply chain record into a natural language sentence for embedding."""
    delay       = float(rec.get("delay_days", 0))
    stock       = float(rec.get("stock_level_units", 0))
    days_supply = float(rec.get("days_of_supply", 0))
    cost        = float(rec.get("shipment_cost_usd", 0))

    inv_status = rec.get("inventory_status", "unknown")
    stockouts  = int(rec.get("stockout_count_30d", 0))

    return (
        f"Shipment {rec.get('shipment_id', 'N/A')}: "
        f"Supplier '{rec.get('supplier_name', 'N/A')}' "
        f"({rec.get('supplier_category', 'N/A')}, {rec.get('supplier_region', 'N/A')}, "
        f"risk tier: {rec.get('risk_tier', 'N/A')}, "
        f"reliability: {float(rec.get('reliability_score', 0)):.2f}, "
        f"on-time rate: {float(rec.get('on_time_delivery_rate', 0)):.2f}, "
        f"defect rate: {float(rec.get('defect_rate', 0)):.3f}). "
        f"Product: '{rec.get('product_name', 'N/A')}' "
        f"(Category: {rec.get('product_category', 'N/A')}, "
        f"cost: ${float(rec.get('unit_cost_usd', 0)):.2f}, "
        f"weight: {float(rec.get('weight_kg', 0)):.1f}kg). "
        f"Route: {rec.get('origin_city', 'N/A')}, {rec.get('origin_country', 'N/A')} "
        f"→ {rec.get('destination_city', 'N/A')}, {rec.get('destination_country', 'N/A')}. "
        f"Warehouse: {rec.get('warehouse_name', 'N/A')} ({rec.get('warehouse_region', 'N/A')}). "
        f"Shipment status: {rec.get('shipment_status', 'N/A')}. "
        f"Shipping mode: {rec.get('shipping_mode', 'N/A')} via {rec.get('carrier', 'N/A')}. "
        f"Delivery delay: {delay:.0f} days. "
        f"Late delivery risk: {float(rec.get('late_delivery_risk', 0)):.2f}. "
        f"Quantity: {int(rec.get('quantity_units', 0))} units at ${cost:.2f} total. "
        f"Inventory at destination warehouse: {stock:.0f} units "
        f"({days_supply:.0f} days of supply, status: {inv_status}, "
        f"stockouts in last 30 days: {stockouts}). "
        f"Risk severity: {rec.get('severity', 'N/A')}. "
        f"Risk score: {float(rec.get('risk_score', 0)):.3f}. "
        f"Order date: {rec.get('order_date', 'N/A')}."
    )


def _record_to_chunk_dict(rec: dict) -> dict:
    return {
        "id":   str(rec["id"]),
        "text": record_to_chunk(rec),
        "metadata": {
            "doc_type":              "shipment",
            # Supplier
            "supplier_id":           str(rec.get("supplier_id", "unknown")),
            "supplier_name":         str(rec.get("supplier_name", "unknown")),
            "supplier_category":     str(rec.get("supplier_category", "unknown")),
            "supplier_region":       str(rec.get("supplier_region", "unknown")),
            "risk_tier":             str(rec.get("risk_tier", "medium")),
            "on_time_delivery_rate": float(rec.get("on_time_delivery_rate", 0.5)),
            "defect_rate":           float(rec.get("defect_rate", 0.05)),
            "reliability_score":     float(rec.get("reliability_score", 0.7)),
            # Product
            "product_id":            str(rec.get("product_id", "unknown")),
            "product_name":          str(rec.get("product_name", "unknown")),
            "product_category":      str(rec.get("product_category", "unknown")),
            "weight_kg":             float(rec.get("weight_kg", 1.0)),
            # Warehouse
            "warehouse_id":          str(rec.get("warehouse_id", "unknown")),
            "warehouse_name":        str(rec.get("warehouse_name", "unknown")),
            "warehouse_city":        str(rec.get("warehouse_city", "unknown")),
            "warehouse_region":      str(rec.get("warehouse_region", "unknown")),
            # Shipment
            "shipment_status":       str(rec.get("shipment_status", "unknown")),
            "shipping_mode":         str(rec.get("shipping_mode", "unknown")),
            "delay_days":            float(rec.get("delay_days", 0)),
            "late_delivery_risk":    float(rec.get("late_delivery_risk", 0)),
            "is_late":               int(rec.get("is_late", 0)),
            "severity":              str(rec.get("severity", "low")),
            "risk_score":            float(rec.get("risk_score", 0)),
            "origin_city":           str(rec.get("origin_city", "unknown")),
            "destination_city":      str(rec.get("destination_city", "unknown")),
            # Inventory
            "stock_level_units":     float(rec.get("stock_level_units", 0)),
            "days_of_supply":        float(rec.get("days_of_supply", 0)),
            "stockout_count_30d":    int(rec.get("stockout_count_30d", 0)),
            "inventory_status":      str(rec.get("inventory_status", "unknown")),
            # Time
            "timestamp":             str(rec.get("order_date", "unknown")),
        }
    }


def build_chunks(records: list = None, mode: str = "incremental") -> list:
    os.makedirs(PROCESSED_DATA_PATH, exist_ok=True)

    if mode == "full":
        if records is None:
            records = _read_jsonl(CLEANED_RECORDS_PATH)
        new_chunks = [_record_to_chunk_dict(rec) for rec in records]
        _write_jsonl(CHUNKS_PATH, new_chunks, mode="w")
        print(f"Full mode: built {len(new_chunks):,} chunks -> {CHUNKS_PATH}")
        return new_chunks

    if not records:
        print("Incremental: no new records to chunk.")
        return []

    new_chunks = [_record_to_chunk_dict(rec) for rec in records]
    _write_jsonl(CHUNKS_PATH, new_chunks, mode="a")
    print(f"Incremental: {len(new_chunks):,} new chunks appended -> {CHUNKS_PATH}")
    return new_chunks


if __name__ == "__main__":
    build_chunks(mode="full")
