from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

from models.company import CompanyProfile
from models.competitor import CompetitorProfile


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineRun(BaseModel):
    id: str
    company_domain: str
    status: PipelineStatus = PipelineStatus.PENDING
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    company_profile: Optional[CompanyProfile] = None
    competitors: List[CompetitorProfile] = []
    discover_source_urls: List[str] = []
    radar_scores: dict[str, List[float]] = {}
    from_cache: bool = False
