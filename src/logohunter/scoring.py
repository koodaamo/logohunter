"""Rule-based scoring system for logo detection."""

import importlib
import logging
from pathlib import Path
from typing import Callable, List, Tuple, Dict
from PIL import Image


logger = logging.getLogger(__name__)


class ScoringEngine:
    """Main scoring engine that loads and applies all scoring rules."""

    def __init__(self):
        self.rules: List[Tuple[Callable, str, int]] = []
        self.rule_values: Dict[str, int] = {}
        self._load_all_rules()

    def _load_all_rules(self):
        """Load all scoring rules from the rules directory."""
        rules_dir = Path(__file__).parent / "rules"

        for category_dir in rules_dir.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("__"):
                continue

            category_name = category_dir.name

            # Load bonus values and rules
            bonus_values_file = category_dir / "bonuses.txt"
            if bonus_values_file.exists():
                bonus_values = self._load_rule_values(bonus_values_file)
                self.rule_values.update(bonus_values)

                bonus_module_path = f"logo_hunter.rules.{category_name}.bonus"
                try:
                    bonus_module = importlib.import_module(bonus_module_path)
                    self._load_rules_from_module(
                        bonus_module, category_name, "bonus", bonus_values
                    )
                except ImportError as e:
                    logger.debug(
                        f"Could not load bonus rules from {bonus_module_path}: {e}"
                    )

            # Load penalty values and rules
            penalty_values_file = category_dir / "penalties.txt"
            if penalty_values_file.exists():
                penalty_values = self._load_rule_values(penalty_values_file)
                self.rule_values.update(penalty_values)

                penalty_module_path = f"logo_hunter.rules.{category_name}.penalty"
                try:
                    penalty_module = importlib.import_module(penalty_module_path)
                    self._load_rules_from_module(
                        penalty_module, category_name, "penalty", penalty_values
                    )
                except ImportError as e:
                    logger.debug(
                        f"Could not load penalty rules from {penalty_module_path}: {e}"
                    )

    def _load_rule_values(self, values_file: Path) -> Dict[str, int]:
        """Load rule values from a text file."""
        values = {}
        try:
            with open(values_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split(None, 1)  # Split on first whitespace
                        if len(parts) == 2:
                            value, function_name = parts
                            values[function_name] = int(value)
        except Exception as e:
            logger.warning(f"Could not load rule values from {values_file}: {e}")
        return values

    def _load_rules_from_module(
        self, module, category: str, rule_type: str, rule_values: Dict[str, int]
    ):
        """Load all rule functions from a module."""
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue

            attr = getattr(module, attr_name)
            if (
                callable(attr)
                and hasattr(attr, "__doc__")
                and hasattr(attr, "__module__")
                and attr.__module__ == module.__name__
            ):
                # Use the function's docstring as the rule description
                description = attr.__doc__.strip() if attr.__doc__ else attr_name
                rule_label = f"{category}/{rule_type}: {description}"
                rule_value = rule_values.get(attr_name, 0)
                self.rules.append((attr, rule_label, rule_value))
                logger.debug(f"Loaded rule: {rule_label} (value: {rule_value})")

    def calculate_score(
        self,
        img: Image.Image,
        width: int,
        height: int,
        url: str,
        alt_text: str,
        css_classes: str,
        element_id: str,
        parent_classes: List[str],
        **kwargs,
    ) -> Tuple[int, List[Tuple[str, int]]]:
        """
        Calculate cumulative score by applying all rules.

        Returns:
            Tuple of (total_score, rule_details) where rule_details is a list
            of (rule_name, score_contribution) tuples for debugging/logging.
        """
        total_score = 0
        rule_details = []

        for rule_func, rule_label, rule_value in self.rules:
            try:
                # Call rule function to check if it applies (returns boolean or multiplier)
                rule_applies = rule_func(
                    img=img,
                    width=width,
                    height=height,
                    url=url,
                    alt_text=alt_text,
                    css_classes=css_classes,
                    element_id=element_id,
                    parent_classes=parent_classes,
                    **kwargs,
                )

                # Calculate actual score contribution
                if isinstance(rule_applies, bool):
                    score_contribution = rule_value if rule_applies else 0
                elif isinstance(rule_applies, (int, float)):
                    score_contribution = int(rule_value * rule_applies)
                else:
                    score_contribution = 0

                if score_contribution != 0:
                    total_score += score_contribution
                    rule_details.append((rule_label, score_contribution))
                    logger.debug(
                        f"Rule '{rule_label}' contributed {score_contribution} points"
                    )

            except Exception as e:
                logger.warning(f"Error applying rule '{rule_label}': {e}")
                continue

        return total_score, rule_details


# Global scoring engine instance
_scoring_engine = None


def get_scoring_engine() -> ScoringEngine:
    """Get the global scoring engine instance (singleton pattern)."""
    global _scoring_engine
    if _scoring_engine is None:
        _scoring_engine = ScoringEngine()
    return _scoring_engine
