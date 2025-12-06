from fastapi import APIRouter, HTTPException
from app.services.onchain_fetcher import (
    Chain,
    OnchainTokenData,
    fetch_token_onchain_data,
    OnchainFetcherError,
)

router = APIRouter(prefix="/api/onchain", tags=["onchain"])


@router.get(
    "/token",
    response_model=OnchainTokenData,
    summary="Récupérer les infos on-chain d'un token",
)
async def get_token_onchain_data(chain: Chain, contract_address: str):
    """
    Exemple d'appel :
    GET /api/onchain/token?chain=ethereum&contract_address=0x...
    """
    try:
        data = await fetch_token_onchain_data(chain, contract_address)
        return data
    except OnchainFetcherError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne : {e}")
