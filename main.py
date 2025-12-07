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

app = FastAPI(
    title="HacherScan Backend API",
    version="0.1.0",
    description="Backend d'analyse de risque crypto & quantique.",
)

# CORS – pour que Base44 / ton front puissent appeler l’API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # on pourra restreindre plus tard
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


@app.post(
    "/api/hacherscan",
    response_model=RiskResult,
    summary="Scanner un token et obtenir un HacherScore V2",
)
async def scan_token(request: ScanRequest):   # 🔴 ICI : le paramètre s'appelle `request`
    """
    Body attendu :
    {
      "chain": "ethereum",
      "contract_address": "0x..."
    }
    """
    try:
        chain_enum = Chain(request.chain.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Chaîne non supportée : {request.chain}",
        )

    result = await compute_risk_score(chain_enum, request.contract_address.strip())
    return result

