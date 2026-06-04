import re

SUPPLY_CHAIN_KEYWORDS = [
    "supplier", "shipment", "inventory", "warehouse", "delivery", "delay",
    "transport", "logistics", "order", "stock", "demand", "freight",
    "port", "route", "vendor", "procurement", "distribution", "cargo",
    "disruption", "risk", "bottleneck", "forecast", "shortage", "cost",
    "fulfillment", "depot", "dispatch", "carrier", "lead", "time",
]

PII_PATTERNS = [
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
    r'\b\d{3}-\d{2}-\d{4}\b',
]

MIN_LENGTH = 5
MAX_LENGTH = 500


class ValidationError(Exception):
    pass


def validate_query(query: str) -> str:
    query = query.strip()

    if len(query) < MIN_LENGTH:
        raise ValidationError(f"Query too short. Minimum {MIN_LENGTH} characters.")

    if len(query) > MAX_LENGTH:
        raise ValidationError(f"Query too long. Maximum {MAX_LENGTH} characters.")

    for pattern in PII_PATTERNS:
        if re.search(pattern, query):
            raise ValidationError(
                "Query contains sensitive personal information. Please remove it."
            )

    return query
