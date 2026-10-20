from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
from app.engine import TimelineEngine,make_timeline
from app.models import Operation
from app.parser import parse_instruction
from app.media import probe,sha256_file,render_timeline

def run_session(spec):
    video=spec.get("video"); duration=spec.get("duration_s")
    if video:
        meta=probe(video); duration=meta['duration_s']; tl=make_timeline(Path(video).stem,duration,str(Path(video).resolve()),sha256_file(video),meta['fps'])
    else:tl=make_timeline("sample-session",float(duration or 120))
    engine=TimelineEngine(tl); results=[]
    wants_render=False
    for i,step in enumerate(spec.get('steps',[]),1):
        say=step.get('say','')
        if say.strip().lower()=='render':
            wants_render=True; results.append({'step':i,'instruction':say,'status':'applied','operations':[{'type':'render'}],'summary':'Render requested; rendering is a separate step after edits.','timeline_hash':engine.current.timeline_hash,'duration_s':engine.current.duration,'time_policy':'original source time'}); continue
        parsed=parse_instruction(say)
        if parsed is False:result={"status":"needs_clarification","summary":"Unsupported instruction; provide explicit source-time ranges.","question":"What source-time range should I use?","options":["Specify range","Cancel"],"operations":[],"timeline_hash":engine.current.timeline_hash,"duration_s":engine.current.duration,"time_policy":"original source time"}
        elif parsed is None:result={"status":"needs_clarification","summary":"Ambiguous semantic reference.","question":"Which occurrence do you mean?","options":["First","Second","All","Cancel"],"operations":[],"timeline_hash":engine.current.timeline_hash,"duration_s":engine.current.duration,"time_policy":"original source time"}
        else:result=engine.apply(parsed).model_dump(mode='json')
        result['step']=i; result['instruction']=say; results.append(result)
    out={"results":results,"final_timeline":engine.current.model_dump(mode='json'),"timeline_hash":engine.current.timeline_hash,"duration_s":engine.current.duration,"source_hash":engine.current.source_hash,"source_time_policy":"original source time"}
    return out
def main():
    p=argparse.ArgumentParser(); p.add_argument('session'); p.add_argument('--output',default='outputs/session-run'); a=p.parse_args(); spec=json.loads(Path(a.session).read_text()); result=run_session(spec); dest=Path(a.output); dest.mkdir(parents=True,exist_ok=True); (dest/'results.json').write_text(json.dumps(result,indent=2)); (dest/'timeline.json').write_text(json.dumps(result['final_timeline'],indent=2))
    if spec.get('video') and wants_render:
        from app.engine import make_timeline
        # The CLI's edit loop is the authoritative timeline; render that final state.
        # run_session output includes source path, so rehydrate model from it.
        from app.models import Timeline
        tl=Timeline.model_validate(result['final_timeline']); render=render_timeline(tl,dest/'final.mp4'); result['render']=render; (dest/'results.json').write_text(json.dumps(result,indent=2))
    print(f"Wrote {dest/'results.json'}; final hash={result['timeline_hash']}")
if __name__=='__main__':main()
