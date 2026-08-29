# Architecture

RepoXray operates in two phases:
1. **Indexing Phase**: `scan` walks the project, hashes files, parses imports via regex, and builds a directed graph stored in `.repoxray.json`.
2. **Query Phase**: Commands like `impact`, `who-uses`, and `overview` read the JSON index to provide instant, graph-backed responses.

The graph tracks:
- Nodes: Files (with metadata like size, hash, type).
- Edges: Dependencies (File A imports File B).
