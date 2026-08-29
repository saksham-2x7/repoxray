#!/usr/bin/env python3
import os
import sys
import argparse
import json
import re
import hashlib
from collections import defaultdict, deque

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

IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', 'venv', 'env', 'dist', 'build', '.next'}
INDEX_FILE = '.repoxray.json'

class Colors:
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

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
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract dependencies
            for pattern in IMPORT_PATTERNS.get(file_type, []):
                for match in pattern.findall(content):
                    deps.add(match)
            # Extract words for search index
            for w in re.findall(r'[a-zA-Z0-9_]{3,}', content.lower()):
                words.add(w)
    except Exception:
        pass
    return list(deps), list(words)

def get_file_type(ext):
    if ext in ['.py']: return 'python'
    if ext in ['.js', '.jsx', '.ts', '.tsx']: return 'js'
    return 'unknown'

def scan(directory, output_file=None):
    if not output_file:
        print(f"{Colors.OKBLUE}Scanning directory (Incremental): {directory}{Colors.ENDC}")
    
    old_index = load_index(directory) or {'files': {}}
    index = {'files': {}, 'metadata': {'total_files': 0, 'total_dirs': 0, 'total_size': 0}}
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        index['metadata']['total_dirs'] += 1
        
        for file in files:
            if file == INDEX_FILE:
                continue
                
            filepath = os.path.join(root, file)
            rel_path = os.path.normpath(os.path.relpath(filepath, directory))
            
            try:
                mtime = os.path.getmtime(filepath)
                size = os.path.getsize(filepath)
                index['metadata']['total_size'] += size
                index['metadata']['total_files'] += 1
                
                # Incremental check
                old_record = old_index['files'].get(rel_path)
                if old_record and old_record.get('mtime') == mtime and old_record.get('size') == size:
                    index['files'][rel_path] = old_record
                    continue
                
                _, ext = os.path.splitext(file)
                f_type = get_file_type(ext)
                is_text = is_text_file(filepath)
                
                deps, words = ([], [])
                if is_text:
                    deps, words = parse_text_file(filepath, f_type)
                
                cat = 'source' if f_type != 'unknown' else 'other'
                if 'test' in file.lower() or 'spec' in file.lower(): cat = 'test'
                elif ext in ['.json', '.yaml', '.yml', '.toml', '.env']: cat = 'config'
                    
                index['files'][rel_path] = {
                    'path': rel_path,
                    'mtime': mtime,
                    'size': size,
                    'hash': get_file_hash(filepath),
                    'is_text': is_text,
                    'extension': ext,
                    'dependencies': deps,
                    'words': words,
                    'category': cat
                }
            except Exception:
                pass
                
    index_path = os.path.join(directory, INDEX_FILE)
    with open(index_path, 'w') as f:
        json.dump(index, f)

    if output_file:
        output_result(index, output_file)
    else:
        print(f"{Colors.OKGREEN}Scan complete. Index saved to {INDEX_FILE}.{Colors.ENDC}")

def load_index(directory):
    index_path = os.path.join(directory, INDEX_FILE)
    if not os.path.exists(index_path):
        return None
    try:
        with open(index_path, 'r') as f:
            return json.load(f)
    except:
        return None

def resolve_dependency(file_path, raw_dep, all_files):
    dir_name = os.path.dirname(file_path)
    # JS/TS relative imports
    if raw_dep.startswith('.'):
        target = os.path.normpath(os.path.join(dir_name, raw_dep))
        for ext in ['', '.js', '.jsx', '.ts', '.tsx', '.py', '/index.js', '/index.ts']:
            if target + ext in all_files:
                return target + ext
    else:
        # Absolute or module import (Python or Node)
        # Convert dot notation to path for python
        py_target = raw_dep.replace('.', '/')
        for ext in ['', '.py', '.js', '.ts']:
            # Check relative first (python modules)
            local_target = os.path.normpath(os.path.join(dir_name, py_target)) + ext
            if local_target in all_files: return local_target
            # Check global root
            if py_target + ext in all_files: return py_target + ext
            # Check just the basename as fallback
            for f in all_files:
                if os.path.basename(f) == raw_dep + ext or os.path.basename(f) == py_target + ext:
                    return f
    return None

def build_graph(index):
    forward = defaultdict(list)
    reverse = defaultdict(list)
    all_files = set(index['files'].keys())
        
    for p, info in index['files'].items():
        for dep in info.get('dependencies', []):
            resolved = resolve_dependency(p, dep, all_files)
            if resolved:
                forward[p].append(resolved)
                reverse[resolved].append(p)
                    
    return forward, reverse

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
        for d, sub in node["dirs"].items():
            lines.append(f"{prefix}├── {d}/")
            walk(sub, prefix + "│   ")
        for f in node["files"]:
            lines.append(f"{prefix}├── {f}")
    walk(tree)
    return "\n".join(lines)

def output_result(data, output_file):
    if output_file == '-':
        print(json.dumps(data, indent=2))
    else:
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Report saved to {output_file}")

def overview(directory, output_file=None):
    index = load_index(directory)
    if not index:
        print(f"{Colors.FAIL}Error: No index found. Run 'scan' first.{Colors.ENDC}", file=sys.stderr)
        sys.exit(1)
        
    _, reverse = build_graph(index)
    orphans = [p for p in index['files'] if p not in reverse and index['files'][p]['category'] == 'source']
    
    categories = defaultdict(int)
    for info in index['files'].values():
        categories[info['category']] += 1

    if output_file:
        output_result({
            "metadata": index["metadata"],
            "categories": categories,
            "orphans": orphans
        }, output_file)
        return

    print(f"\n{Colors.BOLD}Project Overview:{Colors.ENDC}")
    print(f"Total files: {index['metadata']['total_files']}")
    print(f"Total size:  {index['metadata']['total_size'] / (1024*1024):.2f} MB")
    
    print(f"\n{Colors.BOLD}Categories:{Colors.ENDC}")
    for cat, count in categories.items():
        print(f"  {cat.capitalize():<10} {count}")
        
    print(f"\n{Colors.BOLD}Project Map (First 30 paths):{Colors.ENDC}")
    tree_out = generate_tree(index['files'].keys())
    print("\n".join(tree_out.split("\n")[:30]))
    
    print(f"\n{Colors.WARNING}Potential Orphans (Source files with 0 incoming dependencies): {len(orphans)}{Colors.ENDC}")
    for o in orphans[:10]: print(f"  - {o}")

def who_uses(filepath, directory, output_file=None):
    index = load_index(directory)
    if not index:
        sys.exit(1)
    _, reverse = build_graph(index)
    matches = [p for p in reverse.keys() if filepath in p]
    if not matches:
        if output_file: output_result([], output_file)
        else: print(f"{Colors.OKGREEN}No files found using '{filepath}'.{Colors.ENDC}")
        return
        
    target = matches[0]
    users = reverse[target]
    
    if output_file:
        output_result(users, output_file)
        return
        
    print(f"{Colors.OKBLUE}Files directly using '{target}':{Colors.ENDC}")
    for u in users: print(f"  - {u}")

def impact(filepath, directory, output_file=None):
    index = load_index(directory)
    if not index:
        sys.exit(1)
    _, reverse = build_graph(index)
    matches = [p for p in index['files'].keys() if filepath in p]
    if not matches:
        if output_file: output_result({}, output_file)
        else: print(f"{Colors.FAIL}File not found in index.{Colors.ENDC}")
        return
        
    target = matches[0]
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
                
    if output_file:
        output_result({"direct": list(direct), "indirect": list(indirect)}, output_file)
        return
        
    print(f"{Colors.WARNING}Graph-based impact analysis for '{target}'{Colors.ENDC}")
    print(f"\n{Colors.BOLD}Direct dependents ({len(direct)}):{Colors.ENDC}")
    for v in direct: print(f"  - {v}")
    
    print(f"\n{Colors.BOLD}Indirect/Transitive dependents ({len(indirect)}):{Colors.ENDC}")
    for v in indirect: print(f"  - {v}")

def search(query, directory, output_file=None):
    index = load_index(directory)
    matches_found = []
    
    query_words = set(re.findall(r'[a-zA-Z0-9_]{3,}', query.lower()))
    
    for filepath, info in (index['files'].items() if index else []):
        if not info.get('is_text'): continue
        
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
    try:
        with open(filepath, 'rb') as f: header = f.read(32)
    except Exception:
        sys.exit(1)

    file_type, confidence = "Unknown", "Low"
    if header.startswith(b'\x89PNG\r\n\x1a\n'): file_type, confidence = "PNG Image", "High (Signature)"
    elif header.startswith(b'\xff\xd8\xff'): file_type, confidence = "JPEG Image", "High (Signature)"
    elif header.startswith(b'%PDF-'): file_type, confidence = "PDF Document", "High (Signature)"
    elif header.startswith(b'PK\x03\x04'): file_type, confidence = "ZIP Archive", "High (Signature)"
    elif header.startswith(b'SQLite format 3\x00'): file_type, confidence = "SQLite Database", "High (Signature)"
    elif is_text_file(filepath): file_type, confidence = "Text/Source", "Medium (Heuristic)"

    if output_file:
        output_result({"size": size, "type": file_type, "confidence": confidence, "hash": get_file_hash(filepath)}, output_file)
        return

    print(f"{Colors.OKBLUE}Inspecting: {filepath}{Colors.ENDC}")
    print(f"Size: {size} bytes")
    print(f"Detected Type: {Colors.BOLD}{file_type}{Colors.ENDC} (Confidence: {confidence})")
    print(f"SHA-256: {get_file_hash(filepath)}")

def main():
    parser = argparse.ArgumentParser(description="RepoXray - Zero Dependency Codebase Analyzer")
    subparsers = parser.add_subparsers(dest="command")
    
    p_scan = subparsers.add_parser("scan")
    p_scan.add_argument("path", nargs="?", default=".")
    p_scan.add_argument("--output", help="Output JSON report file")
    
    p_overview = subparsers.add_parser("overview")
    p_overview.add_argument("path", nargs="?", default=".")
    p_overview.add_argument("--output", help="Output JSON report file")
    
    p_search = subparsers.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("path", nargs="?", default=".")
    p_search.add_argument("--output", help="Output JSON report file")
    
    p_inspect = subparsers.add_parser("inspect")
    p_inspect.add_argument("file")
    p_inspect.add_argument("--output", help="Output JSON report file")
    
    p_impact = subparsers.add_parser("impact")
    p_impact.add_argument("file")
    p_impact.add_argument("path", nargs="?", default=".")
    p_impact.add_argument("--output", help="Output JSON report file")
    
    p_who = subparsers.add_parser("who-uses")
    p_who.add_argument("file")
    p_who.add_argument("path", nargs="?", default=".")
    p_who.add_argument("--output", help="Output JSON report file")

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "scan": scan(args.path, args.output)
    elif args.command == "overview": overview(args.path, args.output)
    elif args.command == "search": search(args.query, args.path, args.output)
    elif args.command == "inspect": inspect(args.file, args.output)
    elif args.command == "impact": impact(args.file, args.path, args.output)
    elif args.command == "who-uses": who_uses(args.file, args.path, args.output)

if __name__ == "__main__":
    main()
