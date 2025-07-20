# Engineer Status Request - PM Check-in Command

**Command Arguments**: #$ARGUMENTS

You are receiving a **PM status request**. You must respond with a structured upstream report.

## Status Request Instructions

### 1. Understand the Request
```bash
echo "📊 PM STATUS REQUEST RECEIVED"
echo "You must send a structured status report upstream to your PM"
echo "This includes both your self-assessment AND terminal context for PM analysis"
echo ""
```

### 2. Gather Status Information
```bash
# Determine your current phase and progress
echo "📋 Preparing status report..."
echo ""
echo "Required information to include:"
echo "- Current phase (Phase 1, 2, 3, etc.)"
echo "- Progress percentage for current phase"
echo "- Specific task you're working on right now"
echo "- Estimated time to complete current phase"
echo "- Any blockers or issues"
echo ""
```

### 3. Capture Terminal Context
```bash
# Capture your recent work context (last 300 lines)
echo "📡 Capturing terminal context for PM analysis..."
TERMINAL_CONTEXT=$(tmux capture-pane -t $(tmux display-message -p '#S'):0 -p | tail -300)

echo "Context captured: $(echo "$TERMINAL_CONTEXT" | wc -l) lines"
echo "This shows PM your recent commands, commits, tests, errors, etc."
echo ""
```

### 4. Send Upstream Report
```bash
# Calculate PM session name from your engineer session
CURRENT_SESSION=$(tmux display-message -p '#S')
# Engineer session format: eng-FEATURE_NAME-ISSUE_NUMBER
# PM session format: pm-FEATURE_NAME
# Extract feature name by removing "eng-" prefix and "-ISSUE_NUMBER" suffix
FEATURE_NAME=$(echo "$CURRENT_SESSION" | sed 's/^eng-//' | sed 's/-[0-9]*$//')
PM_SESSION="pm-$FEATURE_NAME"

echo "🚀 Sending upstream report to: $PM_SESSION"
echo "   (Your session: $CURRENT_SESSION -> PM session: $PM_SESSION)"
echo ""
echo "Required format:"
echo '/engineer-report --status "Phase X Y% complete. ETA: Zmin. Current: [specific task]. Blockers: [none/details]" --context "$TERMINAL_CONTEXT"'
echo ""
echo "Example:"
echo '/engineer-report --status "Phase 2 80% complete. ETA: 45min. Current: implementing URL validation tests. Blockers: none" --context "$TERMINAL_CONTEXT"'
echo ""
```

### 5. Execute the Report
```bash
# Now provide YOUR actual status and send the report:

echo "=== PROVIDE YOUR STATUS NOW ==="
echo "Fill in the template with your actual information:"
echo ""
echo "Current Phase: [1/2/3/etc.]"
echo "Progress %: [0-100%]"  
echo "Current Task: [what specific step you're working on]"
echo "ETA: [time estimate to finish current phase]"
echo "Blockers: [any issues preventing progress, or 'none']"
echo ""
echo "Then execute:"
echo "./scripts/send-claude-message.sh \"$PM_SESSION:0\" \"/engineer-report --status \"[your status]\" --context \"\$TERMINAL_CONTEXT\"\""
echo ""
echo "After sending, continue with your implementation work."
```

## Status Request Benefits

This command ensures engineers:
- ✅ **Understand exactly what PM needs** - structured status format
- ✅ **Include both self-assessment and context** - status + 300 lines
- ✅ **Follow consistent reporting format** - always same structure
- ✅ **Know how to send upstream** - exact command syntax provided
- ✅ **Continue work after reporting** - clear next steps

**No ambiguity about what status information is needed or how to send it.**