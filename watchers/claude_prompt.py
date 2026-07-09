#!/usr/bin/env python3
# claude_prompt.py - Claude -> Jimmy on mobile (the me->him half of the text Sage Game). Writes a prompt
# (text + optional tap-choices) to .king_prompts.jsonl; the King mobile page (sage_command.html) polls
# /api/prompts and shows it with reply buttons -> his tap comes back as a command to the executor.
# Usage: python claude_prompt.py "your question" "Yes|No|Later"
import os, sys, json, time
PROJECT=os.path.join(os.path.expanduser("~"),"Documents","Claude","Projects","Video System elementLOTUS")
F=os.path.join(PROJECT,".king_prompts.jsonl")
def post(text, choices=None):
    rec={"id":"p%d"%int(time.time()),"ts":int(time.time()),
         "iso":time.strftime("%Y-%m-%d %H:%M",time.gmtime(time.time()-10*3600)),
         "text":text,"choices":choices or []}
    with open(F,"a",encoding="utf-8") as f: f.write(json.dumps(rec,ensure_ascii=False)+"\n")
    return rec
if __name__=="__main__":
    if len(sys.argv)<2:
        print("usage: claude_prompt.py \"question\" \"choiceA|choiceB|...\""); sys.exit(1)
    ch=sys.argv[2].split("|") if len(sys.argv)>2 else []
    r=post(sys.argv[1], ch)
    print("posted to King mobile:", r["id"], "| choices:", ch)
