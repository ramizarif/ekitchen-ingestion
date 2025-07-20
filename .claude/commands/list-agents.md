# List Agents - View All Active Autonomous Agents

**Command Arguments**: $ARGUMENTS

List all active autonomous agents with their health status, current work, and session information.

Parse arguments for filtering options (--orchestrator, --pm, --engineers, --health, or default all).

## Usage

```bash
/list-agents                     # Show all active agents
/list-agents --orchestrator      # Show only orchestrator agents  
/list-agents --pm               # Show only PM agents
/list-agents --engineers        # Show only engineer agents
/list-agents --health           # Show agents with health issues
```

## Implementation

```bash
#!/bin/bash

# Enhanced agent listing with health and activity info
MONITOR_SCRIPT="/Users/ramiz/ekitchen/ekitchen-ingestion/utils/tmux_utils.py"

case "$1" in
  --orchestrator)
    echo "## Orchestrator Agents"
    echo ""
    python3 "$MONITOR_SCRIPT" --snapshot | jq -r '
      if .orchestrator_status then
        "🎯 **Orchestrator Agent**",
        "   Session: " + .orchestrator_status.session_name,
        "   Health: " + .orchestrator_status.estimated_health,
        "   Active: " + (.orchestrator_status.is_active | tostring),
        "   Recent: " + (.orchestrator_status.content_preview[-100:] // "No content"),
        ""
      else
        "No orchestrator agents active"
      end'
    ;;
    
  --pm)
    echo "## Project Manager Agents"
    echo ""
    python3 "$MONITOR_SCRIPT" --snapshot | jq -r '
      if (.pm_agents | length) > 0 then
        .pm_agents[] | 
        "🏗️ **PM Agent: " + .feature_name + "**",
        "   Session: " + .session_name,
        "   Health: " + .estimated_health,
        "   Window: " + .window_name,
        "   Active: " + (.is_active | tostring),
        "   Recent: " + (.content_preview[-100:] // "No content"),
        ""
      else
        "No PM agents active"
      end'
    ;;
    
  --engineers)
    echo "## Engineer Agents"
    echo ""
    python3 "$MONITOR_SCRIPT" --snapshot | jq -r '
      if (.engineer_agents | length) > 0 then
        .engineer_agents[] | 
        "⚙️ **Engineer: Issue #" + .issue_number + "**",
        "   Session: " + .session_name,
        "   Feature: " + .feature_name,
        "   Health: " + .estimated_health,
        "   Window: " + .window_name,
        "   Active: " + (.is_active | tostring),
        "   Recent: " + (.content_preview[-100:] // "No content"),
        ""
      else
        "No engineer agents active"
      end'
    ;;
    
  --health)
    echo "## Agents with Health Issues"
    echo ""
    python3 "$MONITOR_SCRIPT" --snapshot | jq -r '
      (.pm_agents[] | select(.estimated_health != "healthy")),
      (.engineer_agents[] | select(.estimated_health != "healthy")),
      (if .orchestrator_status and .orchestrator_status.estimated_health != "healthy" then .orchestrator_status else empty end)
      | 
      "⚠️ **" + (.feature_name // "Orchestrator") + "**",
      "   Session: " + .session_name,
      "   Health: " + .estimated_health,
      "   Issue: " + (.issue_number // "N/A"),
      "   Recent: " + (.content_preview[-100:] // "No content"),
      ""'
    ;;
    
  *)
    # Default: Show all agents with organized view
    echo "# Autonomous Agent System Status"
    echo ""
    echo "Generated: $(date)"
    echo ""
    
    # Get comprehensive status
    SNAPSHOT=$(python3 "$MONITOR_SCRIPT" --snapshot)
    
    # Show orchestrator
    echo "## 🎯 Orchestrator Agent"
    ORCH_STATUS=$(echo "$SNAPSHOT" | jq -r '.orchestrator_status.estimated_health // "not_active"')
    if [ "$ORCH_STATUS" != "not_active" ] && [ "$ORCH_STATUS" != "null" ]; then
      ORCH_SESSION=$(echo "$SNAPSHOT" | jq -r '.orchestrator_status.session_name')
      echo "- **Session**: $ORCH_SESSION"
      echo "- **Health**: $ORCH_STATUS"
      echo "- **Active**: $(echo "$SNAPSHOT" | jq -r '.orchestrator_status.is_active')"
    else
      echo "- **Status**: Not active"
    fi
    echo ""
    
    # Show PM agents
    echo "## 🏗️ Project Manager Agents"
    PM_COUNT=$(echo "$SNAPSHOT" | jq -r '.pm_agents | length')
    if [ "$PM_COUNT" -gt 0 ]; then
      echo "$SNAPSHOT" | jq -r '.pm_agents[] | "- **\(.feature_name)** (\(.session_name)): \(.estimated_health)"'
    else
      echo "- No PM agents active"
    fi
    echo ""
    
    # Show engineer agents
    echo "## ⚙️ Engineer Agents"
    ENG_COUNT=$(echo "$SNAPSHOT" | jq -r '.engineer_agents | length')
    if [ "$ENG_COUNT" -gt 0 ]; then
      echo "$SNAPSHOT" | jq -r '.engineer_agents[] | "- **Issue #\(.issue_number)** in \(.feature_name) (\(.session_name)): \(.estimated_health)"'
    else
      echo "- No engineer agents active"
    fi
    echo ""
    
    # Show resource utilization
    echo "## 📊 Resource Utilization"
    ENGINEERS_ACTIVE=$(echo "$SNAPSHOT" | jq -r '.resource_utilization.engineers_active')
    ENGINEERS_MAX=$(echo "$SNAPSHOT" | jq -r '.resource_utilization.engineers_max')
    UTILIZATION=$(echo "$SNAPSHOT" | jq -r '.resource_utilization.utilization_percentage | round')
    echo "- **Engineers**: $ENGINEERS_ACTIVE/$ENGINEERS_MAX ($UTILIZATION% capacity)"
    echo "- **PM Agents**: $PM_COUNT"
    echo "- **Total Sessions**: $(echo "$SNAPSHOT" | jq -r '.total_sessions')"
    echo ""
    
    # Show recent activity
    echo "## 🔄 Recent Activity"
    RECENT_ACTIVITY=$(echo "$SNAPSHOT" | jq -r '.recent_activity[]?' 2>/dev/null)
    if [ -n "$RECENT_ACTIVITY" ]; then
      echo "$RECENT_ACTIVITY" | while read -r line; do
        echo "- $line"
      done
    else
      echo "- No recent activity detected"
    fi
    echo ""
    
    # Show potential issues
    ISSUE_COUNT=$(echo "$SNAPSHOT" | jq -r '.potential_issues | length')
    if [ "$ISSUE_COUNT" -gt 0 ]; then
      echo "## ⚠️ Issues Requiring Attention"
      echo "$SNAPSHOT" | jq -r '.potential_issues[]' | while read -r line; do
        echo "- 🚨 $line"
      done
    else
      echo "## ✅ System Health"
      echo "- All agents operating normally"
    fi
    echo ""
    
    # Show quick actions
    echo "## 🔧 Quick Actions"
    echo "- \`/system-monitor --health\` - Quick health check"
    echo "- \`/system-monitor --recovery\` - Fix unresponsive agents"
    echo "- \`/kill-agents --health\` - Kill unhealthy agents"
    echo "- \`/kill-agents --all\` - Stop all autonomous agents"
    echo ""
    ;;
esac
```

## Integration Notes

This command uses the enhanced `utils/tmux_utils.py` monitoring system to provide:

- **Real-time agent discovery** from tmux sessions
- **Health status analysis** from terminal content
- **Activity monitoring** with recent output
- **Resource utilization** tracking
- **Structured data** for quick decision making

Perfect for understanding the current state of your autonomous development system at a glance.