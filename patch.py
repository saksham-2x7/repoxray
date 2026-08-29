import re

with open('repoxray.py', 'r') as f:
    content = f.read()

# Fix impact warnings
content = content.replace(
    '"warnings": ["Dependency-based potential impact. Heuristic edges are included."]',
    '"warnings": ["Dependency-based potential impact. Heuristic edges included.", "Ambiguous edges were excluded from traversal."]'
)

# Fix overview warnings
content = content.replace(
    '"warnings": index[\'metadata\'][\'warnings\']',
    '"warnings": index[\'metadata\'][\'warnings\'] + (["Some ambiguous edges were excluded from relationship counts and graph traversal."] if metrics["ambiguous"] > 0 else [])'
)

with open('repoxray.py', 'w') as f:
    f.write(content)

with open('README.md', 'a') as f:
    f.write("\n\n## Output Schemas\n")
    f.write("```json\n{\n  \"metadata\": { \"total_files\": 0, \"total_dirs\": 0, \"total_size\": 0, \"warnings\": [] },\n  \"categories\": { \"source\": 0 },\n  \"project_tree\": \"├── ...\"\n}\n```\n")
    f.write("\n## Verification\nRun `python3 -S -c \"import repoxray; print('stdlib check passed')\"` to verify zero dependencies.\n")
