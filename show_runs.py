import sys, json
d = json.load(sys.stdin)
runs = d['workflow_runs']
print('All run conclusions (newest first):')
for r in runs[:20]:
    conc = r['conclusion'] or 'pending'
    date = r['created_at'][:10]
    name = r['name']
    print(f"  {date}  {conc:12s}  {name}")
