# Kill Agents - Terminate Autonomous Agents

**Command Arguments**: $ARGUMENTS

Safely terminate autonomous agents with options for selective or complete shutdown.

Parse arguments for termination scope (--all, --health, --pm, --engineers, --session {name}, or default interactive selection).

## Usage

```bash
/kill-agents                     # Interactive selection of agents to kill
/kill-agents --all              # Kill all autonomous agents
/kill-agents --health           # Kill only unhealthy agents
/kill-agents --pm               # Kill all PM agents (and their engineers)
/kill-agents --engineers        # Kill all engineer agents only
/kill-agents --session {name}   # Kill specific session by name
```

## Implementation

```bash
#!/bin/bash

# Enhanced agent termination with safety checks
MONITOR_SCRIPT="/Users/ramiz/ekitchen/ekitchen-ingestion/utils/tmux_utils.py"

# Safety confirmation function
confirm_action() {
  local message="$1"
  echo "⚠️  WARNING: $message"
  read -p "Are you sure? Type 'yes' to continue: " -r
  if [[ $REPLY != "yes" ]]; then
    echo "Operation cancelled."
    exit 0
  fi
}

case "$1" in
  --all)
    confirm_action "This will terminate ALL autonomous agents and stop all development work."
    
    echo "## Terminating All Autonomous Agents"
    echo ""
    
    # Get all autonomous sessions
    AUTONOMOUS_SESSIONS=$(tmux list-sessions -F '#{session_name}' | grep -E '^(orchestrator|pm-|eng-)' || echo "")
    
    if [ -z "$AUTONOMOUS_SESSIONS" ]; then
      echo "No autonomous agents found to terminate."
      exit 0
    fi
    
    echo "Found autonomous sessions:"
    echo "$AUTONOMOUS_SESSIONS" | while read session; do
      echo "- $session"
    done
    echo ""
    
    # Kill each session
    echo "Terminating sessions..."
    echo "$AUTONOMOUS_SESSIONS" | while read session; do
      if [ -n "$session" ]; then
        echo "Killing $session..."
        tmux kill-session -t "$session" 2>/dev/null && echo "✅ $session terminated" || echo "❌ Failed to kill $session"
      fi
    done
    
    echo ""
    echo "🛑 All autonomous agents terminated."
    echo "Use '/orchestrator --feature {name}' to restart autonomous development."
    ;;
    
  --health)
    echo "## Terminating Unhealthy Agents"
    echo ""
    
    # Use tmux_utils.py to identify unhealthy agents
    python3 "$MONITOR_SCRIPT" --kill-unresponsive
    
    echo ""
    echo "Unhealthy agents have been terminated."
    echo "Healthy agents continue working normally."
    ;;
    
  --pm)
    confirm_action "This will terminate all PM agents and their engineers."
    
    echo "## Terminating All PM Agents"
    echo ""
    
    PM_SESSIONS=$(tmux list-sessions -F '#{session_name}' | grep '^pm-' || echo "")
    
    if [ -z "$PM_SESSIONS" ]; then
      echo "No PM agents found to terminate."
      exit 0
    fi
    
    echo "Found PM sessions:"
    echo "$PM_SESSIONS" | while read session; do
      echo "- $session"
    done
    echo ""
    
    # Also find engineers under these PMs
    echo "Finding associated engineer sessions..."
    for pm_session in $PM_SESSIONS; do
      feature_name=$(echo "$pm_session" | sed 's/^pm-//')
      eng_sessions=$(tmux list-sessions -F '#{session_name}' | grep "^eng-$feature_name-" || echo "")
      if [ -n "$eng_sessions" ]; then
        echo "Engineers under $pm_session:"
        echo "$eng_sessions" | while read eng; do
          echo "  - $eng"
        done
      fi
    done
    echo ""
    
    # Kill PM sessions (engineers will be orphaned and should also be killed)
    echo "Terminating PM agents and their engineers..."
    for pm_session in $PM_SESSIONS; do
      feature_name=$(echo "$pm_session" | sed 's/^pm-//')
      
      # Kill engineers first
      eng_sessions=$(tmux list-sessions -F '#{session_name}' | grep "^eng-$feature_name-" || echo "")
      for eng_session in $eng_sessions; do
        if [ -n "$eng_session" ]; then
          echo "Killing engineer $eng_session..."
          tmux kill-session -t "$eng_session" 2>/dev/null
        fi
      done
      
      # Kill PM
      echo "Killing PM $pm_session..."
      tmux kill-session -t "$pm_session" 2>/dev/null && echo "✅ $pm_session terminated"
    done
    
    echo ""
    echo "🛑 All PM agents and their engineers terminated."
    ;;
    
  --engineers)
    confirm_action "This will terminate all engineer agents but leave PM agents running."
    
    echo "## Terminating All Engineer Agents"
    echo ""
    
    ENG_SESSIONS=$(tmux list-sessions -F '#{session_name}' | grep '^eng-' || echo "")
    
    if [ -z "$ENG_SESSIONS" ]; then
      echo "No engineer agents found to terminate."
      exit 0
    fi
    
    echo "Found engineer sessions:"
    echo "$ENG_SESSIONS" | while read session; do
      echo "- $session"
    done
    echo ""
    
    # Kill engineer sessions
    echo "Terminating engineer agents..."
    echo "$ENG_SESSIONS" | while read session; do
      if [ -n "$session" ]; then
        echo "Killing $session..."
        tmux kill-session -t "$session" 2>/dev/null && echo "✅ $session terminated"
      fi
    done
    
    echo ""
    echo "🛑 All engineer agents terminated."
    echo "PM agents remain active and can spawn new engineers."
    ;;
    
  --session)
    if [ -z "$2" ]; then
      echo "Error: Please specify session name."
      echo "Usage: /kill-agents --session {session-name}"
      echo ""
      echo "Available sessions:"
      tmux list-sessions -F '#{session_name}' | grep -E '^(orchestrator|pm-|eng-)' || echo "No autonomous sessions found"
      exit 1
    fi
    
    SESSION_NAME="$2"
    
    # Check if session exists
    if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
      echo "Error: Session '$SESSION_NAME' not found."
      echo ""
      echo "Available sessions:"
      tmux list-sessions -F '#{session_name}' | grep -E '^(orchestrator|pm-|eng-)' || echo "No autonomous sessions found"
      exit 1
    fi
    
    # Determine session type for appropriate warning
    if [[ "$SESSION_NAME" == "orchestrator" ]]; then
      confirm_action "This will terminate the orchestrator agent and stop all coordination."
    elif [[ "$SESSION_NAME" == pm-* ]]; then
      confirm_action "This will terminate PM agent '$SESSION_NAME' and potentially orphan its engineers."
    elif [[ "$SESSION_NAME" == eng-* ]]; then
      confirm_action "This will terminate engineer agent '$SESSION_NAME' and stop its work."
    fi
    
    echo "## Terminating Session: $SESSION_NAME"
    echo ""
    
    # Show session info before killing
    echo "Session information:"
    tmux list-sessions -F '#{session_name}: #{session_windows} windows, #{?session_attached,attached,not attached}' | grep "^$SESSION_NAME:" || echo "Session details not available"
    echo ""
    
    # Kill the session
    echo "Terminating $SESSION_NAME..."
    if tmux kill-session -t "$SESSION_NAME" 2>/dev/null; then
      echo "✅ Session '$SESSION_NAME' terminated successfully."
    else
      echo "❌ Failed to terminate session '$SESSION_NAME'."
    fi
    ;;
    
  *)
    # Interactive mode - show agents and let user choose
    echo "# Interactive Agent Termination"
    echo ""
    
    # Get current agents
    SNAPSHOT=$(python3 "$MONITOR_SCRIPT" --snapshot 2>/dev/null || echo '{"pm_agents":[],"engineer_agents":[],"orchestrator_status":null}')
    
    # Show current agents
    echo "## Current Autonomous Agents"
    echo ""
    
    # Orchestrator
    ORCH_STATUS=$(echo "$SNAPSHOT" | jq -r '.orchestrator_status.estimated_health // "not_active"')
    if [ "$ORCH_STATUS" != "not_active" ] && [ "$ORCH_STATUS" != "null" ]; then
      ORCH_SESSION=$(echo "$SNAPSHOT" | jq -r '.orchestrator_status.session_name')
      echo "🎯 **Orchestrator**: $ORCH_SESSION ($ORCH_STATUS)"
    fi
    
    # PM agents
    PM_COUNT=$(echo "$SNAPSHOT" | jq -r '.pm_agents | length')
    if [ "$PM_COUNT" -gt 0 ]; then
      echo ""
      echo "🏗️ **PM Agents**:"
      echo "$SNAPSHOT" | jq -r '.pm_agents[] | "   - \(.feature_name) (\(.session_name)): \(.estimated_health)"'
    fi
    
    # Engineer agents
    ENG_COUNT=$(echo "$SNAPSHOT" | jq -r '.engineer_agents | length')
    if [ "$ENG_COUNT" -gt 0 ]; then
      echo ""
      echo "⚙️ **Engineer Agents**:"
      echo "$SNAPSHOT" | jq -r '.engineer_agents[] | "   - Issue #\(.issue_number) in \(.feature_name) (\(.session_name)): \(.estimated_health)"'
    fi
    
    if [ "$ORCH_STATUS" = "not_active" ] && [ "$PM_COUNT" -eq 0 ] && [ "$ENG_COUNT" -eq 0 ]; then
      echo "No autonomous agents currently active."
      exit 0
    fi
    
    echo ""
    echo "## Termination Options"
    echo ""
    echo "Choose what to terminate:"
    echo "1. All agents (complete shutdown)"
    echo "2. Only unhealthy agents"
    echo "3. All PM agents (and their engineers)"
    echo "4. All engineer agents only"
    echo "5. Specific session by name"
    echo "6. Cancel"
    echo ""
    
    read -p "Enter your choice (1-6): " -r choice
    
    case $choice in
      1)
        /kill-agents --all
        ;;
      2)
        /kill-agents --health
        ;;
      3)
        /kill-agents --pm
        ;;
      4)
        /kill-agents --engineers
        ;;
      5)
        echo ""
        echo "Available sessions:"
        tmux list-sessions -F '#{session_name}' | grep -E '^(orchestrator|pm-|eng-)'
        echo ""
        read -p "Enter session name: " -r session_name
        /kill-agents --session "$session_name"
        ;;
      6)
        echo "Operation cancelled."
        ;;
      *)
        echo "Invalid choice. Operation cancelled."
        ;;
    esac
    ;;
esac
```

## Safety Features

- **Confirmation prompts** for destructive operations
- **Session validation** before termination
- **Cascade handling** (PM termination includes engineers)
- **Interactive mode** for safe selection
- **Clear feedback** on termination success/failure

## Integration Notes

- Uses `utils/tmux_utils.py` for intelligent agent detection
- Handles proper cleanup of dependent sessions
- Provides clear status feedback
- Maintains system state consistency