# Architecture

RepoXray operates in two primary phases to ensure efficiency and analytical depth:

## 1. Indexing Phase (`scan`)
Walks the project directory incrementally.
- **File Fingerprinting**: Uses `mtime`, `size`, and bounded SHA-256 chunking to quickly detect additions, modifications, and deletions.
- **Classification**: Safely identifies text vs. binary using heuristic chunk reading, avoiding memory exhaustion on large files.
- **Tokenization**: Extracts normalized alphanumeric tokens into the index to act as a fast prefilter for future searches.
- **Dependency Extraction**: Uses `re.MULTILINE` regexes to capture Python and JS/TS imports.
- **Path-Aware Resolution**: Matches raw imports against the scanned file tree to produce deterministic resolved paths (or explicitly marks them as unresolved).
- **Atomic Storage**: Saves `.repoxray.json` atomically via a temporary file replacement to prevent corruption.

## 2. Query Phase (Commands)
Reads the pre-computed index to serve fast responses.
- **Graph Traversal**: Builds adjacency lists for forward and reverse edges in memory. Uses cycle-safe BFS/DFS (maintaining `visited` sets) for `impact`, `who-uses`, and `depends-on`.
- **Health Metrics**: Scans the adjacency lists to identify orphans (in-degree 0) and cycles (using Tarjan's or simple DFS back-edge detection).
- **Search**: Intersects query tokens with the file token sets before touching the disk, providing a significant speedup over naive recursive grep.
- **Inspector**: Compares reported extensions against magic byte signatures, surfacing spoofed or mismatched types, and selectively parses safe structured data (like JSON keys or ZIP catalogs).
