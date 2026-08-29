import re

IMPORT_PATTERNS = {
    'python': [
        re.compile(r'^\s*import\s+([a-zA-Z0-9_\.]+)', re.MULTILINE),
        re.compile(r'^\s*from\s+([a-zA-Z0-9_\.]+)\s+import', re.MULTILINE)
    ],
    'js': [
        re.compile(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE),
        re.compile(r'require\([\'"]([^\'"]+)[\'"]\)', re.MULTILINE)
    ]
}
text = """
from config import API_KEY
from database import connect
"""
print(IMPORT_PATTERNS['python'][1].findall(text))
