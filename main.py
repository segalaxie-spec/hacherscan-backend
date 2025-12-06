from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from utils.scoring import compute_hacherscan_scores

# -------------------------
# CONFIG FASTAPI
# -------------------------
app = FastAPI(title="HacherScan Backend API")

# CORS : pour autoriser ton site Base44 à appeler l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tu mettras ton domaine Base44 quand il sera en ligne
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# MODELES DE DONNÉES
# -------------------------
class ScanRequest(BaseModel):
    query: str

class ScanResponse(BaseModel):
    hacher_score: int
    hack_risk: int
    quantum_risk: int
    risk_level: str
    message: str

# -------------------------
# ROUTE PRINCIPALE : /api/hacherscan
# -------------------------
@app.post("/api/hacherscan", response_model=ScanResponse)
def scan(data: ScanRequest):
    # On délègue tout le calcul à l'algorithme dans utils/scoring.py
    result = compute_hacherscan_scores(data.query)

    return ScanResponse(
        hacher_score=result.hacher_score,
        hack_risk=result.hack_risk,
        quantum_risk=result.quantum_risk,
        risk_level=result.risk_level,
        message=result.message
    )


# -------------------------
# PROJETS (FAUSSES DONNÉES POUR TEST)
# -------------------------
@app.get("/api/projects")
def projects():
    return [
        {
            "id": "naoris",
            "name": "Naoris Protocol",
            "hacher_score": 78,
            "hack_risk": 82,
            "quantum_risk": 72
        },
        {
            "id": "qanx",
            "name": "QANX",
            "hacher_score": 71,
            "hack_risk": 75,
            "quantum_risk": 68
        }
    ]
