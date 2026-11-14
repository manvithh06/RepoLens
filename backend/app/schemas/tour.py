from pydantic import BaseModel


class Citation(BaseModel):
    path: str  # verified to exist in the analysed repository
    line: int | None = None  # verified to be inside the file
    is_dir: bool = False


class TourOverview(BaseModel):
    text: str
    citations: list[Citation]
    verified: bool  # False when none of the files it cited exist


class TourStep(BaseModel):
    title: str
    detail: str
    citations: list[Citation]


class TourModule(BaseModel):
    name: str
    path: str
    summary: str
    citations: list[Citation]


class StartHere(BaseModel):
    path: str
    reason: str


class Tour(BaseModel):
    analysis_id: str
    model: str
    commit: str | None
    overview: TourOverview | None
    steps: list[TourStep]
    modules: list[TourModule]
    start_here: list[StartHere]
    diagram: str | None  # Mermaid flowchart built from the verified steps only
    files_read: list[str]
    dropped_claims: int  # model statements removed because their citations failed
    cached: bool = False
