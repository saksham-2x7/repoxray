with open('repoxray.py', 'r') as f:
    code = f.read()

# Fix the IndentationError caused by bad replacement
# Let's just output the correct block. 

code = code.replace(
'''def overview(directory, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
        
    forward, reverse, orphans, cycles, categories, metrics = compute_metrics(index)''',
'''def overview(directory, output_file=None):
    index = load_index(directory)
    if not index: sys.exit(1)
        
    forward, reverse, orphans, cycles, categories, metrics = compute_metrics(index)'''
)
# Wait, let's see what's actually there.
