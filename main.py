from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.scoring import compute_risk_score, RiskResult
from app.services.onchain_fetcher import (
    Chain,
    OnchainTokenData,
    fetch_token_onchain_data,
    OnchainFetcherError,
)

# plus tard : from app.services.data_aggregator import DataAggregator


app = FastAPI(
    title="HacherScan Backend API",
    version="0.1.0",
    description="Backend d'analyse de risque crypto & quantique.",
)

# 🔓 CORS : autoriser les appels venant de ton site Base44 (et autres frontends)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # si tu veux, on pourra plus tard limiter à ton domaine Base44
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanRequest(BaseModel):
    chain: str
    contract_address: str


@app.get("/health")
def health_check():
    return {"status": "ok", "app": "HacherScan V2"}


# --- Route Onchain brute : récupère uniquement les données on-chain ---
@app.get(
    "/api/onchain/token",
    response_model=OnchainTokenData,
    summary="Récupérer les infos on-chain d'un token",
)
async def get_token_onchain_data(chain: Chain, contract_address: str):
    """
    Exemple :
    GET /api/onchain/token?chain=ethereum&contract_address=0xA0b8...
    """
    try:
        data = await fetch_token_onchain_data(chain, contract_address.strip())
        return data
    except OnchainFetcherError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne : {e}")


# --- Route HacherScan : renvoie le score de risque complet ---
@app.post(
    "/api/hacherscan",
    response_model=RiskResult,
    summary="Scanner un token et obtenir un HacherScore V2",
)
async def scan_token(request: ScanRequest):
    """
    Body attendu :
    {
      "chain": "ethereum" | "bsc" | "base",
      "contract_address": "0x..."
    }
    """
    # normaliser la chaîne
    try:
        chain_enum = Chain(request.chain.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Chaîne non supportée : {request.chain}",
        )

    result = await compute_risk_score(chain_enum, request.contract_address.strip())
    return result

# plus tard : ajouter des routes pour d'autres services (DataAggregator, etc.)

