import unittest

from app.scoring import compute_risk_score


class TestContractScoring(unittest.TestCase):
    def test_honeypot_gives_very_low_score(self):
        """Un token marqué honeypot doit avoir un score de contrat ≈ 5."""
        snapshot = {
            "contract": {
                "is_honeypot": True
            }
        }

        result = compute_risk_score(
            chain="ethereum",
            contract_address="0xHONEY",
            snapshot=snapshot,
        )
        contract_score = result["scores"]["contract"]

        self.assertEqual(contract_score, 5.0)

    def test_owner_renounced_improves_contract_score(self):
        """Un owner renounced doit donner un meilleur score que owner actif."""
        base_snapshot = {
            "contract": {
                "owner_renounced": False,
                "is_proxy": False,
                "functions": ["transfer", "approve"],
                "tax_buy": 5,
                "tax_sell": 5,
                "is_honeypot": False,
            }
        }

        renounced_snapshot = {
            "contract": {
                "owner_renounced": True,
                "is_proxy": False,
                "functions": ["transfer", "approve"],
                "tax_buy": 5,
                "tax_sell": 5,
                "is_honeypot": False,
            }
        }

        result_not_renounced = compute_risk_score(
            chain="ethereum",
            contract_address="0xOWNER1",
            snapshot=base_snapshot,
        )
        result_renounced = compute_risk_score(
            chain="ethereum",
            contract_address="0xOWNER2",
            snapshot=renounced_snapshot,
        )

        score_not_renounced = result_not_renounced["scores"]["contract"]
        score_renounced = result_renounced["scores"]["contract"]

        self.assertGreater(score_renounced, score_not_renounced)

    def test_high_taxes_reduce_contract_score(self):
        """Des taxes très élevées doivent baisser le score du contrat."""
        low_tax_snapshot = {
            "contract": {
                "owner_renounced": False,
                "is_proxy": False,
                "functions": ["transfer", "approve"],
                "tax_buy": 3,
                "tax_sell": 3,
                "is_honeypot": False,
            }
        }

        high_tax_snapshot = {
            "contract": {
                "owner_renounced": False,
                "is_proxy": False,
                "functions": ["transfer", "approve"],
                "tax_buy": 25,
                "tax_sell": 25,
                "is_honeypot": False,
            }
        }

        result_low = compute_risk_score(
            chain="ethereum",
            contract_address="0xLOWTAX",
            snapshot=low_tax_snapshot,
        )
        result_high = compute_risk_score(
            chain="ethereum",
            contract_address="0xHIGHTAX",
            snapshot=high_tax_snapshot,
        )

        score_low = result_low["scores"]["contract"]
        score_high = result_high["scores"]["contract"]

        self.assertGreater(score_low, score_high)


class TestMarketScoring(unittest.TestCase):
    def test_low_liquidity_has_lower_market_score(self):
        """Une faible liquidité doit donner un plus mauvais score market qu'une forte."""
        high_liq_snapshot = {
            "market": {
                "liquidity_usd": 200_000,
                "volume_24h_usd": 500_000,
                "volatility_7d": 0.3,
                "slippage_impact_1000usd": 2.0,
                "volume_distribution": {"dex_1": 40, "dex_2": 35, "dex_3": 25},
            }
        }

        low_liq_snapshot = {
            "market": {
                "liquidity_usd": 2_000,
                "volume_24h_usd": 10_000,
                "volatility_7d": 0.3,
                "slippage_impact_1000usd": 8.0,
                "volume_distribution": {"dex_1": 90, "dex_2": 10},
            }
        }

        result_high = compute_risk_score(
            chain="ethereum",
            contract_address="0xHIGHLIQ",
            snapshot=high_liq_snapshot,
        )
        result_low = compute_risk_score(
            chain="ethereum",
            contract_address="0xLOWLIQ",
            snapshot=low_liq_snapshot,
        )

        score_high = result_high["scores"]["market"]
        score_low = result_low["scores"]["market"]

        self.assertGreater(score_high, score_low)
class TestHoldersScoring(unittest.TestCase):
    def test_high_concentration_gives_lower_holders_score(self):
        """Une forte concentration top10 doit donner un plus mauvais score holders."""
        diversified_snapshot = {
            "holders": {
                "total_holders": 5000,
                "top10_share": 0.20,      # 20%
                "dead_wallet_share": 0.05
            }
        }

        concentrated_snapshot = {
            "holders": {
                "total_holders": 5000,
                "top10_share": 0.85,      # 85%
                "dead_wallet_share": 0.05
            }
        }

        result_div = compute_risk_score(
            chain="ethereum",
            contract_address="0xDIVERS",
            snapshot=diversified_snapshot,
        )
        result_conc = compute_risk_score(
            chain="ethereum",
            contract_address="0xWHALES",
            snapshot=concentrated_snapshot,
        )

        score_div = result_div["scores"]["holders"]
        score_conc = result_conc["scores"]["holders"]

        self.assertGreater(score_div, score_conc)


if __name__ == "__main__":
    unittest.main()
