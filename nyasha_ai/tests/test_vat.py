import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.currency_normalisation import normalise_to_reporting_currency
from rules.vat_rules import calculate_vat_summary


class TestVatRules(unittest.TestCase):
    def _df(self, rows):
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return normalise_to_reporting_currency(df, "USD").df

    def test_standard_rate_applied(self):
        df = self._df([
            dict(transaction_id="T1", date="2025-01-01", description="Sale", customer="A", supplier="",
                 transaction_type="income", category="Sales - Retail", amount=1000.0, currency="USD",
                 vat_status="standard"),
        ])
        vat = calculate_vat_summary(df)
        self.assertAlmostEqual(vat.output_vat, 150.0)  # 15% of 1000

    def test_zero_rated_and_exempt_produce_no_vat(self):
        df = self._df([
            dict(transaction_id="T1", date="2025-01-01", description="Sale", customer="A", supplier="",
                 transaction_type="income", category="Sales - Retail", amount=1000.0, currency="USD",
                 vat_status="zero_rated"),
            dict(transaction_id="T2", date="2025-01-02", description="Sale", customer="A", supplier="",
                 transaction_type="income", category="Sales - Retail", amount=500.0, currency="USD",
                 vat_status="exempt"),
        ])
        vat = calculate_vat_summary(df)
        self.assertEqual(vat.output_vat, 0.0)

    def test_missing_vat_status_flagged_not_dropped(self):
        df = self._df([
            dict(transaction_id="T1", date="2025-01-01", description="Sale", customer="A", supplier="",
                 transaction_type="income", category="Sales - Retail", amount=1000.0, currency="USD",
                 vat_status=""),
        ])
        vat = calculate_vat_summary(df)
        self.assertEqual(vat.transactions_missing_vat_status, 1)
        self.assertIn("T1", vat.transactions_flagged_for_review)

    def test_net_vat_payable_is_output_minus_input(self):
        df = self._df([
            dict(transaction_id="T1", date="2025-01-01", description="Sale", customer="A", supplier="",
                 transaction_type="income", category="Sales - Retail", amount=1000.0, currency="USD",
                 vat_status="standard"),
            dict(transaction_id="T2", date="2025-01-02", description="Purchase", customer="", supplier="Supp",
                 transaction_type="expense", category="Supplier Payments", amount=400.0, currency="USD",
                 vat_status="standard"),
        ])
        vat = calculate_vat_summary(df)
        self.assertAlmostEqual(vat.output_vat, 150.0)
        self.assertAlmostEqual(vat.input_vat, 60.0)
        self.assertAlmostEqual(vat.net_vat_payable, 90.0)


if __name__ == "__main__":
    unittest.main()
