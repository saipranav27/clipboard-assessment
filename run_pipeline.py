#!/usr/bin/env python3
"""Daily pipeline: scrape website -> pull CRM -> match -> queue proposals for review.

Never writes to the CRM. Writes happen only from the review app after approval.

Usage:
  BH_TOKEN=... python run_pipeline.py            # normal run
  BH_TOKEN=... python run_pipeline.py --dry-run  # print proposals, don't touch the queue
"""
import argparse
import json
import os
import sys
import uuid
from collections import Counter

from bh import config, store
from bh.crm import CRM
from bh.matcher import build_proposals
from bh.scraper import Scraper


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--parent-id", default=os.environ.get("BH_PARENT_ID"))
    args = ap.parse_args(argv)

    started = store.now()
    run_id = started.replace(":", "").replace("-", "")[:15] + "-" + uuid.uuid4().hex[:4]

    locations, scrape_errors = Scraper().scrape()
    print(f"[scrape] {len(locations)} locations, {len(scrape_errors)} errors")
    for e in scrape_errors:
        print("   !", e)
    if len(locations) < 5:
        # A broken scrape would make every Bellhaven account look orphaned. Refuse.
        print("[abort] too few locations scraped; refusing to generate proposals", file=sys.stderr)
        return 2

    crm = CRM()
    accounts = crm.list_accounts()
    fields = crm.detect_fields(accounts)
    missing = [k for k, v in fields.items() if v is None and k not in ("care", "website", "phone")]
    print(f"[crm] {len(accounts)} accounts; field map: {fields}")
    if missing:
        print(f"[crm] WARNING: fields not found in data: {missing}")

    proposals, report = build_proposals(locations, accounts, fields, args.parent_id, scrape_errors)
    report["locations"] = locations
    print(f"[match] Bellhaven parent: {report['bellhaven_parent']['id']} "
          f"{report['bellhaven_parent']['name']!r}; matched {len(report['matches'])}/{len(locations)}")
    print("[match] proposals by kind:", dict(Counter(p["kind"] for p in proposals)))

    config.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    (config.SNAPSHOT_DIR / f"{run_id}.json").write_text(
        json.dumps({"run_id": run_id, "report": report, "proposals": proposals}, indent=2, default=str))

    if args.dry_run:
        for p in proposals:
            print(f"  - [{p['kind']}] ({p['confidence']}) {p['title']}")
        return 0

    con = store.connect()
    stats = store.upsert_proposals(con, run_id, proposals)
    store.record_run(con, run_id, started, stats, report)
    print(f"[queue] {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
