import re
text = """
import a, \
  b
from pkg import c, d as d_alias
"""
# Need a better regex to handle multiline imports without matching \n literally as text
p1 = re.compile(r'^\s*import\s+((?:[a-zA-Z0-9_\.]+\s*,\s*)*[a-zA-Z0-9_\.]+)', re.MULTILINE)
for m in p1.findall(text): print(m)
