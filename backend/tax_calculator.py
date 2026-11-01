"""
Tax Savings Calculator for S-Corporation vs. Sole Proprietor/LLC

This module calculates estimated federal self-employment tax savings when converting
from a sole proprietor or single-member LLC to an S-corporation.

IMPORTANT: This calculator provides estimates only and does not constitute tax advice.
Results should be reviewed by a qualified tax professional before implementation.

Assumptions and Formulas:
- Federal self-employment (SE) tax rate: 15.3% (12.4% Social Security + 2.9% Medicare)
- Only 92.35% of net profit is subject to SE tax (after deducting SE tax itself)
- S-Corp strategy: Pay reasonable W-2 salary, distribute remainder as dividends (not subject to SE tax)
- S-Corp annual costs: ~$2,500-4,000 (formation, accounting, payroll processing, state filing)
- Payroll provider fee: ~$500-800/year if not already using one
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class EntityType(str, Enum):
    SOLE_PROPRIETOR = "sole_proprietor"
    LLC = "llc"
    S_CORP = "s_corp"
    OTHER = "other"


@dataclass
class TaxSavingsResult:
    """Result of S-Corp tax savings estimation."""
    annual_net_profit: float
    current_entity_type: EntityType
    state: str

    # Calculated values
    current_se_tax_annual: float
    recommended_w2_salary: float
    estimated_se_tax_with_scorp: float
    gross_tax_savings: float
    estimated_annual_costs: float
    net_annual_savings: float
    net_annual_savings_min: float
    net_annual_savings_max: float

    # Assumptions for transparency
    assumptions: dict

    def to_dict(self):
        return {
            "annual_net_profit": self.annual_net_profit,
            "current_entity_type": self.current_entity_type.value,
            "state": self.state,
            "current_se_tax_annual": round(self.current_se_tax_annual, 2),
            "recommended_w2_salary": round(self.recommended_w2_salary, 2),
            "estimated_se_tax_with_scorp": round(self.estimated_se_tax_with_scorp, 2),
            "gross_tax_savings": round(self.gross_tax_savings, 2),
            "estimated_annual_costs": round(self.estimated_annual_costs, 2),
            "net_annual_savings": round(self.net_annual_savings, 2),
            "net_annual_savings_min": round(self.net_annual_savings_min, 2),
            "net_annual_savings_max": round(self.net_annual_savings_max, 2),
            "assumptions": self.assumptions,
        }


class TaxCalculator:
    """
    Calculates estimated tax savings for S-Corp conversion.

    Key assumptions documented for CPA review:
    - Federal SE tax: 15.3% on 92.35% of net profit for sole prop/LLC
    - S-Corp must pay "reasonable salary" in W-2 wages
    - Reasonable salary: typically 50-60% of net profit (conservative: 60%)
    - S-Corp costs: accounting, payroll, state filing, setup (~$3,000/year)
    """

    # Federal self-employment tax rates (2024)
    SOCIAL_SECURITY_RATE = 0.124  # 12.4% on first $168,600
    MEDICARE_RATE = 0.029  # 2.9% on all income
    SE_TAX_RATE = SOCIAL_SECURITY_RATE + MEDICARE_RATE  # 15.3%

    # Only a portion of net profit is subject to SE tax (after SE tax deduction)
    SE_TAX_BASE_PERCENT = 0.9235  # Approximation for SE tax deduction

    # S-Corp must pay reasonable salary (IRS requirement)
    # Conservative estimate: 60% of net profit
    REASONABLE_SALARY_PERCENT_LOW = 0.50
    REASONABLE_SALARY_PERCENT_MID = 0.60
    REASONABLE_SALARY_PERCENT_HIGH = 0.70

    # Annual S-Corp costs (conservative estimates)
    SCORP_SETUP_COST = 500  # One-time, but amortized
    SCORP_ANNUAL_FILING_COST = 300  # Annual state/federal filing
    SCORP_ACCOUNTING_COST = 1500  # Additional accounting complexity
    SCORP_PAYROLL_COST = 600  # Payroll service fees (only if not already using payroll)

    TOTAL_SCORP_ANNUAL_COST_BASE = (
        SCORP_ANNUAL_FILING_COST + SCORP_ACCOUNTING_COST
    )

    @staticmethod
    def calculate_sole_prop_se_tax(annual_net_profit: float) -> float:
        """
        Calculate self-employment tax for sole proprietor or single-member LLC.

        Formula: (net_profit * 0.9235) * 0.153
        The 0.9235 factor accounts for the deductibility of SE tax.
        """
        se_tax_base = annual_net_profit * TaxCalculator.SE_TAX_BASE_PERCENT
        return se_tax_base * TaxCalculator.SE_TAX_RATE

    @staticmethod
    def calculate_scorp_se_tax(w2_salary: float) -> float:
        """
        Calculate self-employment tax for S-Corporation.

        Only W-2 wages are subject to SE tax. Dividend distributions are not.
        Formula: (w2_salary * 0.9235) * 0.153
        """
        se_tax_base = w2_salary * TaxCalculator.SE_TAX_BASE_PERCENT
        return se_tax_base * TaxCalculator.SE_TAX_RATE

    @staticmethod
    def estimate_reasonable_salary(
        annual_net_profit: float,
        salary_percent: float = REASONABLE_SALARY_PERCENT_MID
    ) -> float:
        """
        Estimate reasonable W-2 salary for S-Corp.

        IRS requires "reasonable compensation" - typically interpreted as
        a percentage of net profit sufficient to justify the income.

        Conservative estimate: 60% of net profit.
        Range: 50-70% depending on industry and justification.
        """
        return annual_net_profit * salary_percent

    @staticmethod
    def calculate_breakeven_profit(
        pays_payroll_provider: bool = False
    ) -> float:
        """
        Calculate minimum annual net profit where S-Corp becomes worthwhile.

        S-Corp setup and annual costs generally only make sense above $50k-$60k profit.
        """
        total_cost = TaxCalculator.TOTAL_SCORP_ANNUAL_COST_BASE
        if not pays_payroll_provider:
            total_cost += TaxCalculator.SCORP_PAYROLL_COST

        # Rough rule: need to save at least 15.3% * profit difference to cover costs
        # Total cost / 0.153 / (1 - 0.60) = cost / 0.153 / 0.40
        breakeven = total_cost / (TaxCalculator.SE_TAX_RATE * 0.40)
        return breakeven

    @staticmethod
    def estimate_savings(
        annual_net_profit: float,
        current_entity_type: str,
        state: str,
        pays_payroll_provider: bool = False,
        reasonable_salary_percent: float = REASONABLE_SALARY_PERCENT_MID
    ) -> TaxSavingsResult:
        """
        Estimate annual tax savings from S-Corp conversion.

        Args:
            annual_net_profit: Annual business net profit
            current_entity_type: "sole_proprietor", "llc", etc.
            state: US state (for future state-specific tax calculations)
            pays_payroll_provider: True if already using payroll service
            reasonable_salary_percent: % of net profit to use as W-2 salary (0.50-0.70)

        Returns:
            TaxSavingsResult with detailed breakdown
        """
        # Validate input
        if annual_net_profit < 0:
            raise ValueError("Annual net profit cannot be negative")

        entity = EntityType(current_entity_type) if current_entity_type in [e.value for e in EntityType] else EntityType.OTHER

        # Only makes sense for sole prop or LLC
        if entity not in [EntityType.SOLE_PROPRIETOR, EntityType.LLC]:
            return TaxSavingsResult(
                annual_net_profit=annual_net_profit,
                current_entity_type=entity,
                state=state,
                current_se_tax_annual=0,
                recommended_w2_salary=0,
                estimated_se_tax_with_scorp=0,
                gross_tax_savings=0,
                estimated_annual_costs=0,
                net_annual_savings=0,
                net_annual_savings_min=0,
                net_annual_savings_max=0,
                assumptions={
                    "eligible_for_scorp_conversion": False,
                    "reason": f"S-Corp conversion not applicable for {entity.value}"
                }
            )

        # Calculate current SE tax (sole prop/LLC)
        current_se_tax = TaxCalculator.calculate_sole_prop_se_tax(annual_net_profit)

        # Estimate reasonable W-2 salary
        recommended_salary = TaxCalculator.estimate_reasonable_salary(
            annual_net_profit,
            reasonable_salary_percent
        )

        # Calculate S-Corp SE tax
        scorp_se_tax = TaxCalculator.calculate_scorp_se_tax(recommended_salary)

        # Gross tax savings (federal SE tax only)
        gross_savings = current_se_tax - scorp_se_tax

        # S-Corp annual costs
        total_costs = TaxCalculator.TOTAL_SCORP_ANNUAL_COST_BASE
        if not pays_payroll_provider:
            total_costs += TaxCalculator.SCORP_PAYROLL_COST

        # Net savings (accounting for costs)
        net_savings = gross_savings - total_costs

        # Calculate range (using low and high salary percents)
        salary_low = TaxCalculator.estimate_reasonable_salary(
            annual_net_profit,
            TaxCalculator.REASONABLE_SALARY_PERCENT_LOW
        )
        salary_high = TaxCalculator.estimate_reasonable_salary(
            annual_net_profit,
            TaxCalculator.REASONABLE_SALARY_PERCENT_HIGH
        )

        se_tax_low = TaxCalculator.calculate_scorp_se_tax(salary_low)
        se_tax_high = TaxCalculator.calculate_scorp_se_tax(salary_high)

        # Lower salary = higher savings; higher salary = lower savings
        net_savings_max = (current_se_tax - se_tax_low) - total_costs
        net_savings_min = (current_se_tax - se_tax_high) - total_costs

        assumptions = {
            "federal_se_tax_rate": TaxCalculator.SE_TAX_RATE,
            "se_tax_base_percent": TaxCalculator.SE_TAX_BASE_PERCENT,
            "reasonable_salary_percent": reasonable_salary_percent,
            "reasonable_salary_range": {
                "low_percent": TaxCalculator.REASONABLE_SALARY_PERCENT_LOW,
                "mid_percent": TaxCalculator.REASONABLE_SALARY_PERCENT_MID,
                "high_percent": TaxCalculator.REASONABLE_SALARY_PERCENT_HIGH,
            },
            "annual_scorp_costs": {
                "annual_filing": TaxCalculator.SCORP_ANNUAL_FILING_COST,
                "accounting": TaxCalculator.SCORP_ACCOUNTING_COST,
                "payroll": TaxCalculator.SCORP_PAYROLL_COST if not pays_payroll_provider else 0,
                "total": total_costs,
            },
            "notes": [
                "This calculation includes federal SE tax only (not state or income tax)",
                "S-Corp must pay 'reasonable salary' as W-2 wages (IRS requirement)",
                "Does not include state-specific tax benefits or costs",
                "Does not factor in any 20% QBI deduction or other special considerations",
                "Payroll complexity and quarterly filing requirements apply",
                "Consult a CPA before implementing S-Corp election",
            ],
            "eligible_for_scorp_conversion": True,
        }

        return TaxSavingsResult(
            annual_net_profit=annual_net_profit,
            current_entity_type=entity,
            state=state,
            current_se_tax_annual=current_se_tax,
            recommended_w2_salary=recommended_salary,
            estimated_se_tax_with_scorp=scorp_se_tax,
            gross_tax_savings=gross_savings,
            estimated_annual_costs=total_costs,
            net_annual_savings=net_savings,
            net_annual_savings_min=net_savings_min,
            net_annual_savings_max=net_savings_max,
            assumptions=assumptions,
        )
