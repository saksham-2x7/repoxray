# RepoXray

RepoXray is a zero-dependency CLI tool that scans, searches, explores, and inspects software projects so developers can understand unfamiliar codebases faster.

## Features
- **Zero Dependencies**: Built entirely using the Python 3 standard library.
- **Scan & Overview**: Build a persistent project map, identify files, detect entry points, orphans and cyclic dependencies.
- **Dependency Graph**: Path-aware resolution for Python and JS/TS imports. Tracks forward and reverse relationships, categorizing them as proven, heuristic, ambiguous, or unresolved.
  - *Python imports are parsed using compiler-grade ASTs.*
- **Impact Tracing**: Cycle-safe traversal to separate direct vs. indirect (transitive) dependents.
- **Binary Inspector**: X-ray unknown files using magic bytes, extracting safe metadata (like SQLite schemas, ZIP contents) and warning on extension mismatches or file corruption (full structural validation for ZIPs and JSON).
- **Indexed Search**: O(1) line-level inverted index lookup for blazing-fast precise searches.
- **JSON Export**: Every command supports `--output <file>` or `--output -` for clean integration into other tools.

## Commands
- `scan [path] [--output FILE|-]`: Builds or incrementally updates `.repoxray.json`. It is O(changed-files) fast via an mtime+size fast-path and tracks rename operations natively.
- `overview [path] [--output FILE|-]`: Shows project health, counts, warnings, and a directory tree map.
- `depends-on <file> [path] [--output FILE|-]`: Shows what the given file imports (forward dependencies).
- `who-uses <file> [path] [--output FILE|-]`: Shows what imports the given file (reverse dependencies).
- `impact <file> [path] [--output FILE|-]`: Estimates potential direct and indirect impact if the file changes.
- `search <query> [path] [--path <glob>] [--output FILE|-]`: Fast content and/or path search.
- `inspect <file> [--output FILE|-]`: Deep inspection of a single file.

## Output Schemas
```json
{
  "metadata": { "total_files": 0, "total_dirs": 0, "total_size": 0, "warnings": [] },
  "categories": { "source": 0 },
  "project_tree": "├── ..."
}
```

## Verification
Run `python3 -S -c "import repoxray; print('stdlib check passed')"` to verify zero dependencies.
