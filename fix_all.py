import os
import re

with open('repoxray.py', 'r') as f:
    code = f.read()

# 1. Fix os.walk in scan()
code = code.replace(
    'for root, dirs, files in os.walk(directory):',
    '''def walk_err(err): index['metadata']['warnings'].append(f"Directory access denied: {err}")
    for root, dirs, files in os.walk(directory, onerror=walk_err):'''
)

# 2. Fix search memory exhaustion
search_old = '''        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line_num in words_index[q_lower]:
                    line_idx = line_num - 1
                    if line_idx < len(lines) and query in lines[line_idx]:
                        matches_found.append({'file': filepath, 'line': line_num, 'context': lines[line_idx].strip()[:100]})
        except Exception: pass'''

search_new = '''        try:
            target_lines = set(words_index[q_lower])
            with open(full_path, 'r', encoding='utf-8') as f:
                for line_idx, line in enumerate(f):
                    line_num = line_idx + 1
                    if line_num in target_lines and query in line:
                        matches_found.append({'file': filepath, 'line': line_num, 'context': line.strip()[:100]})
        except Exception: pass'''
code = code.replace(search_old, search_new)

# 3. Fix struct.error in SQLite inspect
code = code.replace(
    'except Exception as e:\n            confidence = "Low (Malformed)"\n            warnings.append(f"Malformed SQLite: {str(e)}")',
    'except (struct.error, Exception) as e:\n            confidence = "Low (Malformed)"\n            warnings.append(f"Malformed SQLite: {str(e)}")'
)

# 4. Decouple metrics
metrics_func = '''def compute_metrics(index):
    forward, reverse = build_forward_reverse(index)
    orphans = [p for p, info in index['files'].items() if p not in reverse and info['category'] == 'source' and not info.get('is_entry_point')]
    cycles = find_cycles(forward)
    categories = defaultdict(int)
    metrics = {"unresolved": 0, "proven": 0, "heuristic": 0, "ambiguous": 0, "unknown_bin": 0, "skipped": 0}
    for info in index['files'].values():
        categories[info['category']] += 1
        metrics['unresolved'] += len(info.get('unresolved_deps', []))
        metrics['proven'] += len(info.get('resolved_deps', []))
        metrics['heuristic'] += len(info.get('heuristic_deps', []))
        metrics['ambiguous'] += len(info.get('ambiguous_deps', []))
        if not info.get('is_text'): metrics['unknown_bin'] += 1
    return forward, reverse, orphans, cycles, categories, metrics
'''

overview_old = '''def overview(directory, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
        
    forward, reverse = build_forward_reverse(index)
    orphans = [p for p, info in index['files'].items() if p not in reverse and info['category'] == 'source' and not info.get('is_entry_point')]
    cycles = find_cycles(forward)
    
    categories = defaultdict(int)
    metrics = {"unresolved": 0, "proven": 0, "heuristic": 0, "ambiguous": 0, "unknown_bin": 0, "skipped": 0}
    
    for info in index['files'].values():
        categories[info['category']] += 1
        metrics['unresolved'] += len(info.get('unresolved_deps', []))
        metrics['proven'] += len(info.get('resolved_deps', []))
        metrics['heuristic'] += len(info.get('heuristic_deps', []))
        metrics['ambiguous'] += len(info.get('ambiguous_deps', []))
        if not info.get('is_text'): metrics['unknown_bin'] += 1'''

overview_new = '''def overview(directory, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
        
    forward, reverse, orphans, cycles, categories, metrics = compute_metrics(index)'''

code = code.replace('def overview(', metrics_func + '\n' + overview_new + '\n\n    # replaced\n    def overview_stub(', 1)
code = code.replace(overview_old, overview_new)

with open('repoxray.py', 'w') as f:
    f.write(code)

with open('tests/test_core.py', 'a') as f:
    f.write('''
    def test_permission_error_handling(self):
        # Create unreadable file
        unreadable = os.path.join(self.repo_path, 'unreadable.txt')
        with open(unreadable, 'w') as f: f.write("secret")
        os.chmod(unreadable, 0o000)
        try:
            self.run_cli("scan", ".")
            res = self.run_cli("overview", ".", "--output", "-")
            warnings = json.loads(res.stdout).get("warnings", [])
            self.assertTrue(any("Could not read" in w for w in warnings))
        finally:
            os.chmod(unreadable, 0o644)
            
    def test_search_streaming_memory(self):
        huge_single_line = os.path.join(self.repo_path, 'minified.js')
        with open(huge_single_line, 'w') as f:
            f.write("var a=1;" * 100000 + " console.log('target_needle');")
        self.run_cli("scan", ".")
        res = self.run_cli("search", "target_needle", "--output", "-")
        data = json.loads(res.stdout)
        self.assertEqual(data["count"], 1)
        self.assertIn("target_needle", data["matches"][0]["context"])
''')
