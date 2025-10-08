# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Convenience entrypoint for applying SQL migrations with backup."""

from __future__ import annotations

import argparse
from pathlib import Path

from .scripts.migrate_data import MIGRATIONS_DIR, apply_migration, backup_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply all migrations to the app database")
    parser.add_argument(
        "database",
        type=Path,
        nargs="?",
        default=Path("app.db"),
        help="Path to SQLite database file",
    )
    args = parser.parse_args()
    db_path = args.database

    if db_path.exists():
        backup_path = backup_database(db_path)
        print(f"Backup created at {backup_path}")

    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migrations:
        print("No migrations found")
        return

    for migration in migrations:
        print(f"Applying {migration.name}")
        apply_migration(migration)

    print("Migrations applied successfully")


if __name__ == "__main__":
    main()
