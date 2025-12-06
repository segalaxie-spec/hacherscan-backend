import os
from textwrap import dedent

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
    print(f"[DIR]  {path}")

def write_file(path: str, content: str, overwrite: bool = False):
    if not overwrite and os.path.exists(path):
        print(f"[SKIP] {path} existe déjà")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(dedent(content).lstrip("\n"))
    print(f"[FILE] {path} créé")

def main():
    # On suppose que tu lances ce script depuis la racine du projet
    project_root = os.getcwd()
    print(f"Racine projet : {project_root}")

    # 1. Dossiers principaux
    ensure_dir("app")
    ensure_dir("app/services")
    ensure_dir("app/ai")

    # 2. __init__.py pour les modules Python
    write_file("app/__init__.py", "")
    write_file("app/services/__init__.py", "")
    write_file("app/ai/__init__.py", "")

    # 3. Fichier main.py (API FastAPI)
    write_file(
        "app/main.py",
        """
        from fastapi import FastAPI
        from pydantic import BaseModel
        from app.scoring import compute_risk_score
        # from app.services.data_aggregator import DataAggregator  # pour plus tard

        app = FastAPI(
            title="HacherScan V2 API",
            version="0.1.0",
            description="Backend d'analyse de risque crypto & quantique."
        )

        class ScanRequest(BaseModel):
            chain: str
            contract_address: str

        @app.get("/health")
        def health_check():
            return {"status": "ok", "app": "HacherScan V2"}

        @app.post("/api/hacherscan")
        async def scan_token(request: ScanRequest):
            # TODO: plus tard, récupérer un snapshot réel via DataAggregator
            result = compute_risk_score(
                chain=request.chain,
                contract_address=request.contract_address,
                snapshot=None
            )
            return result
        """
    )

    # 4. Fichier scoring.py (squelette de l'algo)
    write_file(
        "app/scoring.py",
        """
        from typing import Any, Dict, Optional

        # IA_HOOK: plus tard, on pourra brancher ici un modèle IA
        # pour ajuster dynamiquement les pondérations ou analyser les résultats.

        def compute_risk_score(
            chain: str,
            contract_address: str,
            snapshot: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            \"\"\"Fonction centrale de scoring.
            Pour l'instant, renvoie des valeurs fixes.
            On remplira les calculs étape par étape.
            \"\"\"

            network_score = _score_network(snapshot)
            contract_score = _score_contract(snapshot)
            market_score = _score_market(snapshot)
            social_score = _score_social(snapshot)
            quantum_score = _score_quantum(snapshot)

            weights = {
                "network": 0.20,
                "contract": 0.25,
                "market": 0.20,
                "social": 0.15,
                "quantum": 0.20,
            }

            global_score = (
                network_score * weights["network"]
                + contract_score * weights["contract"]
                + market_score * weights["market"]
                + social_score * weights["social"]
                + quantum_score * weights["quantum"]
            )

            return {
                "chain": chain,
                "contract_address": contract_address,
                "scores": {
                    "global": round(global_score, 2),
                    "network": network_score,
                    "contract": contract_score,
                    "market": market_score,
                    "social": social_score,
                    "quantum": quantum_score,
                },
                "explanations": {
                    "global": "Score global calculé à partir des 5 modules (network, contract, market, social, quantum).",
                    "network": "Sera basé sur la décentralisation et le risque 51%.",
                    "contract": "Sera basé sur l'analyse du smart contract.",
                    "market": "Sera basé sur la liquidité et la volatilité.",
                    "social": "Sera basé sur la gouvernance et la réputation.",
                    "quantum": "Sera basé sur la résistance aux futures attaques quantiques.",
                },
            }

        # --- Modules internes de scoring (à améliorer plus tard) ----------------

        def _score_network(snapshot: Optional[Dict[str, Any]]) -> float:
            return 70.0  # TODO: calcul réel

        def _score_contract(snapshot: Optional[Dict[str, Any]]) -> float:
            return 65.0  # TODO: calcul réel

        def _score_market(snapshot: Optional[Dict[str, Any]]) -> float:
            return 60.0  # TODO: calcul réel

        def _score_social(snapshot: Optional[Dict[str, Any]]) -> float:
            return 55.0  # TODO: calcul réel

        def _score_quantum(snapshot: Optional[Dict[str, Any]]) -> float:
            return 50.0  # TODO: calcul réel
        """
    )

    # 5. DataAggregator (récupération de données – vide pour l’instant)
    write_file(
        "app/services/data_aggregator.py",
        """
        from typing import Dict, Any

        class DataAggregator:
            \"\"\"Responsable de récupérer toutes les données nécessaires
            (on-chain, marché, contrat, social, etc.).
            Pour l'instant, renvoie un snapshot minimal.
            \"\"\"

            async def build_token_snapshot(self, chain: str, contract_address: str) -> Dict[str, Any]:
                # TODO: appeler ici les vraies APIs plus tard
                return {
                    "chain": chain,
                    "contract_address": contract_address,
                    "market": {},
                    "onchain": {},
                    "contract": {},
                    "social": {},
                }
        """
    )

    # 6. Placeholder IA (pour plus tard)
    write_file(
        "app/ai/ai_client.py",
        """
        \"\"\"Client IA pour HacherScan.
        Ici, plus tard, on pourra intégrer l'API OpenAI
        pour:
        - expliquer les scores
        - analyser des whitepapers
        - classer les risques
        - assister l'utilisateur.

        Pour l'instant, ce fichier est juste un placeholder dans l'architecture.
        \"\"\"

        class HacherScanAIClient:
            def __init__(self):
                # TODO: config IA plus tard (clé API, modèle, etc.)
                pass

            def explain_scores(self, scoring_result):
                \"\"\"Expliquer les scores de manière lisible.
                Version future IA.
                \"\"\"
                raise NotImplementedError("IA non encore intégrée.")
        """
    )

    # 7. requirements.txt (si tu ne l’as pas déjà)
    write_file(
        "requirements.txt",
        """
        fastapi
        uvicorn[standard]
        httpx
        pydantic
        """
    )

    print("\\nArchitecture de base HacherScan V2 créée / mise à jour.")

if __name__ == "__main__":
    main()
