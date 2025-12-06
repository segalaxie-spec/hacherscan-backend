# utils/scoring.py

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


# -------------------------------------------------
#  DATA MODEL
# -------------------------------------------------

@dataclass
class HacherScanResult:
    """
    Résultat global HacherScan.
    - hacher_score : 0–100 (plus c'est haut, plus le projet est "safe")
    - hack_risk / quantum_risk : 0–100 (plus c'est haut, plus c'est risqué)
    """
    hacher_score: int
    hack_risk: int
    quantum_risk: int
    risk_level: str
    message: str


@dataclass
class SubScore:
    """Sous-score avec explications humaines."""
    value: int             # 0–100 (risque ou score brut)
    reasons: List[str]


def _clamp(value: float, min_value: int = 0, max_value: int = 100) -> int:
    """Force une valeur à rester entre 0 et 100."""
    return int(max(min_value, min(max_value, value)))


# -------------------------------------------------
#  MODULE 0 – Détection type + projet connu
# -------------------------------------------------

def detect_entity_type_and_known_project(normalized: str) -> Tuple[str, Optional[str], List[str]]:
    """
    Détecte le type d'entité (contrat, wallet, projet, domaine)
    + identifie quelques projets connus (Naoris, QANX, BTC, ETH).
    """
    reasons: List[str] = []
    entity_type = "project"
    known_project: Optional[str] = None

    # Adresse EVM (simplifiée)
    if normalized.startswith("0x") and len(normalized) in (42, 64):
        entity_type = "evm_contract"
        reasons.append("Adresse de contrat EVM détectée.")
    # Nom de domaine
    elif re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", normalized):
        entity_type = "domain"
        reasons.append("Nom de domaine détecté.")
    # Wallet type BTC (simplifié)
    elif re.match(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$", normalized):
        entity_type = "wallet"
        reasons.append("Adresse de wallet détectée.")
    else:
        entity_type = "project"
        reasons.append("Analyse en tant que nom de projet/token.")

    # Projets connus
    if "naoris" in normalized:
        known_project = "naoris"
        reasons.append("Projet identifié comme Naoris Protocol (profil sécurité élevé, post-quantique).")
    elif "qanx" in normalized or "qanplatform" in normalized:
        known_project = "qanx"
        reasons.append("Projet identifié comme QANX (profil intermédiaire, orienté sécu/quantique).")
    elif normalized in ("btc", "bitcoin"):
        known_project = "btc"
        reasons.append("Projet identifié comme Bitcoin.")
    elif normalized in ("eth", "ethereum"):
        known_project = "eth"
        reasons.append("Projet identifié comme Ethereum.")

    return entity_type, known_project, reasons


# -------------------------------------------------
#  MODULE 1 – Risque Smart Contract / Code
# -------------------------------------------------

def analyze_contract_and_code(normalized: str, entity_type: str, known_project: Optional[str]) -> SubScore:
    """
    Analyse heuristique du risque de hack lié au code / smart contract.
    Plus la valeur est haute, plus le risque est élevé.
    """
    reasons: List[str] = []
    risk = 60  # base : projet inconnu

    # Projets connus (profils de base)
    if known_project == "naoris":
        risk = 25
        reasons.append("Naoris : projet orienté cybersécurité, profil de code généralement robuste.")
    elif known_project == "qanx":
        risk = 45
        reasons.append("QANX : projet intermédiaire, focus sécurité et infra.")
    elif known_project == "btc":
        risk = 20
        reasons.append("Bitcoin : code très testé et éprouvé.")
    elif known_project == "eth":
        risk = 30
        reasons.append("Ethereum : écosystème mature, mais complexité plus élevée du code.")

    # Type d'entité
    if entity_type == "evm_contract":
        risk += 10
        reasons.append("Contrat EVM : surface d'attaque élevée (bugs potentiels dans le code).")
    elif entity_type == "wallet":
        risk += 5
        reasons.append("Wallet : risque lié surtout à la gestion des clés privées.")

    # Indices positifs
    if "audit" in normalized:
        risk -= 12
        reasons.append("Mention d'audit : réduction du risque de bug critique.")
    if "audited by" in normalized or "certik" in normalized:
        risk -= 8
        reasons.append("Mention d'audit par un tiers (ex: Certik).")
    if "multisig" in normalized:
        risk -= 7
        reasons.append("Multisig détecté : meilleure gouvernance de clés.")
    if "open source" in normalized or "github" in normalized:
        risk -= 5
        reasons.append("Référence open source / Github : code plus auditable.")

    # Indices négatifs
    if "proxy" in normalized and "upgradable" in normalized:
        risk += 8
        reasons.append("Contrat upgradable via proxy : nécessite plus de confiance dans l'équipe.")
    if "no audit" in normalized or "unaudited" in normalized:
        risk += 10
        reasons.append("Absence explicite d'audit : risque accru.")
    if "renounced" in normalized and "false" in normalized:
        risk += 8
        reasons.append("Propriété non renoncée : contrôle fort de l'équipe sur le contrat.")

    risk = _clamp(risk)
    return SubScore(value=risk, reasons=reasons)


# -------------------------------------------------
#  MODULE 2 – Risque Liquidité / Marché
# -------------------------------------------------

def analyze_liquidity_and_market(normalized: str) -> SubScore:
    """
    Analyse du risque lié à la liquidité (LP lock, burn, etc.) et au comportement de marché.
    Plus la valeur est haute, plus le risque est élevé.
    """
    reasons: List[str] = []
    risk = 60  # base

    # Signaux positifs
    if "liquidity locked" in normalized or "lp locked" in normalized:
        risk -= 15
        reasons.append("Mention de liquidité bloquée (LP locked) : réduction du risque de rug.")
    if "lp burned" in normalized or "liquidity burned" in normalized:
        risk -= 10
        reasons.append("LP burned : rug pull beaucoup plus difficile.")
    if "no tax" in normalized:
        risk -= 3
        reasons.append("No tax : moins de mécanique de ponzi via taxes exagérées.")

    # Signaux négatifs
    if "low liquidity" in normalized:
        risk += 12
        reasons.append("Liquidité faible annoncée : sensibilité très forte aux mouvements de prix.")
    if "high tax" in normalized or "buy tax" in normalized or "sell tax" in normalized:
        risk += 8
        reasons.append("Taxes importantes sur les transactions : risque de tokenomics toxiques.")
    if "anti-whale disabled" in normalized:
        risk += 8
        reasons.append("Anti-whale désactivé : gros dumps possibles.")

    return SubScore(value=_clamp(risk), reasons=reasons)


# -------------------------------------------------
#  MODULE 3 – Risque Distribution / Holders
# -------------------------------------------------

def analyze_distribution_and_holders(normalized: str) -> SubScore:
    """
    Analyse simplifiée de la distribution (whales, top holders, etc.).
    Pour v2, on reste heuristique (mots-clés),
    mais plus tard ce module utilisera les vraies données on-chain.
    """
    reasons: List[str] = []
    risk = 55  # base

    if "top 10 hold" in normalized or "top10" in normalized:
        risk += 10
        reasons.append("Top 10 holders très concentrés : risque de dumps massifs.")
    if "anti-whale" in normalized:
        risk -= 8
        reasons.append("Mécanisme anti-whale détecté : limitation des grosses ventes.")
    if "fair launch" in normalized:
        risk -= 5
        reasons.append("Fair launch : distribution initiale plus équilibrée.")
    if "team wallet" in normalized and "40%" in normalized:
        risk += 12
        reasons.append("Gros pourcentage détenu par l'équipe : dépendance forte à leur comportement.")

    return SubScore(value=_clamp(risk), reasons=reasons)


# -------------------------------------------------
#  MODULE 4 – Réputation Off-chain
# -------------------------------------------------

def analyze_offchain_reputation(normalized: str) -> SubScore:
    """
    Analyse la réputation off-chain : communication, sérieux, signaux de scam.
    """
    reasons: List[str] = []
    risk = 55

    # Red flags marketing
    risky_keywords = [
        "1000x", "100x", "pump", "moon", "lambo",
        "no risk", "garanti", "guaranteed", "double your money"
    ]
    if any(kw in normalized for kw in risky_keywords):
        risk += 15
        reasons.append("Promesses marketing excessives (100x, pump, garanti) : fort signal de scam potentiel.")

    if "airdrop" in normalized and "free" in normalized:
        risk += 8
        reasons.append("Airdrop + gratuit : risque de phishing ou bait marketing.")

    # Signaux positifs
    if "kyc" in normalized:
        risk -= 8
        reasons.append("Mention de KYC : équipe au moins partiellement identifiée.")
    if "doxxed team" in normalized or "team doxxed" in normalized:
        risk -= 10
        reasons.append("Équipe doxxed : meilleure responsabilité publique.")
    if "listed on coingecko" in normalized or "listed on cmc" in normalized:
        risk -= 5
        reasons.append("Listing sur CMC/Coingecko : filtre minimum passé.")
    if "partnership" in normalized and "exchange" in normalized:
        risk -= 4
        reasons.append("Partenariats annoncés avec des exchanges : crédibilité supplémentaire.")

    return SubScore(value=_clamp(risk), reasons=reasons)


# -------------------------------------------------
#  MODULE 5 – Profil Quantique
# -------------------------------------------------

def analyze_quantum_profile(normalized: str, known_project: Optional[str]) -> SubScore:
    """
    Analyse du risque quantique.
    Plus la valeur est haute, plus le projet est vulnérable aux futurs ordis quantiques.
    """
    reasons: List[str] = []
    risk = 60

    if known_project == "naoris":
        risk = 20
        reasons.append("Naoris : projet explicitement orienté défense post-quantique.")
    elif known_project == "qanx":
        risk = 35
        reasons.append("QANX : orientation sécurité / quantique déjà annoncée.")
    elif known_project in ("btc", "eth"):
        risk = 80
        reasons.append("Bitcoin/Ethereum : cryptographie classique vulnérable au long terme.")

    pq_keywords = [
        "post-quantum", "postquantum", "quantum safe",
        "pqc", "lattice", "hash-based", "hash based"
    ]
    if any(kw in normalized for kw in pq_keywords):
        risk -= 20
        reasons.append("Mention explicite de cryptographie post-quantique / PQC.")

    if "ecdsa" in normalized or "rsa" in normalized:
        risk += 10
        reasons.append("Référence explicite à ECDSA/RSA classiques : vulnérables au long terme.")

    return SubScore(value=_clamp(risk), reasons=reasons)


# -------------------------------------------------
#  MODULE 6 – Agrégation → HacherScore global
# -------------------------------------------------

def compute_hacherscan_scores(query: str) -> HacherScanResult:
    """
    Pipeline complet HacherScan v2 (heuristique 6 modules).
    1) Détection type + projet connu
    2) Contrat / code
    3) Liquidité / marché
    4) Distribution / holders
    5) Réputation off-chain
    6) Profil quantique + agrégation en HacherScore
    """

    original_query = query
    normalized = query.strip().lower()

    global_reasons: List[str] = []

    # 0) Type + projet connu
    entity_type, known_project, meta_reasons = detect_entity_type_and_known_project(normalized)
    global_reasons.extend(meta_reasons)

    # 1) Contrat / Code
    contract_score = analyze_contract_and_code(normalized, entity_type, known_project)

    # 2) Liquidité / Marché
    liquidity_score = analyze_liquidity_and_market(normalized)

    # 3) Distribution / Holders
    distribution_score = analyze_distribution_and_holders(normalized)

    # 4) Réputation Off-chain
    reputation_score = analyze_offchain_reputation(normalized)

    # 5) Profil quantique
    quantum_score = analyze_quantum_profile(normalized, known_project)

    # ---- Agrégation des raisons
    for sub in (contract_score, liquidity_score, distribution_score, reputation_score, quantum_score):
        global_reasons.extend(sub.reasons)

    # ---- Agrégation des risques en 2 scores principaux

    # Hack Risk = combinaison contrat + liquidité + distribution + réputation
    hack_weight_contract = 0.4
    hack_weight_liquidity = 0.25
    hack_weight_distribution = 0.2
    hack_weight_reputation = 0.15

    hack_risk_raw = (
        contract_score.value * hack_weight_contract +
        liquidity_score.value * hack_weight_liquidity +
        distribution_score.value * hack_weight_distribution +
        reputation_score.value * hack_weight_reputation
    )
    hack_risk = _clamp(hack_risk_raw)

    # Quantum Risk = directement le score quantique pour l'instant
    quantum_risk = quantum_score.value

    # HacherScore = 100 - combinaison pondérée des risques
    weight_hack_global = 0.7
    weight_quantum_global = 0.3

    total_risk = hack_risk * weight_hack_global + quantum_risk * weight_quantum_global
    hacher_score = _clamp(100 - total_risk)

    # Niveau de risque global
    if hacher_score >= 70:
        risk_level = "LOW"
    elif hacher_score >= 40:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    if not global_reasons:
        global_reasons.append("Aucun signal fort détecté, profil de risque générique appliqué.")

    message = (
        f"Analyse de '{original_query}': HacherScore={hacher_score}/100, "
        f"niveau de risque global={risk_level}. "
        f"(hack_risk={hack_risk}, quantum_risk={quantum_risk}). "
        + " ".join(global_reasons)
    )

    return HacherScanResult(
        hacher_score=hacher_score,
        hack_risk=hack_risk,
        quantum_risk=quantum_risk,
        risk_level=risk_level,
        message=message
    )
