#!/usr/bin/env python3
"""Fix artichoke heart unit conversion in production database"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.database_direct import DatabaseDirectConnection
from dotenv import load_dotenv

# Load production environment
env_path = Path(__file__).parent.parent / "local.env.production"
if env_path.exists():
    load_dotenv(env_path)
else:
    print("❌ Production environment file not found")
    sys.exit(1)

def fix_artichoke_conversion():
    """Fix the artichoke heart unit conversion"""

    # Connect to production database
    db = DatabaseDirectConnection(use_production=True)

    try:
        # Get current data
        query = """
        SELECT id, name, purchase_info, unit_conversions
        FROM global_ingredients
        WHERE id = 'd2ke039peops73cbving'
        """

        results = db.execute_query(query)
        if not results:
            print("❌ Artichoke heart ingredient not found")
            return

        ingredient = results[0]
        print(f"Found ingredient: {ingredient['name']}")
        print(f"Current purchase_info: {ingredient['purchase_info']}")
        print(f"Current unit_conversions: {ingredient['unit_conversions']}")

        # Parse purchase info to verify can size
        purchase_info = json.loads(ingredient['purchase_info']) if ingredient['purchase_info'] else {}
        purchase_quantity = purchase_info.get('purchase_quantity', 14)
        print(f"\nPurchase quantity from purchase_info: {purchase_quantity} oz")

        # Fix the unit conversions
        # 1 can = 14 oz (not 0.04 oz)
        # Keep other conversions as-is
        new_conversions = {
            "cup": 8.35,  # Keep existing
            "can": purchase_quantity,  # Fix: 1 can = 14 oz
            "g": 0.035274,  # 1 g = 0.035274 oz (28.35 g per oz)
            "oz": 1.0,
            "ounce": 1.0
        }

        print(f"\nNew unit_conversions: {json.dumps(new_conversions, indent=2)}")

        # Update the database
        update_query = """
        UPDATE global_ingredients
        SET unit_conversions = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING id, name, unit_conversions
        """

        updated = db.execute_query(
            update_query,
            (json.dumps(new_conversions), ingredient['id'])
        )

        if updated:
            print(f"\n✅ Successfully updated artichoke heart unit conversions")
            print(f"Updated conversions: {updated[0]['unit_conversions']}")
        else:
            print("❌ Failed to update ingredient")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_artichoke_conversion()