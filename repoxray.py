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
from collections import defaultdict, deque

SCHEMA_VERSION = "2.0"
INDEX_FILE = '.repoxray.json'
MAX_TEXT_SCAN_SIZE = 5 * 1024 * 1024  # 5 MB

IMPORT_PATTERNS = {
    'python': [
        re.compile(r'^\s*import\s+([a-zA-Z0-9_\.]+)', re.MULTILINE),
        re.compile(r'^\s*from\s+([a-zA-Z0-9_\.]+)\s+import', re.MULTILINE)
    ],
    'js': [
        re.compile(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE),
        re.compile(r'require\([\'"]([^\'"]+)[\'"]\)', re.MULTILINE)
    ]
}

# Directories to ignore by default
DEFAULT_IGNORE = {'.git', 'node_modules', '__pycache__', 'venv', 'env', 'dist', 'build', '.next'}

class Colors:
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def disable_colors():
    Colors.OKBLUE = Colors.OKCYAN = Colors.OKGREEN = Colors.WARNING = Colors.FAIL = Colors.ENDC = Colors.BOLD = ''

def get_file_hash(filepath):
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def is_text_file(filepath):
    try:
        with open(filepath, 'tr', encoding='utf-8') as f:
            f.read(1024)
            return True
    except Exception:
        return False

def parse_text_file(filepath, file_type):
    deps = set()
    words = set()
    try:
        if os.path.getsize(filepath) > MAX_TEXT_SCAN_SIZE:
            return list(deps), list(words)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            for pattern in IMPORT_PATTERNS.get(file_type, []):
                for match in pattern.findall(content):
                    deps.add(match)
            for w in re.findall(r'[a-zA-Z0-9_]{3,}', content.lower()):
                words.add(w)
    except Exception:
        pass
    return list(deps), list(words)

def get_file_type(ext):
    if ext in ['.py']: return 'python'
    if ext in ['.js', '.jsx', '.ts', '.tsx']: return 'js'
    return 'unknown'

def resolve_dependency(source_file, raw_dep, all_files):
    dir_name = os.path.dirname(source_file)
    exts_js = ['', '.js', '.jsx', '.ts', '.tsx', '/index.js', '/index.ts']
    exts_py = ['', '.py', '/__init__.py']
    
    # JS/TS relative imports
    if raw_dep.startswith('.'):
        target = os.path.normpath(os.path.join(dir_name, raw_dep))
        exts = exts_js if source_file.endswith(('.js','.ts','.jsx','.tsx')) else exts_py
        for ext in exts:
            if target + ext in all_files:
                return target + ext
    else:
        # Python module format or JS Node Module
        py_target = raw_dep.replace('.', '/')
        for ext in exts_py + exts_js:
            # Check relative to source (e.g., python relative without dots if they are in same dir)
            local_target = os.path.normpath(os.path.join(dir_name, py_target)) + ext
            if local_target in all_files: return local_target
            
            # Check relative to root
            if py_target + ext in all_files: return py_target + ext
            
        # Fallback heuristic: filename match
        for f in all_files:
            bname = os.path.basename(f)
            if bname == raw_dep + ".py" or bname == raw_dep + ".js" or bname == raw_dep + ".ts":
                return f
    return None

def scan(directory, output_file=None):
    old_index = load_index(directory, silent=True)
    if not old_index or old_index.get('version') != SCHEMA_VERSION:
        old_index = {'files': {}}
        
    index = {
        'version': SCHEMA_VERSION,
        'metadata': {'total_files': 0, 'total_dirs': 0, 'total_size': 0, 'warnings': []},
        'files': {}
    }
    
    incremental_files = 0
    all_current_paths = set()
    
    # Pass 1: Walk and Index files
    for root, dirs, files in os.walk(directory):
        # Hidden files are included unless they are in DEFAULT_IGNORE
        dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORE]
        index['metadata']['total_dirs'] += 1
        
        for file in files:
            if file == INDEX_FILE:
                continue
                
            filepath = os.path.join(root, file)
            rel_path = os.path.normpath(os.path.relpath(filepath, directory))
            all_current_paths.add(rel_path)
            
            try:
                mtime = os.path.getmtime(filepath)
                size = os.path.getsize(filepath)
                index['metadata']['total_size'] += size
                index['metadata']['total_files'] += 1
                
                old_record = old_index['files'].get(rel_path)
                if old_record and old_record.get('mtime') == mtime and old_record.get('size') == size:
                    index['files'][rel_path] = old_record
                    incremental_files += 1
                    continue
                
                _, ext = os.path.splitext(file)
                f_type = get_file_type(ext)
                is_text = is_text_file(filepath)
                
                deps, words = ([], [])
                if is_text:
                    deps, words = parse_text_file(filepath, f_type)
                
                cat = 'source' if f_type != 'unknown' else 'other'
                if 'test' in file.lower() or 'spec' in file.lower(): cat = 'test'
                elif ext in ['.json', '.yaml', '.yml', '.toml', '.env', '.ini']: cat = 'config'
                    
                index['files'][rel_path] = {
                    'path': rel_path,
                    'mtime': mtime,
                    'size': size,
                    'hash': get_file_hash(filepath),
                    'is_text': is_text,
                    'extension': ext.lower(),
                    'raw_dependencies': deps,
                    'resolved_deps': [],
                    'unresolved_deps': [],
                    'words': words,
                    'category': cat
                }
            except Exception as e:
                index['metadata']['warnings'].append(f"Could not read {rel_path}: {str(e)}")

    # Pass 2: Resolve dependencies globally
    all_files = set(index['files'].keys())
    for rel_path, info in index['files'].items():
        resolved = []
        unresolved = []
        for raw_dep in info.get('raw_dependencies', []):
            res = resolve_dependency(rel_path, raw_dep, all_files)
            if res: resolved.append(res)
            else: unresolved.append(raw_dep)
        
        # Deduplicate
        info['resolved_deps'] = sorted(list(set(resolved)))
        info['unresolved_deps'] = sorted(list(set(unresolved)))

    # Save atomically
    index_path = os.path.join(directory, INDEX_FILE)
    tmp_path = index_path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(index, f)
    os.replace(tmp_path, index_path)

    if output_file:
        output_result(index, output_file)
    else:
        print(f"{Colors.OKGREEN}Scan complete. Indexed {index['metadata']['total_files']} files. Incremental reuses: {incremental_files}. Saved to {INDEX_FILE}.{Colors.ENDC}")

def load_index(directory, silent=False):
    index_path = os.path.join(directory, INDEX_FILE)
    if not os.path.exists(index_path):
        if not silent: print(f"{Colors.FAIL}Error: No index found. Run 'scan' first.{Colors.ENDC}", file=sys.stderr)
        return None
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if data.get('version') != SCHEMA_VERSION:
                if not silent: print(f"{Colors.WARNING}Index version mismatch. Please run 'scan' again.{Colors.ENDC}", file=sys.stderr)
                return None
            return data
    except Exception:
        if not silent: print(f"{Colors.FAIL}Error reading index.{Colors.ENDC}", file=sys.stderr)
        return None

def build_forward_reverse(index):
    forward = defaultdict(list)
    reverse = defaultdict(list)
    for p, info in index['files'].items():
        for dep in info.get('resolved_deps', []):
            forward[p].append(dep)
            reverse[dep].append(p)
    return forward, reverse

def find_cycles(forward):
    cycles = []
    visited = set()
    path = []
    path_set = set()

    def dfs(node):
        if node in path_set:
            idx = path.index(node)
            cycles.append(path[idx:] + [node])
            return
        if node in visited:
            return
            
        visited.add(node)
        path.append(node)
        path_set.add(node)
        
        for nxt in forward.get(node, []):
            dfs(nxt)
            
        path.pop()
        path_set.remove(node)

    for node in forward:
        if node not in visited:
            dfs(node)
            
    # Deduplicate cycles (simplistic)
    unique_cycles = []
    seen = set()
    for c in cycles:
        canon = tuple(sorted(set(c)))
        if canon not in seen:
            seen.add(canon)
            unique_cycles.append(c)
    return unique_cycles

def generate_tree(files):
    tree = {"dirs": defaultdict(dict), "files": []}
    for f in sorted(files):
        parts = f.split('/')
        curr = tree
        for part in parts[:-1]:
            if part not in curr["dirs"]:
                curr["dirs"][part] = {"dirs": defaultdict(dict), "files": []}
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
    if output_file == '-':
        disable_colors()
        print(json.dumps(data, indent=2))
    else:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"Report saved to {output_file}")

def overview(directory, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
        
    forward, reverse = build_forward_reverse(index)
    orphans = [p for p, info in index['files'].items() if p not in reverse and info['category'] == 'source']
    cycles = find_cycles(forward)
    
    categories = defaultdict(int)
    unresolved_count = 0
    unknown_binary_count = 0
    rel_count = 0
    
    for info in index['files'].values():
        categories[info['category']] += 1
        unresolved_count += len(info.get('unresolved_deps', []))
        rel_count += len(info.get('resolved_deps', []))
        if not info.get('is_text') and info.get('extension') == '':
            unknown_binary_count += 1

    report = {
        "metadata": index["metadata"],
        "categories": categories,
        "relationship_count": rel_count,
        "unresolved_relationships": unresolved_count,
        "orphans_count": len(orphans),
        "cycles_count": len(cycles),
        "unknown_binary_count": unknown_binary_count,
        "orphans": orphans[:50]
    }

    if output_file:
        output_result(report, output_file)
        return

    print(f"\n{Colors.BOLD}Project Overview & Health Report:{Colors.ENDC}")
    print(f"Total files: {index['metadata']['total_files']}")
    print(f"Total size:  {index['metadata']['total_size'] / (1024*1024):.2f} MB")
    
    print(f"\n{Colors.BOLD}Categories:{Colors.ENDC}")
    for cat, count in categories.items():
        print(f"  {cat.capitalize():<10} {count}")
        
    print(f"\n{Colors.BOLD}Relationships:{Colors.ENDC}")
    print(f"  Total Edges: {rel_count}")
    print(f"  Unresolved : {unresolved_count}")
    print(f"  Cycles     : {len(cycles)}")
    
    print(f"\n{Colors.BOLD}Project Map (First 40 paths):{Colors.ENDC}")
    tree_out = generate_tree(index['files'].keys())
    print("\n".join(tree_out.split("\n")[:40]))
    
    print(f"\n{Colors.WARNING}Potential Orphans (Heuristic: Source files with 0 incoming dependencies): {len(orphans)}{Colors.ENDC}")
    for o in orphans[:10]: print(f"  - {o}")
    if len(orphans) > 10: print("  ... and more")

def match_target(target, all_files):
    matches = [p for p in all_files if target in p]
    if not matches: return None
    return matches[0]

def who_uses(filepath, directory, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
    
    _, reverse = build_forward_reverse(index)
    target = match_target(filepath, index['files'].keys())
    
    if not target:
        if output_file: output_result([], output_file)
        else: print(f"{Colors.FAIL}File not found in index.{Colors.ENDC}")
        return
        
    users = sorted(reverse.get(target, []))
    if output_file:
        output_result(users, output_file)
        return
        
    print(f"{Colors.OKBLUE}Files directly using '{target}':{Colors.ENDC}")
    if not users:
        print("  (None)")
    for u in users: print(f"  - {u}")

def depends_on(filepath, directory, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
    
    target = match_target(filepath, index['files'].keys())
    if not target:
        if output_file: output_result({}, output_file)
        else: print(f"{Colors.FAIL}File not found in index.{Colors.ENDC}")
        return
        
    info = index['files'][target]
    resolved = info.get('resolved_deps', [])
    unresolved = info.get('unresolved_deps', [])
    
    if output_file:
        output_result({"resolved": resolved, "unresolved": unresolved}, output_file)
        return
        
    print(f"{Colors.OKBLUE}Dependencies for '{target}':{Colors.ENDC}")
    print(f"{Colors.BOLD}Resolved:{Colors.ENDC}")
    for d in resolved: print(f"  - {d}")
    if not resolved: print("  (None)")
    print(f"\n{Colors.WARNING}Unresolved:{Colors.ENDC}")
    for u in unresolved: print(f"  - {u}")
    if not unresolved: print("  (None)")

def impact(filepath, directory, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
    
    _, reverse = build_forward_reverse(index)
    target = match_target(filepath, index['files'].keys())
    
    if not target:
        if output_file: output_result({}, output_file)
        else: print(f"{Colors.FAIL}File not found in index.{Colors.ENDC}")
        return
        
    direct = set(reverse.get(target, []))
    visited = set(direct)
    queue = deque(direct)
    indirect = set()
    
    while queue:
        curr = queue.popleft()
        for user in reverse.get(curr, []):
            if user not in visited and user != target:
                visited.add(user)
                indirect.add(user)
                queue.append(user)
                
    result = {
        "changed": target,
        "direct": sorted(list(direct)),
        "indirect": sorted(list(indirect)),
        "potential_impact_count": len(direct) + len(indirect),
        "warnings": "This is a dependency-based potential impact analysis, not a guarantee of runtime breakage."
    }
                
    if output_file:
        output_result(result, output_file)
        return
        
    print(f"{Colors.WARNING}Graph-based impact analysis (Potential impact){Colors.ENDC}")
    print(f"Changed: {target}\n")
    print(f"{Colors.BOLD}Directly affected ({len(direct)}):{Colors.ENDC}")
    for v in sorted(list(direct)): print(f"  - {v}")
    if not direct: print("  (None)")
    
    print(f"\n{Colors.BOLD}Indirectly affected ({len(indirect)}):{Colors.ENDC}")
    for v in sorted(list(indirect)): print(f"  - {v}")
    if not indirect: print("  (None)")

def search(query, directory, path_glob=None, output_file=None):
    index = load_index(directory)
    matches_found = []
    
    query_words = set(re.findall(r'[a-zA-Z0-9_]{3,}', query.lower()))
    
    for filepath, info in (index['files'].items() if index else []):
        if path_glob and not fnmatch.fnmatch(filepath, path_glob):
            continue
            
        if not info.get('is_text'): 
            continue
        
        # Indexed check: skip file if it doesn't contain the query words
        if query_words and not query_words.issubset(set(info.get('words', []))):
            continue
            
        full_path = os.path.join(directory, filepath)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if query in line:
                        matches_found.append({
                            'file': filepath,
                            'line': line_num,
                            'context': line.strip()[:100]
                        })
        except Exception:
            pass
                
    # Basic deterministic ordering
    matches_found.sort(key=lambda x: (x['file'], x['line']))
    
    if output_file:
        output_result(matches_found, output_file)
        return
        
    print(f"{Colors.OKBLUE}Searching for '{query}' (Indexed)...{Colors.ENDC}\n")
    for m in matches_found:
        print(f"{Colors.OKGREEN}{m['file']}:{m['line']}{Colors.ENDC} {m['context']}")
    print(f"\n{Colors.BOLD}Total matches: {len(matches_found)}{Colors.ENDC}")

def inspect(filepath, output_file=None):
    if not os.path.exists(filepath):
        sys.exit(1)
        
    size = os.path.getsize(filepath)
    ext = os.path.splitext(filepath)[1].lower()
    file_hash = get_file_hash(filepath)
    
    try:
        with open(filepath, 'rb') as f: header = f.read(32)
    except Exception:
        sys.exit(1)

    file_type, confidence = "Unknown Binary", "Low"
    metadata = {}
    is_mismatch = False

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
        file_type, confidence = "ZIP Archive", "High (Signature)"
        try:
            with zipfile.ZipFile(filepath, 'r') as z:
                metadata['zip_members'] = z.namelist()[:10]
                if len(z.namelist()) > 10: metadata['zip_truncated'] = True
        except:
            pass
    elif header.startswith(b'SQLite format 3\x00'): 
        file_type, confidence = "SQLite Database", "High (Signature)"
        try:
            with open(filepath, 'rb') as f:
                f.seek(16)
                page_size = struct.unpack(">H", f.read(2))[0]
                metadata['page_size'] = page_size
        except:
            pass
    elif is_text_file(filepath): 
        file_type, confidence = "Text/Source", "Medium (Heuristic)"
        if ext not in ['.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json', '.yaml', '.yml', '.toml', '.ini', '.csv', '.xml', '']:
            is_mismatch = True
        if ext == '.json':
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict): metadata['json_keys'] = list(data.keys())[:10]
            except:
                pass

    result = {
        "size": size,
        "extension": ext,
        "type": file_type,
        "confidence": confidence,
        "hash": file_hash,
        "extension_mismatch": is_mismatch,
        "metadata": metadata
    }

    if file_type == "Unknown Binary":
        result["first_bytes_hex"] = header.hex()
        result["first_bytes_ascii"] = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in header)

    if output_file:
        output_result(result, output_file)
        return

    print(f"{Colors.OKBLUE}Inspecting: {filepath}{Colors.ENDC}")
    print(f"Size: {size} bytes")
    print(f"Extension: {ext}")
    print(f"Detected Type: {Colors.BOLD}{file_type}{Colors.ENDC} (Confidence: {confidence})")
    if is_mismatch:
        print(f"{Colors.FAIL}Warning: Detected signature does not match extension '{ext}'{Colors.ENDC}")
    print(f"SHA-256: {file_hash}")
    
    if metadata:
        print(f"\n{Colors.BOLD}Extracted Metadata:{Colors.ENDC}")
        for k, v in metadata.items():
            print(f"  {k}: {v}")
            
    if file_type == "Unknown Binary":
        print(f"\n{Colors.BOLD}Raw Header Preview:{Colors.ENDC}")
        print(f"  Hex:   {header.hex()}")
        print(f"  ASCII: {''.join(chr(b) if 32 <= b <= 126 else '.' for b in header)}")

def main():
    parser = argparse.ArgumentParser(description="RepoXray - Zero Dependency Codebase Analyzer")
    subparsers = parser.add_subparsers(dest="command")
    
    def add_common(p):
        p.add_argument("--output", help="Output JSON report file (or '-' for stdout)")
    
    p_scan = subparsers.add_parser("scan", help="Scan and index the project")
    p_scan.add_argument("path", nargs="?", default=".")
    add_common(p_scan)
    
    p_overview = subparsers.add_parser("overview", help="Project health and map")
    p_overview.add_argument("path", nargs="?", default=".")
    add_common(p_overview)
    
    p_search = subparsers.add_parser("search", help="Indexed content/path search")
    p_search.add_argument("query")
    p_search.add_argument("path", nargs="?", default=".")
    p_search.add_argument("--path", dest="path_glob", help="Glob pattern for paths (e.g. *.json)")
    add_common(p_search)
    
    p_inspect = subparsers.add_parser("inspect", help="X-ray a specific file")
    p_inspect.add_argument("file")
    add_common(p_inspect)
    
    p_impact = subparsers.add_parser("impact", help="Trace direct and indirect impact")
    p_impact.add_argument("file")
    p_impact.add_argument("path", nargs="?", default=".")
    add_common(p_impact)
    
    p_who = subparsers.add_parser("who-uses", help="Show files importing the target")
    p_who.add_argument("file")
    p_who.add_argument("path", nargs="?", default=".")
    add_common(p_who)
    
    p_depends = subparsers.add_parser("depends-on", help="Show files the target imports")
    p_depends.add_argument("file")
    p_depends.add_argument("path", nargs="?", default=".")
    add_common(p_depends)

    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "scan": scan(args.path, args.output)
    elif args.command == "overview": overview(args.path, args.output)
    elif args.command == "search": search(args.query, args.path, getattr(args, 'path_glob', None), args.output)
    elif args.command == "inspect": inspect(args.file, args.output)
    elif args.command == "impact": impact(args.file, args.path, args.output)
    elif args.command == "who-uses": who_uses(args.file, args.path, args.output)
    elif args.command == "depends-on": depends_on(args.file, args.path, args.output)

if __name__ == "__main__":
    main()
