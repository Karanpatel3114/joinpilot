"""Customer open items (receivables), the input for aging analysis.

Each accounting document has 1 to `max_lines_per_document` lines. The due date
is the baseline date plus the payment days, as in most ERP systems.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pyarrow as pa

from joinpilot.config import SynthSettings
from joinpilot.synth.money import money_array
from joinpilot.synth.orders import popularity
from joinpilot.synth.rng import stream

FIRST_DOCUMENT_NUMBER = 1_400_000_000
COMPANY_CODE = "1000"
PAYMENT_TERMS = (np.array([0, 14, 30, 45, 60, 90]), np.array([0.1, 0.2, 0.35, 0.1, 0.15, 0.1]))
MEAN_AGE_DAYS = 75


def make_open_items(seed: int, n: int, customers: pa.Table, settings: SynthSettings) -> pa.Table:
    """Generate exactly `n` open item lines for customers in the master."""
    rng = stream(seed, "open_items")
    customer_ids = customers.column("customer_id").to_pylist()

    lines_per_doc = rng.integers(1, settings.max_lines_per_document + 1, size=n)
    doc_of_line = np.repeat(np.arange(n), lines_per_doc)[:n]
    line_numbers = np.concatenate([np.arange(1, k + 1) for k in lines_per_doc])[:n]
    n_docs = int(doc_of_line[-1]) + 1 if n else 0

    max_age = (settings.reference_date - settings.open_item_start).days
    ages = np.minimum(rng.exponential(MEAN_AGE_DAYS, size=n_docs).astype(np.int64), max_age)
    doc_dates = [settings.reference_date - timedelta(days=int(a)) for a in ages]
    baseline_shift = rng.integers(0, 6, size=n_docs)
    doc_customer = rng.choice(len(customer_ids), size=n_docs, p=popularity(rng, len(customer_ids)))
    doc_terms = rng.choice(PAYMENT_TERMS[0], size=n_docs, p=PAYMENT_TERMS[1])
    doc_currency = np.where(rng.random(n_docs) < settings.eur_share, "EUR", "USD")
    amounts = np.maximum(np.round(rng.lognormal(np.log(250_000), 1.0, size=n)), 1_000)

    return pa.table(
        {
            "company_code": [COMPANY_CODE] * n,
            "customer_id": [customer_ids[doc_customer[d]] for d in doc_of_line],
            "fiscal_year": pa.array([doc_dates[d].year for d in doc_of_line], pa.int32()),
            "document_no": [str(FIRST_DOCUMENT_NUMBER + int(d)) for d in doc_of_line],
            "line_no": pa.array(line_numbers, pa.int32()),
            "document_date": pa.array([doc_dates[d] for d in doc_of_line], pa.date32()),
            "baseline_date": pa.array(
                [doc_dates[d] + timedelta(days=int(baseline_shift[d])) for d in doc_of_line],
                pa.date32(),
            ),
            "payment_days": pa.array([int(doc_terms[d]) for d in doc_of_line], pa.int32()),
            "amount": money_array(amounts.astype(np.int64)),
            "currency": [str(doc_currency[d]) for d in doc_of_line],
        }
    )
