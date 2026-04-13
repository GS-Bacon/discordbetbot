#!/usr/bin/env python3
"""Delete the SQLite database files to reset the bot state."""
from __future__ import annotations

import sys
from pathlib import Path

DB_GLOBS = ["data/*.db", "data/*.db-journal", "data/*.db-wal", "data/*.db-shm"]

root = Path(__file__).parent.parent

removed = []
for pattern in DB_GLOBS:
    for p in root.glob(pattern):
        p.unlink()
        removed.append(p)

if removed:
    for p in removed:
        print(f"Removed: {p}")
    print(f"\n{len(removed)} file(s) removed.")
else:
    print("No database files found.")
