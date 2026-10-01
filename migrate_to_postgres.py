#!/usr/bin/env python3
"""
Move the JSON collections in data/ into PostgreSQL. Run once, after setting
DATABASE_URL.

    DATABASE_URL=postgresql://... python migrate_to_postgres.py          # dry run
    DATABASE_URL=postgresql://... python migrate_to_postgres.py --write  # do it

It is safe to run twice: each collection is upserted by name, so a second run
overwrites with the same content rather than duplicating anything. The JSON
files are left exactly where they are — nothing is deleted, so a rollback is
just unsetting DATABASE_URL.
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import db

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SKIP = {"sessions"}          # sessions live in their own table, never as a document


def main() -> int:
    write = "--write" in sys.argv

    if not db.configured():
        print("DATABASE_URL is not set. Nothing to migrate into.")
        return 1

    ok, msg = db.init()
    print(f"Schema: {msg}")
    if not ok:
        return 1

    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    if not files:
        print(f"No JSON collections found in {DATA_DIR}.")
        return 0

    existing = {d["name"] for d in db.list_documents()}
    moved = skipped = failed = 0

    for path in files:
        name = os.path.splitext(os.path.basename(path))[0]
        if name in SKIP:
            print(f"  skip      {name:16s} (has its own table)")
            skipped += 1
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                body = json.load(f)
        except Exception as exc:
            print(f"  UNREADABLE {name:16s} {exc}")
            failed += 1
            continue

        rows = len(body) if isinstance(body, list) else (
            len(body.get("users", body.get("plans", body.get("offers", body)))) 
            if isinstance(body, dict) else 0)
        verb = "overwrite" if name in existing else "insert"
        print(f"  {verb:9s} {name:16s} {os.path.getsize(path):>7,} bytes  ~{rows} entries")

        if write:
            try:
                db.write_document(name, body)
                moved += 1
            except Exception as exc:
                print(f"             FAILED: {exc}")
                failed += 1

    print()
    if not write:
        print(f"Dry run — {len(files) - skipped} collections would move. "
              f"Re-run with --write to do it.")
    else:
        print(f"Moved {moved} collections. {failed} failed. JSON files left untouched.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
