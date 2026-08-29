# RepoXray

RepoXray is a zero-dependency CLI tool that scans, searches, explores, and inspects software projects so developers can understand unfamiliar codebases faster.

## Features
- **Zero Dependencies**: Built entirely using the Python 3 standard library.
- **Scan & Overview**: Build a persistent project map, identify files, detect orphans and cyclic dependencies.
- **Dependency Graph**: Path-aware resolution for Python and JS/TS imports. Tracks forward and reverse relationships, categorizing them as proven, heuristic, ambiguous, or unresolved.
- **Impact Tracing**: Cycle-safe traversal to separate direct vs. indirect (transitive) dependents.
- **Binary Inspector**: X-ray unknown files using magic bytes, extracting safe metadata (like SQLite schemas, ZIP contents) and warning on extension mismatches.
- **Indexed Search**: Caches normalized tokens to meaningfully accelerate content searches (prefilter) and supports path/glob searches.
- **JSON Export**: Every command supports `--output <file>` or `--output -` for clean integration into other tools.

## Commands
- `scan [path] [--output FILE|-]`: Builds or incrementally updates `.repoxray.json`.
- `overview [path] [--output FILE|-]`: Shows project health, counts, warnings, and a directory tree map.
- `depends-on <file> [path] [--output FILE|-]`: Shows what the given file imports (forward dependencies).
- `who-uses <file> [path] [--output FILE|-]`: Shows what imports the given file (reverse dependencies).
- `impact <file> [path] [--output FILE|-]`: Estimates potential direct and indirect impact if the file changes.
- `search <query> [path] [--path <glob>] [--output FILE|-]`: Fast content and/or path search.
- `inspect <file> [--output FILE|-]`: Deep inspection of a single file.

## Limitations (Out-of-Scope)
- **Regex Parsing, Not AST**: Dependency extraction uses regex heuristics, not compiler-grade ASTs. It parses `import a`, `from a import b, c`, and `import a as b` for Python, and `import/require` for JS. Dynamic imports or complex aliases may be unhandled.
- **Ambiguous Fallbacks**: If a dependency cannot be perfectly path-resolved, we fall back to a basename match. If multiple files share that basename, the edge is flagged as `"ambiguous"`.
- **Search Prefilter**: The index stores a token prefilter, avoiding reading files that lack the queried words, but does open candidate files to extract match context lines. It is not an enterprise inverted index (e.g., Elasticsearch).
- **Large Files**: Files are streamed in chunks to extract dependencies and tokens safely, avoiding memory exhaustion.
- **Renames**: Renamed files are treated as deletions + additions during incremental scans.

