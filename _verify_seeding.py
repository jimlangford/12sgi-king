#!/usr/bin/env python3
import sqlite3
c = sqlite3.connect('data/db/govos_v2_tenant.db')
rows = c.execute('SELECT id, name, status FROM studio_projects LIMIT 5').fetchall()
all_rows = c.execute('SELECT * FROM studio_projects').fetchall()
print(f'{len(all_rows)} projects seeded:')
for r in rows:
    print(f'  {r[0]:20} {r[1][:30]:30} {r[2][:20]}')
c.close()
