"""
Generate an example sales dataset for testing the Autonomous AI Data Analyst.

Run from the repo root:
    python examples/generate_example_data.py
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

CUSTOMERS = [
    ("C001", "Alice Johnson", "Enterprise"),
    ("C002", "Bob Smith", "SMB"),
    ("C003", "Carol Davis", "Enterprise"),
    ("C004", "Daniel Lee", "Startup"),
    ("C005", "Emily Chen", "Enterprise"),
    ("C006", "Frank Garcia", "SMB"),
    ("C007", "Grace Kim", "Startup"),
    ("C008", "Henry Patel", "Enterprise"),
    ("C009", "Iris Martin", "SMB"),
    ("C010", "Jack Wilson", "Startup"),
]

REGIONS = ["North America", "Europe", "APAC", "LATAM"]
PRODUCTS = [
    ("P-100", "Widget Pro", "Hardware", 199.0),
    ("P-110", "Widget Lite", "Hardware", 89.0),
    ("P-200", "Cloud Sync", "SaaS", 49.0),
    ("P-210", "Cloud Sync Plus", "SaaS", 129.0),
    ("P-300", "Insight Suite", "Analytics", 299.0),
    ("P-310", "Insight Pro", "Analytics", 599.0),
]


def main() -> None:
    out = Path(__file__).parent / "sample_sales.csv"
    start = date.today() - timedelta(days=365)
    rows = []
    for i in range(1, 1201):
        cust = random.choice(CUSTOMERS)
        prod = random.choice(PRODUCTS)
        region = random.choice(REGIONS)
        qty = random.randint(1, 12)
        discount = round(random.choice([0, 0, 0.05, 0.1, 0.15, 0.2]), 2)
        unit_price = prod[3]
        amount = round(unit_price * qty * (1 - discount), 2)
        order_date = start + timedelta(
            days=random.randint(0, 364),
            hours=random.randint(0, 23),
        )
        rows.append({
            "order_id": f"O-{i:05d}",
            "order_date": order_date.isoformat(),
            "customer_id": cust[0],
            "customer_name": cust[1],
            "segment": cust[2],
            "region": region,
            "product_id": prod[0],
            "product_name": prod[1],
            "category": prod[2],
            "unit_price": unit_price,
            "quantity": qty,
            "discount": discount,
            "amount": amount,
        })

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
