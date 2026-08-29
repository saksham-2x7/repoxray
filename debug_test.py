import unittest
import os
import json
from tests.test_core import TestRepoXray

class Debug(TestRepoXray):
    def test_python_imports(self):
        self.run_cli("scan", ".")
        res = self.run_cli("depends-on", "multi.py", "--output", "-")
        print("MULTI_PY", res.stdout)
        
    def test_relative_imports(self):
        self.run_cli("scan", ".")
        res = self.run_cli("depends-on", "pkg/sub/__init__.py", "--output", "-")
        print("PKG_SUB", res.stdout)

if __name__ == '__main__':
    unittest.main()
