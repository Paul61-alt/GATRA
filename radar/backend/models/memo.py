"""Pydantic models for the VC comparative memo (downstream of RadarOutput).

A memo is generated on-demand from a finished RadarOutput + a TemplateSpec.
Every claim carries a citation back to a source_url that physically exists in
the gathered data — see pipeline/memo.py for the grounding + backstop.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic import BaseModel

Confidence = Literal["high", "medium", "low"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ── Template (built-in generalist or VC-defined custom) ──────────────────────

class TemplateSection(_CamelModel):
    id: str
    title: str
    instruction: str  # generation hint fed to Claude for this section


class TemplateSpec(_CamelModel):
    id: str
    name: str
    sections: list[TemplateSection] = Field(default_factory=list)


# ── Generated memo ───────────────────────────────────────────────────────────

class MemoCitation(_CamelModel):
    claim: str                       # the sentence/number being sourced
    source_url: Optional[str] = None
    confidence: Confidence = "medium"
    company: Optional[str] = None    # which company the claim is about


class MemoSection(_CamelModel):
    id: str
    title: str
    body: str = ""                   # markdown
    citations: list[MemoCitation] = Field(default_factory=list)
    confidence: Confidence = "medium"
    has_gaps: bool = False           # true if any "Non disponible" used


class Memo(_CamelModel):
    template_id: str
    template_name: str
    subject_name: str
    generated_at: str                # ISO 8601
    sections: list[MemoSection] = Field(default_factory=list)
