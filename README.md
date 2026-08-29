# RepoXray

RepoXray is a zero-dependency CLI tool that scans, searches, explores, and inspects software projects so developers can understand unfamiliar codebases faster.

## Features
- **Zero Dependencies**: Built entirely using the Python 3 standard library.
- **Scan & Overview**: Build a persistent project map, identify files, detect orphans and cyclic dependencies.
- **Dependency Graph**: Path-aware resolution for Python and JS/TS imports. Tracks forward and reverse relationships, as well as unresolved/heuristic links.
- **Impact Tracing**: Cycle-safe traversal to separate direct vs. indirect (transitive) dependents.
- **Binary Inspector**: X-ray unknown files using magic bytes, extracting safe metadata (like SQLite schemas, ZIP contents) and warning on extension mismatches.
- **Indexed Search**: Caches normalized tokens to meaningfully accelerate content searches (prefilter) and supports path/glob searches.
- **JSON Export**: Every command supports `--output <file>` or `--output -` for clean integration into other tools.

## Commands
- `scan [path]`: Builds or incrementally updates `.repoxray.json`.
- `overview [path]`: Shows project health, counts, warnings, and a directory tree map.
- `depends-on <file> [path]`: Shows what the given file imports (forward dependencies).
- `who-uses <file> [path]`: Shows what imports the given file (reverse dependencies).
- `impact <file> [path]`: Estimates potential direct and indirect impact if the file changes.
- `search <query> [path] [--path <glob>]`: Fast content and/or path search.
- `inspect <file>`: Deep inspection of a single file.

## Edge Cases & Limitations
- **Incremental Scanning**: Relies primarily on `mtime` and `size` for the fast path, using SHA-256 for definitive identity when needed. Renames are treated as deletion + addition.
- **Search Index**: The index stores a token prefilter, meaning it avoids reading files that lack the queried words, but does open candidate files to extract match context lines.
- **Heuristic Graph**: Dependency resolution is based on static regex parsing. Highly dynamic imports, complex aliases, or unhandled language features may result in unresolved edges.

