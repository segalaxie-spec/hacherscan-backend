"""
reputation_fetcher.py

Version V1 : récupération simple des liens officiels d’un projet crypto.
Sources utilisées :
- Etherscan / BscScan / BaseScan (via fetch_token_onchain_data)
- DexScreener (via market_fetcher)

Cette version ne fait que collecter les liens (pas encore d'analyse profonde).
"""

from __future__ import annotations

from typing import Optional, Dict
from pydantic import BaseModel

from app.services.onchain_fetcher import (
    Chain,
    fetch_token_onchain_data,
    OnchainTokenData,
)
from app.services.market_fetcher import (
    fetch_market_data,
    MarketTokenData,
)


class ReputationLinks(BaseModel):
    website: Optional[str] = None
    twitter: Optional[str] = None
    discord: Optional[str] = None
    github: Optional[str] = None


async def fetch_reputation_links(chain: Chain, contract_address: str) -> ReputationLinks:
    """
    Fusionne les liens venant de différentes sources (Etherscan, DexScreener).
    Priorité :
    1. Etherscan / block explorer
    2. DexScreener (si trouvé)
    """

    contract_address = contract_address.strip()

    # ---------- 1) Infos on-chain : explorer ----------
    onchain: OnchainTokenData = await fetch_token_onchain_data(chain, contract_address)

    explorer_links = {
        "website": onchain.website,
        "twitter": onchain.twitter,
        "discord": onchain.discord,
        "github": onchain.github,
    }

    # ---------- 2) Infos DexScreener ----------
    market: Optional[MarketTokenData] = None
    try:
        market = await fetch_market_data(chain, contract_address)
    except Exception:
        pass

    ds_links: Dict[str, Optional[str]] = {
        "website": None,
        "twitter": None,
        "discord": None,
        "github": None,
    }

    # Dexscreener ajoute parfois des social links dans baseToken
    if market and market.raw_pairs:
        for p in market.raw_pairs:
            token_info = p.get("baseToken") or {}

            ds_links = {
                "website": token_info.get("website"),
                "twitter": token_info.get("twitter"),
                "discord": token_info.get("discord"),
                "github": token_info.get("github"),
            }

            break  # première paire suffit

    # ---------- 3) Fusion des deux sources ----------
    def choose(primary, fallback):
        return primary if primary else fallback

    final_links = ReputationLinks(
        website=choose(explorer_links["website"], ds_links["website"]),
        twitter=choose(explorer_links["twitter"], ds_links["twitter"]),
        discord=choose(explorer_links["discord"], ds_links["discord"]),
        github=choose(explorer_links["github"], ds_links["github"]),
    )

    return final_links
