#!/usr/bin/env python3
"""Check the exact Git index before publishing; never print secret values."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PATTERNS = {
    "github-token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "github-fine-grained-token": re.compile(rb"github_pat_[A-Za-z0-9_]{35,}"),
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
}
FORBIDDEN_NAMES = {".env", ".git-credentials", "hosts.yml", "credentials.json"}
FORBIDDEN_SUFFIXES = {".fpk", ".db", ".sqlite", ".sqlite3", ".pid", ".sock", ".log"}


def audit(root: Path) -> dict:
    names = subprocess.check_output(["/usr/bin/git", "ls-files", "-z"], cwd=root).split(b"\0")
    failures = []
    count = 0
    total = 0
    for encoded in names:
        if not encoded:
            continue
        rel = Path(os.fsdecode(encoded))
        path = root / rel
        count += 1
        if path.is_symlink():
            failures.append({"file": str(rel), "issue": "symlink-requires-review"})
            continue
        data = path.read_bytes()
        total += len(data)
        if rel.name in FORBIDDEN_NAMES or rel.suffix in FORBIDDEN_SUFFIXES:
            failures.append({"file": str(rel), "issue": "private-or-runtime-file"})
        if len(data) > 5 * 1024 * 1024:
            failures.append({"file": str(rel), "issue": "large-build-artifact"})
        for name, pattern in PATTERNS.items():
            if pattern.search(data):
                failures.append({"file": str(rel), "issue": name})
    return {"tracked_files": count, "tracked_bytes": total, "failures": failures, "passed": not failures}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    result = audit(Path(args.root).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
