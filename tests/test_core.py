import unittest
import os
import json
import tempfile
import subprocess

class TestRepoXray(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.test_dir.name
        
        with open(os.path.join(self.repo_path, 'a.py'), 'w') as f:
            f.write("import b\nprint('A')\nfrom c import func")
            
        with open(os.path.join(self.repo_path, 'b.py'), 'w') as f:
            f.write("from c import func\nprint('B')")
            
        with open(os.path.join(self.repo_path, 'c.py'), 'w') as f:
            f.write("def func(): pass\nprint('C')")
            
        with open(os.path.join(self.repo_path, 'index.js'), 'w') as f:
            f.write("const utils = require('./utils.js');")
            
        with open(os.path.join(self.repo_path, 'utils.js'), 'w') as f:
            f.write("module.exports = {};")
            
        self.cli_path = os.path.abspath("repoxray.py")

    def run_cli(self, *args):
        return subprocess.run([self.cli_path] + list(args), cwd=self.repo_path, capture_output=True, text=True)

    def test_scan_incremental(self):
        res1 = self.run_cli("scan", ".")
        self.assertTrue(os.path.exists(os.path.join(self.repo_path, '.repoxray.json')))
        res2 = self.run_cli("scan", ".")
        self.assertIn("Incremental", res2.stdout)
        
    def test_multiline_import_and_impact(self):
        self.run_cli("scan", ".")
        res = self.run_cli("impact", "c.py", ".", "--output", "report.json")
        self.assertEqual(res.returncode, 0)
        with open(os.path.join(self.repo_path, 'report.json')) as f:
            data = json.load(f)
        # c is used by b and a directly
        self.assertIn("b.py", data["direct"])
        self.assertIn("a.py", data["direct"])

    def test_js_relative_import(self):
        self.run_cli("scan", ".")
        res = self.run_cli("who-uses", "utils.js", ".", "--output", "report.json")
        with open(os.path.join(self.repo_path, 'report.json')) as f:
            data = json.load(f)
        self.assertIn("index.js", data)
        
    def test_search_indexed(self):
        self.run_cli("scan", ".")
        res = self.run_cli("search", "func", ".", "--output", "report.json")
        with open(os.path.join(self.repo_path, 'report.json')) as f:
            data = json.load(f)
        files = [d['file'] for d in data]
        self.assertIn("c.py", files)
        self.assertIn("b.py", files)
        self.assertIn("a.py", files)

    def tearDown(self):
        self.test_dir.cleanup()

if __name__ == '__main__':
    unittest.main()
