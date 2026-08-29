import os

with open('tests/test_core.py', 'a') as f:
    f.write('''
    def test_permission_error_handling(self):
        unreadable = os.path.join(self.repo_path, 'unreadable.txt')
        with open(unreadable, 'w') as f: f.write("secret")
        os.chmod(unreadable, 0o000)
        try:
            self.run_cli("scan", ".")
            res = self.run_cli("overview", ".", "--output", "-")
            warnings = __import__('json').loads(res.stdout).get("warnings", [])
            self.assertTrue(any("Permission denied" in w or "Could not read" in w for w in warnings))
        finally:
            os.chmod(unreadable, 0o644)
            
    def test_search_streaming_memory(self):
        huge_single_line = os.path.join(self.repo_path, 'minified.js')
        with open(huge_single_line, 'w') as f:
            f.write("var a=1;" * 1000 + " console.log('target_needle');")
        self.run_cli("scan", ".")
        res = self.run_cli("search", "target_needle", "--output", "-")
        data = __import__('json').loads(res.stdout)
        self.assertEqual(data["count"], 1)
        self.assertIn("target_needle", data["matches"][0]["context"])
''')
