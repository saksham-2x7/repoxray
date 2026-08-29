# Architecture

RepoXray operates in two primary phases:

## 1. Indexing Phase (`scan`)
- **File Fingerprinting**: Hashes every file (`SHA-256`) to ensure perfectly robust incremental fast-paths, even for same-size content changes.
- **Classification**: Safely identifies text vs. binary using heuristic chunk reading.
- **Tokenization**: Reads text files into memory, then extracts normalized alphanumeric tokens into the index to act as a fast prefilter for future searches. Search result retrieval iterates over matching files line by line, but indexing itself is not constant-memory for arbitrarily large files.
- **Path-Aware Resolution**: Matches raw imports against the scanned file tree. Separates edges into proven (`resolved_local`/`resolved_root`/`resolved_relative`), `heuristic_basename`, `ambiguous`, and `unresolved`.
- **Atomic Storage**: Saves `.repoxray.json` atomically via a temporary file replacement.

## 2. Query Phase (Commands)
- **Graph Traversal**: Builds adjacency lists for forward and reverse edges in memory. Uses cycle-safe BFS/DFS for `impact`, `who-uses`, and `depends-on`.
- **Search**: Intersects query tokens with the file token sets before touching the disk.
- **Inspector**: Compares reported extensions against magic byte signatures, surfacing spoofed types, and selectively parses safe structured data (with explicit warnings for malformed data).
