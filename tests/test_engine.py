import pytest
from app.engine import make_timeline,TimelineEngine
from app.models import Operation
from app.parser import parse_time,parse_instruction

def engine(d=100):return TimelineEngine(make_timeline('test',d))
def test_original_unchanged():
 e=engine(); before=e.original.model_dump_json(); e.apply(Operation(type='cut',start=10,end=20)); assert e.original.model_dump_json()==before
def test_cut_length():
 e=engine(); assert e.apply(Operation(type='cut',start=10,end=20)).status=='applied'; assert e.current.duration==90
def test_cut_duplicate_is_safe():
 e=engine();e.apply(Operation(type='cut',start=10,end=20));h=e.current.timeline_hash;r=e.apply(Operation(type='cut',start=10,end=20));assert r.status=='rejected' and e.current.timeline_hash==h
def test_reject_whole_video_cut():assert engine().apply(Operation(type='cut',start=0,end=100)).status=='rejected'
def test_keep():
 e=engine();e.apply(Operation(type='keep',start=10,end=20));assert e.current.duration==10
def test_speed():
 e=engine();e.apply(Operation(type='speed',start=10,end=20,speed=2));assert e.current.duration==95
def test_speed_limit():assert engine().apply(Operation(type='speed',start=10,end=20,speed=10)).status=='rejected'
def test_caption_anchor():
 e=engine();assert e.apply(Operation(type='caption',start=10,end=12,text='Welcome')).status=='applied';assert e.current.captions[0].anchor_start==10
def test_caption_on_cut_range_clarifies():
 e=engine();e.apply(Operation(type='cut',start=10,end=20));assert e.apply(Operation(type='caption',start=12,end=13,text='hi')).status=='needs_clarification'
def test_mute_bleep():
 e=engine();e.apply(Operation(type='mute',start=2,end=3));e.apply(Operation(type='bleep',start=4,end=5));assert [x.kind for x in e.current.effects]==['mute','bleep']
def test_undo_redo():
 e=engine();h=e.current.timeline_hash;e.apply(Operation(type='cut',start=10,end=20));e.apply(Operation(type='undo'));assert e.current.timeline_hash==h;e.apply(Operation(type='redo'));assert e.current.duration==90
def test_new_edit_clears_redo():
 e=engine();e.apply(Operation(type='cut',start=10,end=20));e.apply(Operation(type='undo'));e.apply(Operation(type='cut',start=30,end=40));assert e.apply(Operation(type='redo')).status=='rejected'
def test_restore_snapshot():
 e=engine();e.apply(Operation(type='cut',start=10,end=20));assert e.apply(Operation(type='restore',step=0)).status=='applied';assert e.current.duration==100
def test_parser_times():
 assert parse_time('01:20')==80;assert parse_time('80 seconds')==80;assert parse_time('a minute twenty')==80
def test_parser_ambiguous():assert parse_instruction('remove the part about pricing') is None
def test_hash_deterministic():assert engine().current.timeline_hash==engine().current.timeline_hash
@pytest.mark.parametrize('start,end', [(-1,3),(5,5),(0,101),(90,110)])
def test_invalid_ranges_rejected(start,end):assert engine().apply(Operation(type='cut',start=start,end=end)).status=='rejected'
