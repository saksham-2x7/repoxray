# STDLIB Substitutions Log

RepoXray strictly avoids external dependencies. Here is how we substituted common third-party packages with the Python Standard Library:

1. **`argparse`** instead of `click` or `typer` for CLI routing and robust argument parsing.
2. **`os.walk` and `os.path`** instead of external tree utilities, combined with manual tree string generation for the project map.
3. **`re` with `re.MULTILINE`** instead of `tree-sitter` for static, heuristic-based import/dependency extraction across languages.
4. **`json`** instead of `sqlite3` or `PyYAML` for fast, portable, and persistent index storage.
5. **`hashlib` (SHA-256)** instead of external hashing tools for file fingerprinting and incremental cache validation.
6. **Raw byte reading (`open(rb)`) & `struct`** instead of `python-magic` to safely identify file types via magic headers and extract binary metadata (like SQLite header info).
7. **`unittest`** instead of `pytest` for the comprehensive automated testing suite.
8. **ANSI escape codes** instead of `colorama` or `rich` for terminal colors (conditionally disabled when outputting to JSON).
9. **`collections.defaultdict` & `collections.deque`** instead of `networkx` or external graph libraries for performing cycle-safe BFS graph traversals and metrics aggregation.
10. **`zipfile` & `json` parsers** instead of dedicated metadata extractors to safely peek inside archives and structured data during file inspection.
