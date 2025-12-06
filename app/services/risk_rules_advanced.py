"""
risk_rules_advanced.py

Analyse heuristique du code du contrat pour détecter
des patterns de risque avancés (honeypot, mintable, proxy, blacklist, etc.).

⚠️ IMPORTANT :
Ce module ne remplace PAS un audit, c'est un détecteur de signaux faibles.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from app.services.onchain_fetcher import OnchainTokenData
from app.services.market_fetcher import MarketTokenData


class AdvancedRiskFlag(BaseModel):
    name: str
    severity: str  # "low" | "medium" | "high" | "critical"
    reason: str


def _extract_source_code(onchain: OnchainTokenData) -> str:
    """
    Récupère la chaîne de code Solidity depuis raw_source_code_response.
    Si rien n'est disponible, renvoie une chaîne vide.
    """
    if not onchain.raw_source_code_response:
        return ""

    result = onchain.raw_source_code_response.get("result")
    if isinstance(result, list) and result:
        obj = result[0]
        return obj.get("SourceCode") or ""
    elif isinstance(result, dict):
        return result.get("SourceCode") or ""

    return ""


def analyze_advanced_risks(
    onchain: Optional[OnchainTokenData],
    market: Optional[MarketTokenData] = None,
) -> List[AdvancedRiskFlag]:
    """
    Analyse le code et les méta-données pour générer une liste de flags.

    On se base uniquement sur :
    - le code source (patterns textuels)
    - quelques infos marché générales si disponibles
    """

    flags: List[AdvancedRiskFlag] = []

    if onchain is None:
        # Pas d'info on-chain -> impossible d'analyser finement
        return flags

    source_code = _extract_source_code(onchain)
    if not source_code:
        # Pas de code -> rien à analyser, mais pas de flag non plus
        return flags

    code_lower = source_code.lower()

    # ---------- 1) Proxy / upgradeable ----------
    contract_name_lower = (onchain.name or "").lower()
    if (
        "proxy" in contract_name_lower
        or "proxy" in code_lower
        or "delegatecall" in code_lower
        or "transparentupgradeableproxy" in code_lower
    ):
        flags.append(
            AdvancedRiskFlag(
                name="Contrat proxy / upgradable",
                severity="medium",
                reason=(
                    "Le code du contrat contient des éléments de proxy ou d'upgrade "
                    "(Proxy, delegatecall...). La logique peut être modifiée après le déploiement."
                ),
            )
        )

    # ---------- 2) Mint / supply illimitée ----------
    if "function mint" in code_lower or "mint(" in code_lower:
        flags.append(
            AdvancedRiskFlag(
                name="Fonction de mint détectée",
                severity="high",
                reason=(
                    "Le contrat contient une fonction de mint. "
                    "Si elle est contrôlée par un owner, la supply peut être augmentée "
                    "à tout moment."
                ),
            )
        )

    # ---------- 3) Blacklist / blocklist / restrictions d'adresse ----------
    if "blacklist" in code_lower or "blocklist" in code_lower or "isblacklisted" in code_lower:
        flags.append(
            AdvancedRiskFlag(
                name="Mécanisme de blacklist",
                severity="medium",
                reason=(
                    "Le contrat contient une logique de blacklist/blocklist. "
                    "Certaines adresses peuvent être empêchées de transférer ou vendre le token."
                ),
            )
        )

    # ---------- 4) Pause / trading lock ----------
    if "pausable" in code_lower or "whennotpaused" in code_lower or "pause()" in code_lower:
        flags.append(
            AdvancedRiskFlag(
                name="Contrat pausable / trading lock potentiel",
                severity="medium",
                reason=(
                    "Le contrat est pausable. Le propriétaire peut potentiellement bloquer "
                    "les transferts à tout moment."
                ),
            )
        )

    # ---------- 5) Taxes / fees sur les transferts ----------
    tax_keywords = [
        "taxfee",
        "liquidityfee",
        "marketingfee",
        "buytax",
        "selltax",
        "feepercent",
        "totalfees",
    ]
    if any(k in code_lower for k in tax_keywords):
        flags.append(
            AdvancedRiskFlag(
                name="Taxes sur les transferts",
                severity="medium",
                reason=(
                    "Le contrat contient des variables de taxe (fees) sur les transferts. "
                    "Les frais peuvent être élevés ou modifiables."
                ),
            )
        )

    # ---------- 6) Ownership / onlyOwner très puissant ----------
    if "onlyowner" in code_lower or "ownable" in code_lower:
        # On ne sait pas si c'est clean ou abusif, mais on le signale
        flags.append(
            AdvancedRiskFlag(
                name="Contrôle propriétaire (Ownable)",
                severity="low",
                reason=(
                    "Le contrat utilise un schéma Ownable / onlyOwner. "
                    "Certaines fonctions critiques sont réservées au propriétaire."
                ),
            )
        )

    # ---------- 7) Cooldown / anti-bot agressif ----------
    if "cooldown" in code_lower or "maxtransactionamount" in code_lower:
        flags.append(
            AdvancedRiskFlag(
                name="Limites de trading / anti-bot",
                severity="low",
                reason=(
                    "Le contrat contient des variables de limite de transaction ou cooldown. "
                    "Mal configuré, cela peut bloquer les utilisateurs légitimes."
                ),
            )
        )

    # (Plus tard : on pourra croiser ça avec market pour détecter honeypots via tests de swap réels.)

    return flags
