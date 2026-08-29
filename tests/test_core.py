import unittest
import os
import json
import tempfile
import subprocess
import time

class TestRepoXray(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.test_dir.name
        
        os.makedirs(os.path.join(self.repo_path, 'lib'))
        
        with open(os.path.join(self.repo_path, 'a.py'), 'w') as f:
            f.write("import b\nprint('A')\n")
            
        with open(os.path.join(self.repo_path, 'b.py'), 'w') as f:
            f.write("from lib import e\nprint('B')")
            
        with open(os.path.join(self.repo_path, 'c.py'), 'w') as f:
            f.write("import a, b\ndef func(): pass\nprint('C')")
            
        with open(os.path.join(self.repo_path, 'd.js'), 'w') as f:
            f.write("const e = require('./lib/e');")
            
        with open(os.path.join(self.repo_path, 'lib', '__init__.py'), 'w') as f:
            f.write("from . import e")
            
        with open(os.path.join(self.repo_path, 'lib', 'e.py'), 'w') as f:
            f.write("print('E')")
            
        with open(os.path.join(self.repo_path, 'lib', 'e.js'), 'w') as f:
            f.write("module.exports = {};")
            
        with open(os.path.join(self.repo_path, 'fake.png'), 'w') as f:
            f.write("This is actually a text file with a fake extension.")
            
        # Large file > 5MB
        with open(os.path.join(self.repo_path, 'large.txt'), 'w') as f:
            f.write("huge_word " * (1024 * 600))
            
        self.cli_path = os.path.abspath("repoxray.py")

    def run_cli(self, *args):
        return subprocess.run([self.cli_path] + list(args), cwd=self.repo_path, capture_output=True, text=True)

    def test_scan_creates_index(self):
        res = self.run_cli("scan", ".")
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.repo_path, '.repoxray.json')))

    def test_incremental_scan(self):
        self.run_cli("scan", ".")
        # Keep same size but different mtime/content
        with open(os.path.join(self.repo_path, 'c.py'), 'w') as f:
            f.write("import a, x\ndef func(): pass\nprint('C')")
        res2 = self.run_cli("scan", ".")
        # Should not be incremental for c.py because hash differs
        self.assertIn("Incremental", res2.stdout)

    def test_multi_module_import(self):
        self.run_cli("scan", ".")
        res = self.run_cli("depends-on", "c.py", ".", "--output", "-")
        data = json.loads(res.stdout)
        self.assertIn("a.py", data["resolved"])
        self.assertIn("b.py", data["resolved"])
        
    def test_python_relative_import(self):
        self.run_cli("scan", ".")
        res = self.run_cli("depends-on", "lib/__init__.py", ".", "--output", "-")
        data = json.loads(res.stdout)
        self.assertIn("lib/e.py", data["resolved"])
        
    def test_overview_json_tree(self):
        self.run_cli("scan", ".")
        res = self.run_cli("overview", ".", "--output", "-")
        data = json.loads(res.stdout)
        self.assertIn("project_tree", data)
        self.assertIn("lib/", data["project_tree"])
        self.assertIn("a.py", data["project_tree"])

    def test_large_file_streaming(self):
        self.run_cli("scan", ".")
        res = self.run_cli("search", "huge_word", ".", "--output", "-")
        data = json.loads(res.stdout)
        files = [d['file'] for d in data]
        self.assertIn("large.txt", files)

    def tearDown(self):
        self.test_dir.cleanup()

if __name__ == '__main__':
    unittest.main()
