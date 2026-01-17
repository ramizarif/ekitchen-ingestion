#!/usr/bin/env python3
"""
Ambiguous Step Match Resolution Script

This script connects to the production database, fetches unresolved ambiguous step matches,
and uses OpenAI API to intelligently resolve them by analyzing the step context and
possible ingredient matches.

The script analyzes the full step text, ambiguous word, and possible matches to determine
the most contextually appropriate ingredient reference.

Usage:
    python resolve_ambiguous_step_matches.py --dry-run    # Preview resolutions without saving
    python resolve_ambiguous_step_matches.py --live       # Actually resolve matches
    python resolve_ambiguous_step_matches.py --limit 10   # Process only 10 matches
    python resolve_ambiguous_step_matches.py --match-id d2jv43o5vf6c73cbr180  # Resolve specific match
"""

import sys
import os
import argparse
import json
import time
import requests
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from openai import OpenAI

# Add the processing directory to path for reusing existing classes
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'processing'))
from ingredient_processor_direct import DirectIngredientProcessor

@dataclass
class AmbiguousStepMatch:
    """Data structure for ambiguous step match information"""
    id: str
    recipe_id: str
    step_position: int
    template: str
    ingredient_refs: List[str]
    ambiguous_word: str
    possible_matches: List[str]
    resolved_match: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: Optional[str] = None

class AmbiguousStepMatchResolver:
    """Resolves ambiguous step matches using AI analysis"""

    def __init__(self):
        print("🔧 Initializing ambiguous step match resolver...")

        # Initialize ingredient processor for environment config
        self.ingredient_processor = DirectIngredientProcessor()

        # Initialize OpenAI for AI resolution
        try:
            # Load OpenAI API key from environment config
            env_config = self.ingredient_processor._load_env_config()
            openai_api_key = env_config.get('OPENAI_API_KEY', '')

            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found in environment configuration")

            self.openai_client = OpenAI(api_key=openai_api_key)
            print("✅ OpenAI client initialized")
        except Exception as e:
            print(f"❌ Failed to initialize OpenAI: {e}")
            raise

        print(f"✅ Ingredient processor initialized")

    def authenticate(self) -> bool:
        """Authenticate with eKitchen API"""
        print("🔐 Authenticating with eKitchen...")

        # Load configuration
        env_config = self.ingredient_processor._load_env_config()
        admin_email = env_config.get('EKITCHEN_ADMIN_EMAIL', '')
        admin_password = env_config.get('EKITCHEN_ADMIN_PASSWORD', '')

        success = self.ingredient_processor.authenticate_ekitchen(admin_email, admin_password)
        if success:
            print("✅ eKitchen authentication successful")
            return True
        else:
            print("❌ eKitchen authentication failed")
            return False

    def get_unresolved_matches(self, limit: int = 50, offset: int = 0) -> List[AmbiguousStepMatch]:
        """Fetch unresolved ambiguous step matches from the API"""
        try:
            url = f"{self.ingredient_processor.ekitchen_base_url}/global-recipes/ambiguous-step-matches"
            headers = {
                "Authorization": f"Bearer {self.ingredient_processor.access_token}",
                "Content-Type": "application/json"
            }

            params = {
                "limit": limit,
                "offset": offset
            }

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            matches_data = response.json()
            matches = []

            for match_data in matches_data:
                # Only include matches that are not resolved
                if not match_data.get('resolved_match'):
                    match = AmbiguousStepMatch(
                        id=match_data['id'],
                        recipe_id=match_data['recipe_id'],
                        step_position=match_data['step_position'],
                        template=match_data['template'],
                        ingredient_refs=match_data.get('ingredient_refs', []),
                        ambiguous_word=match_data['ambiguous_word'],
                        possible_matches=match_data['possible_matches'],
                        resolved_match=match_data.get('resolved_match'),
                        resolved_at=match_data.get('resolved_at'),
                        created_at=match_data.get('created_at')
                    )
                    matches.append(match)

            print(f"📋 Found {len(matches)} unresolved ambiguous step matches")
            return matches

        except Exception as e:
            print(f"❌ Error fetching ambiguous step matches: {e}")
            return []

    def get_specific_match(self, match_id: str) -> Optional[AmbiguousStepMatch]:
        """Fetch a specific ambiguous step match by ID"""
        try:
            url = f"{self.ingredient_processor.ekitchen_base_url}/global-recipes/ambiguous-step-matches/{match_id}"
            headers = {
                "Authorization": f"Bearer {self.ingredient_processor.access_token}",
                "Content-Type": "application/json"
            }

            response = requests.get(url, headers=headers)
            response.raise_for_status()

            match_data = response.json()

            match = AmbiguousStepMatch(
                id=match_data['id'],
                recipe_id=match_data['recipe_id'],
                step_position=match_data['step_position'],
                template=match_data['template'],
                ingredient_refs=match_data.get('ingredient_refs', []),
                ambiguous_word=match_data['ambiguous_word'],
                possible_matches=match_data['possible_matches'],
                resolved_match=match_data.get('resolved_match'),
                resolved_at=match_data.get('resolved_at'),
                created_at=match_data.get('created_at')
            )

            print(f"📋 Retrieved match {match_id}")
            return match

        except Exception as e:
            print(f"❌ Error fetching match {match_id}: {e}")
            return None

    def analyze_with_ai(self, match: AmbiguousStepMatch) -> Optional[str]:
        """Use OpenAI to analyze the step context and resolve the ambiguous match"""
        try:
            # Clean the step text by removing template brackets
            step_text = re.sub(r'\{\{[^}]+\}\}', match.ambiguous_word, match.template)

            # Format possible matches for the prompt
            matches_text = "\n".join([f"- {match}" for match in match.possible_matches])

            prompt = f"""
You are a professional chef and recipe analyst. I need you to resolve an ambiguous ingredient reference in a recipe step.

**Recipe Step Text:**
"{step_text}"

**Ambiguous Word:** "{match.ambiguous_word}"

**Possible Ingredient Matches:**
{matches_text}

**Task:**
Analyze the step context carefully and determine which of the possible ingredient matches the ambiguous word "{match.ambiguous_word}" most likely refers to in this specific context.

**Consider:**
1. The cooking context and method described in the step
2. How ingredients are typically used together
3. The specific wording and phrasing around the ambiguous word
4. Common culinary practices and ingredient relationships
5. Any quantity or preparation indicators that might provide clues

**Response Format:**
Return ONLY the exact ingredient name from the possible matches list that best fits the context. Do not include any explanation or additional text.

**Important:** If none of the possible matches make sense in the context, or if you cannot determine with reasonable confidence which ingredient is being referenced, return exactly: NO_MATCH

This ensures we only resolve matches where we can be confident about the correct ingredient, rather than forcing an incorrect resolution.

**Examples:**
- If the ambiguous word is "pepper" and the options are "ground black pepper" and "red bell pepper", and the step mentions seasoning with "salt and pepper", return: ground black pepper
- If the ambiguous word is "oil" and the options are "olive oil" and "coconut oil", but the context doesn't provide clear indicators of which type, return: NO_MATCH
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional chef and recipe analyst specializing in ingredient identification and recipe interpretation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1  # Low temperature for consistent, logical responses
            )

            resolved_ingredient = response.choices[0].message.content.strip()

            # Check if AI determined no match is appropriate
            if resolved_ingredient == "NO_MATCH":
                print(f"🤖 AI determined no clear match for '{match.ambiguous_word}' - leaving unresolved")
                return None

            # Validate that the response is one of the possible matches
            if resolved_ingredient in match.possible_matches:
                print(f"🤖 AI resolved '{match.ambiguous_word}' → '{resolved_ingredient}'")
                return resolved_ingredient
            else:
                print(f"⚠️  AI returned invalid match: '{resolved_ingredient}' not in possible matches")
                # Try to find a partial match
                for possible_match in match.possible_matches:
                    if resolved_ingredient.lower() in possible_match.lower() or possible_match.lower() in resolved_ingredient.lower():
                        print(f"🔍 Found partial match: '{possible_match}'")
                        return possible_match
                print(f"❌ No valid match found for AI response: '{resolved_ingredient}'")
                return None

        except Exception as e:
            print(f"❌ Error in AI analysis: {e}")
            return None

    def resolve_match(self, match_id: str, resolved_ingredient: str, dry_run: bool = True) -> bool:
        """Resolve an ambiguous step match by updating it via the API"""
        if dry_run:
            print(f"🔍 DRY RUN: Would resolve match {match_id} with '{resolved_ingredient}'")
            return True

        try:
            url = f"{self.ingredient_processor.ekitchen_base_url}/global-recipes/ambiguous-step-matches/{match_id}"
            headers = {
                "Authorization": f"Bearer {self.ingredient_processor.access_token}",
                "Content-Type": "application/json"
            }

            payload = {
                "resolved_match": resolved_ingredient
            }

            response = requests.patch(url, json=payload, headers=headers)
            response.raise_for_status()

            print(f"✅ Successfully resolved match {match_id} with '{resolved_ingredient}'")
            return True

        except Exception as e:
            print(f"❌ Error resolving match {match_id}: {e}")
            return False

    def process_matches(self, matches: List[AmbiguousStepMatch], dry_run: bool = True) -> Dict[str, int]:
        """Process a list of ambiguous step matches"""
        stats = {
            "total": len(matches),
            "resolved": 0,
            "failed": 0,
            "skipped": 0,  # Already resolved
            "no_match": 0  # AI determined no clear match
        }

        for i, match in enumerate(matches, 1):
            print(f"\n📍 Processing match {i}/{len(matches)}: {match.id}")
            print(f"   Recipe: {match.recipe_id}")
            print(f"   Step {match.step_position}: {match.template}")
            print(f"   Ambiguous word: '{match.ambiguous_word}'")
            print(f"   Possible matches: {', '.join(match.possible_matches)}")

            # Skip if already resolved
            if match.resolved_match:
                print(f"⏭️  Already resolved: '{match.resolved_match}'")
                stats["skipped"] += 1
                continue

            # Use AI to analyze and resolve
            resolved_ingredient = self.analyze_with_ai(match)

            if resolved_ingredient:
                # Resolve the match
                success = self.resolve_match(match.id, resolved_ingredient, dry_run)
                if success:
                    stats["resolved"] += 1
                else:
                    stats["failed"] += 1
            else:
                print(f"⏭️  Leaving match {match.id} unresolved (no clear match found)")
                stats["no_match"] += 1

            # Add a small delay to be respectful to APIs
            time.sleep(0.5)

        return stats

    def print_summary(self, stats: Dict[str, int], dry_run: bool):
        """Print processing summary"""
        print(f"\n{'='*60}")
        print(f"📊 PROCESSING SUMMARY ({'DRY RUN' if dry_run else 'LIVE RUN'})")
        print(f"{'='*60}")
        print(f"Total matches processed: {stats['total']}")
        print(f"Successfully resolved: {stats['resolved']}")
        print(f"Failed to resolve: {stats['failed']}")
        print(f"Already resolved (skipped): {stats['skipped']}")
        print(f"Left unresolved (no clear match): {stats['no_match']}")

        if stats['total'] > 0:
            # Calculate success rate only for matches that could potentially be resolved
            attempted = stats['total'] - stats['skipped']
            if attempted > 0:
                success_rate = (stats['resolved'] / attempted) * 100
                print(f"Success rate (of attempted): {success_rate:.1f}%")

            resolution_rate = (stats['resolved'] / stats['total']) * 100
            print(f"Overall resolution rate: {resolution_rate:.1f}%")

        if dry_run and stats['resolved'] > 0:
            print(f"\n💡 Run with --live to actually resolve {stats['resolved']} matches")

def main():
    parser = argparse.ArgumentParser(description="Resolve ambiguous step matches using AI")
    parser.add_argument("--dry-run", action="store_true", help="Preview resolutions without saving")
    parser.add_argument("--live", action="store_true", help="Actually resolve matches")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of matches to process")
    parser.add_argument("--match-id", type=str, help="Resolve a specific match by ID")

    args = parser.parse_args()

    # Validate arguments
    if not args.dry_run and not args.live:
        print("❌ Error: You must specify either --dry-run or --live")
        return

    if args.dry_run and args.live:
        print("❌ Error: Cannot specify both --dry-run and --live")
        return

    dry_run = args.dry_run

    try:
        # Initialize the resolver
        resolver = AmbiguousStepMatchResolver()

        # Authenticate with eKitchen
        if not resolver.authenticate():
            print("❌ Failed to authenticate with eKitchen API")
            return

        if args.match_id:
            # Process a specific match
            print(f"🎯 Processing specific match: {args.match_id}")
            match = resolver.get_specific_match(args.match_id)
            if match:
                matches = [match]
            else:
                print(f"❌ Match {args.match_id} not found")
                return
        else:
            # Get unresolved matches
            print(f"🔍 Fetching unresolved ambiguous step matches (limit: {args.limit})...")
            matches = resolver.get_unresolved_matches(limit=args.limit)

        if not matches:
            print("✅ No unresolved ambiguous step matches found!")
            return

        # Process the matches
        stats = resolver.process_matches(matches, dry_run=dry_run)

        # Print summary
        resolver.print_summary(stats, dry_run)

    except KeyboardInterrupt:
        print("\n⏹️  Processing interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main()