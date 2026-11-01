"""
Unit tests for tax_calculator.py

Tests verify the tax formulas, reasonable salary calculations, and savings estimates.
"""

import pytest
from tax_calculator import (
    TaxCalculator,
    EntityType,
    TaxSavingsResult,
)


class TestSECalculations:
    """Test self-employment tax calculations."""

    def test_sole_prop_se_tax_calculation(self):
        """Test SE tax calculation for sole proprietor."""
        # For $100,000 net profit:
        # SE tax = $100,000 * 0.9235 * 0.153 = $14,129.55
        profit = 100_000
        se_tax = TaxCalculator.calculate_sole_prop_se_tax(profit)

        expected = 100_000 * 0.9235 * 0.153
        assert abs(se_tax - expected) < 0.01
        assert se_tax == pytest.approx(14_129.55, abs=0.01)

    def test_sole_prop_se_tax_zero_profit(self):
        """Test SE tax for zero profit."""
        assert TaxCalculator.calculate_sole_prop_se_tax(0) == 0

    def test_scorp_se_tax_calculation(self):
        """Test SE tax calculation for S-Corp (W-2 wages only)."""
        # For $60,000 W-2 salary (from $100k profit):
        # SE tax = $60,000 * 0.9235 * 0.153 = $8,477.73
        salary = 60_000
        se_tax = TaxCalculator.calculate_scorp_se_tax(salary)

        expected = 60_000 * 0.9235 * 0.153
        assert abs(se_tax - expected) < 0.01
        assert se_tax == pytest.approx(8_477.73, abs=0.01)

    def test_se_tax_difference(self):
        """Test that S-Corp reduces SE tax vs. sole prop."""
        profit = 100_000
        sole_prop_tax = TaxCalculator.calculate_sole_prop_se_tax(profit)

        # With S-Corp at 60% salary
        salary = profit * 0.60
        scorp_tax = TaxCalculator.calculate_scorp_se_tax(salary)

        # Should be significant savings
        savings = sole_prop_tax - scorp_tax
        assert savings > 0
        assert savings > 3_000  # Should save more than $3k on $100k profit


class TestReasonableSalary:
    """Test reasonable salary calculations."""

    def test_salary_at_60_percent(self):
        """Test default 60% salary calculation."""
        profit = 100_000
        salary = TaxCalculator.estimate_reasonable_salary(profit)

        assert salary == pytest.approx(60_000)

    def test_salary_custom_percent(self):
        """Test salary at custom percentage."""
        profit = 100_000
        salary_low = TaxCalculator.estimate_reasonable_salary(profit, 0.50)
        salary_high = TaxCalculator.estimate_reasonable_salary(profit, 0.70)

        assert salary_low == pytest.approx(50_000)
        assert salary_high == pytest.approx(70_000)

    def test_salary_range(self):
        """Test salary range for different profit levels."""
        for profit in [50_000, 100_000, 200_000, 500_000]:
            salary_50 = TaxCalculator.estimate_reasonable_salary(profit, 0.50)
            salary_60 = TaxCalculator.estimate_reasonable_salary(profit, 0.60)
            salary_70 = TaxCalculator.estimate_reasonable_salary(profit, 0.70)

            assert salary_50 == profit * 0.50
            assert salary_60 == profit * 0.60
            assert salary_70 == profit * 0.70
            assert salary_50 < salary_60 < salary_70


class TestBreakevenCalculation:
    """Test S-Corp breakeven point."""

    def test_breakeven_without_existing_payroll(self):
        """Test breakeven when not using payroll provider."""
        breakeven = TaxCalculator.calculate_breakeven_profit(pays_payroll_provider=False)

        # Should be positive and reasonable
        assert breakeven > 0
        assert breakeven < 200_000  # Should be reasonable number
        assert breakeven > 10_000  # Should be at least $10k

    def test_breakeven_with_existing_payroll(self):
        """Test breakeven when already using payroll provider."""
        breakeven_with = TaxCalculator.calculate_breakeven_profit(pays_payroll_provider=True)
        breakeven_without = TaxCalculator.calculate_breakeven_profit(pays_payroll_provider=False)

        # Should be lower when already using payroll (no extra payroll cost)
        assert breakeven_with <= breakeven_without


class TestSavingsEstimation:
    """Test full savings calculation."""

    def test_savings_sole_proprietor_100k_profit(self):
        """Test savings calculation for $100k sole proprietor."""
        result = TaxCalculator.estimate_savings(
            annual_net_profit=100_000,
            current_entity_type="sole_proprietor",
            state="CA",
            pays_payroll_provider=False
        )

        # Verify structure
        assert isinstance(result, TaxSavingsResult)
        assert result.annual_net_profit == 100_000
        assert result.current_entity_type == EntityType.SOLE_PROPRIETOR

        # Current SE tax should be ~$14,130
        assert result.current_se_tax_annual == pytest.approx(14_129.55, abs=1)

        # Recommended salary should be $60k
        assert result.recommended_w2_salary == pytest.approx(60_000)

        # S-Corp SE tax should be ~$8,478
        assert result.estimated_se_tax_with_scorp == pytest.approx(8_477.73, abs=1)

        # Gross savings should be ~$5,652
        assert result.gross_tax_savings == pytest.approx(5_651.82, abs=1)

        # Net savings after costs should be positive
        assert result.net_annual_savings > 0
        assert result.net_annual_savings < result.gross_tax_savings

    def test_savings_range(self):
        """Test that savings range is correct."""
        result = TaxCalculator.estimate_savings(
            annual_net_profit=100_000,
            current_entity_type="sole_proprietor",
            state="CA"
        )

        # Lower salary percent = higher savings; higher salary percent = lower savings
        # So max is with low salary percent (50%), min is with high salary percent (70%)
        assert result.net_annual_savings_max > result.net_annual_savings_min

        # Both should bracket the mid estimate
        assert result.net_annual_savings_min < result.net_annual_savings <= result.net_annual_savings_max

    def test_savings_llc(self):
        """Test that LLC is treated same as sole proprietor."""
        result_sole = TaxCalculator.estimate_savings(
            annual_net_profit=100_000,
            current_entity_type="sole_proprietor",
            state="CA"
        )

        result_llc = TaxCalculator.estimate_savings(
            annual_net_profit=100_000,
            current_entity_type="llc",
            state="CA"
        )

        # Should have identical savings calculations
        assert result_sole.current_se_tax_annual == result_llc.current_se_tax_annual
        assert result_sole.net_annual_savings == result_llc.net_annual_savings

    def test_savings_already_scorp(self):
        """Test that already S-Corp returns zero savings."""
        result = TaxCalculator.estimate_savings(
            annual_net_profit=100_000,
            current_entity_type="s_corp",
            state="CA"
        )

        # Should indicate not eligible
        assert result.net_annual_savings == 0
        assert not result.assumptions["eligible_for_scorp_conversion"]

    def test_savings_low_profit(self):
        """Test savings at low profit level."""
        result = TaxCalculator.estimate_savings(
            annual_net_profit=30_000,
            current_entity_type="sole_proprietor",
            state="CA"
        )

        # Current SE tax should be ~$4,239
        assert result.current_se_tax_annual == pytest.approx(4_238.87, abs=1)

        # Recommended salary should be $18k
        assert result.recommended_w2_salary == pytest.approx(18_000)

        # Net savings might be negative or small (not worth it at low profit)
        # This is important - S-Corp not always beneficial
        gross = result.gross_tax_savings
        costs = result.estimated_annual_costs
        assert result.net_annual_savings == pytest.approx(gross - costs, abs=0.01)

    def test_savings_high_profit(self):
        """Test savings at high profit level."""
        result = TaxCalculator.estimate_savings(
            annual_net_profit=500_000,
            current_entity_type="sole_proprietor",
            state="CA"
        )

        # At high profit, S-Corp should be very worthwhile
        assert result.net_annual_savings > 20_000

        # Savings should increase with profit
        result_low = TaxCalculator.estimate_savings(
            annual_net_profit=100_000,
            current_entity_type="sole_proprietor",
            state="CA"
        )

        assert result.net_annual_savings > result_low.net_annual_savings

    def test_negative_profit_raises_error(self):
        """Test that negative profit raises error."""
        with pytest.raises(ValueError):
            TaxCalculator.estimate_savings(
                annual_net_profit=-100_000,
                current_entity_type="sole_proprietor",
                state="CA"
            )

    def test_result_to_dict(self):
        """Test serialization to dict."""
        result = TaxCalculator.estimate_savings(
            annual_net_profit=100_000,
            current_entity_type="sole_proprietor",
            state="CA"
        )

        result_dict = result.to_dict()

        # Should be serializable
        assert isinstance(result_dict, dict)
        assert result_dict["annual_net_profit"] == 100_000
        assert result_dict["current_entity_type"] == "sole_proprietor"
        assert result_dict["state"] == "CA"

        # All values should be rounded
        assert isinstance(result_dict["current_se_tax_annual"], float)
        assert isinstance(result_dict["net_annual_savings"], float)

    def test_payroll_cost_savings(self):
        """Test that payroll provider flag affects costs."""
        result_no_payroll = TaxCalculator.estimate_savings(
            annual_net_profit=100_000,
            current_entity_type="sole_proprietor",
            state="CA",
            pays_payroll_provider=False
        )

        result_with_payroll = TaxCalculator.estimate_savings(
            annual_net_profit=100_000,
            current_entity_type="sole_proprietor",
            state="CA",
            pays_payroll_provider=True
        )

        # No payroll should have higher costs
        assert result_no_payroll.estimated_annual_costs >= result_with_payroll.estimated_annual_costs

        # With payroll should have better net savings
        assert result_with_payroll.net_annual_savings > result_no_payroll.net_annual_savings


class TestAssumptions:
    """Test that assumptions are clearly documented."""

    def test_assumptions_included(self):
        """Test that all key assumptions are in result."""
        result = TaxCalculator.estimate_savings(
            annual_net_profit=100_000,
            current_entity_type="sole_proprietor",
            state="CA"
        )

        assumptions = result.assumptions

        # Check key assumptions are present
        assert "federal_se_tax_rate" in assumptions
        assert "se_tax_base_percent" in assumptions
        assert "reasonable_salary_percent" in assumptions
        assert "annual_scorp_costs" in assumptions
        assert "notes" in assumptions
        assert "eligible_for_scorp_conversion" in assumptions

        # Verify values
        assert assumptions["federal_se_tax_rate"] == 0.153
        assert assumptions["se_tax_base_percent"] == 0.9235
        assert isinstance(assumptions["notes"], list)
        assert len(assumptions["notes"]) > 0

    def test_assumptions_breakdown(self):
        """Test that cost breakdown is available."""
        result = TaxCalculator.estimate_savings(
            annual_net_profit=100_000,
            current_entity_type="sole_proprietor",
            state="CA"
        )

        costs = result.assumptions["annual_scorp_costs"]

        assert "annual_filing" in costs
        assert "accounting" in costs
        assert "payroll" in costs
        assert "total" in costs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
