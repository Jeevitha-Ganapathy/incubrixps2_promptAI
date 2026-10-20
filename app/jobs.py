from threading import Lock
from uuid import uuid4
from datetime import datetime,timezone
JOBS={}; LOCK=Lock()
def create_job(kind,session_id):
    jid=str(uuid4()); job={"job_id":jid,"kind":kind,"session_id":session_id,"status":"queued","progress":0,"created_at":datetime.now(timezone.utc).isoformat(),"result":None,"error":None}
    with LOCK:JOBS[jid]=job
    return job
def update_job(jid,**kwargs):
    with LOCK:JOBS[jid].update(kwargs)
    return JOBS[jid]
def get_job(jid):return JOBS.get(jid)
