from __future__ import annotations
from copy import deepcopy
from .models import Timeline, Segment, Caption, Effect, Operation, InstructionResult, Music

def make_timeline(source_id: str, duration_s: float, source_path=None, source_hash="synthetic", fps=30):
    return Timeline(source_id=source_id,source_path=source_path,source_duration=duration_s,source_hash=source_hash,fps=fps,segments=[Segment(id="seg-0000",source_start=0,source_end=duration_s)])

class TimelineEngine:
    """Deterministic source-anchored edit engine. Original source is never modified."""
    def __init__(self, timeline: Timeline):
        self.original=timeline.model_copy(deep=True); self.current=timeline.model_copy(deep=True)
        self.undo_stack=[]; self.redo_stack=[]; self.snapshots={0:timeline.model_copy(deep=True)}; self.edit_counter=0
    def _result(self,status,summary,operations=None,question=None,options=None,warnings=None):
        return InstructionResult(status=status,summary=summary,operations=operations or [],question=question,options=options or [],timeline_hash=self.current.timeline_hash,duration_s=round(self.current.duration,6),warnings=warnings or [])
    def _commit(self,nxt):
        self.undo_stack.append(self.current.model_copy(deep=True)); nxt.version=self.current.version+1; self.current=nxt; self.redo_stack.clear(); self.edit_counter+=1; self.snapshots[self.edit_counter]=nxt.model_copy(deep=True)
    def apply(self,op:Operation):
        if op.type=="undo":
            if not self.undo_stack:return self._result("rejected","Nothing to undo.")
            self.redo_stack.append(self.current.model_copy(deep=True)); self.current=self.undo_stack.pop(); return self._result("applied","Undid exactly one instruction.",[op.model_dump(exclude_none=True)])
        if op.type=="redo":
            if not self.redo_stack:return self._result("rejected","Nothing to redo.")
            self.undo_stack.append(self.current.model_copy(deep=True)); self.current=self.redo_stack.pop(); return self._result("applied","Redid one instruction.",[op.model_dump(exclude_none=True)])
        if op.type=="restore":
            if op.step is None or op.step not in self.snapshots:return self._result("rejected","Requested history step does not exist.")
            nxt=self.snapshots[op.step].model_copy(deep=True); self._commit(nxt); return self._result("applied",f"Restored snapshot after edit step {op.step}.",[op.model_dump(exclude_none=True)])
        if op.type in ("cut","keep","speed","reorder","caption","mute","bleep") and (op.start is None or op.end is None):return self._result("rejected","Start and end in original source seconds are required.")
        if op.type not in ("music",) and op.type not in ("undo","redo","restore"):
            if op.start is None or op.end is None or op.start<0 or op.end<=op.start or op.end>self.current.source_duration:return self._result("rejected","Invalid or out-of-source range.")
        nxt=self.current.model_copy(deep=True)
        if op.type in ("cut","keep"):
            out=[]
            for seg in self.current.segments:
                if op.type=="cut":
                    ranges=[(seg.source_start,min(op.start,seg.source_end)),(max(op.end,seg.source_start),seg.source_end)]
                    for a,b in ranges:
                        if b>a and a<seg.source_end and b>seg.source_start:out.append(Segment(id=f"seg-{len(out):04d}",source_start=a,source_end=b,speed=seg.speed))
                else:
                    a=max(seg.source_start,op.start); b=min(seg.source_end,op.end)
                    if b>a:out.append(Segment(id=f"seg-{len(out):04d}",source_start=a,source_end=b,speed=seg.speed))
            if not out:return self._result("rejected","Operation would leave an empty timeline.")
            if op.type=="cut" and len(out)==len(self.current.segments) and all(abs(a.source_start-b.source_start)<1e-8 and abs(a.source_end-b.source_end)<1e-8 for a,b in zip(out,self.current.segments)):return self._result("rejected","This range is already absent; duplicate cut ignored.")
            nxt.segments=out; self._commit(nxt); return self._result("applied",f"{op.type.title()} applied to original source range {op.start:.3f}-{op.end:.3f}s.",[op.model_dump(exclude_none=True)])
        if op.type=="speed":
            if op.speed is None or not .25<=op.speed<=4:return self._result("rejected","Speed must be between 0.25x and 4x.")
            out=[]
            for seg in self.current.segments:
                a=max(seg.source_start,op.start); b=min(seg.source_end,op.end)
                if a>=b:out.append(seg.model_copy(deep=True)); continue
                if seg.source_start<a:out.append(Segment(id=f"seg-{len(out):04d}",source_start=seg.source_start,source_end=a,speed=seg.speed))
                out.append(Segment(id=f"seg-{len(out):04d}",source_start=a,source_end=b,speed=op.speed))
                if b<seg.source_end:out.append(Segment(id=f"seg-{len(out):04d}",source_start=b,source_end=seg.source_end,speed=seg.speed))
            nxt.segments=out; self._commit(nxt); return self._result("applied",f"Speed set to {op.speed}x on source range. Overlaps use the latest instruction.",[op.model_dump(exclude_none=True)])
        if op.type=="reorder":
            if op.index is None or op.index<0 or op.index>len(nxt.segments):return self._result("rejected","Destination segment index is invalid.")
            selected=[s for s in nxt.segments if s.source_start>=op.start and s.source_end<=op.end]
            if not selected:return self._result("rejected","No complete visible segment matches the reorder range.")
            rest=[s for s in nxt.segments if s not in selected]; idx=min(op.index,len(rest)); nxt.segments=rest[:idx]+selected+rest[idx:]; self._commit(nxt); return self._result("applied","Reordered selected source content.",[op.model_dump(exclude_none=True)])
        if op.type=="caption":
            if not op.text:return self._result("rejected","Caption text is required.")
            if not any(op.start>=s.source_start and op.end<=s.source_end for s in nxt.segments):return self._result("needs_clarification","Caption anchor is cut or spans a cut.",question="Which visible source range should the caption use?",options=["Choose another range","Cancel"])
            nxt.captions.append(Caption(id=f"caption-{len(nxt.captions):04d}",text=op.text,anchor_start=op.start,anchor_end=op.end,color=op.color or "white",size=op.size or 32)); self._commit(nxt); return self._result("applied","Caption attached to original source range; time policy: original source time.",[op.model_dump(exclude_none=True)])
        if op.type in ("mute","bleep"):
            nxt.effects.append(Effect(id=f"effect-{len(nxt.effects):04d}",kind=op.type,anchor_start=op.start,anchor_end=op.end)); self._commit(nxt); return self._result("applied",f"{op.type.title()} effect anchored to source range.",[op.model_dump(exclude_none=True)])
        if op.type=="music":
            if not op.path:return self._result("rejected","Music file path is required.")
            nxt.music=Music(path=op.path,volume=op.volume if op.volume is not None else .15); self._commit(nxt); return self._result("applied","Background music configured.",[op.model_dump(exclude_none=True)])
        return self._result("rejected",f"Unsupported operation: {op.type}")
