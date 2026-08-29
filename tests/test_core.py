import unittest
import os
import sys
import repoxray
import json
import tempfile
import subprocess
import time

class TestRepoXray(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.test_dir.name
        
        # Ignored dir
        os.makedirs(os.path.join(self.repo_path, 'node_modules'))
        with open(os.path.join(self.repo_path, 'node_modules', 'skip.js'), 'w') as f: f.write("console.log('skip');")
            
        # Hidden file
        with open(os.path.join(self.repo_path, '.hidden.py'), 'w') as f: f.write("print('hidden')")
            
        # Empty text file
        with open(os.path.join(self.repo_path, 'empty.txt'), 'w') as f: pass
        
        # Unicode and spaces
        with open(os.path.join(self.repo_path, 'tést spâce.py'), 'w') as f: f.write("import os\n")
        
        # Duplicate basenames
        os.makedirs(os.path.join(self.repo_path, 'dirA'))
        os.makedirs(os.path.join(self.repo_path, 'dirB'))
        with open(os.path.join(self.repo_path, 'dirA', 'conf.py'), 'w') as f: f.write("A=1")
        with open(os.path.join(self.repo_path, 'dirB', 'conf.py'), 'w') as f: f.write("B=1")
        with open(os.path.join(self.repo_path, 'main.py'), 'w') as f: f.write("import conf\n") # Ambiguous
        
        # Python multi-line & multi-import
        with open(os.path.join(self.repo_path, 'multi.py'), 'w') as f:
            f.write("import a, \\\n  b\nfrom pkg import c, d as d_alias\n")
            
        # Python relative imports
        os.makedirs(os.path.join(self.repo_path, 'pkg', 'sub'))
        with open(os.path.join(self.repo_path, 'pkg', '__init__.py'), 'w') as f: f.write("from . import c\n")
        with open(os.path.join(self.repo_path, 'pkg', 'c.py'), 'w') as f: f.write("C=1\n")
        with open(os.path.join(self.repo_path, 'pkg', 'sub', '__init__.py'), 'w') as f: f.write("from .. import c\nfrom .module import name\n")
        with open(os.path.join(self.repo_path, 'pkg', 'sub', 'module.py'), 'w') as f: f.write("name=1\n")
        
        # JS relative and index resolution
        os.makedirs(os.path.join(self.repo_path, 'jsapp', 'utils'))
        with open(os.path.join(self.repo_path, 'jsapp', 'index.js'), 'w') as f: f.write("import {x} from './utils';\nrequire('fs');")
        with open(os.path.join(self.repo_path, 'jsapp', 'utils', 'index.js'), 'w') as f: f.write("export const x = 1;")
        
        # Cycle & Self Reference
        with open(os.path.join(self.repo_path, 'cyc1.py'), 'w') as f: f.write("import cyc2\nimport cyc1\n")
        with open(os.path.join(self.repo_path, 'cyc2.py'), 'w') as f: f.write("import cyc1\n")
        
        # Impact chains (A -> B -> C)
        with open(os.path.join(self.repo_path, 'imp_c.py'), 'w') as f: f.write("C=1")
        with open(os.path.join(self.repo_path, 'imp_b.py'), 'w') as f: f.write("import imp_c")
        with open(os.path.join(self.repo_path, 'imp_a.py'), 'w') as f: f.write("import imp_b")
        
        # Large file
        with open(os.path.join(self.repo_path, 'large.txt'), 'w') as f: f.write("huge_word " * (1024 * 600))
        
        # Malformed JSON
        with open(os.path.join(self.repo_path, 'bad.json'), 'w') as f: f.write("{bad json")
            
        self.cli_path = os.path.abspath("repoxray.py")

    def run_cli(self, *args):
        # Use sys.executable so the correct Python interpreter is invoked on all
        # platforms.  On Windows, .py files cannot be executed directly as
        # Win32 applications (shebang lines are ignored), so passing the script
        # path alone to subprocess raises OSError [WinError 193].
        return subprocess.run([sys.executable, self.cli_path] + list(args), cwd=self.repo_path, capture_output=True, text=True)

    def test_empty_project(self):
        with tempfile.TemporaryDirectory() as empty_dir:
            res = subprocess.run([sys.executable, self.cli_path, "scan", "."], cwd=empty_dir, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            res2 = subprocess.run([sys.executable, self.cli_path, "overview", ".", "--output", "-"], cwd=empty_dir, capture_output=True, text=True)
            self.assertEqual(json.loads(res2.stdout)["total_files"], 0)

    def test_empty_file(self):
        self.run_cli("scan", ".")
        res = self.run_cli("inspect", "empty.txt", "--output", "-")
        self.assertEqual(json.loads(res.stdout)["size"], 0)

    def test_hidden_and_ignored(self):
        self.run_cli("scan", ".")
        res = self.run_cli("overview", ".", "--output", "-")
        tree = json.loads(res.stdout)["project_tree"]
        self.assertIn(".hidden.py", tree)
        self.assertNotIn("node_modules", tree)

    def test_unicode_and_spaces(self):
        self.run_cli("scan", ".")
        res = self.run_cli("overview", ".", "--output", "-")
        self.assertIn("tést spâce.py", json.loads(res.stdout)["project_tree"])

    def test_ambiguous_fallback(self):
        self.run_cli("scan", ".")
        res = self.run_cli("depends-on", "main.py", "--output", "-")
        data = json.loads(res.stdout)
        self.assertIn("conf", data["ambiguous"])
        self.assertEqual(len(data["ambiguous_candidates"]["conf"]), 2)

    def test_python_imports(self):
        self.run_cli("scan", ".")
        res = self.run_cli("depends-on", "multi.py", "--output", "-")
        data = json.loads(res.stdout)
        self.assertIn("pkg/c.py", data["resolved"])
        self.assertIn("a", data["unresolved"])
        self.assertIn("b", data["unresolved"])
        self.assertIn("pkg.d", data["unresolved"])

    def test_relative_imports(self):
        self.run_cli("scan", ".")
        res = self.run_cli("depends-on", "pkg/__init__.py", "--output", "-")
        self.assertIn("pkg/c.py", json.loads(res.stdout)["resolved"])
        res2 = self.run_cli("depends-on", "pkg/sub/__init__.py", "--output", "-")
        self.assertIn("pkg/c.py", json.loads(res2.stdout)["resolved"])
        self.assertIn("pkg/sub/module.py", json.loads(res2.stdout)["resolved"])

    def test_js_imports(self):
        self.run_cli("scan", ".")
        res = self.run_cli("depends-on", "jsapp/index.js", "--output", "-")
        self.assertIn("jsapp/utils/index.js", json.loads(res.stdout)["resolved"])
        self.assertIn("fs", json.loads(res.stdout)["unresolved"])

    def test_cycle_and_self_reference(self):
        self.run_cli("scan", ".")
        res = self.run_cli("overview", ".", "--output", "-")
        self.assertGreaterEqual(json.loads(res.stdout)["cycles_count"], 1)

    def test_three_level_impact(self):
        self.run_cli("scan", ".")
        res = self.run_cli("impact", "imp_c.py", "--output", "-")
        data = json.loads(res.stdout)
        self.assertIn("imp_b.py", data["direct"])
        self.assertIn("imp_a.py", data["indirect"])

    def test_incremental_same_size(self):
        self.run_cli("scan", ".")
        time.sleep(0.1)
        with open(os.path.join(self.repo_path, 'imp_c.py'), 'w') as f: f.write("C=2")
        res = self.run_cli("scan", ".", "--output", "-")
        data = json.loads(res.stdout)
        self.assertIn("imp_c.py", data["changed"])

    def test_large_file_streaming_and_search(self):
        self.run_cli("scan", ".")
        res = self.run_cli("search", "huge_word", "--output", "-")
        self.assertIn("large.txt", [m["file"] for m in json.loads(res.stdout)["matches"]])

    def test_inspect_malformed_json(self):
        self.run_cli("scan", ".")
        res = self.run_cli("inspect", "bad.json", "--output", "-")
        self.assertTrue(any("Malformed JSON" in w for w in json.loads(res.stdout)["warnings"]))

    def test_ambiguous_target_cli(self):
        self.run_cli("scan", ".")
        res = self.run_cli("impact", "conf.py")
        self.assertEqual(res.returncode, 1)
        self.assertIn("ambiguous", res.stderr.lower())

    def test_corrupt_index(self):
        with open(os.path.join(self.repo_path, '.repoxray.json'), 'w') as f: f.write("{bad")
        res = self.run_cli("overview", ".")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Error reading index", res.stderr)

    def test_zero_dependency_import(self):
        # Verify the module imports cleanly.  sys.executable is used instead of
        # a hardcoded "python3" so the test runs on Windows and in virtual envs.
        res = subprocess.run([sys.executable, "-c", "import repoxray; print('ok')"], cwd=os.path.dirname(self.cli_path), capture_output=True, text=True)
        self.assertIn("ok", res.stdout)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_category_boundary(self):
        self.run_cli("scan", ".")
        with open(os.path.join(self.repo_path, '.repoxray.json')) as f:
            data = json.load(f)
        self.assertEqual(data["files"]["bad.json"]["category"], "config")

    def test_incremental_dependency_addition_and_deletion(self):
        dep = os.path.join(self.repo_path, "temp_helper.py")
        source = os.path.join(self.repo_path, "temp_source.py")
        with open(source, 'w') as f: f.write("import temp_helper\n")
        self.run_cli("scan", ".")
        with open(dep, 'w') as f: f.write("VALUE = 1\n")
        self.run_cli("scan", ".")
        with open(os.path.join(self.repo_path, '.repoxray.json')) as f:
            added = json.load(f)
        self.assertIn("temp_helper.py", added["files"]["temp_source.py"]["resolved_deps"])
        os.unlink(dep)
        self.run_cli("scan", ".")
        with open(os.path.join(self.repo_path, '.repoxray.json')) as f:
            deleted = json.load(f)
        self.assertIn("temp_helper", deleted["files"]["temp_source.py"]["unresolved_deps"])

    def test_malformed_index_structure(self):
        self.run_cli("scan", ".")
        with open(os.path.join(self.repo_path, '.repoxray.json'), 'w') as f:
            json.dump({"version": "3.1", "files": {}}, f)
        res = self.run_cli("overview", ".")
        self.assertEqual(res.returncode, 1)
        self.assertIn("Malformed index", res.stderr)

    def test_deep_traversals(self):
        deep_path = '/'.join(f'd{i}' for i in range(1100)) + '/x.py'
        self.assertIn('x.py', repoxray.generate_tree([deep_path]))
        forward = {f'n{i}': [f'n{i+1}'] for i in range(1100)}
        forward['n1100'] = []
        self.assertEqual(repoxray.find_cycles(forward), [])

    def test_tree_sorted_order(self):
        # Verify that generate_tree renders directories and files in ascending
        # sorted order, matching the behaviour of the original recursive walk.
        # Input paths chosen so alphabetical ordering is unambiguous.
        files = [
            "alpha/a_file.py",
            "alpha/b_file.py",
            "beta/sub/deep.py",
            "beta/top.py",
            "gamma/only.py",
            "root.py",
        ]
        tree = repoxray.generate_tree(files)
        lines = tree.splitlines()
        # Each line from generate_tree contains "── " as a fixed separator.
        # Split on it to extract just the entry name, stripping all tree-drawing
        # prefix characters regardless of Unicode encoding.
        labels = [l.split("\u2500\u2500 ", 1)[-1].rstrip() for l in lines]
        self.assertEqual(len(labels), 10)
        self.assertEqual(labels[0], "alpha/")
        self.assertEqual(labels[1], "a_file.py")
        self.assertEqual(labels[2], "b_file.py")
        self.assertEqual(labels[3], "beta/")
        # beta/sub/ (dir) comes before beta/top.py (file): dirs rendered before files
        self.assertEqual(labels[4], "sub/")
        self.assertEqual(labels[5], "deep.py")
        self.assertEqual(labels[6], "top.py")
        self.assertEqual(labels[7], "gamma/")
        self.assertEqual(labels[8], "only.py")
        self.assertEqual(labels[9], "root.py")

if __name__ == '__main__':
    unittest.main()
