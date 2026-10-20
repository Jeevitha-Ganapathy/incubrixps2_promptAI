from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_health():assert client.get('/health').json()['status']=='ok'
def test_ready():assert client.get('/ready').status_code==200
def test_demo_session_and_timeline():
 r=client.post('/api/v1/sessions/demo',json={'duration_s':90});assert r.status_code==200;sid=r.json()['session_id'];assert client.get(f'/api/v1/sessions/{sid}/timeline').status_code==200
def test_instruction_idempotency():
 sid=client.post('/api/v1/sessions/demo',json={'duration_s':90}).json()['session_id'];h={'Idempotency-Key':'same-001'};body={'instruction':'cut the first 10 seconds'};a=client.post(f'/api/v1/sessions/{sid}/instructions',json=body,headers=h).json();b=client.post(f'/api/v1/sessions/{sid}/instructions',json=body,headers=h).json();assert a==b
def test_unknown_job():assert client.get('/api/v1/jobs/no-such-job').status_code==404
