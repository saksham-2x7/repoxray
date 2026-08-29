import re

IMPORT_PATTERNS = {
    'python': [
        re.compile(r'^\s*import\s+(.+)', re.MULTILINE),
        re.compile(r'^\s*from\s+([\.a-zA-Z0-9_]+)\s+import', re.MULTILINE)
    ],
    'js': [
        re.compile(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE),
        re.compile(r'require\([\'"]([^\'"]+)[\'"]\)', re.MULTILINE)
    ]
}
text = """
from .config import API_KEY
from ..database import connect
import os, sys
import math
"""
deps = set()
for p in IMPORT_PATTERNS['python']:
    for match in p.findall(text):
        for m in match.split(','):
            deps.add(m.strip())
print(deps)
