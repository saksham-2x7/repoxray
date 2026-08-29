#!/usr/bin/env python3
import os
import sys
import argparse
from collections import defaultdict

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

IGNORE_DIRS = {'.git', '.svn', 'node_modules', '__pycache__', 'venv', 'env', '.idea', '.vscode', 'dist', 'build'}

def print_banner():
    print(f"{Colors.OKCYAN}{Colors.BOLD}🔎 RepoXray - Zero Dependency Codebase Analyzer{Colors.ENDC}\n")

def is_text_file(filepath):
    try:
        with open(filepath, 'tr', encoding='utf-8') as check_file:
            check_file.read(1024)
            return True
    except UnicodeDecodeError:
        return False
    except Exception:
        return False

def scan(directory):
    print(f"{Colors.OKBLUE}Scanning directory: {directory}{Colors.ENDC}")
    
    total_files = 0
    total_dirs = 0
    total_size = 0
    ext_counts = defaultdict(int)
    
    for root, dirs, files in os.walk(directory):
        # Exclude ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        total_dirs += 1
        for file in files:
            total_files += 1
            filepath = os.path.join(root, file)
            try:
                size = os.path.getsize(filepath)
                total_size += size
            except Exception:
                pass
            
            _, ext = os.path.splitext(file)
            ext_counts[ext.lower() if ext else 'no_extension'] += 1

    print(f"\n{Colors.BOLD}Project Overview:{Colors.ENDC}")
    print(f"Total directories: {total_dirs}")
    print(f"Total files:       {total_files}")
    print(f"Total size:        {total_size / (1024*1024):.2f} MB")
    
    print(f"\n{Colors.BOLD}File Extensions:{Colors.ENDC}")
    sorted_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)
    for ext, count in sorted_exts[:15]:
        print(f"  {ext:<15} {count}")
    if len(sorted_exts) > 15:
        print(f"  ... and {len(sorted_exts) - 15} more")

def search(query, directory):
    print(f"{Colors.OKBLUE}Searching for '{query}' in {directory}...{Colors.ENDC}\n")
    matches_found = 0
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            filepath = os.path.join(root, file)
            if is_text_file(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if query in line:
                                rel_path = os.path.relpath(filepath, directory)
                                print(f"{Colors.OKGREEN}{rel_path}:{line_num}{Colors.ENDC} {line.strip()[:100]}")
                                matches_found += 1
                except Exception:
                    pass
                    
    print(f"\n{Colors.BOLD}Total matches found: {matches_found}{Colors.ENDC}")

def inspect(filepath):
    print(f"{Colors.OKBLUE}Inspecting: {filepath}{Colors.ENDC}\n")
    
    if not os.path.exists(filepath):
        print(f"{Colors.FAIL}Error: File not found.{Colors.ENDC}")
        return
        
    try:
        size = os.path.getsize(filepath)
        print(f"Size: {size} bytes ({size / 1024:.2f} KB)")
    except Exception as e:
        print(f"Could not get file size: {e}")
        return

    # Check magic bytes
    try:
        with open(filepath, 'rb') as f:
            header = f.read(32)
    except Exception as e:
        print(f"Could not read file: {e}")
        return

    file_type = "Unknown binary / text format"
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        file_type = "PNG Image"
    elif header.startswith(b'\xff\xd8\xff'):
        file_type = "JPEG Image"
    elif header.startswith(b'%PDF-'):
        file_type = "PDF Document"
    elif header.startswith(b'PK\x03\x04'):
        file_type = "ZIP Archive (or JAR, DOCX, etc.)"
    elif header.startswith(b'SQLite format 3\x00'):
        file_type = "SQLite Database"
    elif header.startswith(b'\x7fELF'):
        file_type = "ELF Executable"
    elif header.startswith(b'MZ'):
        file_type = "Windows PE Executable / DLL"
    elif header.startswith(b'\xca\xfe\xba\xbe') or header.startswith(b'\xce\xfa\xed\xfe') or header.startswith(b'\xcf\xfa\xed\xfe'):
        file_type = "Mach-O Executable (macOS)"
    elif is_text_file(filepath):
        file_type = "Text File"
        
    print(f"Detected Type: {Colors.BOLD}{file_type}{Colors.ENDC}")
    
    if "Unknown" in file_type and not is_text_file(filepath):
        print("\nHexdump (first 32 bytes):")
        hex_str = ' '.join(f'{b:02x}' for b in header)
        ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in header)
        # Simple formatting
        if len(hex_str) > 24:
            print(f"{hex_str[:24]:<24} {ascii_str[:8]}")
            print(f"{hex_str[24:]:<24} {ascii_str[8:]}")
        else:
            print(f"{hex_str} {ascii_str}")

def impact(filepath, directory):
    basename = os.path.basename(filepath)
    print(f"{Colors.OKBLUE}Analyzing impact of '{basename}' across '{directory}'{Colors.ENDC}\n")
    
    affected_files = []
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            check_path = os.path.join(root, file)
            # Skip checking the file itself
            if os.path.abspath(check_path) == os.path.abspath(filepath):
                continue
                
            if is_text_file(check_path):
                try:
                    with open(check_path, 'r', encoding='utf-8') as f:
                        if basename in f.read():
                            affected_files.append(os.path.relpath(check_path, directory))
                except Exception:
                    pass

    if affected_files:
        print(f"{Colors.WARNING}Potentially affected files ({len(affected_files)}):{Colors.ENDC}")
        for af in affected_files:
            print(f"  - {af}")
    else:
        print(f"{Colors.OKGREEN}No direct references to '{basename}' found in text files.{Colors.ENDC}")

def main():
    parser = argparse.ArgumentParser(description="RepoXray - Zero Dependency Codebase Analyzer")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Scan
    scan_parser = subparsers.add_parser("scan", help="Scan directory and show overview")
    scan_parser.add_argument("path", nargs="?", default=".", help="Path to directory (default: .)")
    
    # Search
    search_parser = subparsers.add_parser("search", help="Search for text across the project")
    search_parser.add_argument("query", help="Text to search for")
    search_parser.add_argument("path", nargs="?", default=".", help="Path to directory (default: .)")
    
    # Inspect
    inspect_parser = subparsers.add_parser("inspect", help="X-ray a specific file")
    inspect_parser.add_argument("file", help="Path to the file to inspect")
    
    # Impact
    impact_parser = subparsers.add_parser("impact", help="See what might be affected by a file")
    impact_parser.add_argument("file", help="Path to the file")
    impact_parser.add_argument("path", nargs="?", default=".", help="Path to project directory (default: .)")

    args = parser.parse_args()
    
    if args.command is None:
        print_banner()
        parser.print_help()
        return

    print_banner()

    if args.command == "scan":
        scan(args.path)
    elif args.command == "search":
        search(args.query, args.path)
    elif args.command == "inspect":
        inspect(args.file)
    elif args.command == "impact":
        impact(args.file, args.path)

if __name__ == "__main__":
    main()
