"""
onchain_fetcher.py

Module chargé de récupérer les informations on-chain d'un token
à partir de sa blockchain et de son adresse de contrat.

Il s'appuie sur l'API Etherscan v2 qui supporte plusieurs chaînes EVM
(Ethereum, BNB Smart Chain, Base, etc.) via un paramètre `chainid`.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel, Field


ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"


class Chain(str, Enum):
    """Blockchains EVM supportées par ce fetcher."""

    ETHEREUM = "ethereum"
    BSC = "bsc"
    BASE = "base"


# Mapping HacherScan -> chainid Etherscan v2
CHAIN_ID_MAP: Dict[Chain, int] = {
    Chain.ETHEREUM: 1,
    Chain.BSC: 56,
    Chain.BASE: 8453,
}


class OnchainTokenData(BaseModel):
    """
    Structure standardisée des infos on-chain d'un token.
    """

    chain: Chain
    contract_address: str

    # Infos basiques
    name: Optional[str] = None
    symbol: Optional[str] = None
    decimals: Optional[int] = None

    total_supply_raw: Optional[str] = None  # en "wei" / unité brute
    total_supply_normalized: Optional[float] = None

    # Liens officiels (si fournis par l'explorateur / tokeninfo)
    website: Optional[str] = None
    twitter: Optional[str] = None
    discord: Optional[str] = None
    github: Optional[str] = None

    # Contrat & vérification
    is_contract_verified: Optional[bool] = None
    contract_creator: Optional[str] = None
    creation_tx_hash: Optional[str] = None
    creation_block: Optional[int] = None
    creation_timestamp: Optional[int] = None

    # Holders & distribution (si dispo via API)
    holders_count: Optional[int] = None

    # Champs bruts
    raw_source_code_response: Optional[Dict[str, Any]] = Field(default=None, repr=False)
    raw_token_info_response: Optional[Dict[str, Any]] = Field(default=None, repr=False)
    raw_holders_response: Optional[Dict[str, Any]] = Field(default=None, repr=False)


class OnchainFetcherError(Exception):
    """Exception personnalisée pour le module onchain_fetcher."""

    pass


def _get_api_key() -> str:
    """Récupère la clé API Etherscan dans les variables d'environnement."""

    api_key = os.getenv("ETHERSCAN_API_KEY")
    if not api_key:
        raise OnchainFetcherError(
            "La variable d'environnement ETHERSCAN_API_KEY est manquante. "
            "Crée une clé sur Etherscan et ajoute-la à ton environnement."
        )
    return api_key


def _build_params(
    chain: Chain,
    module: str,
    action: str,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construit les paramètres communs pour l'appel Etherscan."""

    chain_id = CHAIN_ID_MAP.get(chain)
    if chain_id is None:
        raise OnchainFetcherError(f"Chaîne non supportée : {chain}")

    params: Dict[str, Any] = {
        "apikey": _get_api_key(),
        "chainid": chain_id,
        "module": module,
        "action": action,
    }

    if extra_params:
        params.update(extra_params)

    return params


async def _call_etherscan(params: Dict[str, Any]) -> Dict[str, Any]:
    """Appelle l'API Etherscan et renvoie le JSON, avec gestion d'erreurs basique."""

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(ETHERSCAN_BASE_URL, params=params)

    if resp.status_code != 200:
        raise OnchainFetcherError(
            f"Erreur HTTP {resp.status_code} depuis Etherscan: {resp.text}"
        )

    data = resp.json()
    status = data.get("status")
    message = data.get("message")

    # Etherscan renvoie status = "1" et message = "OK" quand tout est bon
    if status not in ("1", 1, None) and message not in ("OK", None):
        raise OnchainFetcherError(
            f"Réponse Etherscan indiquant une erreur: status={status}, message={message}"
        )

    return data


async def _fetch_source_code(chain: Chain, contract_address: str) -> Dict[str, Any]:
    """Récupère les infos de vérification & métadonnées du contrat."""

    params = _build_params(
        chain=chain,
        module="contract",
        action="getsourcecode",
        extra_params={"address": contract_address},
    )
    return await _call_etherscan(params)


async def _fetch_token_supply(chain: Chain, contract_address: str) -> Dict[str, Any]:
    """Récupère la totalSupply du token (en valeur brute)."""

    params = _build_params(
        chain=chain,
        module="stats",
        action="tokensupply",
        extra_params={"contractaddress": contract_address},
    )
    return await _call_etherscan(params)


async def _fetch_token_info(chain: Chain, contract_address: str) -> Dict[str, Any]:
    """Récupère des infos complémentaires sur le token."""

    params = _build_params(
        chain=chain,
        module="token",
        action="tokeninfo",  # à adapter selon le plan Etherscan
        extra_params={"contractaddress": contract_address},
    )
    return await _call_etherscan(params)


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_float(value: Any, decimals: Optional[int]) -> Optional[float]:
    try:
        if value is None or decimals is None:
            return None
        return float(value) / (10 ** decimals)
    except (ValueError, TypeError):
        return None


async def fetch_token_onchain_data(
    chain: Chain,
    contract_address: str,
) -> OnchainTokenData:
    """
    Fonction principale appelée par ton backend.
    """

    contract_address = contract_address.strip()

    # 1) Source du contrat
    source_resp = await _fetch_source_code(chain, contract_address)
    source_result = source_resp.get("result")

    if isinstance(source_result, list) and source_result:
        source_obj = source_result[0]
    elif isinstance(source_result, dict):
        source_obj = source_result
    else:
        source_obj = {}

    # Vérification du contrat
    is_verified = bool(source_obj.get("SourceCode"))

    # Nom / symbole
    name = source_obj.get("ContractName") or source_obj.get("TokenName")
    symbol = source_obj.get("Symbol") or source_obj.get("TokenSymbol")

    # Créateur & tx de création
    contract_creator = source_obj.get("ContractCreator")
    creation_tx_hash = source_obj.get("TxHash")

    # Liens officiels depuis getsourcecode
    website = source_obj.get("Website")
    twitter = source_obj.get("Twitter")
    discord = source_obj.get("Discord")
    github = source_obj.get("Github") or source_obj.get("GitHub")

    # 2) Total supply brute
    supply_resp = await _fetch_token_supply(chain, contract_address)
    supply_result = supply_resp.get("result")
    if isinstance(supply_result, dict):
        total_supply_raw = supply_result.get("tokensupply") or supply_result.get(
            "TokenSupply"
        )
    else:
        total_supply_raw = supply_result

    # 3) Infos token (optionnelles)
    token_info_resp: Optional[Dict[str, Any]] = None
    holders_count: Optional[int] = None
    decimals: Optional[int] = None

    try:
        token_info_resp = await _fetch_token_info(chain, contract_address)
        token_info_result = token_info_resp.get("result")

        if isinstance(token_info_result, list) and token_info_result:
            token_info = token_info_result[0]
        elif isinstance(token_info_result, dict):
            token_info = token_info_result
        else:
            token_info = {}

        # Compléter nom / symbole si manquants
        if not name:
            name = token_info.get("tokenName") or token_info.get("name")

        if not symbol:
            symbol = token_info.get("tokenSymbol") or token_info.get("symbol")

        # Decimals
        decimals = _safe_int(
            token_info.get("divisor")
            or token_info.get("decimals")
            or token_info.get("tokenDecimal")
        )

        # Holders
        holders_count = _safe_int(
            token_info.get("tokenHolderCount") or token_info.get("holders")
        )

        # Compléter les liens officiels si non fournis par getsourcecode
        if not website:
            website = (
                token_info.get("website")
                or token_info.get("Website")
                or token_info.get("homePage")
            )

        if not twitter:
            twitter = (
                token_info.get("twitter")
                or token_info.get("Twitter")
                or token_info.get("twitterHandle")
            )

        if not discord:
            discord = token_info.get("discord") or token_info.get("Discord")

        if not github:
            github = (
                token_info.get("github")
                or token_info.get("Github")
                or token_info.get("GitHub")
            )

    except OnchainFetcherError:
        token_info_resp = None
        decimals = None
        holders_count = None

    # 4) Normalisation de la supply
    total_supply_normalized = _safe_float(total_supply_raw, decimals)

    return OnchainTokenData(
        chain=chain,
        contract_address=contract_address,
        name=name,
        symbol=symbol,
        decimals=decimals,
        total_supply_raw=str(total_supply_raw) if total_supply_raw is not None else None,
        total_supply_normalized=total_supply_normalized,
        website=website,
        twitter=twitter,
        discord=discord,
        github=github,
        is_contract_verified=is_verified,
        contract_creator=contract_creator,
        creation_tx_hash=creation_tx_hash,
        holders_count=holders_count,
        raw_source_code_response=source_resp,
        raw_token_info_response=token_info_resp,
        raw_holders_response=None,
    )


def fetch_token_onchain_data_sync(
    chain: Chain, contract_address: str
) -> OnchainTokenData:
    """Wrapper synchrone (pratique pour les tests)."""
    import asyncio

    return asyncio.run(fetch_token_onchain_data(chain, contract_address))
