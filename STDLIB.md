# STDLIB Substitutions Log

RepoXray strictly avoids external runtime dependencies. These standard-library modules provide the capabilities used by the project:

1. **`argparse`** provides CLI routing instead of `click` or `typer`.
2. **`os.walk`** provides recursive filesystem traversal instead of external tree utilities.
3. **`ast`** extracts Python imports without a third-party parser.
4. **`re`** extracts JavaScript and TypeScript imports and tokenizes searchable text without `tree-sitter`; this is intentionally heuristic, not feature-equivalent.
5. **`json`** stores the persistent index and emits command reports in a portable file format.
6. **`hashlib`** computes SHA-256 fingerprints for incremental scan checks without an external cache.
7. **Raw byte reads with `open(..., 'rb')`** identify common file types from magic headers without `python-magic`.
8. **`zipfile`** validates ZIP archives and lists their members without an archive-inspection dependency.
9. **`sqlite3`** performs the inspector's read-only SQLite schema validation; it is not used as index storage.
10. **`unittest`** runs the automated tests instead of `pytest`.
11. **`collections.defaultdict` and `deque`** provide graph maps and breadth-first impact traversal instead of `networkx`.

These are capability substitutions used by RepoXray, not claims of feature equivalence with the named external tools.

## Verification

```bash
python3 -S -c "import repoxray; print('stdlib import check passed')"
```

The command imports RepoXray with site-packages disabled, verifying that its runtime imports resolve from the Python standard library.

[1]: https://docs.python.org/3/library/ "Python Standard Library documentation"
