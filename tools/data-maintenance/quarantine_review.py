#!/usr/bin/env python3
"""
Quarantine Review — triage non-canonical / quarantined global ingredients.

This is the review/promotion pass that the `needs_enrichment` flag always
implied but nothing executed (docs/CATALOG_POLLUTION_HANDOFF.md): ingestion
creates unmatched ingredients as non-canonical "quarantine" rows, and this
tool decides what each one actually is. It serves both the existing backlog
(the 123 rows from the 2026-06-06 Caribbean batch) and all future quarantined
rows on an ongoing basis.

Each non-canonical row is bucketed:

  GARBAGE  — fails the ingredient-name validation gate (raw recipe lines,
             placeholders like 'ingredient needed'). Should be deleted along
             with its recipe links. No delete API exists → emitted as SQL.
  MERGE    — fuzzy+GPT match to an existing CANONICAL ingredient
             ('escallion'→'scallion', 'codfish'→'cod'). Recipe/kitchen links
             must be re-pointed to the canonical id → emitted as SQL.
  PROMOTE  — a genuinely missing ingredient (callaloo, ackee, plantain).
             Promoted to canonical via PATCH /global-ingredients/{id}.

Usage:
    python3 tools/data-maintenance/quarantine_review.py            # dry run (default)
    python3 tools/data-maintenance/quarantine_review.py --apply    # apply promotions via API
    python3 tools/data-maintenance/quarantine_review.py --limit 10 # triage first 10 only

Outputs (both modes):
    logs/quarantine_review_<ts>.json  — full triage decisions with reasons
    logs/quarantine_review_<ts>.sql   — SQL for merges + deletions (run against
                                        prod ekitchen DB after review; the API
                                        exposes no delete/relink endpoints)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

# Match the canonical scripts/ import style (see scripts/backfill_gram_anchors.py).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from services.ingredient_processor import DirectIngredientProcessor, load_env_file
from services.ingredient_validator import validate_ingredient_name


class QuarantineReviewer:
    def __init__(self):
        self.processor = DirectIngredientProcessor(log_to_file=True)
        self.stats = {
            "quarantined_total": 0,
            "garbage": 0,
            "merge": 0,
            "promote": 0,
            "promote_applied": 0,
            "promote_failed": 0,
        }

    def _log(self, msg: str):
        print(msg)
        if self.processor.logger:
            self.processor.logger.info(msg)

    def authenticate(self) -> bool:
        env_file_path = os.path.join(os.path.dirname(__file__), "..", "..", "local.env")
        env_vars = load_env_file(env_file_path)
        admin_email = env_vars.get("EKITCHEN_ADMIN_EMAIL")
        admin_password = env_vars.get("EKITCHEN_ADMIN_PASSWORD")
        if not admin_email or not admin_password:
            self._log("❌ Missing eKitchen admin credentials in local.env")
            return False
        return self.processor.authenticate_ekitchen(admin_email, admin_password)

    # ── Triage ─────────────────────────────────────────────────────────

    def triage_row(self, row: Dict[str, Any], canonical_catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Decide GARBAGE / MERGE / PROMOTE for one quarantined row."""
        name = (row.get("name") or "").strip()
        decision: Dict[str, Any] = {
            "id": row.get("id"),
            "name": name,
            "needs_enrichment": row.get("needs_enrichment"),
        }

        # 1. Garbage check — same gate the pipeline now enforces pre-create.
        is_valid, reason = validate_ingredient_name(name)
        if not is_valid:
            decision.update({"bucket": "garbage", "reason": reason})
            return decision

        # 2. Merge check — fuzzy candidates against CANONICAL rows only, then
        #    the GPT resolve-or-NONE arbiter (same logic the pipeline uses).
        candidates = self.processor._find_match_candidates(name, catalog=canonical_catalog)
        resolution = self.processor._resolve_to_catalog(name, candidates)
        match = resolution.get("match")
        if match:
            decision.update({
                "bucket": "merge",
                "merge_into_id": match["id"],
                "merge_into_name": match["name"],
                "match_type": match["match_type"],
                "reason": resolution.get("reason", ""),
            })
            return decision

        # 3. Genuinely missing ingredient → promote to canonical.
        decision.update({
            "bucket": "promote",
            "reason": resolution.get("reason") or "no canonical match; valid ingredient name",
        })
        return decision

    # ── Actions ────────────────────────────────────────────────────────

    def promote_ingredient(self, ingredient_id: str, name: str) -> bool:
        """Mark a quarantined row canonical via PATCH /global-ingredients/{id}."""
        url = f"{self.processor.ekitchen_base_url}/global-ingredients/{ingredient_id}"
        headers = {
            "Authorization": f"Bearer {self.processor.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"id": ingredient_id, "is_canonical": True}
        try:
            resp = requests.patch(url, data=json.dumps(payload), headers=headers, timeout=30)
            if resp.status_code == 200:
                self._log(f"   ✅ Promoted '{name}' → canonical")
                return True
            self._log(f"   ❌ Promote failed for '{name}': {resp.status_code} — {resp.text[:200]}")
            return False
        except Exception as e:  # noqa: BLE001
            self._log(f"   ❌ Promote error for '{name}': {e}")
            return False

    @staticmethod
    def merge_sql(dup_id: str, dup_name: str, canon_id: str, canon_name: str) -> str:
        return f"""
-- MERGE: '{dup_name}' ({dup_id}) → '{canon_name}' ({canon_id})
UPDATE recipe_ingredients ri SET ingredient_id = '{canon_id}'
 WHERE ri.ingredient_id = '{dup_id}'
   AND NOT EXISTS (SELECT 1 FROM recipe_ingredients r2
                    WHERE r2.recipe_id = ri.recipe_id AND r2.ingredient_id = '{canon_id}');
DELETE FROM recipe_ingredients WHERE ingredient_id = '{dup_id}';
UPDATE kitchen_ingredients ki SET ingredient_id = '{canon_id}'
 WHERE ki.ingredient_id = '{dup_id}'
   AND NOT EXISTS (SELECT 1 FROM kitchen_ingredients k2
                    WHERE k2.kitchen_id = ki.kitchen_id AND k2.ingredient_id = '{canon_id}');
DELETE FROM kitchen_ingredients WHERE ingredient_id = '{dup_id}';
DELETE FROM global_ingredients WHERE id = '{dup_id}';"""

    @staticmethod
    def delete_sql(dup_id: str, dup_name: str, reason: str) -> str:
        return f"""
-- GARBAGE: '{dup_name}' ({dup_id}) — {reason}
DELETE FROM recipe_ingredients WHERE ingredient_id = '{dup_id}';
DELETE FROM kitchen_ingredients WHERE ingredient_id = '{dup_id}';
DELETE FROM global_ingredients WHERE id = '{dup_id}';"""

    # ── Run ────────────────────────────────────────────────────────────

    def run(self, apply: bool, limit: Optional[int] = None):
        self._log("🚀 Quarantine Review")
        self._log("=" * 70)
        self._log(f"Mode: {'APPLY (promotions via API; merges/deletes still SQL)' if apply else 'DRY RUN'}")
        self._log("=" * 70)

        if not self.authenticate():
            self._log("❌ Authentication failed")
            return 1

        catalog = self.processor.get_full_catalog()
        canonical = [r for r in catalog if r.get("is_canonical")]
        quarantined = [r for r in catalog if not r.get("is_canonical")]
        if limit:
            quarantined = quarantined[:limit]

        self.stats["quarantined_total"] = len(quarantined)
        self._log(f"📚 Catalog: {len(catalog)} rows — {len(canonical)} canonical, "
                  f"{len(quarantined)} quarantined to triage")

        decisions: List[Dict[str, Any]] = []
        sql_statements: List[str] = []

        for i, row in enumerate(quarantined, 1):
            self._log(f"\n[{i}/{len(quarantined)}] Triaging '{row.get('name')}'...")
            decision = self.triage_row(row, canonical)
            decisions.append(decision)
            bucket = decision["bucket"]
            self.stats[bucket] += 1
            self._log(f"   → {bucket.upper()}: {decision.get('reason', '')}")

            if bucket == "garbage":
                sql_statements.append(self.delete_sql(decision["id"], decision["name"], decision["reason"]))
            elif bucket == "merge":
                sql_statements.append(self.merge_sql(
                    decision["id"], decision["name"],
                    decision["merge_into_id"], decision["merge_into_name"],
                ))
            elif bucket == "promote" and apply:
                if self.promote_ingredient(decision["id"], decision["name"]):
                    self.stats["promote_applied"] += 1
                else:
                    self.stats["promote_failed"] += 1

        # ── Write outputs ──────────────────────────────────────────────
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
        os.makedirs(log_dir, exist_ok=True)

        report_path = os.path.join(log_dir, f"quarantine_review_{ts}.json")
        with open(report_path, "w") as f:
            json.dump({"stats": self.stats, "decisions": decisions}, f, indent=2)

        sql_path = os.path.join(log_dir, f"quarantine_review_{ts}.sql")
        with open(sql_path, "w") as f:
            f.write(
                "-- Quarantine review: merges + garbage deletions\n"
                f"-- Generated {ts} by tools/data-maintenance/quarantine_review.py\n"
                "-- REVIEW BEFORE RUNNING against prod ekitchen DB. Verify the\n"
                "-- kitchen_ingredients column names (kitchen_id assumed) match schema.\n"
                "BEGIN;\n"
                + "\n".join(sql_statements)
                + "\n\n-- COMMIT;  -- uncomment after verifying\nROLLBACK;\n"
            )

        self._log("\n" + "=" * 70)
        self._log("📊 Triage summary:")
        for k, v in self.stats.items():
            self._log(f"   {k}: {v}")
        self._log(f"\n📄 Report: {report_path}")
        self._log(f"📄 SQL (merges + deletions): {sql_path}")
        if not apply and self.stats["promote"]:
            self._log(f"\nℹ️  {self.stats['promote']} promotions pending — rerun with --apply to execute via API")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Triage quarantined (non-canonical) global ingredients")
    parser.add_argument("--apply", action="store_true",
                        help="Apply promotions via API (merges/deletes are always SQL output)")
    parser.add_argument("--limit", type=int, default=None, help="Triage at most N rows")
    args = parser.parse_args()
    sys.exit(QuarantineReviewer().run(apply=args.apply, limit=args.limit))


if __name__ == "__main__":
    main()
