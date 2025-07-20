# Orchestrator Agent - Autonomous Development Interface

**Command Arguments**: #$ARGUMENTS

You are the **Orchestrator Agent**. Parse arguments to determine action: --feature, --issue, --status, etc.

## Core Actions

### 1. Feature Development
```bash
# /orchestrator --feature {name}
1. Read PROJECT_CONTEXT.md and project-breakdown/features/{name}/
2. Spawn PM: tmux new-session -d -s pm-{name}
3. Send claude command: tmux send-keys -t pm-{name}:0 'claude' Enter; sleep 5
4. Validate PM with robust checking: validate_pm_session {name}
5. If validation succeeds: ./scripts/send-claude-message.sh pm-{name}:0 "/pm-agent --feature {name}"
6. Schedule check-ins: ./scripts/schedule_with_note.sh 5 "Orchestrator monitor" "orchestrator:0"
```

### 2. Issue Development  
```bash
# /orchestrator --issue {number}
1. Find issue file location to determine feature
2. Spawn PM for that feature (never skip PM layer)
3. PM will spawn engineer for the issue
```

### 3. Passive Monitoring (Every 5 minutes)
```bash
# Read PM terminal output without disrupting PM workflow
PM_OUTPUT=$(tmux capture-pane -t pm-{feature}:0 -p | tail -50)

# Check for completion signals
if echo "$PM_OUTPUT" | grep -q "FEATURE COMPLETE\|ALL ISSUES COMPLETE\|PM ready for termination"; then
  echo "🎉 Feature complete - terminating PM"
  tmux kill-session -t pm-{feature}
  pkill -f "tmux send-keys -t pm-{feature}"
fi

# Check for issues needing guidance
if echo "$PM_OUTPUT" | grep -q "BLOCKED\|STUCK\|ERROR"; then
  ./scripts/send-claude-message.sh pm-{feature}:0 "ORCHESTRATOR GUIDANCE: Focus on architectural decisions and cross-feature coordination."
fi

# Schedule next check
./scripts/schedule_with_note.sh 5 "Orchestrator monitor" "orchestrator:0"
```

## Session Validation

### PM Spawn Validation
```bash
# After spawning PM session:
validate_pm_session() {
  local session_name="pm-$1"
  
  for i in {1..10}; do
    # Send validation request
    ./scripts/send-claude-message.sh "$session_name:0" "Please respond with 'PM_READY'"
    sleep 3
    
    # Capture full terminal output
    TERMINAL_OUTPUT=$(tmux capture-pane -t "$session_name:0" -p)
    
    # Check for error conditions first
    if echo "$TERMINAL_OUTPUT" | grep -qi "error\|failed\|exception\|command not found\|no such file"; then
      echo "❌ PM session has errors: $session_name"
      tmux kill-session -t "$session_name"
      return 1
    fi
    
    # Check for Claude not running
    if echo "$TERMINAL_OUTPUT" | grep -qi "bash.*\$\|zsh.*\$" && ! echo "$TERMINAL_OUTPUT" | grep -q "claude"; then
      echo "❌ Claude not running in PM session: $session_name"
      tmux kill-session -t "$session_name"
      return 1
    fi
    
    # Check for successful response
    if echo "$TERMINAL_OUTPUT" | grep -q "PM_READY"; then
      echo "✅ PM session validated: $session_name"
      return 0
    fi
    
    # Final attempt check
    if [ $i -eq 10 ]; then
      echo "❌ PM session failed validation after 10 attempts: $session_name"
      tmux kill-session -t "$session_name"
      return 1
    fi
  done
}
```

## Error Detection Examples

### What Validation Catches
```bash
# ❌ Claude not running (shell prompt visible)
user@machine:~$ 

# ❌ Command not found errors
claude: command not found

# ❌ Python/Node errors
Error: Failed to initialize Claude
Exception: Connection refused

# ❌ File system errors  
No such file or directory: /usr/local/bin/claude

# ✅ Healthy Claude session
PM_READY
```

## Slash Command Integration

### Robust Session Management
```bash
# Both PM and Engineer agents now have robust validation that:
# 1. Detects error conditions before proceeding
# 2. Verifies Claude is actually running (not just shell)
# 3. Kills failed sessions immediately
# 4. Provides clear success/failure feedback
```

That's it. Focus on core orchestration only.