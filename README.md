# RepoXray

> **Understand an unfamiliar codebase without installing anything.**

RepoXray is a zero-third-party-runtime-dependency CLI that turns an unfamiliar repository into a searchable project map and explainable dependency graph.

It helps answer questions that plain text search cannot:

- **Where is this functionality?**
- **What does this file depend on?**
- **What files use it?**
- **What might be affected if it changes?**

## ✨ Features

- **Project mapping** — scan repositories and build a persistent JSON index.
- **Indexed search** — fast content search with line-level results and path filtering.
- **Dependency analysis** — Python and JS/TS import extraction with proven, heuristic, ambiguous, and unresolved relationships.
- **Impact tracing** — identify direct and indirect potential dependents.
- **File inspection** — inspect common structured and binary formats using standard-library parsers and magic-byte checks.
- **Incremental scanning** — reuse unchanged records and report added, changed, deleted, and renamed files.
- **JSON output** — every command can emit machine-readable reports.

## ⚙️ How it works

```text
SCAN → INDEX → RESOLVE → ANALYZE → ANSWER
```

| Stage | What happens |
|---|---|
| **Scan** | Walk the repository and detect file changes. |
| **Index** | Record metadata, hashes, searchable content, and imports. |
| **Resolve** | Match local Python and JS/TS imports to repository paths. |
| **Analyze** | Build forward/reverse relationships for dependency and impact queries. |
| **Answer** | Return human-readable results or JSON. |

## 🚀 Quick Start

```bash
# Build or update the project index
python3 repoxray.py scan .

# Project health and structure
python3 repoxray.py overview .

# Search and inspect
python3 repoxray.py search "RepoXray" .
python3 repoxray.py inspect repoxray.py

# Dependency questions
python3 repoxray.py depends-on repoxray.py .
python3 repoxray.py who-uses repoxray.py .
python3 repoxray.py impact repoxray.py .
```

Run `scan` again after adding, changing, or deleting files. Use `--force-hash` when you want content hashing to be forced.

## 🔍 The seven commands

| Command | Purpose |
|---|---|
| `scan [path]` | Build or update the persistent project index. |
| `overview [path]` | Show project health, relationships, warnings, and the tree. |
| `search <query> [path]` | Search indexed content with optional path filtering. |
| `inspect <file>` | Identify and inspect supported file formats and metadata. |
| `depends-on <file> [path]` | Show the target file's dependencies. |
| `who-uses <file> [path]` | Show files that directly use the target. |
| `impact <file> [path]` | Trace direct and indirect potential dependents. |

All commands support `--output FILE` and `--output -` for JSON output.

## 🧠 Why RepoXray?

Basic `grep` is excellent at finding text, but it does not maintain a project model or answer dependency and impact questions.

RepoXray keeps an inspectable local index and explicitly distinguishes:

**proven · heuristic · ambiguous · unresolved**

That means uncertain relationships are surfaced instead of silently guessed.

| Capability | Basic `grep` | RepoXray |
|---|:---:|:---:|
| Text search | ✅ | ✅ |
| Project map | ❌ | ✅ |
| Dependency relationships | ❌ | ✅ |
| Impact tracing | ❌ | ✅ |
| Explainable uncertainty | ❌ | ✅ |

## 🧪 Zero third-party runtime dependencies

RepoXray uses only the Python 3 standard library at runtime.

No package installation is required, and there is no third-party runtime dependency or network service involved.

The claim is intentionally narrow: this is **zero third-party runtime dependencies**, not zero operating-system assumptions. Indexing reads text files into memory, while search retrieval is line-oriented. JavaScript and TypeScript import extraction is heuristic rather than a complete language parser.

## 🏗️ Technical design

RepoXray is intentionally a **single-file CLI** backed by a persistent JSON index.

- Python imports use the standard-library `ast` module.
- JS/TS imports use regex-based extraction.
- Dependency relationships are classified by confidence.
- Reverse relationships enable `who-uses`, cycle analysis, and impact tracing.
- Tree and dependency traversals use iterative algorithms so deep structures do not depend on Python's recursion limit.
- Supported file inspection uses standard-library parsing and magic-byte checks.

Read the deeper design notes:

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [STDLIB.md](STDLIB.md)
- [deps-proof.txt](deps-proof.txt)

## ✅ Verification

From the repository root:

```bash
python3 -m unittest discover -v
python3 -S -c "import repoxray; print('stdlib import check passed')"
```

The test suite verifies CLI behavior and edge cases. The `-S` check confirms that the application imports using the Python standard library without loading site packages.

## 👥 Contributors

- [HamzaShaikh-source](https://github.com/HamzaShaikh-source)
- [santoshsubramanian-web](https://github.com/santoshsubramanian-web?tab=repositories)
- [Kaustubh-Negi-01](https://github.com/Kaustubh-Negi-01)
