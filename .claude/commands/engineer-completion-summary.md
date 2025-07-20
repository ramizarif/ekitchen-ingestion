# Engineer Completion Summary - Change Documentation

**Command Arguments**: #$ARGUMENTS

You are providing a **completion summary** to the PM for CHANGES_DELIVERED.md documentation.

## Summary Processing

### 1. Parse Summary Details
```bash
# Extract summary components
CHANGES=$(echo "#$ARGUMENTS" | grep -o '\--changes "[^"]*"' | sed 's/--changes "//; s/"//')
FILES=$(echo "#$ARGUMENTS" | grep -o '\--files "[^"]*"' | sed 's/--files "//; s/"//')
TESTING=$(echo "#$ARGUMENTS" | grep -o '\--testing "[^"]*"' | sed 's/--testing "//; s/"//')
USAGE=$(echo "#$ARGUMENTS" | grep -o '\--usage "[^"]*"' | sed 's/--usage "//; s/"//')

echo "📋 COMPLETION SUMMARY RECEIVED"
echo "Changes: $CHANGES"
echo "Files: $FILES"
echo "Testing: $TESTING"
echo "Usage: $USAGE"
```

### 2. Update Issue File
```bash
# Find and update the engineer's issue file
CURRENT_SESSION=$(tmux display-message -p '#S')
ISSUE_NUMBER=$(echo "$CURRENT_SESSION" | grep -o '[0-9]\+$')
ISSUE_FILE=$(find project-breakdown/features/*/issues/ -name "*$ISSUE_NUMBER*" | head -1)

if [ -f "$ISSUE_FILE" ]; then
  # Add completion summary to issue file
  echo "" >> "$ISSUE_FILE"
  echo "## Implementation Summary" >> "$ISSUE_FILE"
  echo "" >> "$ISSUE_FILE"
  echo "**Changes Made**: $CHANGES" >> "$ISSUE_FILE"
  echo "**Files Modified/Created**: $FILES" >> "$ISSUE_FILE"
  echo "**Testing Completed**: $TESTING" >> "$ISSUE_FILE"
  echo "**Usage Instructions**: $USAGE" >> "$ISSUE_FILE"
  echo "**Completion Date**: $(date +%Y-%m-%d)" >> "$ISSUE_FILE"
  
  echo "✅ Issue file updated with implementation summary"
else
  echo "❌ Could not find issue file for #$ISSUE_NUMBER"
fi
```

### 3. Signal PM for Final Validation
```bash
# Send back to PM for final completion processing  
# Engineer session format: eng-FEATURE_NAME-ISSUE_NUMBER -> PM session: pm-FEATURE_NAME
FEATURE_NAME=$(echo "$CURRENT_SESSION" | sed 's/^eng-//' | sed 's/-[0-9]*$//')
PM_SESSION="pm-$FEATURE_NAME"

echo "📤 Notifying PM of completion with summary"
./scripts/send-claude-message.sh "$PM_SESSION:0" "/engineer-validated --issue $ISSUE_NUMBER --summary-complete"

echo ""
echo "=== ENGINEER COMPLETION PROCESS ==="
echo "✅ Summary provided to PM"
echo "✅ Issue file updated"  
echo "⏳ Awaiting PM final validation"
echo "================================="
```

## Summary Requirements

This command ensures:
- ✅ **Structured change documentation** for PM reporting
- ✅ **Issue file updates** with implementation details
- ✅ **Clear handoff to PM** for final validation
- ✅ **CHANGES_DELIVERED.md preparation** with actual implementation details

Engineers provide **comprehensive summaries** instead of vague completion claims.