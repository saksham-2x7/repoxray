#!/usr/bin/env python3
import os
import sys
import argparse
import json
import re
import hashlib
from collections import defaultdict, deque

# Regex patterns for imports
IMPORT_PATTERNS = {
    'python': [
        re.compile(r'^\s*import\s+([a-zA-Z0-9_\.]+)'),
        re.compile(r'^\s*from\s+([a-zA-Z0-9_\.]+)\s+import')
    ],
    'js': [
        re.compile(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]'),
        re.compile(r'require\([\'"]([^\'"]+)[\'"]\)')
    ]
}

IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', 'venv', 'env', 'dist', 'build', '.next'}
INDEX_FILE = '.repoxray.json'

class Colors:
    HEADER = '\033[95m'
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
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
    except Exception:
        return None

def is_text_file(filepath):
    try:
        with open(filepath, 'tr', encoding='utf-8') as f:
            f.read(1024)
            return True
    except UnicodeDecodeError:
        return False
    except Exception:
        return False

def extract_dependencies(filepath, file_type):
    deps = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            for pattern in IMPORT_PATTERNS.get(file_type, []):
                for match in pattern.findall(content):
                    dep = match.split('/')[-1] if '/' in match else match
                    dep = dep.split('.')[0] # remove ext
                    deps.add(dep)
    except Exception:
        pass
    return list(deps)

def get_file_type(ext):
    if ext in ['.py']: return 'python'
    if ext in ['.js', '.jsx', '.ts', '.tsx']: return 'js'
    return 'unknown'

def scan(directory, output_json=False):
    if not output_json:
        print(f"{Colors.OKBLUE}Scanning directory: {directory}{Colors.ENDC}")
    
    index = {
        'files': {},
        'metadata': {
            'total_files': 0,
            'total_dirs': 0,
            'total_size': 0
        }
    }
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        index['metadata']['total_dirs'] += 1
        
        for file in files:
            if file == INDEX_FILE:
                continue
                
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, directory)
            
            try:
                size = os.path.getsize(filepath)
                index['metadata']['total_size'] += size
                index['metadata']['total_files'] += 1
                
                _, ext = os.path.splitext(file)
                f_type = get_file_type(ext)
                is_text = is_text_file(filepath)
                
                file_info = {
                    'path': rel_path,
                    'size': size,
                    'hash': get_file_hash(filepath),
                    'is_text': is_text,
                    'extension': ext,
                    'dependencies': extract_dependencies(filepath, f_type) if is_text else [],
                    'category': 'source' if f_type != 'unknown' else 'other'
                }
                if 'test' in file.lower() or 'spec' in file.lower():
                    file_info['category'] = 'test'
                elif ext in ['.json', '.yaml', '.yml', '.toml', '.env']:
                    file_info['category'] = 'config'
                    
                index['files'][rel_path] = file_info
            except Exception:
                pass
                
    index_path = os.path.join(directory, INDEX_FILE)
    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)

    if output_json:
        print(json.dumps(index))
    else:
        print(f"{Colors.OKGREEN}Scan complete. Index saved to {INDEX_FILE}.{Colors.ENDC}")
        print(f"Indexed {index['metadata']['total_files']} files across {index['metadata']['total_dirs']} directories.")

def load_index(directory):
    index_path = os.path.join(directory, INDEX_FILE)
    if not os.path.exists(index_path):
        return None
    with open(index_path, 'r') as f:
        return json.load(f)

def build_graph(index):
    # forward: file -> [deps it imports]
    # reverse: file -> [files that import it]
    forward = defaultdict(list)
    reverse = defaultdict(list)
    
    # Simple heuristic matcher since we extract basenames
    basename_map = defaultdict(list)
    for p in index['files']:
        basename = os.path.basename(p).split('.')[0]
        basename_map[basename].append(p)
        
    for p, info in index['files'].items():
        for dep in info['dependencies']:
            if dep in basename_map:
                for resolved_dep in basename_map[dep]:
                    forward[p].append(resolved_dep)
                    reverse[resolved_dep].append(p)
                    
    return forward, reverse

def overview(directory, output_json=False):
    index = load_index(directory)
    if not index:
        print(f"{Colors.FAIL}Error: No index found. Run 'scan' first.{Colors.ENDC}")
        sys.exit(1)
        
    forward, reverse = build_graph(index)
    orphans = [p for p in index['files'] if p not in reverse and index['files'][p]['category'] == 'source']
    
    categories = defaultdict(int)
    for info in index['files'].values():
        categories[info['category']] += 1

    if output_json:
        print(json.dumps({
            "metadata": index["metadata"],
            "categories": categories,
            "orphans_count": len(orphans)
        }))
        return

    print(f"\n{Colors.BOLD}Project Overview:{Colors.ENDC}")
    print(f"Total files: {index['metadata']['total_files']}")
    print(f"Total size:  {index['metadata']['total_size'] / (1024*1024):.2f} MB")
    
    print(f"\n{Colors.BOLD}Categories:{Colors.ENDC}")
    for cat, count in categories.items():
        print(f"  {cat.capitalize():<10} {count}")
        
    print(f"\n{Colors.WARNING}Potential Orphans (Source files with 0 incoming dependencies): {len(orphans)}{Colors.ENDC}")
    for o in orphans[:10]:
        print(f"  - {o}")
    if len(orphans) > 10:
        print("  ... and more")

def who_uses(filepath, directory, output_json=False):
    index = load_index(directory)
    if not index:
        print(f"{Colors.FAIL}Error: No index found. Run 'scan' first.{Colors.ENDC}")
        sys.exit(1)
        
    _, reverse = build_graph(index)
    
    # Try to find exact match or substring
    matches = [p for p in reverse.keys() if filepath in p]
    if not matches:
        if not output_json: print(f"{Colors.OKGREEN}No files found using '{filepath}'.{Colors.ENDC}")
        else: print("[]")
        return
        
    target = matches[0]
    users = reverse[target]
    
    if output_json:
        print(json.dumps(users))
        return
        
    print(f"{Colors.OKBLUE}Files directly using '{target}':{Colors.ENDC}")
    for u in users:
        print(f"  - {u}")

def impact(filepath, directory, output_json=False):
    index = load_index(directory)
    if not index:
        print(f"{Colors.FAIL}Error: No index found. Run 'scan' first.{Colors.ENDC}")
        sys.exit(1)
        
    _, reverse = build_graph(index)
    
    matches = [p for p in index['files'].keys() if filepath in p]
    if not matches:
        if not output_json: print(f"{Colors.FAIL}File '{filepath}' not found in index.{Colors.ENDC}")
        else: print("[]")
        return
        
    target = matches[0]
    
    # BFS to find all transitive dependencies
    visited = set()
    queue = deque([target])
    
    while queue:
        curr = queue.popleft()
        for user in reverse.get(curr, []):
            if user not in visited:
                visited.add(user)
                queue.append(user)
                
    if output_json:
        print(json.dumps(list(visited)))
        return
        
    print(f"{Colors.WARNING}Graph-based impact analysis for '{target}'{Colors.ENDC}")
    print(f"Direct & indirect dependents: {len(visited)}")
    for v in visited:
        print(f"  - {v}")

def search(query, directory, output_json=False):
    index = load_index(directory)
    matches_found = []
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        for file in files:
            if file == INDEX_FILE: continue
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, directory)
            
            # Use index if available to skip binary
            if index and rel_path in index['files'] and not index['files'][rel_path]['is_text']:
                continue
            elif not index and not is_text_file(filepath):
                continue
                
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if query in line:
                            matches_found.append({
                                'file': rel_path,
                                'line': line_num,
                                'context': line.strip()[:100]
                            })
            except Exception:
                pass
                
    if output_json:
        print(json.dumps(matches_found))
        return
        
    print(f"{Colors.OKBLUE}Searching for '{query}'...{Colors.ENDC}\n")
    for m in matches_found:
        print(f"{Colors.OKGREEN}{m['file']}:{m['line']}{Colors.ENDC} {m['context']}")
    print(f"\n{Colors.BOLD}Total matches: {len(matches_found)}{Colors.ENDC}")

def inspect(filepath, output_json=False):
    if not os.path.exists(filepath):
        print(f"{Colors.FAIL}Error: File not found.{Colors.ENDC}")
        sys.exit(1)
        
    try:
        size = os.path.getsize(filepath)
    except Exception as e:
        if not output_json: print(f"Could not read size: {e}")
        sys.exit(1)

    try:
        with open(filepath, 'rb') as f:
            header = f.read(32)
    except Exception as e:
        if not output_json: print(f"Could not read file: {e}")
        sys.exit(1)

    file_type = "Unknown"
    confidence = "Low"
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        file_type = "PNG Image"
        confidence = "High"
    elif header.startswith(b'\xff\xd8\xff'):
        file_type = "JPEG Image"
        confidence = "High"
    elif header.startswith(b'%PDF-'):
        file_type = "PDF Document"
        confidence = "High"
    elif header.startswith(b'PK\x03\x04'):
        file_type = "ZIP Archive"
        confidence = "High"
    elif header.startswith(b'SQLite format 3\x00'):
        file_type = "SQLite Database"
        confidence = "High"
    elif header.startswith(b'\x7fELF'):
        file_type = "ELF Executable"
        confidence = "High"
    elif header.startswith(b'MZ'):
        file_type = "Windows PE Executable"
        confidence = "High"
    elif header.startswith(b'\xca\xfe\xba\xbe') or header.startswith(b'\xce\xfa\xed\xfe') or header.startswith(b'\xcf\xfa\xed\xfe'):
        file_type = "Mach-O Executable"
        confidence = "High"
    elif is_text_file(filepath):
        file_type = "Text/Source"
        confidence = "Medium"

    if output_json:
        print(json.dumps({
            "size": size,
            "type": file_type,
            "confidence": confidence,
            "hash": get_file_hash(filepath)
        }))
        return

    print(f"{Colors.OKBLUE}Inspecting: {filepath}{Colors.ENDC}")
    print(f"Size: {size} bytes")
    print(f"Detected Type: {Colors.BOLD}{file_type}{Colors.ENDC} (Confidence: {confidence})")
    print(f"SHA-256: {get_file_hash(filepath)}")

def main():
    parser = argparse.ArgumentParser(description="RepoXray - Zero Dependency Codebase Analyzer")
    parser.add_argument("--output", choices=['json'], help="Output format")
    subparsers = parser.add_subparsers(dest="command")
    
    p_scan = subparsers.add_parser("scan")
    p_scan.add_argument("path", nargs="?", default=".")
    
    p_overview = subparsers.add_parser("overview")
    p_overview.add_argument("path", nargs="?", default=".")
    
    p_search = subparsers.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("path", nargs="?", default=".")
    
    p_inspect = subparsers.add_parser("inspect")
    p_inspect.add_argument("file")
    
    p_impact = subparsers.add_parser("impact")
    p_impact.add_argument("file")
    p_impact.add_argument("path", nargs="?", default=".")
    
    p_who = subparsers.add_parser("who-uses")
    p_who.add_argument("file")
    p_who.add_argument("path", nargs="?", default=".")

    args = parser.parse_args()
    out_json = args.output == 'json'
    
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "scan":
        scan(args.path, out_json)
    elif args.command == "overview":
        overview(args.path, out_json)
    elif args.command == "search":
        search(args.query, args.path, out_json)
    elif args.command == "inspect":
        inspect(args.file, out_json)
    elif args.command == "impact":
        impact(args.file, args.path, out_json)
    elif args.command == "who-uses":
        who_uses(args.file, args.path, out_json)

if __name__ == "__main__":
    main()
