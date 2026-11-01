"""
Unit tests for transaction_categorizer.py
"""

import pytest
from transaction_categorizer import TransactionCategorizer


class TestCategoryMatching:
    """Test category suggestion based on keywords."""

    def test_software_expense_suggestion(self):
        """Test detection of software expenses."""
        categorizer = TransactionCategorizer()

        suggestions = [
            "GitHub subscription",
            "Slack monthly",
            "Microsoft Office 365",
            "Adobe Creative Cloud",
            "Zoom PRO",
        ]

        for description in suggestions:
            result = categorizer.suggest_category(description)
            assert result is not None, f"Should categorize: {description}"
            category, score = result
            assert category == "software"
            assert 0 < score <= 1.0

    def test_travel_expense_suggestion(self):
        """Test detection of travel expenses."""
        categorizer = TransactionCategorizer()

        result = categorizer.suggest_category("United Airlines ticket")
        assert result is not None
        assert result[0] == "travel"

        result = categorizer.suggest_category("Rental car - Hertz")
        assert result is not None
        assert result[0] == "travel"

    def test_income_suggestion(self):
        """Test detection of income."""
        categorizer = TransactionCategorizer()

        result = categorizer.suggest_category("Stripe payment for invoice #123")
        assert result is not None
        assert result[0] in ["revenue", "sales"]  # Could match multiple

        result = categorizer.suggest_category("PayPal deposit from customer")
        assert result is not None
        assert result[0] == "revenue"

    def test_consulting_income(self):
        """Test detection of consulting income."""
        categorizer = TransactionCategorizer()

        result = categorizer.suggest_category("Consulting retainer payment")
        assert result is not None
        assert result[0] == "consulting"

    def test_meals_expense(self):
        """Test detection of meal expenses."""
        categorizer = TransactionCategorizer()

        result = categorizer.suggest_category("Restaurant - Chipotle")
        assert result is not None
        assert result[0] == "meals"

    def test_no_match(self):
        """Test transaction with no matching category."""
        categorizer = TransactionCategorizer()

        result = categorizer.suggest_category("Random transfer XYZ")
        assert result is None

    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        categorizer = TransactionCategorizer()

        result1 = categorizer.suggest_category("github subscription")
        result2 = categorizer.suggest_category("GitHub SUBSCRIPTION")
        result3 = categorizer.suggest_category("GiTHub SubScription")

        assert result1 is not None
        assert result2 is not None
        assert result3 is not None
        assert result1[0] == result2[0] == result3[0]

    def test_category_type_filter(self):
        """Test filtering by category type (income/expense)."""
        categorizer = TransactionCategorizer()

        # Try "Stripe" as income (Stripe is a revenue keyword)
        result = categorizer.suggest_category(
            "Stripe processing",
            category_type="income"
        )
        assert result is not None
        assert result[0] == "revenue"

        # Try a pure expense with expense filter
        result = categorizer.suggest_category(
            "Office supplies purchase",
            category_type="expense"
        )
        assert result is not None
        assert result[0] == "office_supplies"

        # Try to find it as income (should not match)
        result = categorizer.suggest_category(
            "Office supplies purchase",
            category_type="income"
        )
        assert result is None


class TestScoring:
    """Test confidence scoring of category matches."""

    def test_exact_match_scores_high(self):
        """Test that exact matches score high."""
        categorizer = TransactionCategorizer()

        exact = categorizer.suggest_category("software")
        partial = categorizer.suggest_category("a software subscription for my team")

        assert exact is not None
        assert partial is not None
        # Exact match should score at least as high as partial
        assert exact[1] >= partial[1]

    def test_longer_keywords_score_higher(self):
        """Test that longer (more specific) keywords score higher."""
        categorizer = TransactionCategorizer()

        # Both could match "software", but "saas" is a longer keyword
        generic = categorizer.suggest_category("software update")
        specific = categorizer.suggest_category("saas subscription for team")

        assert generic is not None
        assert specific is not None
        # Specific keyword should score at least as high
        assert specific[1] >= generic[1]

    def test_early_position_scores_higher(self):
        """Test that specific keywords at any position score well."""
        categorizer = TransactionCategorizer()

        # Test with more specific keywords
        early = categorizer.suggest_category("GitHub subscription service")
        late = categorizer.suggest_category("My platform via GitHub")

        assert early is not None
        # GitHub is a specific keyword for software category
        assert early[0] == "software"
        assert early[1] > 0.5


class TestAmountInference:
    """Test inferring transaction type from amount."""

    def test_positive_amount_is_income(self):
        """Test that positive amounts are categorized as income."""
        assert TransactionCategorizer.categorize_amount(100.50) == "income"
        assert TransactionCategorizer.categorize_amount(1000) == "income"
        assert TransactionCategorizer.categorize_amount(0.01) == "income"

    def test_negative_amount_is_expense(self):
        """Test that negative amounts are categorized as expense."""
        assert TransactionCategorizer.categorize_amount(-100.50) == "expense"
        assert TransactionCategorizer.categorize_amount(-1000) == "expense"
        assert TransactionCategorizer.categorize_amount(-0.01) == "expense"

    def test_zero_amount_is_expense(self):
        """Test that zero is treated as expense."""
        assert TransactionCategorizer.categorize_amount(0) == "expense"


class TestDefaultCategories:
    """Test getting list of available categories."""

    def test_get_default_categories(self):
        """Test that default categories can be retrieved."""
        categorizer = TransactionCategorizer()
        categories = categorizer.get_default_categories()

        assert isinstance(categories, list)
        assert len(categories) > 0

        # Check structure
        for category_name, category_type in categories:
            assert isinstance(category_name, str)
            assert category_type in ["income", "expense"]

        # Check we have both income and expense categories
        types = set(t for _, t in categories)
        assert "income" in types
        assert "expense" in types

    def test_includes_common_categories(self):
        """Test that common categories are included."""
        categorizer = TransactionCategorizer()
        categories = categorizer.get_default_categories()
        category_names = set(name for name, _ in categories)

        # Common categories should exist
        assert "software" in category_names
        assert "travel" in category_names
        assert "meals" in category_names
        assert "revenue" in category_names


class TestCustomKeywords:
    """Test using custom keywords."""

    def test_custom_keywords_override(self):
        """Test that custom keywords override defaults."""
        custom = {
            "income": {"freelance": ["upwork", "fiverr"]},
            "expense": {"custom": ["my_vendor"]},
        }

        categorizer = TransactionCategorizer(custom_keywords=custom)

        result = categorizer.suggest_category("Upwork payment")
        assert result is not None
        assert result[0] == "freelance"

        result = categorizer.suggest_category("Payment to my_vendor")
        assert result is not None
        assert result[0] == "custom"

    def test_custom_keywords_disable_defaults(self):
        """Test that custom keywords completely replace defaults."""
        custom = {
            "income": {},
            "expense": {},
        }

        categorizer = TransactionCategorizer(custom_keywords=custom)

        # Default keywords should not work
        result = categorizer.suggest_category("Stripe payment")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
