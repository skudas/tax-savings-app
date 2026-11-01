"""
Transaction categorization logic with keyword matching.

Suggests categories for transactions based on description matching.
"""

from typing import Optional, List, Tuple


class TransactionCategorizer:
    """Simple keyword-based transaction categorizer."""

    # Default category keywords mapping
    DEFAULT_KEYWORDS = {
        "income": {
            "revenue": ["stripe", "paypal", "square", "invoice", "payment received", "deposit"],
            "sales": ["sale", "sold", "customer", "client"],
            "consulting": ["consulting", "retainer", "hourly", "contract work"],
            "other_income": ["refund", "reimbursement", "returned", "credit", "income"],
        },
        "expense": {
            "office_supplies": ["office", "supplies", "paper", "pens", "ink", "stapler"],
            "software": ["software", "saas", "subscription", "github", "slack", "zoom", "microsoft", "adobe"],
            "professional_services": ["accounting", "lawyer", "consulting", "professional", "service fee"],
            "travel": ["hotel", "airline", "flight", "rental car", "uber", "taxi", "travel", "gas", "parking"],
            "meals": ["restaurant", "coffee", "lunch", "dinner", "meal", "food", "catering"],
            "utilities": ["electric", "water", "gas", "internet", "phone", "utility"],
            "rent": ["rent", "lease", "office space"],
            "insurance": ["insurance", "premium"],
            "advertising": ["ads", "advertising", "marketing", "google ads", "facebook ads"],
            "equipment": ["equipment", "computer", "laptop", "monitor", "keyboard", "mouse", "desk", "printer"],
            "training": ["course", "training", "education", "conference", "workshop"],
            "other_expense": ["expense", "cost", "payment"],
        }
    }

    def __init__(self, custom_keywords: Optional[dict] = None):
        """
        Initialize categorizer with keywords.

        Args:
            custom_keywords: Optional custom keywords dict to override defaults
        """
        if custom_keywords:
            self.keywords = custom_keywords
        else:
            self.keywords = self.DEFAULT_KEYWORDS

    def suggest_category(
        self,
        description: str,
        category_type: str = "all"
    ) -> Optional[Tuple[str, float]]:
        """
        Suggest a category for a transaction based on description.

        Args:
            description: Transaction description (e.g., "Stripe payment for invoice")
            category_type: Filter by type: "income", "expense", or "all"

        Returns:
            Tuple of (category_name, confidence_score) or None if no match
        """
        description_lower = description.lower()
        best_match = None
        best_score = 0

        # Determine which types to search
        if category_type == "all":
            types_to_search = ["income", "expense"]
        else:
            types_to_search = [category_type]

        # Search keywords
        for type_key in types_to_search:
            if type_key not in self.keywords:
                continue

            for category, keywords in self.keywords[type_key].items():
                for keyword in keywords:
                    if keyword.lower() in description_lower:
                        # Score based on keyword specificity and position
                        score = self._calculate_score(description_lower, keyword)
                        if score > best_score:
                            best_score = score
                            best_match = category

        if best_match and best_score > 0:
            return (best_match, min(best_score, 1.0))

        return None

    @staticmethod
    def _calculate_score(description: str, keyword: str) -> float:
        """
        Calculate confidence score for a keyword match.

        Factors:
        - Exact matches score higher
        - Matches at start score higher
        - Length of keyword (longer = more specific)
        """
        keyword_lower = keyword.lower()

        if keyword_lower == description:
            return 1.0

        if keyword_lower in description:
            # Position: match at start scores higher
            position = description.find(keyword_lower)
            position_score = max(0.5, 1.0 - (position / len(description)))

            # Length: longer keywords are more specific
            length_score = min(len(keyword) / 20, 1.0)  # Normalize to 20 chars

            return (position_score + length_score) / 2

        return 0

    @staticmethod
    def categorize_amount(amount: float) -> str:
        """
        Infer income vs expense from transaction amount.

        Args:
            amount: Transaction amount (positive or negative)

        Returns:
            "income" or "expense"
        """
        return "income" if amount > 0 else "expense"

    def get_default_categories(self) -> List[Tuple[str, str]]:
        """
        Get list of all available default categories.

        Returns:
            List of (category_name, type) tuples
        """
        categories = []
        for type_key in ["income", "expense"]:
            if type_key in self.keywords:
                for category in self.keywords[type_key].keys():
                    categories.append((category, type_key))
        return categories
