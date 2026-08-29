Markdown
# RepoXray

> **Understand an unfamiliar codebase without installing anything.**

RepoXray is a zero-third-party-runtime-dependency CLI that turns an unfamiliar repository into a searchable project map and explainable dependency graph. It helps developers move from “where is this text?” to “what does this file depend on, what uses it, and what might be affected if it changes?”

## The problem

Basic text search is useful for finding strings, but it does not describe the structure around a match. Dependency parsers can answer narrower questions, yet their output can be difficult to inspect when imports are ambiguous or cannot be resolved. RepoXray combines indexed search, file inspection, path-aware import analysis, reverse dependency lookup, and impact tracing in one small Python standard-library program.

RepoXray is intentionally transparent: relationships are classified as **proven**, **heuristic**, **ambiguous**, or **unresolved** instead of being silently guessed.

## How it works

```text
SCAN → INDEX → RESOLVE → ANALYZE → ANSWER
Stage
What RepoXray does
Scan
Walks the repository, skips configured directories, and detects added, changed, deleted, reused, and renamed paths.
Index
Records file metadata, SHA-256 fingerprints, categories, searchable line postings, and extracted imports in .repoxray.json.
Resolve
Matches Python and JS/TS imports against repository paths and preserves the distinction between confident, heuristic, ambiguous, and unresolved results.
Analyze
Builds forward and reverse relationships for dependency, user, cycle, orphan, and impact queries.
Answer
Prints a human-readable report or JSON suitable for scripts and further inspection.
30-second demo
From the repository root:
Bash
# Build or update the persistent project index.
python3 repoxray.py scan .

# See project health, warnings, relationships, and the tree.
python3 repoxray.py overview .

# Search and inspect the repository.
python3 repoxray.py search "RepoXray" .
python3 repoxray.py inspect repoxray.py

# Ask dependency and change-impact questions.
python3 repoxray.py depends-on repoxray.py .
python3 repoxray.py who-uses repoxray.py .
python3 repoxray.py impact repoxray.py .
Run scan again after adding, changing, or deleting files. Metadata fast paths reuse unchanged records; --force-hash is available when content hashing should be forced.
Representative output
The exact counts depend on the repository being scanned. The following is representative output, showing the format and the kinds of answers the CLI provides:
text
Scan complete. Reused: 0, Added: 8, Changed: 0, Deleted: 0, Renamed: 0

Project Overview & Health Report:
total_files: 8
relationship_count: 3
proven_relationship_count: 2
heuristic_relationship_count: 1
ambiguous_relationship_count: 0
unresolved_relationship_count: 4
cycles_count: 0
index_status: ready
text
Searching for 'RepoXray' (Full Inverted Index)...
README.md:1 # RepoXray
Total matches: 1
JSON
{
  "resolved": ["src/config.py"],
  "heuristic": [],
  "ambiguous": [],
  "unresolved": ["external_package"]
}
Every command supports --output FILE to save a JSON report or --output - to print JSON to standard output.
Seven CLI capabilities
Command
What it answers
scan [path]
Builds or updates .repoxray.json, classifies files, indexes text, extracts imports, and resolves local relationships.
overview [path]
Summarizes files, directories, categories, warnings, unresolved relationships, orphans, cycles, and the project tree.
search <query> [path]
Searches indexed text with optional --path <glob> filtering and line-level result context.
inspect <file>
Identifies common file types from magic bytes, validates supported structured formats, reports metadata, and flags extension mismatches.
depends-on <file> [path]
Shows the target file’s resolved, heuristic, ambiguous, and unresolved dependencies.
who-uses <file> [path]
Shows files that directly use the target through indexed relationships.
impact <file> [path]
Traverses reverse relationships to separate direct from indirect potential dependents.
All seven commands accept --output FILE or --output - for JSON reports.
What makes it different?
The comparison below describes fundamental differences in capability, not a claim that RepoXray replaces a full language server or parser.
Tool
Text search
Project map
Dependency relationships
Impact tracing
Explainable uncertainty
Basic grep
Yes
No
No
No
No
RepoXray
Yes
Yes
Yes
Yes
Yes
RepoXray is not simply a prettier search command: it keeps an inspectable index and makes uncertainty part of the result. It is also intentionally smaller and easier to audit than a toolchain that requires a package installation or service setup.
Why zero third-party runtime dependencies matter
RepoXray is designed to be useful as soon as a developer receives a repository. Download the script, invoke Python, and inspect the codebase without installing packages, starting a service, or relying on a dependency lockfile. The small standard-library implementation also makes the constraint easy for judges to verify.
The claim is deliberately narrow: zero third-party runtime dependencies, not zero operating-system assumptions. RepoXray uses Python 3 and the local filesystem. It reads text files into memory while building the index, so it is not presented as a constant-memory analyzer for arbitrarily large files. Search retrieval is line-oriented. It uses os.walk; ignored directories are skipped and symlinked directories are not recursively followed by default.
Architecture and trade-offs
RepoXray is a single-file CLI backed by a persistent JSON index:
Indexing walks the repository, fingerprints files, classifies text and binary content, records searchable token line postings, and parses imports.
Resolution matches Python and JS/TS imports against repository paths. Proven local matches are separated from basename heuristics, ambiguous candidates, and unresolved imports.
Analysis builds forward and reverse in-memory relationships for overview, dependency, user, cycle, and impact queries.
Inspection uses standard-library magic-byte checks and safe parsers for common formats such as JSON, ZIP, and SQLite.
These choices are deliberate. Python imports use the standard-library ast module. JavaScript and TypeScript imports use regex-based extraction, so they are useful heuristics rather than complete language parsers. Ambiguous relationships are reported instead of silently guessed. The tool is practical for ordinary repositories, but its index is not constant-memory for arbitrarily large files.
Read the technical details in:
ARCHITECTURE.md — indexing, resolution, query flow, and trade-offs.
STDLIB.md — standard-library substitutions and the runtime-dependency boundary.
deps-proof.txt — reproducible zero-dependency verification commands.
Installation and usage
No package installation is required. Clone or download the repository, ensure Python 3 is available, and run:
Bash
python3 repoxray.py --help
python3 repoxray.py scan /path/to/repository
python3 repoxray.py overview /path/to/repository --output overview.json
The generated .repoxray.json index is local working data and is ignored by the scanner itself. Reports can be written outside the scanned repository when a clean working tree is required.
Verification
Run the complete test suite and isolated standard-library import proof from the repository root:
Bash
python3 -m unittest discover -v
python3 -S -c "import repoxray; print('stdlib import check passed')"
The -S check disables site-package imports for that process. Together, the tests and proof verify the supported CLI behavior and that RepoXray’s runtime imports resolve from the Python standard library.
Contributors
HamzaShaikh-source
santoshsubramanian-web
Kaustubh-Negi-01