"""Skill matches you marked wrong, so a posting stops counting them toward its fit."""

from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS skill_corrections (
    job_key TEXT NOT NULL,
    skill   TEXT NOT NULL,
    PRIMARY KEY (job_key, skill)
);
"""


class Corrections:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        conn.executescript(SCHEMA)

    def rejected(self, job_key: str) -> set[str]:
        rows = self.conn.execute("SELECT skill FROM skill_corrections WHERE job_key = ?", (job_key,))
        return {row[0] for row in rows}

    def reject(self, job_key: str, skill: str) -> None:
        self.conn.execute("INSERT OR IGNORE INTO skill_corrections (job_key, skill) VALUES (?, ?)", (job_key, skill))
        self.conn.commit()

    def restore(self, job_key: str, skill: str) -> None:
        self.conn.execute("DELETE FROM skill_corrections WHERE job_key = ? AND skill = ?", (job_key, skill))
        self.conn.commit()
