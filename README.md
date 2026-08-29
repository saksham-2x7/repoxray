# RepoXray

RepoXray is a zero-dependency CLI tool that scans, searches, explores, and inspects software projects so developers can understand unfamiliar codebases faster.

## Features
- **Zero Dependencies**: Built entirely using the Python standard library.
- **Scan & Overview**: Build a project map, identify files, and detect orphans.
- **Dependency Graph**: Understand how files connect (supports Python and JS/TS imports).
- **Impact Tracing**: See what files will break if you modify a target file.
- **Binary Inspector**: X-ray unknown files using magic bytes.
- **Persistent Index**: Caches results in `.repoxray.json` for instant queries.

## Usage
```bash
./repoxray.py scan .
./repoxray.py overview
./repoxray.py who-uses src/App.jsx
./repoxray.py impact src/config.js
./repoxray.py inspect unknown.dat
./repoxray.py search "database"
```
