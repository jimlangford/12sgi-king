import yaml, os
wf_dir = '.github/workflows'
ok = 0
errors = []
for f in sorted(os.listdir(wf_dir)):
    if not f.endswith('.yml'):
        continue
    try:
        yaml.safe_load(open(f'{wf_dir}/{f}').read())
        print(f'OK  {f}')
        ok += 1
    except Exception as e:
        errors.append(f)
        print(f'ERR {f}: {e}')
total = len([f for f in os.listdir(wf_dir) if f.endswith('.yml')])
print(f'\n{ok}/{total} valid')
if errors:
    print('ERRORS:', errors)
