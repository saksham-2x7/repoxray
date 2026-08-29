import unittest
import os
import json
import tempfile
import subprocess

class TestRepoXray(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.test_dir.name
        
        # Create a mock project
        # a.py -> imports b.py
        # b.py -> imports c.py
        # c.py -> standalone
        
        with open(os.path.join(self.repo_path, 'a.py'), 'w') as f:
            f.write("import b\nprint('A')")
            
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

    def test_scan_creates_index(self):
        res = self.run_cli("scan", ".")
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.repo_path, '.repoxray.json')))

    def test_who_uses(self):
        self.run_cli("scan", ".")
        res = self.run_cli("who-uses", "b.py")
        self.assertIn("a.py", res.stdout)
        
    def test_impact(self):
        self.run_cli("scan", ".")
        res = self.run_cli("impact", "c.py")
        self.assertIn("b.py", res.stdout)
        self.assertIn("a.py", res.stdout) # Transitive impact
        
    def test_search(self):
        res = self.run_cli("search", "func", ".")
        self.assertIn("c.py:1", res.stdout)
        self.assertIn("b.py:1", res.stdout)

    def tearDown(self):
        self.test_dir.cleanup()

if __name__ == '__main__':
    unittest.main()
