# System Monitor - Advanced Agent Health & Status Analysis

**Command Arguments**: $ARGUMENTS

Provides comprehensive monitoring and health analysis of the autonomous development system using enhanced tmux utilities.

Parse the arguments above to determine the monitoring action (--agents, --health, --snapshot, --recovery, or default full report).

## Usage

```bash
/system-monitor                    # Full system health report
/system-monitor --agents          # Detailed agent status breakdown  
/system-monitor --health          # Quick health check of all agents
/system-monitor --snapshot        # Raw monitoring data for analysis
/system-monitor --recovery        # Identify and fix unresponsive agents
```

## What This Command Does

This command uses the enhanced `tmux_utils.py` to provide deep monitoring capabilities that our bash-based system lacks:

1. **Programmatic Agent Monitoring** - Capture actual terminal content from agents
2. **Health Detection** - Analyze agent output to detect stuck/error states
3. **Resource Analysis** - Track engineer utilization and allocation
4. **Activity Monitoring** - Identify recent progress across all agents
5. **Issue Detection** - Flag potential problems requiring attention

## Implementation

```bash
#!/bin/bash

# Enhanced system monitoring with Python utilities
MONITOR_SCRIPT="/Users/ramiz/ekitchen/ekitchen-ingestion/tmux_utils.py"

case "$1" in
  --agents|--detailed)
    echo "## Detailed Agent Status Analysis"
    echo ""
    python3 "$MONITOR_SCRIPT" --claude-prompt
    ;;
    
  --health|--quick)
    echo "## Quick Health Check"
    echo ""
    python3 "$MONITOR_SCRIPT" --health-check
    echo ""
    echo "### Resource Utilization"
    SNAPSHOT=$(python3 "$MONITOR_SCRIPT" --snapshot)
    echo "$SNAPSHOT" | jq -r '.resource_utilization | "Engineers: \(.engineers_active)/\(.engineers_max) (\(.utilization_percentage | round)% utilization)"'
    echo "$SNAPSHOT" | jq -r '.resource_utilization | "PM Agents: \(.pm_agents_active)"'
    echo "$SNAPSHOT" | jq -r '.resource_utilization | "Orchestrator: \(.orchestrator_active)"'
    ;;
    
  --snapshot|--raw)
    echo "## Raw Monitoring Data"
    echo ""
    python3 "$MONITOR_SCRIPT" --snapshot | jq '.'
    ;;
    
  --recovery|--fix)
    echo "## Agent Recovery Analysis"
    echo ""
    echo "### Checking for unresponsive agents..."
    python3 "$MONITOR_SCRIPT" --kill-unresponsive --dry-run
    echo ""
    echo "### Health summary:"
    python3 "$MONITOR_SCRIPT" --health-check
    echo ""
    read -p "Kill unresponsive agents? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo "Killing unresponsive agents..."
      python3 "$MONITOR_SCRIPT" --kill-unresponsive
      echo ""
      echo "Updated system status:"
      python3 "$MONITOR_SCRIPT" --health-check
    else
      echo "Recovery cancelled."
    fi
    ;;
    
  *)
    # Default: Comprehensive monitoring report
    echo "# Autonomous Development System - Comprehensive Status"
    echo ""
    echo "Generated: $(date)"
    echo ""
    
    # Get the monitoring snapshot
    SNAPSHOT=$(python3 "$MONITOR_SCRIPT" --snapshot)
    
    # Extract key metrics
    TOTAL_SESSIONS=$(echo "$SNAPSHOT" | jq -r '.total_sessions')
    ENGINEERS_ACTIVE=$(echo "$SNAPSHOT" | jq -r '.resource_utilization.engineers_active')
    ENGINEERS_MAX=$(echo "$SNAPSHOT" | jq -r '.resource_utilization.engineers_max')
    UTILIZATION=$(echo "$SNAPSHOT" | jq -r '.resource_utilization.utilization_percentage | round')
    PM_ACTIVE=$(echo "$SNAPSHOT" | jq -r '.resource_utilization.pm_agents_active')
    ORCHESTRATOR_ACTIVE=$(echo "$SNAPSHOT" | jq -r '.resource_utilization.orchestrator_active')
    
    echo "## 📊 System Overview"
    echo "- **Total Agent Sessions**: $TOTAL_SESSIONS"
    echo "- **Engineer Utilization**: $ENGINEERS_ACTIVE/$ENGINEERS_MAX engineers ($UTILIZATION% capacity)"
    echo "- **PM Agents Active**: $PM_ACTIVE"
    echo "- **Orchestrator Active**: $ORCHESTRATOR_ACTIVE"
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
    echo "## ⚠️ System Health"
    ISSUES=$(echo "$SNAPSHOT" | jq -r '.potential_issues[]?' 2>/dev/null)
    if [ -n "$ISSUES" ]; then
      echo "$ISSUES" | while read -r line; do
        echo "- 🚨 $line"
      done
    else
      echo "- ✅ No issues detected - system operating normally"
    fi
    echo ""
    
    # Show agent breakdown
    echo "## 🤖 Agent Status Breakdown"
    echo ""
    
    # Orchestrator status
    ORCHESTRATOR_STATUS=$(echo "$SNAPSHOT" | jq -r '.orchestrator_status.estimated_health // "not_active"')
    echo "### Orchestrator"
    if [ "$ORCHESTRATOR_STATUS" != "not_active" ] && [ "$ORCHESTRATOR_STATUS" != "null" ]; then
      SESSION_NAME=$(echo "$SNAPSHOT" | jq -r '.orchestrator_status.session_name')
      echo "- **Session**: $SESSION_NAME"
      echo "- **Health**: $ORCHESTRATOR_STATUS"
    else
      echo "- **Status**: Not active"
    fi
    echo ""
    
    # PM agents status
    echo "### Project Manager Agents"
    PM_COUNT=$(echo "$SNAPSHOT" | jq -r '.pm_agents | length')
    if [ "$PM_COUNT" -gt 0 ]; then
      echo "$SNAPSHOT" | jq -r '.pm_agents[] | "- **\(.feature_name)** (\(.session_name)): \(.estimated_health)"'
    else
      echo "- No PM agents active"
    fi
    echo ""
    
    # Engineer agents status
    echo "### Engineer Agents"
    ENG_COUNT=$(echo "$SNAPSHOT" | jq -r '.engineer_agents | length')
    if [ "$ENG_COUNT" -gt 0 ]; then
      echo "$SNAPSHOT" | jq -r '.engineer_agents[] | "- **Issue #\(.issue_number)** in \(.feature_name) (\(.session_name)): \(.estimated_health)"'
    else
      echo "- No engineer agents active"
    fi
    echo ""
    
    # Integration with existing commands
    echo "## 🔧 Available Actions"
    echo ""
    echo "**Quick Commands**:"
    echo "- \`/system-monitor --health\` - Quick health check"
    echo "- \`/system-monitor --recovery\` - Fix unresponsive agents"
    echo "- \`/project-status\` - Feature progress overview"
    echo "- \`/orchestrator --status\` - Orchestrator coordination status"
    echo ""
    echo "**Detailed Analysis**:"
    echo "- \`/system-monitor --agents\` - Full agent content analysis"
    echo "- \`/system-monitor --snapshot\` - Raw monitoring data"
    echo ""
    
    # Show Claude analysis prompt for complex issues
    ISSUE_COUNT=$(echo "$SNAPSHOT" | jq -r '.potential_issues | length')
    if [ "$ISSUE_COUNT" -gt 0 ]; then
      echo "**For Complex Issues**:"
      echo "Run \`/system-monitor --agents\` to get detailed analysis and recommendations."
      echo ""
    fi
    ;;
esac
```

## Key Enhancements Over Bash-Only System

### **1. Real Agent Content Analysis**
Unlike our bash scripts that rely on agent self-reporting, this captures actual terminal output:
- See what agents are really doing
- Detect stuck processes or error states
- Analyze response patterns for health assessment

### **2. Intelligent Health Detection**
Programmatically analyzes agent output for:
- Error patterns (exceptions, failed operations)
- Activity indicators (progress updates, command execution)
- Stuck patterns (waiting states, timeouts)
- Unresponsive states (no recent output)

### **3. Structured Data for Decision Making**
Provides JSON-formatted monitoring data that enables:
- Automated resource allocation decisions
- Historical trend analysis
- Integration with external monitoring systems
- Data-driven agent coordination

### **4. Proactive Issue Detection**
Identifies problems before they impact development:
- Engineers working without PM coordination
- PM agents with no active engineers
- Resource allocation imbalances
- Communication breakdowns between agent tiers

### **5. Safe Recovery Operations**
Includes built-in safety mechanisms:
- Confirmation prompts for destructive operations
- Dry-run mode for testing recovery procedures
- Gradual escalation from detection to resolution

## Integration with Existing Framework

This monitoring system seamlessly integrates with your existing tools:

- **Works alongside `/project-status`** - Provides agent-level detail for feature progress
- **Enhances `/orchestrator --status`** - Adds health analysis to coordination reporting  
- **Complements `/board-sync`** - Ensures agents are responsive before attempting sync
- **Supports `/changelog-add`** - Verifies agent completion claims with actual output analysis

The system maintains full compatibility with your bash-based communication while adding the missing programmatic monitoring layer that the original Tmux Orchestrator provided through Python utilities.