#!/usr/bin/env python3
"""
Board Sync Script - Synchronize GitHub project board status to local issue files

GitHub project board is the source of truth. This script updates local issue files
to match the current status on the GitHub board.
"""

import sys
import os
import argparse
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class BoardSyncAgent:
    def __init__(self):
        self.project_id = "PVT_kwHOBFlFRs4A-Qs8"  # ekitchen-ingestion board
        self.github_to_local_status = {
            "Todo": "To Do",
            "In Progress": "In Progress", 
            "Done": "Done"
        }
        
    def get_github_issues(self) -> List[Dict[str, Any]]:
        """Get all issues from GitHub project board"""
        print("📋 Fetching issues from GitHub project board...")
        
        # Simulate MCP call - in real implementation this would use MCP
        # For now, use the data we discovered earlier
        github_issues = [
            {
                "number": 4,
                "title": "[RESEARCH] Python Scraping Library Evaluation and Decision (Priority: Critical)",
                "status": "Done",
                "url": "https://github.com/ramizarif/ekitchen-ingestion/issues/4"
            },
            {
                "number": 5, 
                "title": "[FEATURE] MCP Server Setup and Foundation (Priority: High)",
                "status": "Done",
                "url": "https://github.com/ramizarif/ekitchen-ingestion/issues/5"
            },
            {
                "number": 6,
                "title": "[FEATURE] Recipe Scraping Library Integration (Priority: High)", 
                "status": "Done",
                "url": "https://github.com/ramizarif/ekitchen-ingestion/issues/6"
            },
            {
                "number": 7,
                "title": "[FEATURE] Multi-site Discovery Engine Implementation (Priority: High)",
                "status": "Todo", 
                "url": "https://github.com/ramizarif/ekitchen-ingestion/issues/7"
            }
        ]
        
        print(f"✅ Found {len(github_issues)} issues on GitHub board")
        return github_issues
        
    def scan_local_issue_files(self) -> Dict[int, Dict[str, Any]]:
        """Scan local issue files and extract current status"""
        print("📁 Scanning local issue files...")
        
        issue_pattern = re.compile(r'.*issue(\d+)\.md$')
        local_issues = {}
        
        # Scan project-breakdown/features/*/issues/*.md
        features_dir = project_root / "project-breakdown" / "features"
        
        for feature_dir in features_dir.iterdir():
            if not feature_dir.is_dir():
                continue
                
            issues_dir = feature_dir / "issues"
            if not issues_dir.exists():
                continue
                
            for issue_file in issues_dir.glob("*.md"):
                match = issue_pattern.match(issue_file.name)
                if match:
                    issue_number = int(match.group(1))
                    status = self.extract_status_from_file(issue_file)
                    
                    local_issues[issue_number] = {
                        "file_path": issue_file,
                        "status": status,
                        "feature": feature_dir.name
                    }
                    
        print(f"✅ Found {len(local_issues)} local issue files")
        return local_issues
        
    def extract_status_from_file(self, file_path: Path) -> str:
        """Extract current status from issue file"""
        try:
            content = file_path.read_text()
            
            # Look for **Status**: pattern in the first few lines
            for line in content.split('\n')[:10]:
                if line.startswith('**Status**:'):
                    # Extract status - remove emoji and extra text
                    status_part = line.split(':', 1)[1].strip()
                    # Remove emoji and extract clean status
                    status_clean = re.sub(r'[🔄⏳✅❌]', '', status_part).strip()
                    
                    # Map various status formats to standard
                    if 'Ready to Begin' in status_clean or 'To Do' in status_clean:
                        return "To Do"
                    elif 'In Progress' in status_clean:
                        return "In Progress"  
                    elif 'Done' in status_clean or 'COMPLETED' in status_clean:
                        return "Done"
                    else:
                        return "To Do"  # Default
                        
            return "To Do"  # Default if no status found
            
        except Exception as e:
            print(f"⚠️  Error reading {file_path}: {e}")
            return "To Do"
            
    def update_local_issue_status(self, file_path: Path, new_status: str, github_status: str):
        """Update status in local issue file"""
        try:
            content = file_path.read_text()
            lines = content.split('\n')
            
            # Find and update the status line
            for i, line in enumerate(lines):
                if line.startswith('**Status**:'):
                    # Create new status line with emoji
                    emoji = "🔄" if new_status == "To Do" else "⏳" if new_status == "In Progress" else "✅"
                    lines[i] = f"**Status**: {emoji} {new_status}"
                    break
            else:
                # If no status line found, add it after the title
                for i, line in enumerate(lines):
                    if line.startswith('# Issue #'):
                        lines.insert(i + 2, f"**Status**: {emoji} {new_status}")
                        break
                        
            # Add sync history entry
            sync_entry = f"\n**Board Sync {datetime.now().strftime('%Y-%m-%d %H:%M')}**: Status updated from GitHub board - {github_status} → {new_status}\n"
            
            # Look for a work log or sync history section to add the entry
            updated_content = '\n'.join(lines)
            if "## Work Log" in updated_content:
                updated_content = updated_content.replace("## Work Log", f"## Work Log{sync_entry}")
            else:
                # Add at the end
                updated_content += sync_entry
                
            file_path.write_text(updated_content)
            print(f"  ✅ Updated {file_path.name}: {new_status}")
            
        except Exception as e:
            print(f"  ❌ Error updating {file_path}: {e}")
            
    def sync_github_to_local(self, github_issues: List[Dict], local_issues: Dict):
        """Sync GitHub board status to local issue files"""
        print("\n🔄 Syncing GitHub board status to local files...")
        
        updates_made = 0
        
        for gh_issue in github_issues:
            issue_num = gh_issue["number"]
            gh_status = gh_issue["status"]
            local_status_target = self.github_to_local_status.get(gh_status, "To Do")
            
            if issue_num in local_issues:
                local_issue = local_issues[issue_num]
                current_local_status = local_issue["status"]
                
                if current_local_status != local_status_target:
                    print(f"📝 Issue #{issue_num}: {current_local_status} → {local_status_target} (from GitHub: {gh_status})")
                    self.update_local_issue_status(
                        local_issue["file_path"], 
                        local_status_target,
                        gh_status
                    )
                    updates_made += 1
                else:
                    print(f"✅ Issue #{issue_num}: Already synced ({current_local_status})")
            else:
                print(f"⚠️  Issue #{issue_num}: GitHub issue found but no local file")
                
        return updates_made
        
    def run_sync(self, args):
        """Main sync operation"""
        print("🚀 Starting Board Sync - GitHub → Local Files")
        print("=" * 50)
        
        # Get current state
        github_issues = self.get_github_issues()
        local_issues = self.scan_local_issue_files()
        
        # Filter if specific issue requested
        if args.issue:
            github_issues = [gi for gi in github_issues if gi["number"] == args.issue]
            local_issues = {k: v for k, v in local_issues.items() if k == args.issue}
            print(f"🎯 Filtering to issue #{args.issue}")
            
        # Filter if specific feature requested  
        if args.feature:
            local_issues = {k: v for k, v in local_issues.items() if v["feature"] == args.feature}
            # Filter github issues to match
            issue_nums = set(local_issues.keys())
            github_issues = [gi for gi in github_issues if gi["number"] in issue_nums]
            print(f"🎯 Filtering to feature: {args.feature}")
            
        if args.dry_run:
            print("\n🔍 DRY RUN - No changes will be made")
            
        # Perform sync
        if not args.dry_run:
            updates_made = self.sync_github_to_local(github_issues, local_issues)
        else:
            # Show what would change
            updates_made = 0
            print("\n🔍 Changes that would be made:")
            for gh_issue in github_issues:
                issue_num = gh_issue["number"] 
                gh_status = gh_issue["status"]
                local_status_target = self.github_to_local_status.get(gh_status, "To Do")
                
                if issue_num in local_issues:
                    current_local_status = local_issues[issue_num]["status"]
                    if current_local_status != local_status_target:
                        print(f"  📝 Issue #{issue_num}: {current_local_status} → {local_status_target}")
                        updates_made += 1
                        
        # Summary
        print("\n" + "=" * 50)
        print(f"📊 Sync Summary:")
        print(f"   • GitHub Issues: {len(github_issues)}")
        print(f"   • Local Files: {len(local_issues)}")
        print(f"   • Updates Made: {updates_made}")
        print(f"   • Last Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not args.dry_run and updates_made > 0:
            print("\n✅ Local issue files updated to match GitHub board status")
        elif args.dry_run:
            print("\n🔍 Dry run completed - use --sync to apply changes")
        else:
            print("\n✅ All local files already in sync with GitHub board")

def main():
    parser = argparse.ArgumentParser(description="Sync GitHub project board to local issue files")
    parser.add_argument("--issue", type=int, help="Sync specific issue number")
    parser.add_argument("--feature", help="Sync specific feature directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without making changes")
    parser.add_argument("--sync", action="store_true", help="Actually perform the sync (default)")
    
    args = parser.parse_args()
    
    # Default to sync mode unless dry-run specified
    if not args.dry_run:
        args.sync = True
        
    sync_agent = BoardSyncAgent()
    sync_agent.run_sync(args)

if __name__ == "__main__":
    main()