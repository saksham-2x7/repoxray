# RepoXray

RepoXray is a zero-dependency CLI tool that scans, searches, explores, and inspects software projects so developers can understand unfamiliar codebases faster.

## Features
- **Zero Dependencies**: Built entirely using the Python 3 standard library.
- **Scan & Overview**: Build a persistent project map, identify files, detect heuristic entry points, orphans, and cyclic dependencies.
- **Dependency Graph**: Path-aware resolution for Python and JS/TS imports. Tracks forward and reverse relationships, categorizing them as proven, heuristic, ambiguous, or unresolved.
  - *Python imports use standard-library AST extraction, though resolution to filesystem paths remains heuristic.*
- **Impact Tracing**: Cycle-safe traversal to separate direct vs. indirect (transitive) dependents.
- **Binary Inspector**: X-ray unknown files using magic bytes, extracting metadata, and warning on extension mismatches (with structural CRC validation for ZIPs and JSON, and header inspection for SQLite).
- **Indexed Search**: Per-file line postings cache for fast, precise line-level searches.
- **JSON Export**: Every command supports `--output <file>` or `--output -`.

## Commands
- `scan [path] [--output FILE|-]`: Builds or updates `.repoxray.json`. Employs mtime/size fast-paths and practical rename reporting (note: still performs an O(N) filesystem walk).
- `overview [path] [--output FILE|-]`: Shows project health, counts, warnings, and a directory tree map.
- `depends-on <file> [path] [--output FILE|-]`: Shows what the given file imports.
- `who-uses <file> [path] [--output FILE|-]`: Shows what imports the given file.
- `impact <file> [path] [--output FILE|-]`: Estimates potential direct and indirect impact.
- `search <query> [path] [--path <glob>] [--output FILE|-]`: Fast content/path search using index prefilters.
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

## Contributors
- [HamzaShaikh-source](https://github.com/HamzaShaikh-source)
- [santoshsubramanian-web](https://github.com/santoshsubramanian-web?tab=repositories)
- [Kaustubh-Negi-01](https://github.com/Kaustubh-Negi-01)
