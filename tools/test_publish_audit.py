#!/usr/bin/env python3
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("publish_audit", Path(__file__).with_name("check-publish.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublishAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="publish-audit-")
        self.root = Path(self.temp.name)
        subprocess.run(["/usr/bin/git", "init", "--quiet", str(self.root)], check=True, capture_output=True)

    def tearDown(self):
        self.temp.cleanup()

    def stage(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        subprocess.run(["/usr/bin/git", "add", "--", name], cwd=self.root, check=True)

    def test_clean_source_passes(self):
        self.stage("README.md", b"Packaging source only.\n")
        self.assertTrue(module.audit(self.root)["passed"])

    def test_runtime_env_rejected(self):
        self.stage(".env", b"EXAMPLE=value\n")
        self.assertFalse(module.audit(self.root)["passed"])

    def test_token_never_returned(self):
        token = "ghp_" + "A" * 36
        self.stage("mistake.txt", token.encode())
        result = module.audit(self.root)
        self.assertFalse(result["passed"])
        self.assertNotIn(token, str(result))

    def test_symlink_rejected(self):
        os.symlink("/etc/passwd", self.root / "unexpected-link")
        subprocess.run(["/usr/bin/git", "add", "unexpected-link"], cwd=self.root, check=True)
        self.assertFalse(module.audit(self.root)["passed"])

    def test_large_binary_rejected(self):
        self.stage("binary.bin", b"x" * (5 * 1024 * 1024 + 1))
        self.assertFalse(module.audit(self.root)["passed"])


if __name__ == "__main__":
    unittest.main()
