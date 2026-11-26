#!/usr/bin/env python3
"""Fake PostgreSQL protocol fixture. Never used by a packaged app.
Runs the INSERT against private temporary SQLite; SQL/table-lock adaptation is explicit.
"""
import os
import sqlite3
import sys

sql = sys.stdin.read()
if 'LOCK TABLE t_user IN EXCLUSIVE MODE;' not in sql:
    sys.exit(2)
conn = sqlite3.connect(os.environ['FAKE_DB_PATH'])
conn.create_function('decode', 2, lambda value, encoding: bytes.fromhex(value))
conn.create_function('convert_from', 2, lambda value, encoding: value.decode('utf-8'))
conn.execute('CREATE TABLE IF NOT EXISTS t_user (id TEXT PRIMARY KEY, username TEXT UNIQUE, email TEXT UNIQUE, password_hash TEXT, created_at TEXT, is_active BOOLEAN)')
conn.commit()
conn.executescript(sql.replace('LOCK TABLE t_user IN EXCLUSIVE MODE;', ''))
conn.commit()
print('fake database transaction complete')
