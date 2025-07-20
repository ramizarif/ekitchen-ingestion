# Engineer Validated - Final Completion Handoff

**Command Arguments**: #$ARGUMENTS

You are processing **final engineer validation** - the last step before accepting completion.

## Final Validation Processing

### 1. Parse Validation Status
```bash
# Extract validation flags
TESTS_PASS=$(echo "#$ARGUMENTS" | grep -q "\--tests-pass" && echo "true" || echo "false")
DOCS_UPDATED=$(echo "#$ARGUMENTS" | grep -q "\--docs-updated" && echo "true" || echo "false")
SUMMARY_PROVIDED=$(echo "#$ARGUMENTS" | grep -q "\--summary-provided" && echo "true" || echo "false")
CRITERIA_MET=$(echo "#$ARGUMENTS" | grep -q "\--criteria-met" && echo "true" || echo "false")
SUMMARY_COMPLETE=$(echo "#$ARGUMENTS" | grep -q "\--summary-complete" && echo "true" || echo "false")
ISSUE_NUMBER=$(echo "#$ARGUMENTS" | grep -o '\--issue [^ ]*' | cut -d' ' -f2)

echo "🔍 FINAL VALIDATION CHECKLIST"
echo "Tests Pass: $TESTS_PASS"
echo "Docs Updated: $DOCS_UPDATED" 
echo "Summary Provided: $SUMMARY_PROVIDED"
echo "Criteria Met: $CRITERIA_MET"
echo "Summary Complete: $SUMMARY_COMPLETE"
echo ""
```

### 2. Validation Gate
```bash
# Check all requirements met
if [ "$TESTS_PASS" = "true" ] && [ "$CRITERIA_MET" = "true" ]; then
  echo "✅ VALIDATION PASSED - Engineer has proven completion"
  
  # Get feature and session info
  CURRENT_SESSION=$(tmux display-message -p '#S')
  FEATURE_NAME=$(echo "$CURRENT_SESSION" | sed 's/pm-//')
  ENG_SESSION="eng-$FEATURE_NAME-$ISSUE_NUMBER"
  
  # Accept completion and clean up
  echo "🎉 ACCEPTING ENGINEER COMPLETION"
  echo "Issue #$ISSUE_NUMBER - Validation complete"
  
  # Kill engineer session
  tmux kill-session -t "$ENG_SESSION" 2>/dev/null || echo "Engineer session already closed"
  
  # Sync to board and changelog
  /board-sync --issue "$ISSUE_NUMBER"
  /changelog-add --type implementation --issue "$ISSUE_NUMBER"
  
  echo "✅ Issue #$ISSUE_NUMBER synced to board and changelog"
  
else
  echo "❌ VALIDATION FAILED - Requirements not met"
  echo "Engineer must complete all validation steps before acceptance"
  
  # Send engineer back to validation
  ./scripts/send-claude-message.sh "$ENG_SESSION:0" "/engineer-validation --require-testing --require-summary"
  return 1
fi
```

### 3. Check for Next Issues
```bash
# Look for next ready issue to assign
echo "🔍 Checking for next ready issues..."

NEXT_READY_ISSUE=$(find "project-breakdown/features/$FEATURE_NAME/issues/" -name "*.md" -exec grep -l "\\*\\*Status\\*\\*.*To Do" {} \\; | head -1)

if [ -n "$NEXT_READY_ISSUE" ]; then
  NEXT_ISSUE_NUM=$(basename "$NEXT_READY_ISSUE" | grep -o '[0-9]\+')
  echo "📋 Next ready issue found: #$NEXT_ISSUE_NUM"
  
  # Spawn new engineer for next issue
  if spawn_validated_engineer "$NEXT_ISSUE_NUM"; then
    echo "✅ Engineer reassigned to issue #$NEXT_ISSUE_NUM"
  else
    echo "❌ Failed to spawn engineer for issue #$NEXT_ISSUE_NUM"
  fi
else
  echo "📝 No more ready issues - checking feature completion"
fi
```

### 4. Feature Completion Check
```bash
# Check if all issues in feature are complete
TOTAL_ISSUES=$(find "project-breakdown/features/$FEATURE_NAME/issues/" -name "*.md" | wc -l)
COMPLETED_ISSUES=$(find "project-breakdown/features/$FEATURE_NAME/issues/" -name "*.md" -exec grep -l "\\*\\*Status\\*\\*.*COMPLETED" {} \\; | wc -l)

echo "Feature progress: $COMPLETED_ISSUES/$TOTAL_ISSUES issues complete"

if [ "$COMPLETED_ISSUES" -eq "$TOTAL_ISSUES" ]; then
  echo "🎉 FEATURE COMPLETE - All issues finished!"
  
  # Generate CHANGES_DELIVERED.md
  echo "📋 Generating change guide for user..."
  
  # Trigger feature completion workflow
  # This will create CHANGES_DELIVERED.md and signal orchestrator
  echo "PM ready for termination - feature complete"
  
  # Don't schedule next check-in
else
  echo "⚙️ Feature in progress - $((TOTAL_ISSUES - COMPLETED_ISSUES)) issues remaining"
  
  # Schedule next check-in
  ./scripts/schedule_with_note.sh 5 "PM check for $FEATURE_NAME" "pm-$FEATURE_NAME:0"
fi
```

### 5. Completion Log
```bash
echo ""
echo "=== PM COMPLETION PROCESSING ==="
echo "Issue #$ISSUE_NUMBER: ACCEPTED"
echo "Engineer session: TERMINATED"
echo "Board status: SYNCED"
echo "Changelog: UPDATED"
echo "Next assignment: PROCESSED"
echo "Feature status: $COMPLETED_ISSUES/$TOTAL_ISSUES complete"
echo "================================"
```

## Final Validation Benefits

This command ensures:
- ✅ **Comprehensive validation** before accepting completion
- ✅ **Automatic cleanup** of completed engineer sessions
- ✅ **Board and changelog sync** for completed work
- ✅ **Automatic reassignment** to next ready issues
- ✅ **Feature completion detection** and change guide generation
- ✅ **Clear completion logging** for transparency

Only **fully validated and tested work** is accepted as complete.