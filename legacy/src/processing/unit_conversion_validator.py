#!/usr/bin/env python3
"""
Unit Conversion Validator
Ensures container unit conversions are not inverted
"""

from typing import Dict, List, Tuple
import logging

class UnitConversionValidator:
    """Validates and fixes unit conversion factors to prevent inversion"""

    # Container units that should typically have values > 1.0
    CONTAINER_UNITS = {
        'can', 'jar', 'bottle', 'package', 'box', 'bag', 'container',
        'carton', 'tub', 'packet', 'pouch', 'tin', 'flask'
    }

    # Typical ranges for common container conversions
    TYPICAL_RANGES = {
        'can': (8, 32),      # 8-32 oz typical for cans
        'jar': (8, 64),      # 8-64 oz typical for jars
        'bottle': (8, 128),  # 8-128 oz typical for bottles
        'package': (4, 64),  # varies widely
        'box': (8, 64),      # varies widely
        'bag': (8, 160),     # varies widely (up to 10 lbs = 160 oz)
        'container': (8, 64),
        'carton': (16, 64),  # typically larger
        'tub': (8, 64),
        'packet': (0.5, 4),  # smaller units
        'pouch': (2, 16),
        'tin': (4, 32),
        'flask': (8, 32)
    }

    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)

    def validate_conversion(self, unit: str, value: float, cost_unit: str,
                          ingredient_name: str = "") -> Tuple[bool, str, float]:
        """
        Validate a single unit conversion value

        Args:
            unit: The unit being converted from (e.g., "can")
            value: The conversion factor (how many cost_units in 1 unit)
            cost_unit: The target unit (e.g., "oz", "tablespoon")
            ingredient_name: Optional ingredient name for context

        Returns:
            Tuple of (is_valid, error_message, suggested_value)
        """
        # Check if it's a container unit
        if unit.lower() not in self.CONTAINER_UNITS:
            return (True, "", value)  # Not a container, no validation needed

        # Container units should almost never be < 1.0 when converting to smaller units
        if value < 1.0 and cost_unit.lower() in ['oz', 'ounce', 'g', 'gram',
                                                  'tablespoon', 'tbsp', 'teaspoon',
                                                  'tsp', 'ml', 'milliliter']:
            # This is likely inverted!
            suggested_value = 1.0 / value if value > 0 else 14.0  # Default to 14 oz for cans

            error_msg = (f"⚠️ INVERTED CONVERSION DETECTED: {unit} = {value} {cost_unit}\n"
                        f"   This means 1 {unit} = {value} {cost_unit} (way too small!)\n"
                        f"   Suggested correction: 1 {unit} = {suggested_value:.1f} {cost_unit}")

            if ingredient_name:
                error_msg += f" for '{ingredient_name}'"

            return (False, error_msg, suggested_value)

        # Check if value is within typical range (warning only)
        unit_lower = unit.lower()
        if unit_lower in self.TYPICAL_RANGES:
            min_val, max_val = self.TYPICAL_RANGES[unit_lower]

            # Adjust range based on cost_unit
            if cost_unit.lower() in ['tablespoon', 'tbsp']:
                # Convert oz ranges to tablespoons (1 oz = 2 tbsp)
                min_val *= 2
                max_val *= 2
            elif cost_unit.lower() in ['teaspoon', 'tsp']:
                # Convert oz ranges to teaspoons (1 oz = 6 tsp)
                min_val *= 6
                max_val *= 6
            elif cost_unit.lower() in ['g', 'gram', 'grams']:
                # Convert oz ranges to grams (1 oz = 28.35g)
                min_val *= 28.35
                max_val *= 28.35

            if value < min_val * 0.1:  # Way too small (likely inverted)
                suggested_value = min_val  # Use minimum typical value
                error_msg = (f"⚠️ SUSPICIOUS CONVERSION: {unit} = {value} {cost_unit}\n"
                           f"   Expected range: {min_val:.1f}-{max_val:.1f} {cost_unit}\n"
                           f"   This appears to be inverted. Suggested: {suggested_value:.1f}")
                return (False, error_msg, suggested_value)

        return (True, "", value)

    def validate_all_conversions(self, conversions: Dict[str, float],
                                cost_unit: str, ingredient_name: str = "") -> Dict[str, float]:
        """
        Validate and fix all unit conversions for an ingredient

        Args:
            conversions: Dictionary of unit conversions
            cost_unit: The base cost unit
            ingredient_name: Optional ingredient name for context

        Returns:
            Fixed dictionary of unit conversions
        """
        fixed_conversions = {}
        fixes_made = []

        for unit, value in conversions.items():
            is_valid, error_msg, suggested_value = self.validate_conversion(
                unit, value, cost_unit, ingredient_name
            )

            if not is_valid:
                self.logger.warning(error_msg)
                fixes_made.append(f"{unit}: {value} → {suggested_value:.2f}")
                fixed_conversions[unit] = suggested_value
            else:
                fixed_conversions[unit] = value

        if fixes_made:
            self.logger.info(f"✅ Fixed {len(fixes_made)} inverted conversions for '{ingredient_name}':")
            for fix in fixes_made:
                self.logger.info(f"   {fix}")

        return fixed_conversions

    def detect_inverted_pattern(self, conversions: Dict[str, float]) -> bool:
        """
        Detect if conversions show a pattern of inversion

        Args:
            conversions: Dictionary of unit conversions

        Returns:
            True if inversions are detected
        """
        container_values = []

        for unit, value in conversions.items():
            if unit.lower() in self.CONTAINER_UNITS:
                container_values.append(value)

        if not container_values:
            return False

        # If most container values are < 1.0, likely inverted
        inverted_count = sum(1 for v in container_values if v < 1.0)

        return inverted_count > len(container_values) / 2


def quick_fix_conversion(unit: str, value: float, cost_unit: str) -> float:
    """
    Quick function to fix obviously inverted conversions

    Args:
        unit: The unit being converted from
        value: Current conversion value
        cost_unit: The target unit

    Returns:
        Fixed conversion value
    """
    validator = UnitConversionValidator()
    is_valid, _, suggested_value = validator.validate_conversion(unit, value, cost_unit)

    if not is_valid:
        print(f"🔧 Fixing inverted conversion: {unit} = {value} → {suggested_value:.2f} {cost_unit}")
        return suggested_value

    return value


if __name__ == "__main__":
    # Test the validator
    print("🧪 Testing Unit Conversion Validator")
    print("=" * 60)

    validator = UnitConversionValidator()

    # Test cases
    test_cases = [
        # (unit, value, cost_unit, ingredient_name)
        ("can", 0.04, "oz", "artichoke hearts"),  # Inverted!
        ("can", 14.0, "oz", "diced tomatoes"),    # Correct
        ("jar", 0.03, "oz", "pasta sauce"),       # Inverted!
        ("jar", 24.0, "oz", "pasta sauce"),       # Correct
        ("bottle", 32.0, "tablespoon", "honey"),  # Correct
        ("package", 0.0625, "oz", "pasta"),       # Inverted! (1/16)
        ("bag", 80.0, "cup", "flour"),            # Correct
        ("cup", 8.0, "oz", "water"),              # Not a container unit
    ]

    print("\n📋 Test Results:")
    for unit, value, cost_unit, ingredient in test_cases:
        is_valid, error_msg, suggested = validator.validate_conversion(
            unit, value, cost_unit, ingredient
        )

        if is_valid:
            print(f"✅ VALID: {unit} = {value} {cost_unit} for '{ingredient}'")
        else:
            print(f"❌ INVALID: {unit} = {value} {cost_unit} for '{ingredient}'")
            print(f"   Suggested: {unit} = {suggested:.2f} {cost_unit}")

    print("\n" + "=" * 60)

    # Test full conversion fix
    print("\n🔧 Testing Full Conversion Fix:")
    bad_conversions = {
        "cup": 8.35,
        "can": 0.04,  # Inverted!
        "g": 0.035274,
        "oz": 1.0,
        "jar": 0.03   # Inverted!
    }

    print(f"Original: {bad_conversions}")
    fixed = validator.validate_all_conversions(bad_conversions, "oz", "test ingredient")
    print(f"Fixed: {fixed}")

    print("\n✅ Validator ready for use!")