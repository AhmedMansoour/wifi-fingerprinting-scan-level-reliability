"""Create a schema-only Android asset without radio maps or scan records."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def create_empty_database(output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite an existing database: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(output) as db:
            db.executescript((ROOT / "schema/empty_database.sql").read_text(encoding="utf-8"))
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("SQLite integrity check failed")
    except Exception:
        output.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "app/src/main/assets/database/wifi_integrity_seed.db")
    args = parser.parse_args()
    create_empty_database(args.output)
    print(f"Created schema-only database: {args.output}")
    print("Import an authorized radio-map ZIP from the app's Radio Maps page before positioning.")


if __name__ == "__main__":
    main()
