"""
Tax calculation and form generation engine.

This module is intentionally dependency-free (no database imports) so the
calculations can be unit tested and reused by background jobs. It implements
simplified federal/state rules for planning estimates, not official IRS
calculations. Every response includes assumptions and disclaimers.

Supported features:
- Progressive federal income tax brackets (2024-2026)
- Self-employment / FICA tax with wage base and additional Medicare
- Standard deduction, QBI deduction (simplified), child/other credits input
- Entity comparison: sole proprietor, LLC, S-Corp, C-Corp, partnership
- Schedule C / E / SE, 1040, 1040-NR, 8832, Schedule D form payloads
- Quarterly estimated taxes (1040-ES)
- Capital gains what-if analysis
- Retirement contribution limit comparison
- State income tax estimates
- Audit documentation coverage scoring
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

DISCLAIMER = (
    "Estimates only. This platform does not provide tax, legal, or accounting advice. "
    "Confirm all figures with a qualified tax professional before filing."
)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

FILING_STATUS_LABELS = {
    "single": "Single",
    "married_filing_jointly": "Married Filing Jointly",
    "married_filing_separately": "Married Filing Separately",
    "head_of_household": "Head of Household",
    "qualifying_surviving_spouse": "Qualifying Surviving Spouse",
}

# (upper_bound, rate). The final bracket uses None as the upper bound.
BRACKETS: Dict[int, Dict[str, List[tuple]]] = {
    2024: {
        "single": [(11600, .10), (47150, .12), (100525, .22), (191950, .24), (243725, .32), (609350, .35), (None, .37)],
        "married_filing_jointly": [(23200, .10), (94300, .12), (201050, .22), (383900, .24), (487450, .32), (731200, .35), (None, .37)],
        "married_filing_separately": [(11600, .10), (47150, .12), (100525, .22), (191950, .24), (243725, .32), (365600, .35), (None, .37)],
        "head_of_household": [(16550, .10), (63100, .12), (100500, .22), (191950, .24), (243700, .32), (609350, .35), (None, .37)],
        "qualifying_surviving_spouse": [(23200, .10), (94300, .12), (201050, .22), (383900, .24), (487450, .32), (731200, .35), (None, .37)],
    },
    2025: {
        "single": [(11925, .10), (48475, .12), (103350, .22), (197300, .24), (250525, .32), (626350, .35), (None, .37)],
        "married_filing_jointly": [(23850, .10), (96950, .12), (206700, .22), (394600, .24), (501050, .32), (751600, .35), (None, .37)],
        "married_filing_separately": [(11925, .10), (48475, .12), (103350, .22), (197300, .24), (250525, .32), (375800, .35), (None, .37)],
        "head_of_household": [(17000, .10), (64850, .12), (103350, .22), (197300, .24), (250500, .32), (626350, .35), (None, .37)],
        "qualifying_surviving_spouse": [(23850, .10), (96950, .12), (206700, .22), (394600, .24), (501050, .32), (751600, .35), (None, .37)],
    },
    2026: {
        "single": [(12225, .10), (49700, .12), (105950, .22), (202250, .24), (256800, .32), (642000, .35), (None, .37)],
        "married_filing_jointly": [(24450, .10), (99400, .12), (211850, .22), (404500, .24), (513600, .32), (770400, .35), (None, .37)],
        "married_filing_separately": [(12225, .10), (49700, .12), (105950, .22), (202250, .24), (256800, .32), (385200, .35), (None, .37)],
        "head_of_household": [(17425, .10), (66475, .12), (105950, .22), (202250, .24), (256800, .32), (642000, .35), (None, .37)],
        "qualifying_surviving_spouse": [(24450, .10), (99400, .12), (211850, .22), (404500, .24), (513600, .32), (770400, .35), (None, .37)],
    },
}

STANDARD_DEDUCTION: Dict[int, Dict[str, float]] = {
    2024: {"single": 14600, "married_filing_jointly": 29200, "married_filing_separately": 14600, "head_of_household": 21900, "qualifying_surviving_spouse": 29200},
    2025: {"single": 15000, "married_filing_jointly": 30000, "married_filing_separately": 15000, "head_of_household": 22500, "qualifying_surviving_spouse": 30000},
    2026: {"single": 15400, "married_filing_jointly": 30800, "married_filing_separately": 15400, "head_of_household": 23100, "qualifying_surviving_spouse": 30800},
}

SS_WAGE_BASE = {2024: 168600, 2025: 176100, 2026: 184500}
SOCIAL_SECURITY_RATE = 0.124
MEDICARE_RATE = 0.029
ADDITIONAL_MEDICARE_RATE = 0.009
SE_TAX_BASE_PERCENT = 0.9235

# Simplified top marginal state rates used for planning estimates.
STATE_RATES = {
    "AL": .05, "AK": .00, "AZ": .025, "AR": .044, "CA": .093, "CO": .044,
    "CT": .0699, "DE": .066, "DC": .1075, "FL": .00, "GA": .0539, "HI": .11,
    "ID": .058, "IL": .0495, "IN": .0305, "IA": .038, "KS": .0558, "KY": .04,
    "LA": .03, "ME": .0715, "MD": .0575, "MA": .05, "MI": .0425, "MN": .0985,
    "MS": .044, "MO": .048, "MT": .059, "NE": .052, "NV": .00, "NH": .00,
    "NJ": .1075, "NM": .059, "NY": .109, "NC": .045, "ND": .025, "OH": .035,
    "OK": .0475, "OR": .099, "PA": .0307, "RI": .0599, "SC": .062, "SD": .00,
    "TN": .00, "TX": .00, "UT": .0455, "VT": .0875, "VA": .0575, "WA": .00,
    "WV": .0482, "WI": .0765, "WY": .00,
}

QUARTER_DUE_DATES = {
    "q1": (4, 15),
    "q2": (6, 15),
    "q3": (9, 15),
    "q4": (1, 15),  # following year
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _year_context(tax_year: int) -> int:
    """Return the closest supported year so unknown future years still work."""
    if tax_year in BRACKETS:
        return tax_year
    return max(BRACKETS)


def _brackets(filing_status: str, tax_year: int) -> List[tuple]:
    year = _year_context(tax_year)
    return BRACKETS[year].get(filing_status, BRACKETS[year]["single"])


def standard_deduction(filing_status: str, tax_year: int) -> float:
    year = _year_context(tax_year)
    return STANDARD_DEDUCTION[year].get(filing_status, STANDARD_DEDUCTION[year]["single"])


def marginal_rate(taxable_income: float, filing_status: str, tax_year: int) -> float:
    """Return the marginal bracket rate for a taxable income level."""
    if taxable_income <= 0:
        return 0.0
    rate = 0.0
    lower = 0.0
    for upper, bracket_rate in _brackets(filing_status, tax_year):
        if upper is None or taxable_income <= upper:
            rate = bracket_rate
            break
        lower = upper
    return rate


def federal_income_tax(taxable_income: float, filing_status: str, tax_year: int) -> Dict[str, Any]:
    """Progressive federal income tax with per-bracket breakdown."""
    taxable = max(0.0, float(taxable_income or 0))
    lower = 0.0
    tax = 0.0
    breakdown = []
    for upper, rate in _brackets(filing_status, tax_year):
        if taxable <= lower:
            break
        ceiling = taxable if upper is None else min(taxable, upper)
        amount = max(0.0, ceiling - lower)
        if amount > 0:
            tax += amount * rate
            breakdown.append({"bracket": f"{rate:.0%}", "income_taxed": round(amount, 2), "tax": round(amount * rate, 2)})
        if upper is None:
            break
        lower = upper
    return {"taxable_income": round(taxable, 2), "tax": round(tax, 2), "brackets": breakdown}


def self_employment_tax(net_profit: float, w2_wages: float = 0.0, filing_status: str = "single", tax_year: int = 2025) -> Dict[str, Any]:
    """Calculate Schedule SE tax, including the deductible employer half."""
    year = _year_context(tax_year)
    net = max(0.0, float(net_profit or 0))
    wages = max(0.0, float(w2_wages or 0))
    se_base = net * SE_TAX_BASE_PERCENT
    remaining_ss_room = max(0.0, SS_WAGE_BASE[year] - wages)
    ss_tax = min(se_base, remaining_ss_room) * SOCIAL_SECURITY_RATE
    medicare_tax = se_base * MEDICARE_RATE

    threshold = 200000
    if filing_status == "married_filing_jointly":
        threshold = 250000
    elif filing_status == "married_filing_separately":
        threshold = 125000
    additional_medicare = max(0.0, se_base + wages - threshold) * ADDITIONAL_MEDICARE_RATE

    total = ss_tax + medicare_tax + additional_medicare
    return {
        "net_profit": round(net, 2),
        "se_tax_base": round(se_base, 2),
        "social_security_tax": round(ss_tax, 2),
        "medicare_tax": round(medicare_tax, 2),
        "additional_medicare_tax": round(additional_medicare, 2),
        "total_se_tax": round(total, 2),
        "deductible_half": round(total / 2, 2),
        "ss_wage_base": SS_WAGE_BASE[year],
    }


def payroll_tax(wages: float, filing_status: str = "single", tax_year: int = 2025) -> Dict[str, Any]:
    """FICA on W-2 wages (employee + employer combined) for entity comparisons."""
    year = _year_context(tax_year)
    wages = max(0.0, float(wages or 0))
    ss = min(wages, SS_WAGE_BASE[year]) * SOCIAL_SECURITY_RATE
    medicare = wages * MEDICARE_RATE
    threshold = 250000 if filing_status == "married_filing_jointly" else (125000 if filing_status == "married_filing_separately" else 200000)
    additional = max(0.0, wages - threshold) * ADDITIONAL_MEDICARE_RATE
    total = ss + medicare + additional
    return {
        "wages": round(wages, 2),
        "social_security": round(ss, 2),
        "medicare": round(medicare, 2),
        "additional_medicare": round(additional, 2),
        "total": round(total, 2),
        "employer_half": round(min(wages, SS_WAGE_BASE[year]) * 0.062 + wages * 0.0145 + 0.0, 2),
    }


def qbi_deduction(qualified_income: float, taxable_income_before_qbi: float) -> float:
    """Simplified 20% QBI deduction capped at 20% of taxable income."""
    if qualified_income <= 0 or taxable_income_before_qbi <= 0:
        return 0.0
    return round(min(qualified_income * 0.20, taxable_income_before_qbi * 0.20), 2)


# ---------------------------------------------------------------------------
# Core 1040 calculation
# ---------------------------------------------------------------------------


def calculate_individual_tax(
    *,
    tax_year: int,
    filing_status: str,
    w2_wages: float = 0.0,
    self_employment_income: float = 0.0,
    rental_income: float = 0.0,
    other_income: float = 0.0,
    capital_gains_short: float = 0.0,
    capital_gains_long: float = 0.0,
    itemized_deductions: float = 0.0,
    above_line_deductions: float = 0.0,
    retirement_contributions: float = 0.0,
    health_insurance_premiums: float = 0.0,
    federal_withholding: float = 0.0,
    estimated_payments: float = 0.0,
    credits: float = 0.0,
) -> Dict[str, Any]:
    """Full simplified Form 1040 computation."""
    se = self_employment_tax(self_employment_income, w2_wages, filing_status, tax_year)
    deductible_half_se = se["deductible_half"]
    # Self-employed health insurance is an above-the-line deduction, capped by profit.
    sehi = min(max(0.0, health_insurance_premiums), max(0.0, self_employment_income - deductible_half_se))
    adjustments = above_line_deductions + deductible_half_se + retirement_contributions + sehi

    total_income = max(0.0, w2_wages + self_employment_income + rental_income + other_income + capital_gains_short + capital_gains_long)
    agi = max(0.0, total_income - adjustments)

    standard = standard_deduction(filing_status, tax_year)
    using_itemized = itemized_deductions > standard
    base_deduction = itemized_deductions if using_itemized else standard

    qbi_income = max(0.0, self_employment_income - deductible_half_se) + max(0.0, rental_income)
    taxable_before_qbi = max(0.0, agi - base_deduction)
    qbi = qbi_deduction(qbi_income, taxable_before_qbi)

    # Long-term gains and qualified dividends are taxed at preferential rates.
    taxable_income = max(0.0, taxable_before_qbi - qbi)
    ordinary_income = max(0.0, taxable_income - max(0.0, capital_gains_long))
    ordinary_tax = federal_income_tax(ordinary_income, filing_status, tax_year)
    ltcg_tax = capital_gains_tax(max(0.0, capital_gains_long), ordinary_income, filing_status, tax_year)
    short_term_tax = federal_income_tax(ordinary_income + max(0.0, capital_gains_short), filing_status, tax_year)["tax"] - ordinary_tax["tax"]

    income_tax_before_credits = max(0.0, ordinary_tax["tax"] + ltcg_tax["tax"] + short_term_tax)
    income_tax = max(0.0, income_tax_before_credits - max(0.0, credits))
    total_tax = income_tax + se["total_se_tax"]
    payments = max(0.0, federal_withholding) + max(0.0, estimated_payments)
    refund_or_owed = round(payments - total_tax, 2)

    return {
        "tax_year": tax_year,
        "filing_status": filing_status,
        "filing_status_label": FILING_STATUS_LABELS.get(filing_status, filing_status),
        "income": {
            "w2_wages": round(w2_wages, 2),
            "self_employment": round(self_employment_income, 2),
            "rental": round(rental_income, 2),
            "other": round(other_income, 2),
            "capital_gains_short": round(capital_gains_short, 2),
            "capital_gains_long": round(capital_gains_long, 2),
            "total_income": round(total_income, 2),
        },
        "adjustments": {
            "above_line": round(above_line_deductions, 2),
            "deductible_half_se": deductible_half_se,
            "retirement_contributions": round(retirement_contributions, 2),
            "self_employed_health_insurance": round(sehi, 2),
            "total": round(adjustments, 2),
        },
        "agi": round(agi, 2),
        "deduction": {
            "standard": standard,
            "itemized": round(itemized_deductions, 2),
            "using_itemized": using_itemized,
            "applied": round(base_deduction, 2),
            "qbi": qbi,
        },
        "taxable_income": round(taxable_income, 2),
        "tax": {
            "ordinary": ordinary_tax["tax"],
            "long_term_capital_gains": ltcg_tax["tax"],
            "short_term_capital_gains": round(short_term_tax, 2),
            "credits": round(max(0.0, credits), 2),
            "income_tax": round(income_tax, 2),
            "self_employment_tax": se["total_se_tax"],
            "total_tax": round(total_tax, 2),
        },
        "payments": {
            "withholding": round(federal_withholding, 2),
            "estimated": round(estimated_payments, 2),
            "total": round(payments, 2),
        },
        "refund_or_owed": refund_or_owed,
        "refund": refund_or_owed if refund_or_owed >= 0 else 0.0,
        "amount_owed": abs(refund_or_owed) if refund_or_owed < 0 else 0.0,
        "self_employment_detail": se,
        "brackets": ordinary_tax["brackets"],
        "assumptions": {
            "uses_standard_deduction": not using_itemized,
            "simplified_qbi": True,
            "state_tax_excluded": True,
            "disclaimer": DISCLAIMER,
        },
    }


def capital_gains_tax(long_term_gain: float, ordinary_taxable_income: float, filing_status: str, tax_year: int) -> Dict[str, Any]:
    """Tax long-term capital gains using 0/15/20% breakpoints."""
    thresholds = {
        2024: {"single": (47025, 518900), "married_filing_jointly": (94050, 583750), "married_filing_separately": (47025, 291850), "head_of_household": (63000, 551350)},
        2025: {"single": (48350, 533400), "married_filing_jointly": (96700, 600050), "married_filing_separately": (48350, 300000), "head_of_household": (64750, 566700)},
        2026: {"single": (49675, 548000), "married_filing_jointly": (99350, 616500), "married_filing_separately": (49675, 308250), "head_of_household": (66500, 582250)},
    }
    year = _year_context(tax_year)
    zero_top, fifteen_top = thresholds[year].get(filing_status, thresholds[year]["single"])
    gain = max(0.0, long_term_gain)
    remaining = gain
    tax = 0.0
    start = max(0.0, ordinary_taxable_income)

    # Portion falling in the 0% band
    zero_room = max(0.0, zero_top - start)
    at_zero = min(remaining, zero_room)
    remaining -= at_zero

    fifteen_room = max(0.0, fifteen_top - max(start, zero_top) - at_zero)
    at_fifteen = min(remaining, fifteen_room)
    tax += at_fifteen * 0.15
    remaining -= at_fifteen
    tax += remaining * 0.20

    return {
        "gain": round(gain, 2),
        "tax": round(tax, 2),
        "effective_rate": round(tax / gain, 4) if gain else 0.0,
        "zero_percent_portion": round(at_zero, 2),
        "fifteen_percent_portion": round(at_fifteen, 2),
        "twenty_percent_portion": round(remaining, 2),
    }


def calculate_state_tax(state: str, taxable_income: float, residency_status: str = "resident") -> Dict[str, Any]:
    """Simplified state tax estimate based on top marginal rate."""
    code = (state or "").upper()
    rate = STATE_RATES.get(code, .05)
    multiplier = 1.0
    if residency_status == "non_resident":
        multiplier = 1.0
    elif residency_status == "part_year":
        multiplier = 0.5
    tax = max(0.0, taxable_income) * rate * multiplier
    return {
        "state": code or None,
        "residency_status": residency_status,
        "estimated_rate": rate,
        "taxable_income": round(max(0.0, taxable_income), 2),
        "state_tax": round(tax, 2),
        "no_income_tax_state": rate == 0.0,
        "note": "Planning estimate using a simplified flat rate; actual state brackets vary.",
    }


def calculate_capital_gains(sales: Iterable[Dict[str, Any]], tax_year: int, filing_status: str, ordinary_income: float = 0.0) -> Dict[str, Any]:
    """Summarize Schedule D rows and estimate federal tax impact."""
    short = long = proceeds = basis = 0.0
    rows = []
    for sale in sales:
        p = float(sale.get("proceeds") or 0)
        b = float(sale.get("cost_basis") or 0)
        gain = p - b
        purchase = _to_date(sale.get("purchase_date"))
        sold = _to_date(sale.get("sale_date"))
        days = (sold - purchase).days if purchase and sold else 0
        holding = "long" if days > 365 else "short"
        if holding == "long":
            long += gain
        else:
            short += gain
        proceeds += p
        basis += b
        rows.append({
            "symbol": sale.get("symbol"),
            "description": sale.get("description") or sale.get("symbol"),
            "purchase_date": purchase.isoformat() if purchase else None,
            "sale_date": sold.isoformat() if sold else None,
            "holding_days": days,
            "holding_period": holding,
            "proceeds": round(p, 2),
            "cost_basis": round(b, 2),
            "gain_loss": round(gain, 2),
        })

    net = short + long
    lt_tax = capital_gains_tax(max(0.0, long), max(0.0, ordinary_income), filing_status, tax_year)
    short_tax = 0.0
    if short > 0:
        short_tax = federal_income_tax(max(0.0, ordinary_income) + short, filing_status, tax_year)["tax"] - federal_income_tax(max(0.0, ordinary_income), filing_status, tax_year)["tax"]

    return {
        "tax_year": tax_year,
        "rows": rows,
        "short_term_gain": round(short, 2),
        "long_term_gain": round(long, 2),
        "net_gain": round(net, 2),
        "total_proceeds": round(proceeds, 2),
        "total_basis": round(basis, 2),
        "estimated_tax_short_term": round(short_tax, 2),
        "estimated_tax_long_term": lt_tax["tax"],
        "estimated_total_tax": round(short_tax + lt_tax["tax"], 2),
        "long_term_detail": lt_tax,
        "disclaimer": DISCLAIMER,
    }


def what_if_sale(
    *,
    symbol: str,
    proceeds: float,
    cost_basis: float,
    purchase_date: str,
    sale_date: str,
    tax_year: int,
    filing_status: str,
    ordinary_income: float = 0.0,
) -> Dict[str, Any]:
    """Compare tax impact of selling now vs. holding past one year."""
    summary = calculate_capital_gains(
        [{"symbol": symbol, "proceeds": proceeds, "cost_basis": cost_basis, "purchase_date": purchase_date, "sale_date": sale_date}],
        tax_year,
        filing_status,
        ordinary_income,
    )
    now_tax = summary["estimated_total_tax"]
    gain = max(0.0, proceeds - cost_basis)
    later_tax = capital_gains_tax(gain, ordinary_income, filing_status, tax_year)["tax"]
    return {
        "symbol": symbol,
        "gain": round(proceeds - cost_basis, 2),
        "holding_period": summary["rows"][0]["holding_period"] if summary["rows"] else "short",
        "sell_now_tax": now_tax,
        "hold_to_long_term_tax": round(later_tax, 2),
        "estimated_savings": round(now_tax - later_tax, 2),
        "recommendation": "Consider holding past the one-year mark to qualify for long-term rates." if now_tax > later_tax else "Holding longer does not reduce the estimated tax on this position.",
        "disclaimer": DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Entity comparison
# ---------------------------------------------------------------------------


def _payroll_employer_only(wages: float, tax_year: int) -> float:
    year = _year_context(tax_year)
    wages = max(0.0, wages)
    return min(wages, SS_WAGE_BASE[year]) * 0.062 + wages * 0.0145


def _scenario_base(**kwargs) -> Dict[str, Any]:
    return kwargs


def compare_entities(
    *,
    annual_revenue: float,
    annual_expenses: float,
    tax_year: int,
    filing_status: str,
    state: str = "",
    owner_w2_salary: Optional[float] = None,
    other_income: float = 0.0,
) -> Dict[str, Any]:
    """Compare total tax burden across entity structures."""
    revenue = max(0.0, float(annual_revenue or 0))
    expenses = max(0.0, float(annual_expenses or 0))
    net_profit = max(0.0, revenue - expenses)
    owner_other = max(0.0, float(other_income or 0))
    state_rate = STATE_RATES.get((state or "").upper(), 0.0)
    standard = standard_deduction(filing_status, tax_year)

    scenarios: List[Dict[str, Any]] = []

    # --- Sole proprietor / disregarded LLC -------------------------------
    se = self_employment_tax(net_profit, other_income, filing_status, tax_year)
    sp_agi = net_profit + owner_other - se["deductible_half"]
    sp_taxable = max(0.0, sp_agi - standard)
    sp_qbi = qbi_deduction(net_profit - se["deductible_half"], sp_taxable)
    sp_income_tax = federal_income_tax(max(0.0, sp_taxable - sp_qbi), filing_status, tax_year)["tax"]
    sp_state = (net_profit + owner_other) * state_rate
    sp_total = se["total_se_tax"] + sp_income_tax + sp_state
    scenarios.append({
        "entity_type": "sole_proprietor",
        "label": "Sole Proprietor",
        "description": "Business profit flows to Schedule C and is subject to self-employment tax.",
        "net_profit": round(net_profit, 2),
        "owner_salary": 0.0,
        "distributions": round(net_profit, 2),
        "payroll_tax": se["total_se_tax"],
        "self_employment_tax": se["total_se_tax"],
        "corporate_tax": 0.0,
        "income_tax": round(sp_income_tax, 2),
        "state_tax": round(sp_state, 2),
        "total_tax": round(sp_total, 2),
        "take_home": round(net_profit + owner_other - sp_total, 2),
        "qbi_deduction": sp_qbi,
    })

    # --- S-Corporation ----------------------------------------------------
    salary = float(owner_w2_salary) if owner_w2_salary is not None else net_profit * 0.60
    salary = min(max(0.0, salary), net_profit)
    employer_payroll = _payroll_employer_only(salary, tax_year)
    distribution = max(0.0, net_profit - salary - employer_payroll)
    payroll = payroll_tax(salary, filing_status, tax_year)["total"]
    sc_taxable = max(0.0, salary + distribution + owner_other - standard)
    sc_qbi = qbi_deduction(distribution, sc_taxable)
    sc_income_tax = federal_income_tax(max(0.0, sc_taxable - sc_qbi), filing_status, tax_year)["tax"]
    sc_state = (salary + distribution + owner_other) * state_rate
    sc_total = payroll + sc_income_tax + sc_state
    scenarios.append({
        "entity_type": "s_corp",
        "label": "S-Corporation",
        "description": "Owner takes a reasonable W-2 salary; remaining profit is a non-payroll distribution.",
        "net_profit": round(net_profit, 2),
        "owner_salary": round(salary, 2),
        "distributions": round(distribution, 2),
        "payroll_tax": round(payroll, 2),
        "self_employment_tax": 0.0,
        "corporate_tax": 0.0,
        "income_tax": round(sc_income_tax, 2),
        "state_tax": round(sc_state, 2),
        "total_tax": round(sc_total, 2),
        "take_home": round(net_profit + owner_other - sc_total, 2),
        "qbi_deduction": sc_qbi,
        "reasonable_salary_note": "Salary should reflect market compensation for the owner's services.",
    })

    # --- C-Corporation ----------------------------------------------------
    c_salary = float(owner_w2_salary) if owner_w2_salary is not None else net_profit * 0.40
    c_salary = min(max(0.0, c_salary), net_profit)
    c_employer_payroll = _payroll_employer_only(c_salary, tax_year)
    c_profit = max(0.0, net_profit - c_salary - c_employer_payroll)
    c_corp_tax = c_profit * 0.21
    after_corp = c_profit - c_corp_tax
    dividend_tax = after_corp * 0.15
    c_payroll = payroll_tax(c_salary, filing_status, tax_year)["total"]
    c_income_tax = federal_income_tax(max(0.0, c_salary + owner_other - standard), filing_status, tax_year)["tax"]
    c_state = (c_salary + owner_other + c_profit) * state_rate
    c_total = c_payroll + c_income_tax + c_corp_tax + dividend_tax + c_state
    scenarios.append({
        "entity_type": "c_corp",
        "label": "C-Corporation",
        "description": "Corporation pays 21% federal tax; dividends are taxed again when distributed.",
        "net_profit": round(net_profit, 2),
        "owner_salary": round(c_salary, 2),
        "distributions": round(after_corp, 2),
        "payroll_tax": round(c_payroll, 2),
        "self_employment_tax": 0.0,
        "corporate_tax": round(c_corp_tax, 2),
        "dividend_tax": round(dividend_tax, 2),
        "income_tax": round(c_income_tax, 2),
        "state_tax": round(c_state, 2),
        "total_tax": round(c_total, 2),
        "take_home": round(net_profit + owner_other - c_total, 2),
        "retained_earnings": round(after_corp - (after_corp * 0.15 / 0.85 if False else 0), 2),
    })

    # --- Partnership ------------------------------------------------------
    partner_share = net_profit
    p_se = self_employment_tax(partner_share, other_income, filing_status, tax_year)
    p_taxable = max(0.0, partner_share + owner_other - p_se["deductible_half"] - standard)
    p_qbi = qbi_deduction(partner_share - p_se["deductible_half"], p_taxable)
    p_income_tax = federal_income_tax(max(0.0, p_taxable - p_qbi), filing_status, tax_year)["tax"]
    p_state = (partner_share + owner_other) * state_rate
    p_total = p_se["total_se_tax"] + p_income_tax + p_state
    scenarios.append({
        "entity_type": "partnership",
        "label": "Partnership (K-1)",
        "description": "Profit allocated on a K-1; partners pay self-employment tax on their distributive share.",
        "net_profit": round(net_profit, 2),
        "owner_salary": 0.0,
        "distributions": round(partner_share, 2),
        "payroll_tax": p_se["total_se_tax"],
        "self_employment_tax": p_se["total_se_tax"],
        "corporate_tax": 0.0,
        "income_tax": round(p_income_tax, 2),
        "state_tax": round(p_state, 2),
        "total_tax": round(p_total, 2),
        "take_home": round(net_profit + owner_other - p_total, 2),
        "qbi_deduction": p_qbi,
    })

    # LLC is represented by both disregarded-entity and S-Corp elections.
    llc_as_disregarded = dict(next(s for s in scenarios if s["entity_type"] == "sole_proprietor"))
    llc_as_disregarded.update({
        "entity_type": "llc_disregarded",
        "label": "LLC (Disregarded Entity)",
        "description": "Single-member LLC taxed like a sole proprietor by default.",
    })
    llc_as_scorp = dict(next(s for s in scenarios if s["entity_type"] == "s_corp"))
    llc_as_scorp.update({
        "entity_type": "llc_s_corp",
        "label": "LLC Electing S-Corp",
        "description": "LLC files Form 2553/8832 and is taxed as an S-Corporation.",
    })
    scenarios.extend([llc_as_disregarded, llc_as_scorp])

    ranked = sorted(scenarios, key=lambda s: s["total_tax"])
    best = ranked[0]
    baseline = next(s for s in scenarios if s["entity_type"] == "sole_proprietor")
    for scenario in scenarios:
        scenario["savings_vs_sole_prop"] = round(baseline["total_tax"] - scenario["total_tax"], 2)

    return {
        "input": {
            "annual_revenue": round(revenue, 2),
            "annual_expenses": round(expenses, 2),
            "net_profit": round(net_profit, 2),
            "tax_year": tax_year,
            "filing_status": filing_status,
            "state": (state or "").upper() or None,
        },
        "scenarios": scenarios,
        "recommendation": {
            "entity_type": best["entity_type"],
            "label": best["label"],
            "estimated_total_tax": best["total_tax"],
            "estimated_savings_vs_sole_prop": best.get("savings_vs_sole_prop", 0.0),
            "reason": f"Lowest projected combined federal, payroll, and state tax among the compared structures.",
        },
        "assumptions": {
            "s_corp_salary_default": "60% of net profit unless a salary is supplied",
            "c_corp_salary_default": "40% of net profit unless a salary is supplied",
            "state_tax": "Simplified top marginal rate" if state_rate else "No state rate applied",
            "excluded": ["local taxes", "credits other than input", "AMT", "NIIT", "payroll provider fees", "formation costs"],
            "disclaimer": DISCLAIMER,
        },
    }


# ---------------------------------------------------------------------------
# Estimated taxes
# ---------------------------------------------------------------------------


def calculate_estimated_taxes(
    *,
    tax_year: int,
    filing_status: str,
    projected_total_tax: float,
    prior_year_tax: Optional[float] = None,
    withholding: float = 0.0,
    prior_year_agi: Optional[float] = None,
    reminders_enabled: bool = True,
) -> Dict[str, Any]:
    """Compute 1040-ES quarterly payments and safe harbor amounts."""
    total_tax = max(0.0, float(projected_total_tax or 0))
    withholding = max(0.0, float(withholding or 0))
    prior = max(0.0, float(prior_year_tax)) if prior_year_tax is not None else None

    current_safe = total_tax * 0.90
    prior_safe = prior * (1.10 if (prior_year_agi or 0) > 150000 else 1.00) if prior is not None else 0.0
    safe_harbor = max(current_safe, prior_safe) if prior is not None else current_safe
    required = max(0.0, safe_harbor - withholding)
    per_quarter = required / 4.0

    due_dates = quarterly_due_dates(tax_year)
    schedule = []
    for key in ("q1", "q2", "q3", "q4"):
        due = due_dates[key]
        due_date = date.fromisoformat(due)
        reminder_date = due_date - timedelta(days=30)
        schedule.append({
            "quarter": key.upper(),
            "amount": round(per_quarter, 2),
            "due_date": due,
            "reminder_date": reminder_date.isoformat(),
            "reminder_enabled": reminders_enabled,
            "days_until_due": (due_date - date.today()).days,
        })

    return {
        "tax_year": tax_year,
        "filing_status": filing_status,
        "projected_total_tax": round(total_tax, 2),
        "withholding_credits": round(withholding, 2),
        "prior_year_tax": round(prior, 2) if prior is not None else None,
        "current_year_safe_harbor": round(current_safe, 2),
        "prior_year_safe_harbor": round(prior_safe, 2),
        "safe_harbor_amount": round(safe_harbor, 2),
        "required_annual_payment": round(required, 2),
        "quarterly_payment": round(per_quarter, 2),
        "due_dates": due_dates,
        "schedule": schedule,
        "notes": [
            "Safe harbor: pay at least 90% of current-year tax or 100% of prior-year tax (110% if prior AGI > $150k).",
            "Withholding is treated as paid evenly throughout the year.",
            DISCLAIMER,
        ],
    }


def quarterly_due_dates(tax_year: int) -> Dict[str, str]:
    """Return 1040-ES due dates for the given tax year."""
    return {
        "q1": date(tax_year, 4, 15).isoformat(),
        "q2": date(tax_year, 6, 15).isoformat(),
        "q3": date(tax_year, 9, 15).isoformat(),
        "q4": date(tax_year + 1, 1, 15).isoformat(),
    }


# ---------------------------------------------------------------------------
# Retirement planning
# ---------------------------------------------------------------------------


RETIREMENT_LIMITS = {
    2024: {"traditional_ira": 7000, "roth_ira": 7000, "sep_ira": 69000, "solo_401k": 69000, "solo_401k_deferral": 23000, "catch_up_ira": 1000, "catch_up_401k": 7500},
    2025: {"traditional_ira": 7000, "roth_ira": 7000, "sep_ira": 70000, "solo_401k": 70000, "solo_401k_deferral": 23500, "catch_up_ira": 1000, "catch_up_401k": 7500},
    2026: {"traditional_ira": 7500, "roth_ira": 7500, "sep_ira": 72000, "solo_401k": 72000, "solo_401k_deferral": 24500, "catch_up_ira": 1100, "catch_up_401k": 8000},
}


def retirement_comparison(
    *,
    tax_year: int,
    net_self_employment_income: float,
    marginal_tax_rate: Optional[float] = None,
    age: int = 40,
    filing_status: str = "single",
) -> Dict[str, Any]:
    """Compare contribution limits and tax impact for common retirement accounts."""
    year = _year_context(tax_year)
    limits = RETIREMENT_LIMITS[year]
    net = max(0.0, float(net_self_employment_income or 0))
    if marginal_tax_rate is None:
        marginal_tax_rate = marginal_rate(net, filing_status, tax_year)
    catch_up_eligible = age >= 50
    ira_limit = limits["traditional_ira"] + (limits["catch_up_ira"] if catch_up_eligible else 0)
    deferral = limits["solo_401k_deferral"] + (limits["catch_up_401k"] if catch_up_eligible else 0)

    # SEP and employer Solo 401k contributions are 25% of net SE earnings
    # (20% of net profit after the deductible half of SE tax).
    se = self_employment_tax(net, filing_status=filing_status, tax_year=tax_year)
    net_earnings = max(0.0, net - se["deductible_half"])
    employer_pct_limit = net_earnings * 0.20
    sep_limit = min(limits["sep_ira"], employer_pct_limit)
    solo_total = min(limits["solo_401k"], deferral + employer_pct_limit)

    accounts = [
        {
            "account_type": "traditional_ira",
            "label": "Traditional IRA",
            "max_contribution": round(ira_limit, 2),
            "tax_deduction_now": True,
            "tax_free_growth": False,
            "tax_savings": round(ira_limit * marginal_tax_rate, 2),
            "notes": "Deductible unless you (or a spouse) are covered by a workplace plan and exceed income limits.",
        },
        {
            "account_type": "roth_ira",
            "label": "Roth IRA",
            "max_contribution": round(ira_limit, 2),
            "tax_deduction_now": False,
            "tax_free_growth": True,
            "tax_savings": 0.0,
            "notes": "No current deduction; qualified withdrawals are tax-free. Income limits apply.",
        },
        {
            "account_type": "sep_ira",
            "label": "SEP-IRA",
            "max_contribution": round(sep_limit, 2),
            "tax_deduction_now": True,
            "tax_free_growth": False,
            "tax_savings": round(sep_limit * marginal_tax_rate, 2),
            "notes": "Up to 25% of net self-employment earnings, capped at the annual limit.",
        },
        {
            "account_type": "solo_401k",
            "label": "Solo 401(k)",
            "max_contribution": round(solo_total, 2),
            "tax_deduction_now": True,
            "tax_free_growth": False,
            "tax_savings": round(solo_total * marginal_tax_rate, 2),
            "notes": "Employee deferral plus employer profit-sharing; highest limits for self-employed owners.",
            "employee_deferral": round(min(deferral, solo_total), 2),
            "employer_contribution": round(max(0.0, solo_total - min(deferral, solo_total)), 2),
        },
    ]
    best = max(accounts, key=lambda a: a["max_contribution"])
    return {
        "tax_year": year,
        "net_self_employment_income": round(net, 2),
        "marginal_tax_rate": round(marginal_tax_rate, 4),
        "catch_up_eligible": catch_up_eligible,
        "accounts": accounts,
        "recommendation": {
            "account_type": best["account_type"],
            "label": best["label"],
            "max_contribution": best["max_contribution"],
            "estimated_tax_savings": best["tax_savings"],
            "reason": "Highest contribution capacity based on your self-employment income.",
        },
        "assumptions": {
            "age": age,
            "limits_year": year,
            "disclaimer": DISCLAIMER,
        },
    }


# ---------------------------------------------------------------------------
# Audit documentation
# ---------------------------------------------------------------------------


def audit_coverage(deductions: Iterable[Dict[str, Any]], documents: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Score how well each deduction is documented for audit defense."""
    docs = list(documents)
    categories_with_docs: Dict[str, int] = {}
    for doc in docs:
        cat = str(doc.get("category") or "uncategorized")
        categories_with_docs[cat] = categories_with_docs.get(cat, 0) + 1

    rows = []
    total_amount = 0.0
    documented_amount = 0.0
    under_documented = []
    for deduction in deductions:
        category = str(deduction.get("category") or "uncategorized")
        amount = float(deduction.get("amount") or 0)
        total_amount += amount
        has_receipt = bool(deduction.get("receipt_url"))
        doc_count = categories_with_docs.get(category, 0)
        if has_receipt or doc_count > 0 or deduction.get("verified_bool"):
            status = "complete"
            documented_amount += amount
        elif amount >= 500:
            status = "missing"
        else:
            status = "partial"
        if status != "complete":
            under_documented.append({
                "deduction_id": deduction.get("id"),
                "category": category,
                "amount": round(amount, 2),
                "status": status,
            })
        rows.append({
            "deduction_id": deduction.get("id"),
            "category": category,
            "amount": round(amount, 2),
            "receipt_url": deduction.get("receipt_url"),
            "documents_on_file": doc_count,
            "status": status,
        })

    coverage_percent = round((documented_amount / total_amount * 100), 1) if total_amount else 100.0
    return {
        "total_deductions": round(total_amount, 2),
        "documented_amount": round(documented_amount, 2),
        "coverage_percent": coverage_percent,
        "rows": rows,
        "under_documented": under_documented,
        "document_count": len(docs),
        "risk_level": "low" if coverage_percent >= 85 else ("medium" if coverage_percent >= 60 else "high"),
        "recommendation": (
            "Documentation looks solid." if coverage_percent >= 85
            else "Upload receipts or statements for the flagged deductions before filing."
        ),
        "disclaimer": DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Form generation
# ---------------------------------------------------------------------------


def _form(form_type: str, form_name: str, fields: List[Dict[str, Any]], **extra) -> Dict[str, Any]:
    return {
        "form_type": form_type,
        "form_name": form_name,
        "tax_year": extra.get("tax_year"),
        "completed": True,
        "fields": fields,
        "pdf_ready": True,
        "metadata": {k: v for k, v in extra.items() if k != "tax_year"},
        "disclaimer": DISCLAIMER,
    }


def generate_form_1040(calculation: Dict[str, Any], *, taxpayer: Optional[dict] = None, tax_year: Optional[int] = None) -> Dict[str, Any]:
    income = calculation["income"]
    adj = calculation["adjustments"]
    ded = calculation["deduction"]
    tax = calculation["tax"]
    payments = calculation["payments"]
    fields = [
        {"line": "1a", "label": "W-2 wages", "amount": income["w2_wages"]},
        {"line": "2b", "label": "Taxable interest", "amount": 0.0},
        {"line": "3b", "label": "Ordinary dividends", "amount": 0.0},
        {"line": "4b", "label": "Capital gain or loss", "amount": round(income["capital_gains_short"] + income["capital_gains_long"], 2)},
        {"line": "8", "label": "Additional income (Schedule 1)", "amount": round(income["self_employment"] + income["rental"] + income["other"], 2)},
        {"line": "9", "label": "Total income", "amount": income["total_income"]},
        {"line": "10", "label": "Adjustments to income", "amount": adj["total"]},
        {"line": "11", "label": "Adjusted gross income", "amount": calculation["agi"]},
        {"line": "12", "label": "Standard or itemized deduction", "amount": ded["applied"]},
        {"line": "13", "label": "Qualified business income deduction", "amount": ded["qbi"]},
        {"line": "15", "label": "Taxable income", "amount": calculation["taxable_income"]},
        {"line": "16", "label": "Income tax", "amount": tax["income_tax"]},
        {"line": "23", "label": "Other taxes (self-employment)", "amount": tax["self_employment_tax"]},
        {"line": "24", "label": "Total tax", "amount": tax["total_tax"]},
        {"line": "25", "label": "Federal income tax withheld", "amount": payments["withholding"]},
        {"line": "26", "label": "Estimated tax payments", "amount": payments["estimated"]},
        {"line": "33", "label": "Total payments", "amount": payments["total"]},
        {"line": "34", "label": "Refund", "amount": calculation["refund"]},
        {"line": "37", "label": "Amount you owe", "amount": calculation["amount_owed"]},
    ]
    return _form(
        "1040",
        "Form 1040 - U.S. Individual Income Tax Return",
        fields,
        tax_year=tax_year or calculation.get("tax_year"),
        taxpayer=taxpayer or {},
        filing_status=calculation.get("filing_status"),
        summary=calculation,
    )


def generate_schedule_c(
    *,
    tax_year: int,
    business_name: Optional[str],
    gross_revenue: float,
    expenses: float,
    cost_of_goods_sold: float = 0.0,
    schedule_c_data: Optional[dict] = None,
    owner: Optional[dict] = None,
) -> Dict[str, Any]:
    data = schedule_c_data or {}
    expense_items = []
    if isinstance(data.get("expenses"), list):
        for item in data["expenses"]:
            expense_items.append({
                "line": item.get("line") or "27a",
                "label": item.get("label") or item.get("category") or "Other expense",
                "amount": round(float(item.get("amount") or 0), 2),
            })
    else:
        for key, value in (data.get("expenses") or {}).items():
            expense_items.append({"line": "27a", "label": str(key).replace("_", " ").title(), "amount": round(float(value or 0), 2)})

    itemized_total = sum(item["amount"] for item in expense_items)
    if not expense_items and expenses:
        expense_items.append({"line": "27a", "label": "Total expenses", "amount": round(expenses, 2)})
        itemized_total = expenses

    net = round(gross_revenue - cost_of_goods_sold - max(expenses, itemized_total), 2)
    fields = [
        {"line": "A", "label": "Principal business or profession", "value": data.get("business_type") or "Business services"},
        {"line": "1", "label": "Gross receipts or sales", "amount": round(gross_revenue, 2)},
        {"line": "4", "label": "Cost of goods sold", "amount": round(cost_of_goods_sold, 2)},
        {"line": "5", "label": "Gross profit", "amount": round(gross_revenue - cost_of_goods_sold, 2)},
        *expense_items,
        {"line": "28", "label": "Total expenses", "amount": round(max(expenses, itemized_total, 0), 2)},
        {"line": "29", "label": "Tentative profit or loss", "amount": round(gross_revenue - cost_of_goods_sold - max(expenses, itemized_total), 2)},
        {"line": "31", "label": "Net profit or loss", "amount": net},
    ]
    return _form(
        "schedule_c",
        "Schedule C - Profit or Loss From Business",
        fields,
        tax_year=tax_year,
        business_name=business_name,
        owner=owner or {},
        net_profit=net,
    )


def generate_schedule_e(*, tax_year: int, rental_income: float, rental_expenses: float = 0.0, properties: Optional[List[dict]] = None) -> Dict[str, Any]:
    properties = properties or []
    rows = []
    total_income = 0.0
    total_expenses = 0.0
    if properties:
        for prop in properties:
            inc = float(prop.get("rents_received") or prop.get("income") or 0)
            exp = float(prop.get("expenses") or 0)
            total_income += inc
            total_expenses += exp
            rows.append({
                "address": prop.get("address") or prop.get("name") or "Rental property",
                "type": prop.get("property_type") or "Residential rental",
                "rents_received": round(inc, 2),
                "expenses": round(exp, 2),
                "net": round(inc - exp, 2),
            })
    else:
        total_income = float(rental_income or 0)
        total_expenses = float(rental_expenses or 0)
        rows.append({
            "address": "Rental property",
            "type": "Residential rental",
            "rents_received": round(total_income, 2),
            "expenses": round(total_expenses, 2),
            "net": round(total_income - total_expenses, 2),
        })
    fields = [
        {"line": "3", "label": "Rents received", "amount": round(total_income, 2)},
        {"line": "20", "label": "Total expenses", "amount": round(total_expenses, 2)},
        {"line": "21", "label": "Income or loss", "amount": round(total_income - total_expenses, 2)},
    ]
    return _form(
        "schedule_e",
        "Schedule E - Supplemental Income and Loss",
        fields,
        tax_year=tax_year,
        properties=rows,
        net_rental_income=round(total_income - total_expenses, 2),
    )


def generate_schedule_se(*, tax_year: int, net_profit: float, w2_wages: float = 0.0, filing_status: str = "single") -> Dict[str, Any]:
    se = self_employment_tax(net_profit, w2_wages, filing_status, tax_year)
    fields = [
        {"line": "2", "label": "Net profit from Schedule C", "amount": round(net_profit, 2)},
        {"line": "4a", "label": "Net earnings subject to SE tax", "amount": se["se_tax_base"]},
        {"line": "10", "label": "Social Security tax", "amount": se["social_security_tax"]},
        {"line": "11", "label": "Medicare tax", "amount": round(se["medicare_tax"] + se["additional_medicare_tax"], 2)},
        {"line": "12", "label": "Total self-employment tax", "amount": se["total_se_tax"]},
        {"line": "13", "label": "Deductible part of SE tax", "amount": se["deductible_half"]},
    ]
    return _form("schedule_se", "Schedule SE - Self-Employment Tax", fields, tax_year=tax_year, detail=se)


def generate_form_1040nr(*, tax_year: int, us_source_income: float, treaty_country: Optional[str] = None, visa_type: Optional[str] = None, filing_status: str = "single") -> Dict[str, Any]:
    standard = standard_deduction(filing_status, tax_year)
    taxable = max(0.0, us_source_income - standard)
    tax = federal_income_tax(taxable, "single", tax_year)
    fields = [
        {"line": "1", "label": "Wages, salaries, tips (U.S. source)", "amount": round(us_source_income, 2)},
        {"line": "9", "label": "Total effectively connected income", "amount": round(us_source_income, 2)},
        {"line": "11", "label": "Itemized deductions", "amount": 0.0},
        {"line": "14", "label": "Taxable income", "amount": round(taxable, 2)},
        {"line": "16", "label": "Tax", "amount": tax["tax"]},
    ]
    return _form(
        "1040nr",
        "Form 1040-NR - U.S. Nonresident Alien Income Tax Return",
        fields,
        tax_year=tax_year,
        treaty_country=treaty_country,
        visa_type=visa_type,
        note="Nonresident filers generally cannot claim the standard deduction unless from India or a treaty allows it.",
    )


def generate_form_8832(*, election_year: int, current_entity: str, elected_classification: str, owner_count: int = 1) -> Dict[str, Any]:
    fields = [
        {"line": "1", "label": "Name of eligible entity", "value": "Eligible entity"},
        {"line": "3", "label": "Current entity type", "value": current_entity},
        {"line": "5", "label": "Election effective date", "value": f"{election_year}-01-01"},
        {"line": "6", "label": "Elected classification", "value": elected_classification},
        {"line": "8", "label": "Number of owners", "value": owner_count},
    ]
    return _form(
        "8832",
        "Form 8832 - Entity Classification Election",
        fields,
        tax_year=election_year,
        note="For S-Corp status, Form 2553 is also required within 2 months and 15 days of the election.",
    )


def generate_schedule_d(*, tax_year: int, sales: List[dict], ordinary_income: float = 0.0, filing_status: str = "single") -> Dict[str, Any]:
    summary = calculate_capital_gains(sales, tax_year, filing_status, ordinary_income)
    fields = [
        {"line": "1b", "label": "Proceeds from short-term transactions", "amount": round(sum(r["proceeds"] for r in summary["rows"] if r["holding_period"] == "short"), 2)},
        {"line": "1h", "label": "Short-term gain or loss", "amount": summary["short_term_gain"]},
        {"line": "8b", "label": "Proceeds from long-term transactions", "amount": round(sum(r["proceeds"] for r in summary["rows"] if r["holding_period"] == "long"), 2)},
        {"line": "8h", "label": "Long-term gain or loss", "amount": summary["long_term_gain"]},
        {"line": "16", "label": "Net capital gain or loss", "amount": summary["net_gain"]},
        {"line": "20", "label": "Estimated federal tax on gains", "amount": summary["estimated_total_tax"]},
    ]
    return _form("schedule_d", "Schedule D - Capital Gains and Losses", fields, tax_year=tax_year, detail=summary)


def generate_state_form(*, tax_year: int, state: str, residency_status: str, income_allocated: float, state_tax: float) -> Dict[str, Any]:
    fields = [
        {"line": "1", "label": "Federal adjusted gross income", "amount": round(income_allocated, 2)},
        {"line": "2", "label": f"{state} source income", "amount": round(income_allocated, 2)},
        {"line": "3", "label": "Residency status", "value": residency_status},
        {"line": "10", "label": "Estimated state tax liability", "amount": round(state_tax, 2)},
    ]
    return _form(f"state_{state.lower()}", f"{state} Individual Income Tax Return", fields, tax_year=tax_year, state=state, residency_status=residency_status)


def generate_1040es(*, tax_year: int, calculation: Dict[str, Any], withholding: float = 0.0, prior_year_tax: Optional[float] = None, prior_year_agi: Optional[float] = None) -> Dict[str, Any]:
    estimate = calculate_estimated_taxes(
        tax_year=tax_year,
        filing_status=calculation.get("filing_status", "single"),
        projected_total_tax=calculation["tax"]["total_tax"],
        prior_year_tax=prior_year_tax,
        withholding=withholding,
        prior_year_agi=prior_year_agi,
    )
    fields = [{"line": q["quarter"], "label": f"Payment due {q['due_date']}", "amount": q["amount"]} for q in estimate["schedule"]]
    return _form("1040es", "Form 1040-ES - Estimated Tax for Individuals", fields, tax_year=tax_year, detail=estimate)


def generate_efile_payload(*, tax_return: dict, forms: List[dict], taxpayer: dict) -> Dict[str, Any]:
    """Build a mock IRS MeF-style submission payload."""
    confirmation = f"MEF{datetime.utcnow():%Y%m%d}{tax_return.get('id', 0):06d}"
    return {
        "submission_id": confirmation,
        "tax_year": tax_return.get("tax_year"),
        "taxpayer": {
            "first_name": taxpayer.get("first_name"),
            "last_name": taxpayer.get("last_name"),
            "email": taxpayer.get("email"),
        },
        "return_type": tax_return.get("filing_status"),
        "entity_type": tax_return.get("entity_type"),
        "forms": [{"form_type": f.get("form_type"), "completed": f.get("completed", True)} for f in forms],
        "summary": {
            "total_income": tax_return.get("total_income"),
            "total_deductions": tax_return.get("total_deductions"),
            "estimated_tax": tax_return.get("estimated_tax"),
        },
        "status": "ready_for_transmission",
        "note": "Mock e-file payload for demonstration purposes only.",
    }


# ---------------------------------------------------------------------------
# Deduction rules & questionnaire
# ---------------------------------------------------------------------------

DEFAULT_DEDUCTION_RULES: List[Dict[str, Any]] = [
    {
        "category": "home_office",
        "description": "Exclusive and regular business use of part of your home.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 280A",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099"],
        "common_questions": [
            {"field": "square_footage", "question": "How many square feet is your dedicated office?", "help": "Space must be used exclusively and regularly for business."},
            {"field": "home_square_footage", "question": "What is the total square footage of your home?", "help": "Used to compute the business-use percentage."},
            {"field": "annual_home_expenses", "question": "Annual home expenses (rent/mortgage interest, utilities, insurance)?", "help": "Only the business percentage is deductible."},
        ],
        "documentation_required": ["Lease or mortgage statement", "Utility bills", "Photos of the office", "Floor plan or square footage calculation"],
    },
    {
        "category": "vehicle",
        "description": "Business use of a vehicle, using standard mileage or actual expenses.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099"],
        "common_questions": [
            {"field": "business_miles", "question": "How many business miles did you drive this year?", "help": "Commuting miles are not deductible."},
            {"field": "total_miles", "question": "What were your total miles for the year?", "help": "Used to determine business-use percentage."},
            {"field": "method", "question": "Standard mileage or actual expenses?", "help": "The standard mileage rate for 2025 is 70 cents per mile."},
        ],
        "documentation_required": ["Mileage log", "Fuel and maintenance receipts", "Insurance and registration"],
    },
    {
        "category": "meals",
        "description": "Business meals with clients or during travel (50% limit).",
        "max_amount": None,
        "percentage_limit": 0.50,
        "limit_basis": "absolute",
        "irs_code": "IRC 274(n)",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099", "w2"],
        "common_questions": [
            {"field": "total_meal_expenses", "question": "Total business meal costs for the year?", "help": "Only 50% is generally deductible."},
            {"field": "business_purpose", "question": "What was the business purpose of these meals?", "help": "Record who attended and the business discussed."},
        ],
        "documentation_required": ["Itemized receipts", "Names of attendees", "Business purpose notes"],
    },
    {
        "category": "professional_services",
        "description": "Legal, accounting, bookkeeping, and consulting fees.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099", "rental"],
        "common_questions": [
            {"field": "service_type", "question": "What professional services did you pay for?", "help": "Include tax prep, legal, and consulting fees."},
            {"field": "total_cost", "question": "Total amount paid for professional services?", "help": "Personal legal fees are generally not deductible."},
        ],
        "documentation_required": ["Invoices", "Engagement letters", "Proof of payment"],
    },
    {
        "category": "health_insurance",
        "description": "Self-employed health insurance premiums (above-the-line).",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162(l)",
        "deduction_type": "above_line",
        "income_types": ["self_employed", "1099"],
        "common_questions": [
            {"field": "annual_premiums", "question": "Annual health insurance premiums you paid?", "help": "You cannot deduct premiums if you are eligible for an employer-subsidized plan."},
            {"field": "covered_people", "question": "Who is covered on the policy?", "help": "Self, spouse, dependents, and children under 27 may qualify."},
        ],
        "documentation_required": ["Insurance premium statements", "Form 1095-A if marketplace coverage"],
    },
    {
        "category": "retirement",
        "description": "Retirement contributions (SEP-IRA, Solo 401k, Traditional IRA).",
        "max_amount": 70000,
        "percentage_limit": 0.25,
        "limit_basis": "net_profit",
        "irs_code": "IRC 401/408",
        "deduction_type": "above_line",
        "income_types": ["self_employed", "1099", "w2"],
        "common_questions": [
            {"field": "account_type", "question": "Which retirement account did you contribute to?", "help": "SEP-IRA, Solo 401(k), Traditional IRA, or Roth IRA."},
            {"field": "contribution_amount", "question": "How much did you contribute?", "help": "Limits vary by account type and age."},
        ],
        "documentation_required": ["Brokerage contribution statements", "Form 5498"],
    },
    {
        "category": "equipment",
        "description": "Business equipment, computers, and furniture (Section 179 or bonus depreciation).",
        "max_amount": 1160000,
        "percentage_limit": None,
        "limit_basis": "absolute",
        "irs_code": "IRC 179",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099"],
        "common_questions": [
            {"field": "equipment_cost", "question": "Total cost of equipment purchased for business?", "help": "Section 179 may allow full expensing in the year purchased."},
            {"field": "business_use_percent", "question": "What percentage is used for business?", "help": "Only the business-use portion is deductible."},
        ],
        "documentation_required": ["Purchase receipts", "Asset list", "Business-use calculation"],
    },
    {
        "category": "supplies",
        "description": "Office supplies and materials consumed in the business.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099"],
        "common_questions": [
            {"field": "supply_categories", "question": "What supplies did you purchase?", "help": "Paper, ink, postage, small tools, and similar items."},
            {"field": "total_cost", "question": "Total spent on supplies?", "help": "Keep receipts for items over $75."},
        ],
        "documentation_required": ["Receipts", "Bank or card statements"],
    },
    {
        "category": "utilities",
        "description": "Business portion of utilities for a home office or commercial space.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099"],
        "common_questions": [
            {"field": "annual_utilities", "question": "Annual electric, gas, water, and trash costs?", "help": "For a home office, apply the business-use percentage."},
        ],
        "documentation_required": ["Utility bills", "Business-use percentage calculation"],
    },
    {
        "category": "internet",
        "description": "Business portion of internet service.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099"],
        "common_questions": [
            {"field": "annual_internet", "question": "Annual internet expense?", "help": "Deduct only the business-use percentage."},
            {"field": "business_use_percent", "question": "Estimated business-use percentage?", "help": "A reasonable allocation is required."},
        ],
        "documentation_required": ["Internet bills", "Business-use allocation"],
    },
    {
        "category": "phone",
        "description": "Business portion of phone service.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099"],
        "common_questions": [
            {"field": "annual_phone", "question": "Annual phone expense?", "help": "The first phone line to your home is generally not deductible."},
            {"field": "business_use_percent", "question": "Estimated business-use percentage?", "help": "Use call logs or a reasonable allocation."},
        ],
        "documentation_required": ["Phone bills", "Business-use allocation"],
    },
    {
        "category": "business_insurance",
        "description": "Business liability, property, and malpractice insurance.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099", "rental"],
        "common_questions": [
            {"field": "premium_amount", "question": "Annual business insurance premiums?", "help": "Includes liability, property, and malpractice coverage."},
        ],
        "documentation_required": ["Insurance declarations page", "Premium receipts"],
    },
    {
        "category": "advertising",
        "description": "Marketing, advertising, and website costs.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099"],
        "common_questions": [
            {"field": "total_ad_spend", "question": "Total advertising and marketing spend?", "help": "Includes ads, SEO, design, and promotional materials."},
        ],
        "documentation_required": ["Invoices", "Ad platform statements"],
    },
    {
        "category": "travel",
        "description": "Lodging and travel expenses away from your tax home.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099"],
        "common_questions": [
            {"field": "travel_destinations", "question": "Where did you travel for business?", "help": "Trips must be primarily business-related."},
            {"field": "total_travel_cost", "question": "Total airfare, lodging, and related costs?", "help": "Meals are subject to the 50% limit."},
        ],
        "documentation_required": ["Itinerary", "Flight and hotel receipts", "Business purpose"],
    },
    {
        "category": "education",
        "description": "Education that maintains or improves skills in your current business.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099", "w2"],
        "common_questions": [
            {"field": "course_name", "question": "What course or certification did you complete?", "help": "Education required to enter a new profession is generally not deductible."},
            {"field": "total_cost", "question": "Total tuition and materials cost?", "help": "Books, supplies, and tuition may qualify."},
        ],
        "documentation_required": ["Tuition receipts", "Course description", "Certificate"],
    },
    {
        "category": "rent",
        "description": "Rent for business property or coworking space.",
        "max_amount": None,
        "percentage_limit": None,
        "limit_basis": "net_profit",
        "irs_code": "IRC 162",
        "deduction_type": "business",
        "income_types": ["self_employed", "1099"],
        "common_questions": [
            {"field": "monthly_rent", "question": "Monthly rent for business space?", "help": "Home rent is handled through the home office deduction."},
        ],
        "documentation_required": ["Lease agreement", "Rent receipts"],
    },
    {
        "category": "charitable",
        "description": "Charitable contributions (itemized).",
        "max_amount": None,
        "percentage_limit": 0.60,
        "limit_basis": "gross_income",
        "irs_code": "IRC 170",
        "deduction_type": "itemized",
        "income_types": ["w2", "self_employed", "1099", "rental"],
        "common_questions": [
            {"field": "organization", "question": "Which qualified organization did you donate to?", "help": "Must be a 501(c)(3) or similar qualified organization."},
            {"field": "amount", "question": "How much did you contribute?", "help": "Cash donations up to 60% of AGI may qualify."},
        ],
        "documentation_required": ["Written acknowledgment", "Bank records", "Form 8283 for noncash gifts over $500"],
    },
    {
        "category": "mortgage_interest",
        "description": "Home mortgage interest (itemized).",
        "max_amount": 750000,
        "percentage_limit": None,
        "limit_basis": "absolute",
        "irs_code": "IRC 163(h)",
        "deduction_type": "itemized",
        "income_types": ["w2", "self_employed", "1099", "rental"],
        "common_questions": [
            {"field": "interest_paid", "question": "How much mortgage interest did you pay?", "help": "Reported on Form 1098."},
            {"field": "loan_balance", "question": "What is your mortgage balance?", "help": "Deductible acquisition debt is capped at $750,000."},
        ],
        "documentation_required": ["Form 1098", "Mortgage statement"],
    },
    {
        "category": "state_taxes",
        "description": "State and local income or sales taxes paid (itemized, SALT cap).",
        "max_amount": 10000,
        "percentage_limit": None,
        "limit_basis": "absolute",
        "irs_code": "IRC 164",
        "deduction_type": "itemized",
        "income_types": ["w2", "self_employed", "1099", "rental"],
        "common_questions": [
            {"field": "state_income_tax", "question": "State and local income tax paid?", "help": "SALT deductions are capped at $10,000."},
            {"field": "property_tax", "question": "Property tax paid?", "help": "Counts toward the same SALT cap."},
        ],
        "documentation_required": ["State tax returns", "Property tax bill"],
    },
]

DEDUCTION_QUESTIONNAIRE = {
    "self_employed": ["home_office", "vehicle", "meals", "professional_services", "health_insurance", "retirement", "equipment", "supplies", "utilities", "internet", "phone", "business_insurance", "advertising", "travel", "education", "rent"],
    "1099": ["home_office", "vehicle", "meals", "professional_services", "health_insurance", "retirement", "equipment", "supplies", "internet", "phone", "advertising", "travel", "education"],
    "w2": ["professional_services", "meals", "education", "charitable", "mortgage_interest", "state_taxes"],
    "rental": ["professional_services", "business_insurance", "charitable", "mortgage_interest", "state_taxes"],
}


def deduction_questionnaire(income_type: str = "self_employed", rules: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Return the questionnaire sections relevant to a taxpayer's income type."""
    rules = rules or DEFAULT_DEDUCTION_RULES
    by_category = {rule["category"]: rule for rule in rules}
    categories = DEDUCTION_QUESTIONNAIRE.get(income_type, DEDUCTION_QUESTIONNAIRE["self_employed"])
    sections = []
    for index, category in enumerate(categories):
        rule = by_category.get(category)
        if not rule:
            continue
        sections.append({
            "step": index + 1,
            "category": category,
            "title": category.replace("_", " ").title(),
            "description": rule["description"],
            "irs_code": rule.get("irs_code"),
            "max_amount": rule.get("max_amount"),
            "percentage_limit": rule.get("percentage_limit"),
            "limit_basis": rule.get("limit_basis", "absolute"),
            "questions": rule.get("common_questions") or [],
            "documentation_required": rule.get("documentation_required") or [],
            "estimated_savings_rate": 0.30 if rule.get("deduction_type") == "business" else 0.22,
        })
    return {
        "income_type": income_type,
        "total_steps": len(sections),
        "sections": sections,
        "disclaimer": DISCLAIMER,
    }


def validate_deduction(category: str, amount: float, gross_income: float = 0.0, net_profit: float = 0.0, rule: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate a deduction amount against the matching IRS rule."""
    amount = max(0.0, float(amount or 0))
    if not rule:
        return {"valid": True, "allowed_amount": round(amount, 2), "warnings": [], "rule_found": False}

    warnings = []
    allowed = amount
    basis_value = gross_income
    if rule.get("limit_basis") == "net_profit":
        basis_value = net_profit or gross_income
    if rule.get("percentage_limit") is not None:
        percentage_cap = max(0.0, basis_value) * float(rule["percentage_limit"])
        if amount > percentage_cap:
            allowed = min(allowed, percentage_cap) if rule.get("max_amount") is None else allowed
            warnings.append(
                f"{category} is limited to {rule['percentage_limit']:.0%} of {rule.get('limit_basis', 'gross income')} "
                f"(${percentage_cap:,.2f})."
            )
    if rule.get("max_amount") is not None and amount > float(rule["max_amount"]):
        allowed = min(allowed, float(rule["max_amount"]))
        warnings.append(f"{category} has an IRS cap of ${rule['max_amount']:,.2f}.")
    if amount > max(gross_income, net_profit, 0) and max(gross_income, net_profit, 0) > 0:
        warnings.append("Deduction exceeds reported income; ensure it is a legitimate business expense.")

    return {
        "valid": len([w for w in warnings if "exceeds" not in w]) == 0,
        "allowed_amount": round(max(0.0, allowed), 2),
        "requested_amount": round(amount, 2),
        "warnings": warnings,
        "rule_found": True,
        "irs_code": rule.get("irs_code"),
    }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value[:10], fmt).date()
            except ValueError:
                continue
    return None


def return_progress(*, forms: List[dict], deductions: List[dict], status: str) -> Dict[str, Any]:
    """Compute a completion percentage for dashboard timelines."""
    form_completed = sum(1 for f in forms if f.get("completed_bool") or f.get("completed"))
    total_steps = max(1, len(forms) + 2)
    completed_steps = form_completed + (1 if deductions else 0) + (1 if status in ("ready_to_file", "filed", "accepted") else 0)
    return {
        "completed_forms": form_completed,
        "total_forms": len(forms),
        "deductions_claimed": len(deductions),
        "percent_complete": min(100, round(completed_steps / total_steps * 100)),
    }
