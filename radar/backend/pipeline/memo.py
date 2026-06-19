"""Memo phase — generate a comparative VC investment memo from a finished RadarOutput.

Downstream, on-demand, no Linkup. One Claude call (~€0.01). Mirrors synthesize.py:
pure transform + a single LLM call. The grounding contract is enforced twice:
  1. in the prompt (claude_client.generate_comparative_memo), and
  2. here, by a code-level backstop that drops any citation whose sourceUrl is not
     among the URLs that physically appeared in the payload.

Input `radar_output` is the cached camelCase dict (RadarOutput.model_dump(by_alias=True)).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from clients.claude_client import ClaudeClient
from models.memo import Memo, MemoSection, TemplateSection, TemplateSpec

logger = logging.getLogger(__name__)

_CONF = {"high", "medium", "low"}
# Cap competitors fed to Claude so a large landscape can't blow past the token
# budget (→ truncated JSON → parse failure). Ordered by threat, highest first.
_MAX_COMPETITORS = 12
_THREAT_RANK = {"high": 0, "medium": 1, "low": 2}


def _coerce_conf(v: str | None) -> str:
    """Map an LLM-supplied confidence to the allowed enum, defaulting to medium."""
    return v if v in _CONF else "medium"


# ── Built-in generalist VC comparative memo template ─────────────────────────
# Standard competitive-landscape investment memo structure. Mirrored in the
# frontend as the default; kept here so the backend can stand alone.
def _build_generalist() -> TemplateSpec:
    return TemplateSpec(
        id="generalist-vc",
        name="Mémo VC généraliste",
        sections=[
            TemplateSection(id="exec-summary", title="Executive Summary",
                instruction="2-3 phrases: qui est le sujet, où il se situe vs le champ concurrentiel, et le risque concurrentiel principal."),
            TemplateSection(id="market", title="Market & Category",
                instruction="Définir la catégorie et le segment à partir de category/positioning. Citer les acteurs. Pas d'invention de TAM — seulement ce que la donnée montre."),
            TemplateSection(id="landscape", title="Competitive Landscape",
                instruction="Classer les concurrents par menace (threat) et similarité. Pour chaque concurrent à forte menace, une ligne sur le pourquoi."),
            TemplateSection(id="positioning", title="Per-Competitor Positioning",
                instruction="Pour les 3-4 plus menaçants, contraster keyDifferentiator et targetSegment vs le sujet. Citer chaque affirmation."),
            TemplateSection(id="moats", title="Moats & Differentiation",
                instruction="Ce qui est défendable pour le sujet vs le champ (techStack, keyDifferentiator, notable_customers). Signaler où la preuve est mince."),
            TemplateSection(id="traction", title="Traction & Funding Signals",
                instruction="Comparer funding (stage/total), effectifs, signaux recentNews/recentLinkedinPosts. Citer chaque chiffre."),
            TemplateSection(id="risks", title="Risks & Threats",
                instruction="Menaces concurrentielles concrètes ancrées dans la donnée. Marquer tout inconnu 'Non disponible'."),
            TemplateSection(id="reco", title="Recommendation",
                instruction="Verdict côté investisseur (surveiller / creuser / signal-pass). Lier explicitement aux preuves citées ci-dessus ; aucun fait nouveau."),
        ],
    )


GENERALIST_TEMPLATE = _build_generalist()


# ── Payload builder (the grounding core) ─────────────────────────────────────
# Emit ONLY citation-bearing fields + factual scalars, with provenance inline.
# Every URL we emit is added to `url_whitelist` so the backstop can reject any
# citation the model invents.

def _company_payload(c: dict, urls: set[str]) -> dict:
    def _track(u):
        if u:
            urls.add(u)
        return u

    funding = c.get("funding") or {}
    kd = c.get("keyDifferentiator") or {}
    acq = c.get("acquisition") or {}
    pricing = c.get("pricing") or {}

    out = {
        "name": c.get("name"),
        "domain": c.get("domain"),
        "isSubject": bool(c.get("isSubject")),
        "tagline": c.get("tagline"),
        "category": c.get("category"),
        "positioning": c.get("positioning"),
        "hq": c.get("hq"),
        "founded": c.get("founded"),
        "employees": c.get("employees"),
        "employeeGrowth": c.get("employeeGrowth"),
        "customers": c.get("customers"),
        "arr": c.get("arr"),
        "businessModel": c.get("businessModel"),
        "gtmMotion": c.get("gtmMotion"),
        "targetSegment": c.get("targetSegment"),
        "geoCoverage": c.get("geoCoverage"),
        "similarity": c.get("similarity"),
        "threat": c.get("threat"),
        "fundingStage": c.get("fundingStage"),
        "top3Features": c.get("top3Features") or [],
        "techStack": c.get("techStack") or [],
        "investors": c.get("investors") or [],
        "growthSignals": c.get("growthSignals") or [],
    }
    if pricing:
        out["pricing"] = {"model": pricing.get("model"), "startsAt": pricing.get("startsAt"),
                          "mention": pricing.get("mention")}
    if funding:
        out["funding"] = {
            "totalEur": funding.get("totalRaisedEur") or funding.get("total"),
            "lastRound": funding.get("lastRound"),
            "lastRoundDate": funding.get("lastRoundDate") or funding.get("lastRoundAt"),
            "confidence": funding.get("confidence"),
            "sourceUrl": _track(funding.get("sourceUrl")),
        }
    if kd.get("value"):
        out["keyDifferentiator"] = {
            "value": kd.get("value"),
            "confidence": kd.get("confidence"),
            "sourceUrl": _track(kd.get("sourceUrl")),
        }
    if acq.get("acquired"):
        out["acquisition"] = {
            "acquirer": acq.get("acquirer"),
            "amountEur": acq.get("amountEur"),
            "year": acq.get("year"),
            "sourceUrl": _track(acq.get("sourceUrl")),
        }
    news = c.get("recentNews") or []
    if news:
        out["recentNews"] = [
            {"date": n.get("date"), "headline": n.get("headline"),
             "sourceUrl": _track(n.get("sourceUrl"))}
            for n in news[:5]
        ]
    posts = c.get("recentLinkedinPosts") or []
    if posts:
        out["recentLinkedinPosts"] = [
            {"date": p.get("date"), "author": p.get("author"),
             "excerpt": p.get("excerpt"), "sourceUrl": _track(p.get("sourceUrl"))}
            for p in posts[:3]
        ]
    customers = c.get("notable_customers") or []
    if customers:
        out["notableCustomers"] = [
            {"name": cu.get("name"), "segment": cu.get("segment"),
             "industry": cu.get("industry")}
            for cu in customers[:8]
        ]
    return {k: v for k, v in out.items() if v not in (None, [], {})}


def _build_payload(radar_output: dict, urls: set[str]) -> dict:
    subject = radar_output.get("subject") or {}
    competitors = radar_output.get("competitors") or []
    ranked = sorted(competitors, key=lambda c: _THREAT_RANK.get(c.get("threat"), 3))
    return {
        "subject": _company_payload(subject, urls),
        "competitors": [_company_payload(c, urls) for c in ranked[:_MAX_COMPETITORS]],
    }


def run(radar_output: dict, template: TemplateSpec, claude: ClaudeClient) -> Memo:
    urls: set[str] = set()
    payload = _build_payload(radar_output, urls)

    raw = claude.generate_comparative_memo(
        payload, template.model_dump(by_alias=True, mode="json")
    )

    raw_sections = raw.get("sections") or []
    by_id = {s.get("id"): s for s in raw_sections if isinstance(s, dict)}

    sections: list[MemoSection] = []
    dropped = 0
    for tmpl_sec in template.sections:
        s = by_id.get(tmpl_sec.id, {})
        # Backstop: drop any citation whose sourceUrl is not in the payload whitelist,
        # drop citations missing a claim, and coerce LLM-drifted confidence to the
        # allowed enum — so one malformed field never 500s the whole memo.
        clean_citations = []
        for cit in (s.get("citations") or []):
            if not isinstance(cit, dict) or not cit.get("claim"):
                continue
            src = cit.get("sourceUrl")
            if src and src not in urls:
                dropped += 1
                continue
            clean_citations.append({**cit, "confidence": _coerce_conf(cit.get("confidence"))})
        sections.append(MemoSection.model_validate({
            "id": tmpl_sec.id,
            "title": s.get("title") or tmpl_sec.title,
            "body": s.get("body") or "",
            "citations": clean_citations,
            "confidence": _coerce_conf(s.get("confidence")),
            "hasGaps": bool(s.get("hasGaps")),
        }))

    if dropped:
        logger.warning("memo backstop dropped %d fabricated citation(s)", dropped)

    subject_name = (radar_output.get("subject") or {}).get("name") or "—"
    return Memo(
        template_id=template.id,
        template_name=template.name,
        subject_name=subject_name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        sections=sections,
    )
