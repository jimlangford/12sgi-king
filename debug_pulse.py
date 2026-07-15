import tempfile, pathlib
from services.v2_workboard import emit_workboard_job, workboard_pulse, read_workboard_log

tmp = tempfile.TemporaryDirectory()
log_path = pathlib.Path(tmp.name) / 'test.jsonl'

emit_workboard_job(
    source='s', action='doc', event='DOC',
    status='pending-approval', lane='creative',
    log_path=log_path,
)

entries = read_workboard_log(log_path)
print(f'Entries written: {len(entries)}')
for e in entries:
    kind = e.get('kind')
    lane = e.get('lane')
    status = e.get('status')
    source = e.get('source')
    print(f'  kind={kind} lane={lane} status={status} source={source}')

p = workboard_pulse(log_path=log_path)
print(f'waiting_owner={p["waiting_owner"]}')
tmp.cleanup()
