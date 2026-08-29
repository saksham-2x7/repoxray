# STDLIB Substitutions Log

RepoXray strictly avoids external dependencies. Here is how we substituted common third-party packages with the Python Standard Library:

1. **`argparse`** instead of `click` or `typer` for CLI routing and argument parsing.
2. **`os.walk` and `pathlib`** instead of `scandir` or external tree utilities for fast recursive directory traversal.
3. **`re`** (Regex) instead of `tree-sitter` for heuristic-based import/dependency extraction across languages.
4. **`json`** instead of `sqlite3` or `PyYAML` for fast, portable, and persistent index storage.
5. **`hashlib`** (SHA-256) instead of external hashing tools for file fingerprinting and incremental cache validation.
6. **Raw byte reading (`open(rb)`)** instead of `python-magic` to detect file types via magic headers.
7. **`unittest`** instead of `pytest` for the automated testing suite.
8. **ANSI escape codes** instead of `colorama` or `rich` for terminal colors.
9. **`collections.defaultdict`** instead of `pandas` or external counters for aggregating metrics.
10. **`sys`** for exit codes and standard error routing instead of specialized logging frameworks.
