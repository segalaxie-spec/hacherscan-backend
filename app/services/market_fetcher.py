"""
market_fetcher.py

Module chargé de récupérer les informations de marché d'un token
(prix, volume, liquidité…) à partir de son adresse de contrat.

Pour rester simple, gratuit et sans clé d'API au début, on utilise
l'API publique de DexScreener :

    https://api.dexscreener.com/latest/dex/tokens/{contractAddress}

Puis on filtre les paires trouvées pour ne garder que la plus pertinente
(sur la même chaîne que HacherScan et avec la meilleure liquidité).

Ce module est pensé pour être utilisé par le moteur de scoring.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from app.services.onchain_fetcher import Chain


DEXSCREENER_BASE_URL = "https://api.dexscreener.com/latest/dex/tokens"


class MarketFetcherError(Exception):
    """Exception personnalisée pour le module market_fetcher."""

    pass


class MarketPoolSummary(BaseModel):
    """
    Résumé d'une paire DEX pour un token.
    """

    dex_id: str
    chain: str
    pair_address: str
    pair_name: Optional[str] = None

    price_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    fdv_usd: Optional[float] = None

    volume_24h_usd: Optional[float] = None
    price_change_24h: Optional[float] = None

    url: Optional[str] = None


class MarketTokenData(BaseModel):
    """
    Structure standardisée des infos de marché pour un token.

    Elle est conçue pour être utilisée directement dans scoring.py.
    """

    chain: Chain
    contract_address: str

    symbol: Optional[str] = None
    name: Optional[str] = None

    # données agrégées (pool la plus pertinente)
    best_pool: Optional[MarketPoolSummary] = None

    # brut DexScreener si tu veux analyser plus tard
    raw_pairs: List[Dict[str, Any]] = Field(default_factory=list, repr=False)


def _map_chain_to_dexscreener(chain: Chain) -> str:
    """
    Convertit notre enum Chain en identifiant de chaîne DexScreener.
    """

    mapping = {
        Chain.ETHEREUM: "ethereum",
        Chain.BSC: "bsc",
        Chain.BASE: "base",
    }

    if chain not in mapping:
        raise MarketFetcherError(f"Chaîne non supportée par DexScreener : {chain.value}")

    return mapping[chain]


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


async def _call_dexscreener(contract_address: str) -> Dict[str, Any]:
    """
    Appelle l'API DexScreener pour un contrat donné.
    """

    url = f"{DEXSCREENER_BASE_URL}/{contract_address.strip()}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)

    if resp.status_code != 200:
        raise MarketFetcherError(
            f"Erreur HTTP {resp.status_code} depuis DexScreener: {resp.text}"
        )

    data = resp.json()
    return data


def _select_best_pool(
    pairs: List[Dict[str, Any]], target_chain_id: str
) -> Optional[MarketPoolSummary]:
    """
    Sélectionne la meilleure paire DEX pour le token :
    - même chaîne que celle demandée
    - meilleure liquidité USD
    """

    best_pair: Optional[Dict[str, Any]] = None
    best_liquidity: float = -1.0

    for pair in pairs:
        chain_id = pair.get("chainId")
        if chain_id != target_chain_id:
            continue

        liquidity = pair.get("liquidity", {})
        liquidity_usd = _safe_float(liquidity.get("usd"))

        if liquidity_usd is None:
            continue

        if liquidity_usd > best_liquidity:
            best_liquidity = liquidity_usd
            best_pair = pair

    if best_pair is None:
        return None

    price_usd = _safe_float(best_pair.get("priceUsd"))
    fdv_usd = _safe_float(best_pair.get("fdv"))
    volume_24h_usd = _safe_float(best_pair.get("volume", {}).get("h24"))
    price_change_24h = _safe_float(best_pair.get("priceChange", {}).get("h24"))

    return MarketPoolSummary(
        dex_id=str(best_pair.get("dexId")),
        chain=str(best_pair.get("chainId")),
        pair_address=str(best_pair.get("pairAddress")),
        pair_name=best_pair.get("pairName"),
        price_usd=price_usd,
        liquidity_usd=best_liquidity,
        fdv_usd=fdv_usd,
        volume_24h_usd=volume_24h_usd,
        price_change_24h=price_change_24h,
        url=best_pair.get("url"),
    )


async def fetch_market_data(
    chain: Chain,
    contract_address: str,
) -> MarketTokenData:
    """
    Fonction principale appelée par le backend.

    Étapes :
    1. Appel API DexScreener pour le contrat.
    2. Filtrage des paires pour ne garder que celles de la bonne chaîne.
    3. Sélection de la meilleure pool (max liquidité).
    4. Construction d'un MarketTokenData prêt pour scoring.py.
    """

    contract_address = contract_address.strip()

    # 1) Appel API
    data = await _call_dexscreener(contract_address)
    pairs = data.get("pairs") or []

    if not pairs:
        # On ne lève pas forcément une erreur ici : le token peut être CEX-only.
        # On renverra alors un MarketTokenData avec best_pool=None
        return MarketTokenData(
            chain=chain,
            contract_address=contract_address,
            symbol=None,
            name=None,
            best_pool=None,
            raw_pairs=[],
        )

    target_chain_id = _map_chain_to_dexscreener(chain)

    # 2) Sélection de la meilleure paire sur la bonne chaîne
    best_pool = _select_best_pool(pairs, target_chain_id)

    # On récupère symbol/name depuis la paire choisie si dispo
    symbol = None
    name = None
    if best_pool is not None:
        # retrouver le dict source correspondant pour accéder à "baseToken"
        for p in pairs:
            if (
                p.get("pairAddress") == best_pool.pair_address
                and p.get("chainId") == best_pool.chain
            ):
                base_token = p.get("baseToken") or {}
                symbol = base_token.get("symbol")
                name = base_token.get("name")
                break

    return MarketTokenData(
        chain=chain,
        contract_address=contract_address,
        symbol=symbol,
        name=name,
        best_pool=best_pool,
        raw_pairs=pairs,
    )


# Optionnel : wrapper synchrone pour scripts/tests
def fetch_market_data_sync(chain: Chain, contract_address: str) -> MarketTokenData:
    import asyncio

    return asyncio.run(fetch_market_data(chain, contract_address))
