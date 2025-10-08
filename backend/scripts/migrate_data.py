# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Safe data migration helper."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from backend.db import ENGINE

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def apply_migration(migration: Path) -> None:
    sql = migration.read_text(encoding="utf-8")
    with ENGINE.begin() as connection:
        connection.exec_driver_sql(sql)


def backup_database(path: Path) -> Path:
    backup_path = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup_path)
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply SQL migrations safely")
    parser.add_argument(
        "database",
        type=Path,
        default=Path("app.db"),
        nargs="?",
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--migration",
        type=str,
        default="0001_initial.sql",
        help="Migration filename to apply",
    )
    args = parser.parse_args()
    db_path = args.database
    if db_path.exists():
        backup_path = backup_database(db_path)
        print(f"Backup created at {backup_path}")
    migration_path = MIGRATIONS_DIR / args.migration
    if not migration_path.exists():
        msg = f"Migration {migration_path} not found"
        raise FileNotFoundError(msg)
    apply_migration(migration_path)
    print(f"Applied migration {migration_path.name}")


if __name__ == "__main__":
    main()
