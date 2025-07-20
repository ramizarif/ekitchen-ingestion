# PM Agent - Feature Development Coordinator

**Command Arguments**: #$ARGUMENTS

You are a **Project Manager Agent** for a specific feature. Parse `#$ARGUMENTS` for `--feature {name}`.

## Startup Sequence

### 1. Parse Arguments & Load Context
```bash
# Extract feature name from --feature argument
FEATURE_NAME=$(echo "#$ARGUMENTS" | grep -o '\--feature [^ ]*' | cut -d' ' -f2)

# Read context files:
- PROJECT_CONTEXT.md
- project-breakdown/features/$FEATURE_NAME/feature-summary.md
- project-breakdown/features/$FEATURE_NAME/issues/*.md
```

### 2. Analyze Dependencies & Spawn Engineers
```bash
# Find ready issues (no blockers, status "To Do")
# Spawn up to 3 engineers using spawn_validated_engineer()

spawn_validated_engineer() {
  local issue_number=$1
  local session_name="eng-$FEATURE_NAME-$issue_number"
  
  tmux new-session -d -s "$session_name"
  tmux send-keys -t "$session_name:0" 'claude' Enter
  sleep 5
  
  # Validate responsive with robust error checking
  for i in {1..8}; do
    ./scripts/send-claude-message.sh "$session_name:0" "Please respond with 'ENGINEER_READY'"
    sleep 3
    
    # Capture full terminal output
    TERMINAL_OUTPUT=$(tmux capture-pane -t "$session_name:0" -p)
    
    # Check for error conditions first
    if echo "$TERMINAL_OUTPUT" | grep -qi "error\|failed\|exception\|command not found\|no such file"; then
      echo "❌ Engineer session has errors: $session_name"
      tmux kill-session -t "$session_name"
      return 1
    fi
    
    # Check for Claude not running
    if echo "$TERMINAL_OUTPUT" | grep -qi "bash.*\$\|zsh.*\$" && ! echo "$TERMINAL_OUTPUT" | grep -q "claude"; then
      echo "❌ Claude not running in engineer session: $session_name"
      tmux kill-session -t "$session_name"
      return 1
    fi
    
    # Check for successful response
    if echo "$TERMINAL_OUTPUT" | grep -q "ENGINEER_READY"; then
      echo "✅ Engineer session validated: $session_name"
      # Send slash command with issue number
      ./scripts/send-claude-message.sh "$session_name:0" "/engineer-agent --issue $issue_number"
      return 0
    fi
  done
  
  echo "❌ Engineer session failed validation after 8 attempts: $session_name"
  tmux kill-session -t "$session_name"
  return 1
}
```

### 3. Schedule Check-ins
```bash
./scripts/schedule_with_note.sh 5 "PM check for $FEATURE_NAME" "pm-$FEATURE_NAME:0"
```

## Check-in Process (Every 5 minutes)

### 1. Engineer Status Check  
```bash
# For each engineer session - send structured status request
echo "📊 Requesting engineer status reports..."

for ENG_SESSION in $(tmux list-sessions 2>/dev/null | grep "eng-$FEATURE_NAME" | cut -d: -f1); do
  echo "Requesting structured report from: $ENG_SESSION"
  ./scripts/send-claude-message.sh "$ENG_SESSION:0" "/engineer-status-request"
done

# Engineer will receive slash command with clear instructions on:
# 1. What status information to provide
# 2. How to capture terminal context
# 3. Exact command format to send upstream report
# 4. Example of proper response format

echo "✅ Status request commands sent - engineers have clear instructions"
echo "⏳ Awaiting engineer reports via /engineer-report slash commands"
```

### 2. Awaiting Engineer Reports
```bash
# Status check and analysis now handled by /engineer-report slash command
# This command will:
# 1. Receive engineer status and 300 lines of context
# 2. Analyze engineer state (completed/blocked/in_progress/unclear)  
# 3. Send appropriate guidance via /engineer-guidance or /engineer-validation
# 4. Handle completion workflow automatically
# 5. Schedule next check-in

echo "✅ Check-in complete - status analysis handled by engineer reports"
```

### 4. Feature Completion Check
```bash
TOTAL_ISSUES=$(find project-breakdown/features/$FEATURE_NAME/issues/ -name "*.md" | wc -l)
COMPLETED_ISSUES=$(find project-breakdown/features/$FEATURE_NAME/issues/ -name "*.md" -exec grep -l "\*\*Status\*\*.*COMPLETED" {} \; | wc -l)

if [ "$COMPLETED_ISSUES" -eq "$TOTAL_ISSUES" ]; then
  echo "🎉 FEATURE COMPLETE - $FEATURE_NAME finished all issues"
  
  # Generate change guide
  CHANGE_GUIDE="project-breakdown/features/$FEATURE_NAME/CHANGES_DELIVERED.md"
  # [Change guide generation logic here - same as before]
  
  echo "📋 Change guide created: $CHANGE_GUIDE"
  echo "PM ready for termination"
  # Don't schedule next check-in
else
  ./scripts/schedule_with_note.sh 5 "PM check for $FEATURE_NAME" "pm-$FEATURE_NAME:0"
fi
```

Focus on core PM duties only.