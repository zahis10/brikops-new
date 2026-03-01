#!/usr/bin/env python3
"""
P0 Blocker: Financial Calculation Gate Tests

Rounding Policy:
- All currency values rounded to 2 decimal places
- Percentages applied before rounding
- Final totals calculated from rounded intermediates
"""

import unittest
from decimal import Decimal, ROUND_HALF_UP

class FinancialCalculator:
    """Financial calculation engine with deterministic rounding"""
    
    @staticmethod
    def round_currency(value: float) -> float:
        """Round to 2 decimal places using banker's rounding"""
        return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    
    @classmethod
    def calculate_report_totals(cls, findings_prices: list) -> dict:
        """Calculate all financial totals with proper rounding
        
        Args:
            findings_prices: List of finding prices
            
        Returns:
            Dictionary with all calculated totals
        """
        # Subtotal - sum of all findings
        subtotal = cls.round_currency(sum(findings_prices))
        
        # Contingency (optional, default 0%)
        contingency_pct = 0
        contingency_amt = cls.round_currency(subtotal * contingency_pct / 100)
        
        # Engineering supervision (10%)
        supervision_pct = 10
        supervision_amt = cls.round_currency(subtotal * supervision_pct / 100)
        
        # Before VAT
        before_vat = cls.round_currency(subtotal + contingency_amt + supervision_amt)
        
        # VAT (18%)
        vat_pct = 18
        vat_amt = cls.round_currency(before_vat * vat_pct / 100)
        
        # Grand total
        grand_total = cls.round_currency(before_vat + vat_amt)
        
        return {
            'subtotal': subtotal,
            'contingency_pct': contingency_pct,
            'contingency_amount': contingency_amt,
            'supervision_pct': supervision_pct,
            'supervision_amount': supervision_amt,
            'before_vat': before_vat,
            'vat_pct': vat_pct,
            'vat_amount': vat_amt,
            'grand_total': grand_total
        }

class TestFinancialCalculations(unittest.TestCase):
    """Test suite for financial calculation gate"""
    
    def setUp(self):
        self.calc = FinancialCalculator()
    
    def test_simple_calculation(self):
        """Test basic calculation with round numbers"""
        findings = [100.00, 200.00, 300.00]  # Total: 600
        result = self.calc.calculate_report_totals(findings)
        
        self.assertEqual(result['subtotal'], 600.00)
        self.assertEqual(result['supervision_amount'], 60.00)  # 10% of 600
        self.assertEqual(result['before_vat'], 660.00)  # 600 + 60
        self.assertEqual(result['vat_amount'], 118.80)  # 18% of 660
        self.assertEqual(result['grand_total'], 778.80)  # 660 + 118.80
    
    def test_decimal_rounding(self):
        """Test rounding with decimal values"""
        findings = [123.45, 678.90, 234.56]  # Total: 1036.91
        result = self.calc.calculate_report_totals(findings)
        
        self.assertEqual(result['subtotal'], 1036.91)
        self.assertEqual(result['supervision_amount'], 103.69)  # 10% rounded
        self.assertEqual(result['before_vat'], 1140.60)  # 1036.91 + 103.69
        self.assertEqual(result['vat_amount'], 205.31)  # 18% of 1140.60 rounded
        self.assertEqual(result['grand_total'], 1345.91)  # 1140.60 + 205.31
    
    def test_single_finding(self):
        """Test calculation with single finding"""
        findings = [500.00]
        result = self.calc.calculate_report_totals(findings)
        
        self.assertEqual(result['subtotal'], 500.00)
        self.assertEqual(result['supervision_amount'], 50.00)
        self.assertEqual(result['before_vat'], 550.00)
        self.assertEqual(result['vat_amount'], 99.00)
        self.assertEqual(result['grand_total'], 649.00)
    
    def test_many_findings(self):
        """Test calculation with many findings"""
        findings = [100.00] * 50  # 50 findings of 100 each = 5000
        result = self.calc.calculate_report_totals(findings)
        
        self.assertEqual(result['subtotal'], 5000.00)
        self.assertEqual(result['supervision_amount'], 500.00)
        self.assertEqual(result['before_vat'], 5500.00)
        self.assertEqual(result['vat_amount'], 990.00)
        self.assertEqual(result['grand_total'], 6490.00)
    
    def test_edge_case_pennies(self):
        """Test rounding with values that produce pennies"""
        findings = [33.33, 33.33, 33.34]  # Total: 100.00
        result = self.calc.calculate_report_totals(findings)
        
        self.assertEqual(result['subtotal'], 100.00)
        self.assertEqual(result['supervision_amount'], 10.00)
        self.assertEqual(result['before_vat'], 110.00)
        self.assertEqual(result['vat_amount'], 19.80)
        self.assertEqual(result['grand_total'], 129.80)
    
    def test_zero_findings(self):
        """Test calculation with no findings"""
        findings = []
        result = self.calc.calculate_report_totals(findings)
        
        self.assertEqual(result['subtotal'], 0.00)
        self.assertEqual(result['supervision_amount'], 0.00)
        self.assertEqual(result['before_vat'], 0.00)
        self.assertEqual(result['vat_amount'], 0.00)
        self.assertEqual(result['grand_total'], 0.00)
    
    def test_formula_chain_integrity(self):
        """Verify complete formula chain"""
        findings = [456.78, 123.45, 789.01]
        result = self.calc.calculate_report_totals(findings)
        
        # Verify chain: subtotal → +supervision → before_vat → +vat → grand_total
        expected_subtotal = sum(findings)
        self.assertAlmostEqual(result['subtotal'], expected_subtotal, places=2)
        
        expected_supervision = expected_subtotal * 0.10
        self.assertAlmostEqual(result['supervision_amount'], expected_supervision, places=2)
        
        expected_before_vat = result['subtotal'] + result['supervision_amount']
        self.assertAlmostEqual(result['before_vat'], expected_before_vat, places=2)
        
        expected_vat = result['before_vat'] * 0.18
        self.assertAlmostEqual(result['vat_amount'], expected_vat, places=2)
        
        expected_total = result['before_vat'] + result['vat_amount']
        self.assertAlmostEqual(result['grand_total'], expected_total, places=2)

if __name__ == '__main__':
    print("="*60)
    print("Financial Calculation Gate Tests")
    print("="*60)
    print()
    
    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestFinancialCalculations)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("="*60)
    if result.wasSuccessful():
        print("✓ All Financial Tests PASSED")
    else:
        print("✗ Some Financial Tests FAILED")
    print("="*60)