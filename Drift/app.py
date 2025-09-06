from fastapi import FastAPI
from models import RankingRequest, RankingResponse
from drift_ranker import rank_videos

app = FastAPI()

@app.get("/health")
def health() -> dict:
    # Return service status.
    return {"status": "ok"}

@app.post("/rank", response_model=RankingResponse)
def rank(req: RankingRequest) -> RankingResponse:
    # Return ranked videos.
    results = rank_videos(req.user, req.candidates)
    return RankingResponse(results=results)
