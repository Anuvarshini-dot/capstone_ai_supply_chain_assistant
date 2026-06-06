import re
import sqlite3
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.client import chat
from config import SQLITE_DB_PATH


_DB_SCHEMA = """
Tables in the supply chain SQLite database:

suppliers(supplier_id, supplier_name, category, country, region,
          on_time_delivery_rate, defect_rate, avg_lead_time_days,
          contract_value_usd, payment_terms, risk_tier, reliability_score, active)

products(product_id, product_name, category, supplier_id,
         unit_cost_usd, unit_price_usd, weight_kg,
         reorder_point_units, safety_stock_days)

warehouses(warehouse_id, warehouse_name, city, country, region,
           capacity_units, current_utilization_pct)

inventory(inventory_id, product_id, warehouse_id,
          stock_level_units, reorder_point_units, avg_daily_demand, days_of_supply,
          last_replenishment_date, stockout_count_30d,
          status)  -- values: healthy, low, critical, stockout

shipments(shipment_id, supplier_id, product_id, destination_warehouse_id,
          origin_city, origin_country, destination_city, destination_country,
          order_date, scheduled_delivery_date, actual_delivery_date,
          delay_days, shipping_mode, carrier,
          status,  -- values: Delivered, In Transit, Delayed, Cancelled
          quantity_units, shipment_cost_usd, is_late, late_delivery_risk,
          severity, risk_score)

Rules:
- Always JOIN to get human-readable names — never return IDs alone.
- inventory stock level = stock_level_units; delivery delay = delay_days.
- Warehouse name search: WHERE warehouse_name LIKE '%Tokyo%'
- inventory.warehouse_id joins to warehouses.warehouse_id
- shipments.destination_warehouse_id joins to warehouses.warehouse_id
"""



class NLSQLAgent:
    name = "nlsql"

    def analyze(self, query: str) -> dict:
        collected_dfs: list = []
        sql_queries:   list = []

        def _run_query(sql: str) -> str:
            sql_queries.append(sql)
            try:
                conn = sqlite3.connect(SQLITE_DB_PATH)
                df   = pd.read_sql_query(sql, conn)
                conn.close()
                collected_dfs.append(df)
                return df.to_string(index=False) if not df.empty else "No results found."
            except Exception as e:
                return f"SQL error: {e}"

        def _extract_sql(text: str) -> str:
            # markdown code block (```sql ... ``` or ``` ... ```)
            m = re.search(r"```(?:sql)?\s*(SELECT\b.*?)```", text, re.DOTALL | re.IGNORECASE)
            if m:
                return m.group(1).strip()
            # bare SELECT statement
            m = re.search(r"(SELECT\b.+)", text, re.DOTALL | re.IGNORECASE)
            if m:
                return m.group(1).strip()
            return ""

        # ── Chat-based SQL loop ──────────────────────────────────────────────
        # Gateway does not support function/tool calling; instead we ask the
        # model to write SQL in a code block, extract it, run it, and loop.
        messages = [
            {"role": "system", "content": (
                f"You are a supply chain data analyst with access to a SQLite database.\n"
                f"To answer questions, write a SQL query inside a ```sql code block.\n"
                f"After seeing the result, write another ```sql block if more data is needed,\n"
                f"or write your final answer (no code block).\n\nSchema:\n{_DB_SCHEMA}"
            )},
            {"role": "user", "content": query},
        ]

        for _ in range(5):
            response = chat(messages)
            messages.append({"role": "assistant", "content": response})

            sql = _extract_sql(response)
            if not sql:
                break  # model gave a final answer — stop looping

            result = _run_query(sql)
            messages.append({
                "role":    "user",
                "content": f"Query result:\n{result}\n\nContinue: write another ```sql block if needed, or give your final answer.",
            })

        # ── Generate final answer from collected data ─────────────────────
        if collected_dfs:
            data_str = "\n\n".join(df.to_string(index=False) for df in collected_dfs)
            answer = chat([
                {"role": "system", "content": "Answer the question using only the provided SQL data. Be concise and factual. Use actual names and numbers — never IDs alone."},
                {"role": "user",   "content": f"Question: {query}\n\nData:\n{data_str}"},
            ])
        else:
            answer = "No data could be retrieved from the database."

        display_facts = self._build_display_facts(collected_dfs)
        sql_entities  = self._extract_entities(collected_dfs)

        total_rows = sum(len(df) for df in collected_dfs)

        return {
            "summary":      re.sub(r"\*+", "", answer.split("\n")[0].strip())[:200],
            "answer":       answer,
            "risk_level":   "medium",
            "confidence":   0.9,
            "findings":     display_facts[:6] if display_facts else ["No structured data returned"],
            "sql_queries":  sql_queries,
            "sql_entities": sql_entities,
            "sql_data":     data_str if collected_dfs else "",
            "rows_returned": total_rows,
        }

    def _build_display_facts(self, dfs: list) -> list:
        """Top 3 rows × first 2 cols from the first query result — shown on the agent card."""
        if not dfs:
            return []
        facts = []
        df = dfs[0]
        for _, row in df.head(3).iterrows():
            for col in list(df.columns)[:2]:
                val   = row[col]
                label = str(col).replace("_", " ").title()
                if isinstance(val, float):
                    is_rate = any(k in col.lower() for k in ("rate", "pct", "score", "defect"))
                    val_str = f"{val:.1%}" if (is_rate and val <= 1) else f"{val:,.2f}"
                elif isinstance(val, int):
                    val_str = f"{val:,}"
                else:
                    val_str = str(val)
                facts.append(f"{label}: {val_str}")
        return facts

    def _extract_entities(self, dfs: list) -> dict:
        """Pull supplier/warehouse/product names from all query results for ChromaDB targeting."""
        entities: dict = {
            "supplier_ids": [], "warehouse_ids": [],
            "supplier_names": [], "warehouse_names": [], "product_names": [],
        }
        for df in dfs:
            txt = df.to_string(index=False)
            entities["supplier_ids"].extend(re.findall(r"\b(SUP-\d+)\b", txt))
            entities["warehouse_ids"].extend(re.findall(r"\b(WH-\d+)\b",  txt))
            for col in df.columns:
                vals = [v for v in df[col].dropna().unique().tolist() if isinstance(v, str)][:3]
                if "supplier_name" in col.lower():
                    entities["supplier_names"].extend(vals)
                elif "warehouse_name" in col.lower():
                    entities["warehouse_names"].extend(vals)
                elif "product_name" in col.lower():
                    entities["product_names"].extend(vals)
        for key in entities:
            entities[key] = list(dict.fromkeys(entities[key]))[:3]
        return entities
