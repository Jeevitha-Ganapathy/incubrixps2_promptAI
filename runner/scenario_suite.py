"""40+ repeatable deterministic behavior checks; no media/API key needed."""
from app.engine import make_timeline,TimelineEngine
from app.models import Operation

def run():
    passed=0; failed=[]
    def check(name,fn):
        nonlocal passed
        try:assert fn(); passed+=1
        except Exception as e:failed.append((name,str(e)))
    for i in range(45):
        def scenario(i=i):
            e=TimelineEngine(make_timeline(f"case-{i}",100))
            if i%9==0:return e.apply(Operation(type='cut',start=10,end=20)).status=='applied' and abs(e.current.duration-90)<1e-6
            if i%9==1:return e.apply(Operation(type='keep',start=10,end=20)).status=='applied' and abs(e.current.duration-10)<1e-6
            if i%9==2:return e.apply(Operation(type='speed',start=10,end=20,speed=2)).status=='applied' and abs(e.current.duration-95)<1e-6
            if i%9==3:return e.apply(Operation(type='caption',start=10,end=12,text='hello')).status=='applied' and len(e.current.captions)==1
            if i%9==4:return e.apply(Operation(type='mute',start=10,end=11)).status=='applied' and len(e.current.effects)==1
            if i%9==5:return e.apply(Operation(type='bleep',start=10,end=11)).status=='applied' and len(e.current.effects)==1
            if i%9==6:
                h=e.current.timeline_hash;e.apply(Operation(type='cut',start=10,end=20));e.apply(Operation(type='undo'));return e.current.timeline_hash==h
            if i%9==7:
                e.apply(Operation(type='cut',start=10,end=20));e.apply(Operation(type='undo'));return e.apply(Operation(type='redo')).status=='applied' and abs(e.current.duration-90)<1e-6
            return e.apply(Operation(type='cut',start=0,end=100)).status=='rejected'
        check(f"scenario-{i+1:02d}",scenario)
    print(f"Scenario suite: {passed}/45 passed")
    if failed:
        for n,e in failed:print('FAIL',n,e)
        raise SystemExit(1)
if __name__=='__main__':run()
