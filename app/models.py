from __future__ import annotations
from typing import Literal, Any
from pydantic import BaseModel, Field, model_validator
import hashlib, json

class Segment(BaseModel):
    id: str
    source_start: float = Field(ge=0)
    source_end: float = Field(gt=0)
    speed: float = Field(default=1.0, gt=0, le=4)
    @model_validator(mode="after")
    def valid(self):
        if self.source_end <= self.source_start: raise ValueError("source_end must exceed source_start")
        return self
    @property
    def duration(self): return (self.source_end-self.source_start)/self.speed

class Caption(BaseModel):
    id: str
    text: str
    anchor_start: float = Field(ge=0)
    anchor_end: float = Field(gt=0)
    color: str = "white"
    size: int = Field(default=32, ge=8, le=160)
    @model_validator(mode="after")
    def valid(self):
        if self.anchor_end <= self.anchor_start: raise ValueError("caption end must exceed start")
        return self

class Effect(BaseModel):
    id: str
    kind: Literal["mute", "bleep"]
    anchor_start: float = Field(ge=0)
    anchor_end: float = Field(gt=0)
    @model_validator(mode="after")
    def valid(self):
        if self.anchor_end <= self.anchor_start: raise ValueError("effect end must exceed start")
        return self

class Music(BaseModel):
    path: str
    volume: float = Field(default=0.15, ge=0, le=1)
    duck_under_speech: bool = True

class Timeline(BaseModel):
    source_id: str
    source_path: str | None = None
    source_duration: float = Field(gt=0)
    source_hash: str = "synthetic"
    fps: float = Field(default=30, gt=0)
    segments: list[Segment]
    captions: list[Caption] = Field(default_factory=list)
    effects: list[Effect] = Field(default_factory=list)
    music: Music | None = None
    version: int = 0
    @property
    def duration(self): return sum(s.duration for s in self.segments)
    @property
    def timeline_hash(self):
        payload=self.model_dump(mode="json")
        # Runtime path and version are intentionally part of state; canonical ordering stabilizes hash.
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

class Operation(BaseModel):
    type: Literal["cut","keep","speed","reorder","caption","mute","bleep","music","undo","redo","restore"]
    start: float | None = None
    end: float | None = None
    speed: float | None = None
    text: str | None = None
    color: str | None = None
    size: int | None = None
    index: int | None = None
    path: str | None = None
    volume: float | None = None
    step: int | None = None

class InstructionResult(BaseModel):
    status: Literal["applied","needs_clarification","rejected"]
    operations: list[dict[str,Any]] = Field(default_factory=list)
    summary: str
    question: str | None = None
    options: list[str] = Field(default_factory=list)
    timeline_hash: str
    duration_s: float
    time_policy: str = "original source time"
    warnings: list[str] = Field(default_factory=list)
