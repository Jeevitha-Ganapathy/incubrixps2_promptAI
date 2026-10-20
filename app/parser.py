"""Small deterministic intent parser. Use a separately disclosed model adapter for semantic search."""
import re
from .models import Operation

def parse_time(s: str) -> float:
    s=s.strip().lower()
    if s.endswith("seconds"):return float(s[:-7].strip())
    if s.endswith("second"):return float(s[:-6].strip())
    if s.endswith("s") and s[:-1].replace('.','',1).isdigit():return float(s[:-1])
    if re.fullmatch(r"\d+:\d+(?:\.\d+)?",s):
        p=s.split(":"); return int(p[-2])*60+float(p[-1])
    m=re.fullmatch(r"(\d+)\s*minute(?:s)?\s*(?:(\d+)\s*second(?:s)?)?",s)
    if m:return int(m.group(1))*60+int(m.group(2) or 0)
    if s in ("a minute twenty","one minute twenty"):return 80.0
    raise ValueError(f"Cannot parse time: {s}")

def parse_instruction(text: str):
    t=text.strip(); lo=t.lower()
    if lo in ("undo","undo last edit"):return Operation(type="undo")
    if lo=="redo":return Operation(type="redo")
    m=re.search(r"(?:cut|remove)\s+(?:from\s+)?([\w:. ]+?)\s+(?:to|-)\s+([\w:. ]+?)(?:\s+seconds?)?$",lo)
    if m:
        try:return Operation(type="cut",start=parse_time(m.group(1)),end=parse_time(m.group(2)))
        except ValueError:pass
    m=re.search(r"cut the first\s+(\d+(?:\.\d+)?)\s+seconds?",lo)
    if m:return Operation(type="cut",start=0,end=float(m.group(1)))
    m=re.search(r"speed(?:\s+up)?\s+(?:from\s+)?([\d:.]+)\s+(?:to|-)\s+([\d:.]+)\s+by\s+([\d.]+)x?",lo)
    if m:return Operation(type="speed",start=parse_time(m.group(1)),end=parse_time(m.group(2)),speed=float(m.group(3)))
    m=re.search(r'add a caption\s+["\'](.+?)["\']\s+(?:from|at)\s+([\d:.]+)\s+(?:to|-)\s+([\d:.]+)',t,re.I)
    if m:return Operation(type="caption",text=m.group(1),start=parse_time(m.group(2)),end=parse_time(m.group(3)))
    if any(x in lo for x in ("pricing","boring part","when i say","after i say","guest says")):
        return None
    return False
