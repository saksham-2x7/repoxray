#!/usr/bin/env python3
import os
import sys
import argparse
import json
import re
import hashlib
import fnmatch
import struct
import zipfile
import ast
from collections import defaultdict, deque

SCHEMA_VERSION = "3.0"
INDEX_FILE = '.repoxray.json'
DEFAULT_IGNORE = {'.git', 'node_modules', '__pycache__', 'venv', 'env', 'dist', 'build', '.next'}

IMPORT_PATTERNS = {
    'js': [
        re.compile(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE),
        re.compile(r'require\([\'"]([^\'"]+)[\'"]\)', re.MULTILINE)
    ]
}

def disable_colors(): pass
def eprint(*args, **kwargs): print(*args, file=sys.stderr, **kwargs)

def get_file_hash(filepath):
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''): hasher.update(chunk)
        return hasher.hexdigest()
    except Exception: return None

def is_text_file(filepath):
    try:
        with open(filepath, 'tr', encoding='utf-8') as f:
            f.read(1024)
            return True
    except Exception: return False

def parse_text_file(filepath, file_type):
    deps, words_index, warnings = set(), defaultdict(list), []
    is_entry_point = False
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
            
        # Line-location inverted index
        lines = text.split('\n')
        for line_num, line in enumerate(lines, 1):
            for w in re.findall(r'[a-zA-Z0-9_]{3,}', line.lower()):
                if not words_index[w] or words_index[w][-1] != line_num:
                    words_index[w].append(line_num)
        
        # AST parsing for Python
        if file_type == 'python':
            if "if __name__ == '__main__':" in text or 'if __name__ == "__main__":' in text:
                is_entry_point = True
            try:
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for n in node.names: deps.add(n.name)
                    elif isinstance(node, ast.ImportFrom):
                        mod = node.module or ''
                        prefix = '.' * node.level if node.level > 0 else ''
                        full_mod = prefix + mod
                        deps.add(full_mod)
                        for n in node.names:
                            if full_mod.endswith('.'): deps.add(full_mod + n.name)
                            else: deps.add(full_mod + '.' + n.name)
            except SyntaxError as e:
                warnings.append(f"Python AST SyntaxError: {e}")
        else:
            if os.path.basename(filepath) in ['index.js', 'server.js', 'main.js']:
                is_entry_point = True
            for pattern in IMPORT_PATTERNS.get(file_type, []):
                for match in pattern.findall(text):
                    for m in match.split(','): deps.add(m.strip())
    except Exception as e:
        warnings.append(f"Scan error: {e}")
    return list(deps), dict(words_index), is_entry_point, warnings

def resolve_dependency(source_file, raw_dep, all_files):
    dir_name = os.path.dirname(source_file)
    exts_js = ['', '.js', '.jsx', '.ts', '.tsx', '/index.js', '/index.ts']
    exts_py = ['', '.py', '/__init__.py']
    is_js = source_file.endswith(('.js','.ts','.jsx','.tsx'))
    
    if not is_js and raw_dep.startswith('.'):
        dots = len(raw_dep) - len(raw_dep.lstrip('.'))
        mod_path = raw_dep.lstrip('.').replace('.', '/')
        target_dir = dir_name
        for _ in range(dots - 1): target_dir = os.path.dirname(target_dir)
        target = os.path.normpath(os.path.join(target_dir, mod_path)) if mod_path else target_dir
        for ext in exts_py:
            if target + ext in all_files: return target + ext, "resolved_relative", []
                
    elif raw_dep.startswith('.'):
        target = os.path.normpath(os.path.join(dir_name, raw_dep))
        for ext in (exts_js if is_js else exts_py):
            if target + ext in all_files: return target + ext, "resolved_relative", []
    else:
        py_target = raw_dep.replace('.', '/')
        for ext in (exts_js if is_js else exts_py):
            local_target = os.path.normpath(os.path.join(dir_name, py_target)) + ext
            if local_target in all_files: return local_target, "resolved_local", []
            if py_target + ext in all_files: return py_target + ext, "resolved_root", []
            
        candidates = []
        for f in all_files:
            bname = os.path.basename(f)
            if bname in [raw_dep + ".py", raw_dep + ".js", raw_dep + ".ts"]:
                candidates.append(f)
        
        if len(candidates) == 1:
            return candidates[0], "heuristic_basename", candidates
        elif len(candidates) > 1:
            return raw_dep, "ambiguous", candidates
                
    return raw_dep, "unresolved", []

def scan(directory, output_file=None):
    old_index = load_index(directory, silent=True) or {'files': {}}
    index = {
        'version': SCHEMA_VERSION,
        'metadata': {'total_files': 0, 'total_dirs': 0, 'total_size': 0, 'warnings': []},
        'files': {}
    }
    
    all_current_paths = set()
    added, changed, unchanged = [], [], []
    skipped_count = 0
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORE]
        index['metadata']['total_dirs'] += 1
        for file in files:
            if file == INDEX_FILE: continue
            filepath = os.path.join(root, file)
            rel_path = os.path.normpath(os.path.relpath(filepath, directory))
            all_current_paths.add(rel_path)
            
            try:
                mtime = os.path.getmtime(filepath)
                size = os.path.getsize(filepath)
                index['metadata']['total_size'] += size
                index['metadata']['total_files'] += 1
                
                old_record = old_index['files'].get(rel_path)
                # Fast path O(changed-files) using mtime/size
                if old_record and old_record.get('mtime') == mtime and old_record.get('size') == size:
                    index['files'][rel_path] = old_record
                    unchanged.append(rel_path)
                    continue
                
                current_hash = get_file_hash(filepath)
                if old_record and old_record.get('hash') == current_hash:
                    old_record['mtime'] = mtime
                    index['files'][rel_path] = old_record
                    unchanged.append(rel_path)
                    continue
                
                if old_record: changed.append(rel_path)
                else: added.append(rel_path)
                
                _, ext = os.path.splitext(file)
                f_type = 'python' if ext == '.py' else ('js' if ext in ['.js','.jsx','.ts','.tsx'] else 'unknown')
                is_text = is_text_file(filepath)
                
                deps, words_index, is_entry_point, f_warns = parse_text_file(filepath, f_type) if is_text else ([], {}, False, [])
                if f_warns: skipped_count += 1
                index['metadata']['warnings'].extend([f"{rel_path}: {w}" for w in f_warns])
                
                cat = 'source' if f_type != 'unknown' else 'other'
                if 'test' in file.lower() or 'spec' in file.lower(): cat = 'test'
                elif ext in ['.json', '.yaml', '.yml', '.toml', '.env', '.ini']: cat = 'config'
                    
                index['files'][rel_path] = {
                    'path': rel_path,
                    'mtime': mtime,
                    'size': size,
                    'hash': current_hash,
                    'is_text': is_text,
                    'extension': ext.lower(),
                    'raw_dependencies': deps,
                    'resolved_deps': [],
                    'heuristic_deps': [],
                    'ambiguous_deps': [],
                    'unresolved_deps': [],
                    'words_index': words_index,
                    'is_entry_point': is_entry_point,
                    'category': cat,
                    'ambiguous_candidates': {}
                }
            except Exception as e:
                index['metadata']['warnings'].append(f"Could not read {rel_path}: {str(e)}")
                skipped_count += 1

    old_paths = set(old_index['files'].keys())
    deleted = list(old_paths - all_current_paths)
    
    # Rename detection
    deleted_hashes = {p: old_index['files'][p]['hash'] for p in deleted}
    added_hashes = {p: index['files'][p]['hash'] for p in added}
    renames = []
    for a_path, a_hash in added_hashes.items():
        for d_path, d_hash in list(deleted_hashes.items()):
            if a_hash == d_hash:
                renames.append({'from': d_path, 'to': a_path})
                added.remove(a_path)
                deleted.remove(d_path)
                del deleted_hashes[d_path]
                break

    all_files = set(index['files'].keys())
    for rel_path, info in index['files'].items():
        if info.get('resolved_deps') and rel_path in unchanged: continue
        resolved, heuristic, ambiguous, unresolved = [], [], [], []
        ambig_cand = {}
        for raw_dep in info.get('raw_dependencies', []):
            res, method, cands = resolve_dependency(rel_path, raw_dep, all_files)
            if method.startswith("resolved"): resolved.append(res)
            elif method == "heuristic_basename": heuristic.append(res)
            elif method == "ambiguous": 
                ambiguous.append(res)
                ambig_cand[res] = cands
            else: unresolved.append(raw_dep)
        
        info['resolved_deps'] = sorted(list(set(resolved)))
        info['heuristic_deps'] = sorted(list(set(heuristic)))
        info['ambiguous_deps'] = sorted(list(set(ambiguous)))
        info['unresolved_deps'] = sorted(list(set(unresolved)))
        info['ambiguous_candidates'] = ambig_cand

    index_path = os.path.join(directory, INDEX_FILE)
    tmp_path = index_path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f: json.dump(index, f)
    os.replace(tmp_path, index_path)

    summary = {
        "added": sorted(added),
        "changed": sorted(changed),
        "deleted": sorted(deleted),
        "renames": renames,
        "unchanged": sorted(unchanged),
        "reused_count": len(unchanged),
        "warnings": index['metadata']['warnings']
    }

    if output_file: output_result(summary, output_file)
    else: print(f"Scan complete. Reused: {len(unchanged)}, Added: {len(added)}, Changed: {len(changed)}, Deleted: {len(deleted)}, Renamed: {len(renames)}")

def load_index(directory, silent=False):
    index_path = os.path.join(directory, INDEX_FILE)
    if not os.path.exists(index_path):
        if not silent: eprint("Error: No index found. Run 'scan' first.")
        return None
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if data.get('version') != SCHEMA_VERSION:
                if not silent: eprint("Index version mismatch. Please run 'scan' again.")
                return None
            return data
    except Exception:
        if not silent: eprint("Error reading index.")
        return None

def build_forward_reverse(index):
    forward, reverse = defaultdict(list), defaultdict(list)
    for p, info in index['files'].items():
        for dep in info.get('resolved_deps', []) + info.get('heuristic_deps', []):
            forward[p].append(dep)
            reverse[dep].append(p)
    return forward, reverse

def find_cycles(forward):
    cycles, visited, path, path_set = [], set(), [], set()
    def dfs(node):
        if node in path_set:
            cycles.append(path[path.index(node):] + [node])
            return
        if node in visited: return
        visited.add(node); path.append(node); path_set.add(node)
        for nxt in forward.get(node, []): dfs(nxt)
        path.pop(); path_set.remove(node)
    for node in forward:
        if node not in visited: dfs(node)
    unique_cycles, seen = [], set()
    for c in cycles:
        canon = tuple(sorted(set(c)))
        if canon not in seen:
            seen.add(canon); unique_cycles.append(c)
    return unique_cycles

def generate_tree(files):
    tree = {"dirs": defaultdict(dict), "files": []}
    for f in sorted(files):
        parts = f.split('/')
        curr = tree
        for part in parts[:-1]:
            if part not in curr["dirs"]: curr["dirs"][part] = {"dirs": defaultdict(dict), "files": []}
            curr = curr["dirs"][part]
        curr["files"].append(parts[-1])
    
    lines = []
    def walk(node, prefix=""):
        for i, (d, sub) in enumerate(sorted(node["dirs"].items())):
            is_last = (i == len(node["dirs"]) - 1 and len(node["files"]) == 0)
            ptr = "└── " if is_last else "├── "
            lines.append(f"{prefix}{ptr}{d}/")
            walk(sub, prefix + ("    " if is_last else "│   "))
        for i, f in enumerate(sorted(node["files"])):
            is_last = (i == len(node["files"]) - 1)
            ptr = "└── " if is_last else "├── "
            lines.append(f"{prefix}{ptr}{f}")
    walk(tree)
    return "\n".join(lines)

def output_result(data, output_file):
    if output_file == '-': print(json.dumps(data, indent=2))
    else:
        with open(output_file, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
        print(f"Report saved to {output_file}")

def overview(directory, output_file=None):
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
        if not info.get('is_text'): metrics['unknown_bin'] += 1
            
    tree_out = generate_tree(index['files'].keys())

    report = {
        "metadata": index["metadata"],
        "categories": dict(categories),
        "total_files": index['metadata']['total_files'],
        "total_dirs": index['metadata']['total_dirs'],
        "total_size": index['metadata']['total_size'],
        "relationship_count": metrics['proven'] + metrics['heuristic'],
        "proven_relationship_count": metrics['proven'],
        "heuristic_relationship_count": metrics['heuristic'],
        "ambiguous_relationship_count": metrics['ambiguous'],
        "unresolved_relationship_count": metrics['unresolved'],
        "orphans_count": len(orphans),
        "cycles_count": len(cycles),
        "unknown_binary_count": metrics['unknown_bin'],
        "skipped_or_partial_count": len(index['metadata']['warnings']),
        "index_status": "ready",
        "project_tree": tree_out,
        "warnings": index['metadata']['warnings'] + (["Some ambiguous edges were excluded from relationship counts and graph traversal."] if metrics["ambiguous"] > 0 else [])
    }

    if output_file:
        output_result(report, output_file)
        return

    print("Project Overview & Health Report:\n")
    for k, v in report.items():
        if k not in ['project_tree', 'metadata', 'categories', 'warnings']: print(f"{k}: {v}")
    print("\nProject Map (First 40 paths):")
    print("\n".join(tree_out.split("\n")[:40]))

def match_target(target, all_files):
    if target in all_files: return target
    matches = [p for p in all_files if p.endswith(target) or target in p]
    if len(matches) == 1: return matches[0]
    if len(matches) > 1:
        eprint(f"Error: Target '{target}' is ambiguous. Matches: {', '.join(matches)}")
        sys.exit(1)
    eprint(f"Error: Target '{target}' not found.")
    sys.exit(1)

def who_uses(filepath, directory, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
    _, reverse = build_forward_reverse(index)
    target = match_target(filepath, index['files'].keys())
    users = sorted(reverse.get(target, []))
    if output_file: output_result(users, output_file)
    else:
        print(f"Files directly using '{target}':")
        for u in users: print(f"  - {u}")

def depends_on(filepath, directory, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
    target = match_target(filepath, index['files'].keys())
    info = index['files'][target]
    result = {
        "resolved": info.get('resolved_deps', []),
        "heuristic": info.get('heuristic_deps', []),
        "ambiguous": info.get('ambiguous_deps', []),
        "ambiguous_candidates": info.get('ambiguous_candidates', {}),
        "unresolved": info.get('unresolved_deps', [])
    }
    if output_file: output_result(result, output_file)
    else:
        for k, v in result.items():
            print(f"\n{k.capitalize()}:")
            if isinstance(v, list):
                for d in v: print(f"  - {d}")
            elif isinstance(v, dict):
                for d, cands in v.items(): print(f"  - {d} -> {cands}")

def impact(filepath, directory, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
    _, reverse = build_forward_reverse(index)
    target = match_target(filepath, index['files'].keys())
    
    direct = set(reverse.get(target, []))
    visited, queue, indirect = set(direct), deque(direct), set()
    while queue:
        curr = queue.popleft()
        for user in reverse.get(curr, []):
            if user not in visited and user != target:
                visited.add(user); indirect.add(user); queue.append(user)
                
    result = {
        "changed": target,
        "direct": sorted(list(direct)),
        "indirect": sorted(list(indirect)),
        "potential_impact_count": len(direct) + len(indirect),
        "warnings": ["Dependency-based potential impact. Heuristic edges included.", "Ambiguous edges were excluded from traversal."]
    }
    if output_file: output_result(result, output_file)
    else:
        print(f"Changed: {target}\nDirectly affected ({len(direct)}):")
        for v in sorted(list(direct)): print(f"  - {v}")
        print(f"\nIndirectly affected ({len(indirect)}):")
        for v in sorted(list(indirect)): print(f"  - {v}")

def search(query, directory, path_glob=None, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
    matches_found = []
    q_lower = query.lower()
    
    for filepath, info in index['files'].items():
        if path_glob and not fnmatch.fnmatch(filepath, path_glob): continue
        if not info.get('is_text'): continue
        
        words_index = info.get('words_index', {})
        if q_lower not in words_index: continue
        
        full_path = os.path.join(directory, filepath)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line_num in words_index[q_lower]:
                    line_idx = line_num - 1
                    if line_idx < len(lines) and query in lines[line_idx]:
                        matches_found.append({'file': filepath, 'line': line_num, 'context': lines[line_idx].strip()[:100]})
        except Exception: pass
                
    matches_found.sort(key=lambda x: (x['file'], x['line']))
    if output_file: output_result({"matches": matches_found, "count": len(matches_found)}, output_file)
    else:
        print(f"Searching for '{query}' (Full Inverted Index)...")
        for m in matches_found: print(f"{m['file']}:{m['line']} {m['context']}")
        print(f"Total matches: {len(matches_found)}")

def inspect(filepath, output_file=None):
    if not os.path.exists(filepath):
        eprint("Error: File not found.")
        sys.exit(1)
        
    size = os.path.getsize(filepath)
    ext = os.path.splitext(filepath)[1].lower()
    file_hash = get_file_hash(filepath)
    
    try:
        with open(filepath, 'rb') as f: header = f.read(32)
    except Exception as e:
        eprint(f"Error reading file: {e}")
        sys.exit(1)

    file_type, confidence, evidence = "Unknown Binary", "Low", "first 32 bytes"
    metadata, warnings = {}, []
    is_mismatch, is_text = False, False

    if header.startswith(b'\x89PNG\r\n\x1a\n'): 
        file_type, confidence = "PNG Image", "High (Signature)"
        if ext not in ['.png']: is_mismatch = True
    elif header.startswith(b'\xff\xd8\xff'): 
        file_type, confidence = "JPEG Image", "High (Signature)"
        if ext not in ['.jpg', '.jpeg']: is_mismatch = True
    elif header.startswith(b'%PDF-'): 
        file_type, confidence = "PDF Document", "High (Signature)"
        if ext != '.pdf': is_mismatch = True
    elif header.startswith(b'PK\x03\x04'): 
        file_type, confidence = "ZIP Archive", "High (Validated)"
        try:
            with zipfile.ZipFile(filepath, 'r') as z:
                metadata['zip_members'] = z.namelist()[:10]
                bad_file = z.testzip()
                if bad_file: warnings.append(f"Corrupted file inside ZIP: {bad_file}")
        except Exception as e:
            confidence = "Low (Malformed)"
            warnings.append(f"Malformed ZIP: {str(e)}")
    elif header.startswith(b'SQLite format 3\x00'): 
        file_type, confidence = "SQLite Database", "High (Validated)"
        try:
            with open(filepath, 'rb') as f:
                f.seek(16); metadata['page_size'] = struct.unpack(">H", f.read(2))[0]
                f.seek(28); metadata['size_in_pages'] = struct.unpack(">I", f.read(4))[0]
        except Exception as e:
            confidence = "Low (Malformed)"
            warnings.append(f"Malformed SQLite: {str(e)}")
    elif is_text_file(filepath): 
        file_type, confidence, is_text = "Text/Source", "Medium (Heuristic)", True
        if ext not in ['.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json', '.yaml', '.yml', '.toml', '.ini', '.csv', '.xml', '']:
            is_mismatch = True
        if ext == '.json':
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    confidence = "High (Validated JSON)"
                    if isinstance(data, dict): metadata['json_keys'] = list(data.keys())[:10]
            except Exception as e:
                confidence = "Low (Malformed JSON)"
                warnings.append(f"Malformed JSON: {str(e)}")

    result = {
        "path": filepath,
        "size": size,
        "extension": ext,
        "sha256": file_hash,
        "is_text": is_text,
        "detected_type": file_type,
        "confidence": confidence,
        "evidence": evidence,
        "extension_mismatch": is_mismatch,
        "metadata": metadata,
        "warnings": warnings
    }
    if file_type == "Unknown Binary":
        result["first_bytes_hex"] = header.hex()
        result["first_bytes_ascii"] = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in header)

    if output_file: output_result(result, output_file)
    else: print(json.dumps(result, indent=2))

def main():
    parser = argparse.ArgumentParser(description="RepoXray - Zero Dependency Codebase Analyzer")
    subparsers = parser.add_subparsers(dest="command")
    
    def add_common(p): p.add_argument("--output", help="Output JSON report file (or '-' for stdout)")
    
    p_scan = subparsers.add_parser("scan")
    p_scan.add_argument("path", nargs="?", default=".")
    add_common(p_scan)
    
    p_overview = subparsers.add_parser("overview")
    p_overview.add_argument("path", nargs="?", default=".")
    add_common(p_overview)
    
    p_search = subparsers.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("path", nargs="?", default=".")
    p_search.add_argument("--path", dest="path_glob", help="Glob pattern")
    add_common(p_search)
    
    p_inspect = subparsers.add_parser("inspect")
    p_inspect.add_argument("file")
    add_common(p_inspect)
    
    for cmd in ["impact", "who-uses", "depends-on"]:
        p = subparsers.add_parser(cmd)
        p.add_argument("file")
        p.add_argument("path", nargs="?", default=".")
        add_common(p)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "scan": scan(args.path or ".", args.output)
        elif args.command == "overview": overview(args.path or ".", args.output)
        elif args.command == "search": search(args.query, args.path or ".", getattr(args, 'path_glob', None), args.output)
        elif args.command == "inspect": inspect(args.file, args.output)
        elif args.command == "impact": impact(args.file, args.path or ".", args.output)
        elif args.command == "who-uses": who_uses(args.file, args.path or ".", args.output)
        elif args.command == "depends-on": depends_on(args.file, args.path or ".", args.output)
    except Exception as e:
        eprint(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
