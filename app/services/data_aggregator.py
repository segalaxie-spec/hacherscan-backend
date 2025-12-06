from typing import Dict, Any, Optional

from app.services.onchain_fetcher import (
    Chain,
    OnchainTokenData,
    OnchainFetcherError,
    fetch_token_onchain_data,
)
from app.services.market_fetcher import (
    MarketTokenData,
    MarketFetcherError,
    fetch_market_data,
)
from app.services.reputation_fetcher import (
    ReputationLinks,
    fetch_reputation_links,
)


class DataAggregator:
    """
    Rassemble toutes les données externes (on-chain, marché, réputation)
    dans un snapshot unique utilisé par scoring.py.
    """

    async def build_token_snapshot(
        self,
        chain: Chain,
        contract_address: str,
    ) -> Dict[str, Any]:
        """
        Renvoie un dict avec :
        - 'chain': Chain
        - 'contract_address': str
        - 'onchain': OnchainTokenData | None
        - 'market': MarketTokenData | None
        - 'reputation': ReputationLinks | None
        - éventuellement des clés '*_error' si un fetcher a échoué
        """

        contract_address = contract_address.strip()

        snapshot: Dict[str, Any] = {
            "chain": chain,
            "contract_address": contract_address,
            "onchain": None,
            "market": None,
            "reputation": None,
        }

        # 1) ON-CHAIN
        try:
            onchain: OnchainTokenData = await fetch_token_onchain_data(
                chain, contract_address
            )
            snapshot["onchain"] = onchain
        except OnchainFetcherError as e:
            snapshot["onchain_error"] = str(e)

        # 2) MARKET
        try:
            market: MarketTokenData = await fetch_market_data(chain, contract_address)
            snapshot["market"] = market
        except MarketFetcherError as e:
            snapshot["market_error"] = str(e)

        # 3) RÉPUTATION (LIENS OFFICIELS)
        try:
            reputation: ReputationLinks = await fetch_reputation_links(
                chain, contract_address
            )
            snapshot["reputation"] = reputation
        except Exception as e:
            # Pour l’instant pas d’exception dédiée, on reste générique
            snapshot["reputation_error"] = str(e)

        return snapshot
