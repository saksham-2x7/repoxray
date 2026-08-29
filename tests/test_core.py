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
        
        # Structure:
        # a.py -> imports b (relative to package)
        # b.py -> imports c (relative to package)
        # c.py -> imports a (cycle)
        # d.js -> imports ./lib/e
        # lib/e.js
        # unknown.bin
        
        os.makedirs(os.path.join(self.repo_path, 'lib'))
        
        with open(os.path.join(self.repo_path, 'a.py'), 'w') as f:
            f.write("import b\nprint('A')\n")
            
        with open(os.path.join(self.repo_path, 'b.py'), 'w') as f:
            f.write("from c import func\nprint('B')")
            
        with open(os.path.join(self.repo_path, 'c.py'), 'w') as f:
            f.write("import a\ndef func(): pass\nprint('C')")
            
        with open(os.path.join(self.repo_path, 'd.js'), 'w') as f:
            f.write("const e = require('./lib/e');")
            
        with open(os.path.join(self.repo_path, 'lib', 'e.js'), 'w') as f:
            f.write("module.exports = {};")
            
        with open(os.path.join(self.repo_path, 'fake.png'), 'w') as f:
            f.write("This is actually a text file with a fake extension.")
            
        self.cli_path = os.path.abspath("repoxray.py")

    def run_cli(self, *args):
        return subprocess.run([self.cli_path] + list(args), cwd=self.repo_path, capture_output=True, text=True)

    def test_scan_creates_index(self):
        res = self.run_cli("scan", ".")
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.repo_path, '.repoxray.json')))

    def test_incremental_scan(self):
        self.run_cli("scan", ".")
        with open(os.path.join(self.repo_path, 'c.py'), 'a') as f:
            f.write("\nprint('new')")
        # Ensure mtime is different enough
        time.sleep(0.1) 
        res2 = self.run_cli("scan", ".")
        self.assertIn("Incremental", res2.stdout)

    def test_who_uses(self):
        self.run_cli("scan", ".")
        res = self.run_cli("who-uses", "b.py", ".", "--output", "-")
        data = json.loads(res.stdout)
        self.assertIn("a.py", data)
        
    def test_depends_on(self):
        self.run_cli("scan", ".")
        res = self.run_cli("depends-on", "a.py", ".", "--output", "-")
        data = json.loads(res.stdout)
        self.assertIn("b.py", data["resolved"])
        
    def test_impact(self):
        self.run_cli("scan", ".")
        res = self.run_cli("impact", "c.py", ".", "--output", "-")
        data = json.loads(res.stdout)
        self.assertIn("b.py", data["direct"])
        self.assertIn("a.py", data["indirect"])
        
    def test_search_indexed_and_glob(self):
        self.run_cli("scan", ".")
        res = self.run_cli("search", "require", ".", "--path", "*.js", "--output", "-")
        data = json.loads(res.stdout)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['file'], 'd.js')

    def test_inspect_fake_extension(self):
        res = self.run_cli("inspect", "fake.png", "--output", "-")
        data = json.loads(res.stdout)
        self.assertTrue(data["extension_mismatch"])
        self.assertEqual(data["type"], "Text/Source")
        
    def test_overview_cycles(self):
        self.run_cli("scan", ".")
        res = self.run_cli("overview", ".", "--output", "-")
        data = json.loads(res.stdout)
        self.assertGreaterEqual(data["cycles_count"], 1)

    def tearDown(self):
        self.test_dir.cleanup()

if __name__ == '__main__':
    unittest.main()
