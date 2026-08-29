# STDLIB Substitutions Log

RepoXray strictly avoids external dependencies. We use heuristic and standard-library substitutes for features that typically require massive external libraries:

1. **`argparse`** instead of `click`/`typer` for CLI routing.
2. **`os.walk`** instead of external tree utilities.
3. **`re` (Regex heuristics)** instead of `tree-sitter` for static import extraction. *Note: this is a heuristic substitute, not a feature-equivalent AST replacement.*
4. **`json`** instead of `sqlite3` or Elasticsearch for fast, portable prefilter index storage.
5. **`hashlib` (SHA-256)** instead of external caching tools.
6. **Raw byte reading (`open(rb)`) & `struct`** instead of `python-magic` to safely identify file types via magic headers.
7. **`unittest`** instead of `pytest` for the automated testing suite.
8. **`collections.defaultdict` & `deque`** instead of `networkx` for performing cycle-safe BFS graph traversals.
9. **`zipfile` & `json` parsers** to safely peek inside archives and structured data.
