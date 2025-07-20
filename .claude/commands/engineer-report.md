# Engineer Report - Upstream Communication to PM

**Command Arguments**: #$ARGUMENTS

You are processing an **Engineer Status Report** sent upstream to the PM. Parse `#$ARGUMENTS` for `--status` and `--context`.

## Report Processing

### 1. Parse Report Data
```bash
# Extract status and context from arguments
STATUS=$(echo "#$ARGUMENTS" | grep -o '\--status "[^"]*"' | sed 's/--status "//; s/"//')
CONTEXT=$(echo "#$ARGUMENTS" | grep -o '\--context "[^"]*"' | sed 's/--context "//; s/"//')

# Get current session info
CURRENT_SESSION=$(tmux display-message -p '#S')
FEATURE_NAME=$(echo "$CURRENT_SESSION" | sed 's/pm-//')
```

### 2. Analyze Engineer Status
```bash
# Determine engineer state from status and context
if echo "$STATUS" | grep -qi "completed\|done\|finished"; then
  ENGINEER_STATE="COMPLETED"
elif echo "$STATUS" | grep -qi "blocked\|stuck\|error"; then
  ENGINEER_STATE="BLOCKED"
elif echo "$STATUS" | grep -qi "progress\|working\|implementing"; then
  ENGINEER_STATE="IN_PROGRESS"
else
  ENGINEER_STATE="UNCLEAR"
fi
```

### 3. Context Analysis
```bash
# Analyze last 300 lines for key indicators
RECENT_COMMITS=$(echo "$CONTEXT" | grep -c "git commit\|committed")
ERROR_COUNT=$(echo "$CONTEXT" | grep -ci "error\|failed\|exception")
TEST_ACTIVITY=$(echo "$CONTEXT" | grep -c "npm test\|pytest\|test.*pass")
IMPLEMENTATION_PLAN_REF=$(echo "$CONTEXT" | grep -c "implementation plan\|phase\|step")

# Check if work aligns with implementation plan
ISSUE_NUMBER=$(echo "$CURRENT_SESSION" | grep -o '[0-9]\+$')
ISSUE_FILE=$(find project-breakdown/features/*/issues/ -name "*$ISSUE_NUMBER*" | head -1)
```

## Decision Tree - PM Response Actions

### 4. Execute PM Checklist Based on Analysis
```bash
case "$ENGINEER_STATE" in
  "COMPLETED")
    echo "🎉 Engineer reports completion - initiating validation checklist"
    
    # Send validation workflow to engineer
    ENG_SESSION="eng-$FEATURE_NAME-$ISSUE_NUMBER"
    ./scripts/send-claude-message.sh "$ENG_SESSION:0" "/engineer-validation --require-testing --require-docs --require-summary"
    
    echo "📋 PM CHECKLIST - COMPLETION VALIDATION:"
    echo "- [ ] Engineer must run full test suite"
    echo "- [ ] Engineer must verify all acceptance criteria"
    echo "- [ ] Engineer must provide change summary for CHANGES_DELIVERED.md"
    echo "- [ ] Engineer must update any documentation"
    echo "- [ ] PM will review and approve before marking complete"
    ;;
    
  "BLOCKED")
    echo "🚨 Engineer reports blocker - providing guidance"
    
    # Analyze type of blocker from context
    if echo "$CONTEXT" | grep -qi "test.*fail\|error.*test"; then
      GUIDANCE="TESTING_ISSUE"
    elif echo "$CONTEXT" | grep -qi "dependency\|import\|module"; then
      GUIDANCE="DEPENDENCY_ISSUE"  
    elif echo "$CONTEXT" | grep -qi "implementation\|approach\|architecture"; then
      GUIDANCE="DESIGN_ISSUE"
    else
      GUIDANCE="GENERAL_BLOCKER"
    fi
    
    # Send specific guidance based on blocker type
    ./scripts/send-claude-message.sh "$ENG_SESSION:0" "/engineer-guidance --type $GUIDANCE --context \"$STATUS\""
    ;;
    
  "IN_PROGRESS")
    echo "⚙️ Engineer in progress - analyzing alignment"
    
    # Check if work aligns with implementation plan
    CURRENT_PHASE=$(echo "$STATUS" | grep -o 'Phase [0-9]\+' || echo "Unknown")
    
    # Read implementation plan to verify alignment
    if [ -f "$ISSUE_FILE" ]; then
      EXPECTED_WORK=$(grep -A 20 "## Implementation Plan" "$ISSUE_FILE" | grep -A 10 "$CURRENT_PHASE")
      
      # Check if context shows work aligning with expected phase
      if echo "$CONTEXT" | grep -qi "$(echo "$EXPECTED_WORK" | head -3)"; then
        echo "✅ Engineer work aligns with implementation plan"
        echo "📊 PM STATUS LOG: $STATUS - On track, recent commits: $RECENT_COMMITS"
      else
        echo "⚠️ Engineer work may be off-track from implementation plan"
        ./scripts/send-claude-message.sh "$ENG_SESSION:0" "/engineer-guidance --type REALIGN --plan-section \"$EXPECTED_WORK\""
      fi
    fi
    
    # Check for concerning patterns
    if [ "$ERROR_COUNT" -gt 3 ]; then
      ./scripts/send-claude-message.sh "$ENG_SESSION:0" "/engineer-guidance --type DEBUG_HELP --errors \"Multiple errors detected\""
    elif [ "$RECENT_COMMITS" -eq 0 ]; then
      ./scripts/send-claude-message.sh "$ENG_SESSION:0" "/engineer-guidance --type COMMIT_REMINDER --message \"Remember to commit progress every 30 minutes\""
    fi
    ;;
    
  "UNCLEAR")
    echo "❓ Engineer status unclear - requesting clarification"
    ./scripts/send-claude-message.sh "$ENG_SESSION:0" "/engineer-guidance --type CLARIFY_STATUS --message \"Please provide clearer status: current phase, progress %, specific task\""
    ;;
esac
```

### 5. Log Analysis Results
```bash
echo "=== PM ANALYSIS COMPLETE ==="
echo "Engineer State: $ENGINEER_STATE"
echo "Recent Commits: $RECENT_COMMITS"
echo "Errors Detected: $ERROR_COUNT"
echo "Test Activity: $TEST_ACTIVITY"
echo "Status: $STATUS"
echo "Next Check: 5 minutes"
echo "================================"

# Schedule next check-in
./scripts/schedule_with_note.sh 5 "PM check for $FEATURE_NAME" "pm-$FEATURE_NAME:0"
```

## PM Checklist Summary

This slash command ensures the PM consistently:
- ✅ **Analyzes both status and context** for complete picture
- ✅ **Follows decision tree** based on engineer state  
- ✅ **Sends appropriate guidance** via slash commands
- ✅ **Validates completion** with structured workflow
- ✅ **Monitors alignment** with implementation plan
- ✅ **Logs analysis results** for transparency
- ✅ **Schedules next check-in** automatically

The PM now has a **structured, checklist-driven response** instead of relying on memory during arbitrary check-in triggers.