from __future__ import annotations
import os, json, shutil, logging, hmac, hashlib, time
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, UploadFile, File, Header, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from .config import UPLOAD_DIR, OUTPUT_DIR, MAX_UPLOAD_MB
from .models import Operation
from .engine import TimelineEngine, make_timeline
from .parser import parse_instruction
from .media import probe, sha256_file, render_timeline
from .jobs import create_job, update_job, get_job

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),format='%(message)s'); log=logging.getLogger("incubrix")
app=FastAPI(title="IncuBrix Prompt-Based Video Editing Engine",version="1.0.0",openapi_version="3.1.0")
SESSIONS={}; IDEMPOTENCY={}; MAX_BYTES=MAX_UPLOAD_MB*1024*1024
class CreateSession(BaseModel): source_path:str
class DemoSession(BaseModel): duration_s:float; fps:float=30
class Instruction(BaseModel): instruction:str
class OperationBody(BaseModel): operation:Operation
class RenderBody(BaseModel): output_name:str|None=None

def err(code,message,retryable=False,details=None,status=400):
    return JSONResponse(status_code=status,content={"error":{"code":code,"message":message,"retryable":retryable,"details":details or {}}})
@app.middleware("http")
async def logging_middleware(request:Request,call_next):
    cid=request.headers.get("X-Correlation-Id",str(uuid4())); start=time.perf_counter()
    response=await call_next(request); response.headers["X-Correlation-Id"]=cid
    log.info(json.dumps({"timestamp":time.time(),"level":"INFO","path":request.url.path,"method":request.method,"status":response.status_code,"correlation_id":cid,"elapsed_ms":round((time.perf_counter()-start)*1000,2)})); return response
@app.exception_handler(Exception)
async def exception_handler(request,exc):
    log.exception("Unhandled request error"); return err("INTERNAL_ERROR","An internal error occurred.",True,{},500)
@app.get("/health")
def health():return {"status":"ok"}
@app.get("/ready")
def ready():return {"status":"ready","ffmpeg_available":shutil.which(os.getenv("FFMPEG_BIN","ffmpeg")) is not None}
@app.post("/api/v1/sessions")
def create_session(body:CreateSession):
    p=Path(body.source_path).expanduser().resolve()
    if not p.is_file():return err("INPUT_NOT_FOUND","Source file does not exist.",False,{"source_path":str(p)},404)
    try:meta=probe(p); digest=sha256_file(p)
    except Exception as e:return err("INVALID_MEDIA",str(e),False,{},422)
    sid=str(uuid4()); tl=make_timeline(sid,meta['duration_s'],str(p),digest,meta['fps']); SESSIONS[sid]={"engine":TimelineEngine(tl),"metadata":meta,"source_hash":digest}
    return {"session_id":sid,"source_hash":digest,"metadata":meta,"timeline_hash":tl.timeline_hash,"time_policy":"original source time"}
@app.post("/api/v1/sessions/upload")
async def upload_session(file:UploadFile=File(...)):
    suffix=Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in (".mp4",".mov",".m4v",".mkv"):return err("UNSUPPORTED_MEDIA","Upload an MP4, MOV, M4V, or MKV file.")
    dest=UPLOAD_DIR/f"{uuid4().hex}{suffix}"; total=0
    with dest.open('wb') as out:
        while chunk:=await file.read(1024*1024):
            total+=len(chunk)
            if total>MAX_BYTES:dest.unlink(missing_ok=True); return err("UPLOAD_TOO_LARGE","Upload exceeds configured limit.")
            out.write(chunk)
    return create_session(CreateSession(source_path=str(dest)))
@app.post("/api/v1/sessions/demo")
def demo_session(body:DemoSession):
    if body.duration_s<=0:return err("INVALID_DURATION","duration_s must be positive")
    sid=f"demo-{uuid4().hex[:12]}"; tl=make_timeline(sid,body.duration_s,fps=body.fps); SESSIONS[sid]={"engine":TimelineEngine(tl),"metadata":{"duration_s":body.duration_s,"fps":body.fps,"has_audio":False,"synthetic":True},"source_hash":"synthetic"}
    return {"session_id":sid,"metadata":SESSIONS[sid]['metadata'],"timeline_hash":tl.timeline_hash,"time_policy":"original source time"}
def get_session(sid):
    if sid not in SESSIONS:raise HTTPException(404,"Session not found")
    return SESSIONS[sid]
@app.get("/api/v1/sessions/{sid}/timeline")
def timeline(sid:str):
    e=get_session(sid)['engine']; return {"timeline":e.current.model_dump(mode='json'),"timeline_hash":e.current.timeline_hash,"duration_s":e.current.duration,"time_policy":"original source time"}
@app.post("/api/v1/sessions/{sid}/operations")
def operation(sid:str,body:OperationBody,idempotency_key:str=Header(...,alias="Idempotency-Key")):
    key=(sid,idempotency_key)
    if key in IDEMPOTENCY:return IDEMPOTENCY[key]
    result=get_session(sid)['engine'].apply(body.operation).model_dump(mode='json'); IDEMPOTENCY[key]=result; return result
@app.post("/api/v1/sessions/{sid}/instructions")
def instruction(sid:str,body:Instruction,idempotency_key:str=Header(...,alias="Idempotency-Key")):
    key=(sid,idempotency_key)
    if key in IDEMPOTENCY:return IDEMPOTENCY[key]
    parsed=parse_instruction(body.instruction)
    if parsed is False:result={"status":"needs_clarification","operations":[],"summary":"I could not safely map this instruction to a supported operation.","question":"Please specify the source-time range or select a supported action.","options":["Cut range","Keep range","Add caption with range","Undo","Redo"],"timeline_hash":get_session(sid)['engine'].current.timeline_hash,"duration_s":get_session(sid)['engine'].current.duration,"time_policy":"original source time"}
    elif parsed is None:result={"status":"needs_clarification","operations":[],"summary":"The phrase may refer to multiple content matches; destructive edits are not guessed.","question":"Which occurrence should be edited?","options":["First match","Second match","All matches","Cancel"],"timeline_hash":get_session(sid)['engine'].current.timeline_hash,"duration_s":get_session(sid)['engine'].current.duration,"time_policy":"original source time"}
    else:result=get_session(sid)['engine'].apply(parsed).model_dump(mode='json')
    IDEMPOTENCY[key]=result; return result
@app.post("/api/v1/sessions/{sid}/render",status_code=202)
def render(sid:str,body:RenderBody,background:BackgroundTasks,idempotency_key:str=Header(...,alias="Idempotency-Key")):
    key=(sid,idempotency_key)
    if key in IDEMPOTENCY:return IDEMPOTENCY[key]
    sess=get_session(sid); job=create_job("render",sid); IDEMPOTENCY[key]={"job_id":job['job_id'],"status":"queued"}; background.add_task(_render_job,job['job_id'],sess['engine'].current.model_copy(deep=True),body.output_name); return IDEMPOTENCY[key]
def _render_job(jid,tl,name):
    try:
        update_job(jid,status="running",progress=10)
        output=OUTPUT_DIR/(name or f"{tl.source_id}_{tl.timeline_hash[:10]}.mp4")
        result=render_timeline(tl,output); update_job(jid,status="succeeded",progress=100,result={"output_path":result['path'],"download_url":f"/api/v1/files/{Path(result['path']).name}","manifest_path":result['manifest'],"manifest":result['manifest_data']})
    except Exception as e:update_job(jid,status="failed",progress=100,error={"code":"RENDER_FAILED","message":str(e)})
@app.get("/api/v1/files/{filename}")
def download_file(filename:str):
    # Serve only direct children of the configured output directory.
    if Path(filename).name != filename: return err("INVALID_FILE_NAME","Invalid output filename.",False,{},400)
    target=(OUTPUT_DIR/filename).resolve()
    if target.parent != OUTPUT_DIR.resolve() or not target.is_file(): return err("OUTPUT_NOT_FOUND","Output file not found.",False,{},404)
    return FileResponse(target,filename=target.name)
@app.get("/api/v1/jobs/{job_id}")
def job(job_id:str):
    j=get_job(job_id)
    if not j:return err("JOB_NOT_FOUND","Job not found.",False,{},404)
    return j
@app.get("/api/v1/sessions/{sid}/otio")
def export_otio(sid:str):
    tl=get_session(sid)['engine'].current; tracks=[]; cursor=0
    for s in tl.segments:
        tracks.append({"OTIO_SCHEMA":"Clip.1","name":s.id,"source_range":{"OTIO_SCHEMA":"TimeRange.1","start_time":{"OTIO_SCHEMA":"RationalTime.1","value":s.source_start*tl.fps,"rate":tl.fps},"duration":{"OTIO_SCHEMA":"RationalTime.1","value":(s.source_end-s.source_start)*tl.fps,"rate":tl.fps}},"metadata":{"speed":s.speed,"source_start":s.source_start,"source_end":s.source_end}}); cursor+=s.duration
    return {"OTIO_SCHEMA":"Timeline.1","name":sid,"tracks":{"OTIO_SCHEMA":"Stack.1","children":[{"OTIO_SCHEMA":"Track.1","name":"Video","kind":"Video","children":tracks}]},"metadata":{"timeline_hash":tl.timeline_hash,"time_policy":"original source time"}}
