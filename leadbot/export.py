"""Export collected leads to CSV: python -m leadbot.export leads.db > leads.csv"""
from __future__ import annotations

import csv
import sys
from dataclasses import asdict, fields

from .core import Lead, Store


def export_csv(store: Store, out) -> int:
    writer = csv.DictWriter(out, fieldnames=[f.name for f in fields(Lead)])
    writer.writeheader()
    leads = store.list_leads()
    for lead in leads:
        writer.writerow(asdict(lead))
    return len(leads)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m leadbot.export <path-to-db>")
    export_csv(Store(sys.argv[1]), sys.stdout)
