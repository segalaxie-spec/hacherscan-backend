"""
scoring.py

HacherScan V3 - Moteur de score de risque.

Composants actuels :
- Risque contrat on-chain
- Risque marché & liquidité
- Risque réputation (liens officiels)
- Risques avancés (analyse du code)
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

from app.services.onchain_fetcher import (
    Chain,
    OnchainTokenData,
)
from app.services.market_fetcher import MarketTokenData
from app.services.reputation_fetcher import ReputationLinks
from app.services.data_aggregator import DataAggregator
from app.services.risk_rules_advanced import (
    AdvancedRiskFlag,
    analyze_advanced_risks,
)


class RiskLabel(str, Enum):
    VERY_LOW = "très faible"
    LOW = "faible"
    MEDIUM = "modéré"
    HIGH = "élevé"
    CRITICAL = "critique"


class RiskComponent(BaseModel):
    name: str
    score: float  # 0 = safe, 100 = très risqué
    weight: float
    reasons: List[str]


class RiskResult(BaseModel):
    chain: Chain
    contract_address: str
    project_name: Optional[str] = None
    symbol: Optional[str] = None

    global_score: float
    label: RiskLabel

    components: List[RiskComponent]

    # Pour le front : liens officiels
    reputation_links: Optional[ReputationLinks] = None


def _clip_score(score: float) -> float:
    return max(0.0, min(100.0, score))


def _label_from_score(score: float) -> RiskLabel:
    if score < 20:
        return RiskLabel.VERY_LOW
    if score < 40:
        return RiskLabel.LOW
    if score < 60:
        return RiskLabel.MEDIUM
    if score < 80:
        return RiskLabel.HIGH
    return RiskLabel.CRITICAL


# ---------- CONTRAT / ON-CHAIN ----------


def _score_contract_risk(onchain: Optional[OnchainTokenData]) -> RiskComponent:
    """Score basé sur le contrat (vérification, supply, holders)."""

    reasons: List[str] = []

    if onchain is None:
        score = 80.0
        reasons.append("Impossible de récupérer les infos on-chain (erreur API).")
        return RiskComponent(
            name="Risque contrat on-chain",
            score=_clip_score(score),
            weight=0.4,  # ajusté (avant 0.5)
            reasons=reasons,
        )

    score = 20.0  # base neutre

    # Vérification du contrat
    if onchain.is_contract_verified:
        score -= 10
        reasons.append("Code du contrat vérifié sur l'explorateur.")
    else:
        score += 25
        reasons.append("Code du contrat NON vérifié (possible code caché / backdoor).")

    # Infos de supply
    if onchain.total_supply_normalized is None:
        score += 10
        reasons.append("Total supply inconnue (manque de transparence).")
    else:
        reasons.append(f"Total supply détectée : {onchain.total_supply_normalized}.")

    # Nombre de holders
    if onchain.holders_count is not None:
        if onchain.holders_count < 100:
            score += 30
            reasons.append("Moins de 100 holders (fort risque de manipulation).")
        elif onchain.holders_count < 1000:
            score += 15
            reasons.append("Moins de 1000 holders (risque de centralisation).")
        else:
            score -= 5
            reasons.append("Communauté de holders significative.")
    else:
        score += 5
        reasons.append("Nombre de holders inconnu.")

    score = _clip_score(score)

    return RiskComponent(
        name="Risque contrat on-chain",
        score=score,
        weight=0.4,  # 40% du score global
        reasons=reasons,
    )


# ---------- MARCHÉ / LIQUIDITÉ ----------


def _score_market_risk(market: Optional[MarketTokenData]) -> RiskComponent:
    """Score basé sur liquidité, volume, volatilité, FDV."""

    reasons: List[str] = []

    if market is None or market.best_pool is None:
        score = 75.0
        reasons.append(
            "Aucune pool DEX trouvée pour ce token (token potentiellement illiquide ou peu transparent)."
        )
        return RiskComponent(
            name="Risque marché & liquidité",
            score=_clip_score(score),
            weight=0.25,  # ajusté (avant 0.3)
            reasons=reasons,
        )

    pool = market.best_pool
    score = 40.0  # point de départ

    # Liquidité
    liq = pool.liquidity_usd
    if liq is None:
        score += 20
        reasons.append("Liquidité inconnue (données incomplètes).")
    else:
        if liq < 20_000:
            score += 35
            reasons.append("Liquidité < 20k$ (très risqué, gros slippage possible).")
        elif liq < 100_000:
            score += 20
            reasons.append("Liquidité entre 20k$ et 100k$ (risque élevé).")
        elif liq < 500_000:
            score += 10
            reasons.append("Liquidité entre 100k$ et 500k$ (risque modéré).")
        elif liq < 5_000_000:
            reasons.append("Liquidité > 500k$ (plutôt confortable).")
        else:
            score -= 10
            reasons.append("Très forte liquidité (bon point pour la stabilité).")

    # Volume 24h
    vol = pool.volume_24h_usd
    if vol is None:
        score += 10
        reasons.append("Volume 24h inconnu.")
    else:
        if vol < 10_000:
            score += 25
            reasons.append("Volume 24h < 10k$ (peu de trading, marché inactif).")
        elif vol < 100_000:
            score += 10
            reasons.append("Volume 24h entre 10k$ et 100k$ (activité modérée).")
        elif vol > 1_000_000:
            score -= 10
            reasons.append("Volume 24h > 1M$ (forte activité, bon point).")

    # Volatilité prix 24h
    change = pool.price_change_24h
    if change is not None:
        if abs(change) > 40:
            score += 15
            reasons.append(
                f"Variation prix 24h très forte ({change}%), possible pump & dump."
            )
        elif abs(change) > 20:
            score += 5
            reasons.append(
                f"Variation prix 24h significative ({change}%), volatilité à surveiller."
            )
        elif abs(change) < 5:
            score -= 5
            reasons.append("Prix relativement stable sur 24h (plutôt rassurant).")

    # Rapport FDV / liquidité
    if pool.fdv_usd is not None and pool.liquidity_usd is not None and pool.liquidity_usd > 0:
        ratio = pool.fdv_usd / pool.liquidity_usd
        if ratio > 100:
            score += 10
            reasons.append(
                f"FDV/liquidité très élevée (~{ratio:.1f}) : token peut être surévalué."
            )
        elif ratio < 10:
            score -= 5
            reasons.append(
                f"FDV/liquidité raisonnable (~{ratio:.1f}) : valorisation plus saine."
            )

    score = _clip_score(score)

    return RiskComponent(
        name="Risque marché & liquidité",
        score=score,
        weight=0.25,  # 25% du score global
        reasons=reasons,
    )


# ---------- RÉPUTATION (LIENS OFFICIELS) ----------


def _score_reputation_risk(links: Optional[ReputationLinks]) -> RiskComponent:
    """V1 simple : on regarde le NOMBRE de liens officiels."""

    reasons: List[str] = []

    if links is None:
        score = 80.0
        reasons.append("Impossible de récupérer les liens officiels (erreur API).")
        return RiskComponent(
            name="Risque réputation (liens officiels)",
            score=_clip_score(score),
            weight=0.15,  # ajusté (avant 0.2)
            reasons=reasons,
        )

    link_values = {
        "Site web": links.website,
        "Twitter / X": links.twitter,
        "Discord": links.discord,
        "Github": links.github,
    }

    present = [name for name, url in link_values.items() if url]
    missing = [name for name, url in link_values.items() if not url]

    nb_links = len(present)

    if nb_links == 0:
        score = 85.0
        reasons.append(
            "Aucun lien officiel (website, Twitter, Discord, Github) n'a été trouvé."
        )
    elif nb_links == 1:
        score = 70.0
        reasons.append(
            f"Un seul lien officiel détecté ({present[0]}). Présence publique très limitée."
        )
    elif nb_links == 2:
        score = 50.0
        reasons.append(
            f"Deux liens officiels détectés ({', '.join(present)}). Réputation moyenne."
        )
    elif nb_links == 3:
        score = 35.0
        reasons.append(
            f"Plusieurs liens officiels détectés ({', '.join(present)}). Projet plutôt assumé publiquement."
        )
    else:  # 4
        score = 20.0
        reasons.append(
            "Présence complète (website, Twitter, Discord, Github). Bon point pour la réputation."
        )

    if present:
        reasons.append("Liens trouvés : " + ", ".join(present) + ".")
    if missing:
        reasons.append("Liens manquants : " + ", ".join(missing) + ".")

    score = _clip_score(score)

    return RiskComponent(
        name="Risque réputation (liens officiels)",
        score=score,
        weight=0.15,  # 15% du score global
        reasons=reasons,
    )


# ---------- RISQUES AVANCÉS (ANALYSE DU CODE) ----------


def _score_advanced_risks(
    onchain: Optional[OnchainTokenData],
    market: Optional[MarketTokenData],
) -> RiskComponent:
    """
    Utilise analyze_advanced_risks pour produire un composant de risque.
    """

    reasons: List[str] = []

    if onchain is None:
        score = 70.0
        reasons.append(
            "Impossible d'analyser le code du contrat (pas de données on-chain)."
        )
        return RiskComponent(
            name="Risques avancés du contrat",
            score=_clip_score(score),
            weight=0.2,  # 20% du score global
            reasons=reasons,
        )

    flags: List[AdvancedRiskFlag] = analyze_advanced_risks(onchain, market)

    if not flags:
        score = 20.0
        reasons.append(
            "Aucun pattern de risque avancé détecté dans le code (analyse heuristique basique)."
        )
        return RiskComponent(
            name="Risques avancés du contrat",
            score=_clip_score(score),
            weight=0.2,
            reasons=reasons,
        )

    # Base neutre
    score = 40.0

    for flag in flags:
        if flag.severity == "low":
            score += 5
        elif flag.severity == "medium":
            score += 10
        elif flag.severity == "high":
            score += 20
        elif flag.severity == "critical":
            score += 30

        reasons.append(f"{flag.name} : {flag.reason}")

    score = _clip_score(score)

    return RiskComponent(
        name="Risques avancés du contrat",
        score=score,
        weight=0.2,
        reasons=reasons,
    )


# ---------- AGRÉGATION GLOBALE ----------


async def compute_risk_score(chain: Chain, contract_address: str) -> RiskResult:
    """
    Fonction principale appelée par l'API HacherScan.
    Utilise DataAggregator + tous les composants de risque.
    """

    contract_address = contract_address.strip()

    aggregator = DataAggregator()
    snapshot = await aggregator.build_token_snapshot(chain, contract_address)

    onchain: Optional[OnchainTokenData] = snapshot.get("onchain")
    market: Optional[MarketTokenData] = snapshot.get("market")
    reputation_links: Optional[ReputationLinks] = snapshot.get("reputation")

    contract_component = _score_contract_risk(onchain)
    market_component = _score_market_risk(market)
    reputation_component = _score_reputation_risk(reputation_links)
    advanced_component = _score_advanced_risks(onchain, market)

    components = [
        contract_component,
        market_component,
        reputation_component,
        advanced_component,
    ]

    # Score global pondéré
    weighted_sum = sum(c.score * c.weight for c in components)
    weight_total = sum(c.weight for c in components) or 1.0

    global_score = _clip_score(weighted_sum / weight_total)
    label = _label_from_score(global_score)

    # Nom / symbole
    project_name = (
        (market.name if market and market.name else None)
        or (onchain.name if onchain and onchain.name else None)
    )
    symbol = (
        (market.symbol if market and market.symbol else None)
        or (onchain.symbol if onchain and onchain.symbol else None)
    )

    return RiskResult(
        chain=chain,
        contract_address=contract_address,
        project_name=project_name,
        symbol=symbol,
        global_score=global_score,
        label=label,
        components=components,
        reputation_links=reputation_links,
    )


def compute_risk_score_sync(chain: Chain, contract_address: str) -> RiskResult:
    """Wrapper synchrone pour tests/scripts."""
    import asyncio

    return asyncio.run(compute_risk_score(chain, contract_address))
