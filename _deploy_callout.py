import subprocess,os
os.chdir(r'C:\Users\12sgi\Documents\Claude\12sgi-king')
def run(*a):
    r=subprocess.run(a,capture_output=True,text=True)
    print('$',' '.join(a)); print(r.stdout[-1500:]); print(r.stderr[-800:]); return r
# touch a trigger-path file so publish.yml fires
open(r'watchers\legibility_fix.css','a',encoding='utf-8').write('\n/* callout dark flip %s */\n'%__import__('time').strftime('%Y-%m-%d'))
run('git','add','-A')
run('git','commit','-m','all-dark: darken light callout tints (flag/note/success/info) with hue-matched readable text across 277 files')
run('git','push','origin','main')
