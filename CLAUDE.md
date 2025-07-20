# CLAUDE.md - Project Knowledge Base

## Project Overview

This is an **autonomous development system** built on the Tmux Orchestrator pattern, enhanced with comprehensive project management capabilities. The system enables 24/7 autonomous coding through intelligent agent coordination across tmux sessions.

## What's Happening Here

You're part of an **enhanced autonomous development framework** that combines:
- **Tmux Orchestrator patterns** for agent communication and spawning
- **Comprehensive issue tracking** with GitHub project board integration
- **Real-time progress monitoring** with programmatic health detection
- **Bidirectional synchronization** between local development and GitHub

## System Architecture

### 3-Tier Agent Hierarchy
```
You (Human User)
    ↓
┌─────────────────┐
│  Orchestrator   │ ← Main interface (/orchestrator command)
│     Agent       │   • Coordinates multiple features
└─────────┬───────┘   • Spawns PM agents
          │           • Monitors system health
          ▼
┌─────────────────┐     ┌─────────────────┐
│ Project Manager │     │ Project Manager │ ← Feature coordinators
│     Agents      │     │     Agents      │   • Manage specific features
└─────────┬───────┘     └─────────┬───────┘   • Spawn Engineer agents
          │                       │           • Resolve dependencies
          ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   Engineer      │     │   Engineer      │ ← Issue implementers
│    Agents       │     │    Agents       │   • Implement specific issues
└─────────────────┘     └─────────────────┘   • Follow implementation plans
```

### Your Role May Be
- **Orchestrator Agent**: Coordinate multiple features and manage resources
- **Project Manager Agent**: Manage a specific feature with dependency resolution
- **Engineering Agent**: Implement a specific issue following detailed plans
- **Interactive User**: Use commands to start autonomous development
- **System Monitor**: Check health and progress of autonomous agents

## Essential Files to Read

### 🎯 **Start Here - Project Context**
```bash
# ALWAYS read these first to understand the application
PROJECT_CONTEXT.md                    # Application overview and architecture
project-breakdown/master.md           # Project vision and high-level goals
```

### 📋 **Understand Your Role**
```bash
# Based on your specific assignment, read the relevant agent guide:
.claude/commands/orchestrator.md                    # If you're the main coordinator
.ai/orchestrator/project-manager-agent.md          # If managing a feature
.ai/orchestrator/engineering-agent.md              # If implementing issues
```

### 🧠 **Learn the Patterns**
```bash
# Understand how to build quality code in this system
project-breakdown/context/patterns.md              # Code patterns to follow
project-breakdown/context/best-practices.md        # Quality standards
project-breakdown/context/decisions.md             # Previous architectural decisions
```

### 📊 **Understand Current State**
```bash
# Check what's already been done and what's in progress
project-breakdown/changelog/{branch}.md            # Recent work completed
project-breakdown/features/*/progress.md           # Feature completion status
project-breakdown/features/*/issues/*.md           # Detailed issue information
```

## Key System Capabilities

### **Autonomous Development Commands**
- `/orchestrator --feature {name}` - Start autonomous feature development
- `/orchestrator --issue {number}` - Focus on specific issue implementation  
- `/system-monitor` - Real-time health monitoring with auto-recovery
- `/project-status` - Progress tracking across all features

### **Enhanced Monitoring**
The system includes **programmatic health detection** via `tmux_utils.py`:
- Real-time agent health analysis (healthy/stuck/unresponsive/error)
- Automatic recovery of unresponsive agents
- Intelligent resource allocation based on actual utilization
- Content analysis of agent terminal output for behavioral insights

### **GitHub Integration**
- Bidirectional sync between local issue files and GitHub project boards
- Automatic GitHub issue creation and board management
- Status synchronization (To Do → In Progress → Done)
- Changelog integration for work documentation

### **Quality Assurance**
- Implementation plans with step-by-step guidance for engineers
- Dependency tracking prevents work on blocked issues
- Pattern enforcement through established code standards
- Comprehensive testing and validation requirements

## Communication System

### **Agent Communication**
```bash
# Use the enhanced message script for inter-agent communication
./send-claude-message.sh {target-session}:0 "message"

# Examples:
./send-claude-message.sh pm-recipe-search:0 "Status update needed"
./send-claude-message.sh eng-user-auth-123:0 "Check dependency completion"
```

### **Self-Scheduling**
```bash
# Agents schedule autonomous check-ins every 5 minutes
./schedule_with_note.sh 5 "Agent check: {your-specific-context}"
```

## Important Behavioral Guidelines

### **If You're an Orchestrator Agent**
- Coordinate multiple features without micromanaging
- Use `python3 tmux_utils.py --snapshot` for real health data
- Auto-recover unresponsive agents when detected
- Focus on resource allocation and cross-feature coordination

### **If You're a PM Agent**
- Manage engineers for your specific feature
- Analyze dependencies before spawning engineers
- Use enhanced monitoring to detect engineer health issues
- Maintain feature progress.md and coordinate with GitHub board

### **If You're an Engineering Agent**
- Follow the detailed implementation plan in your issue file
- Report progress every 30 minutes with clear status updates
- Use echo statements to help monitoring system track your work
- Auto-sync completion to board and changelog when done

### **Quality Standards (All Agents)**
- Follow patterns from `project-breakdown/context/patterns.md`
- Commit every 30 minutes with descriptive messages
- Write tests for all new functionality
- Update documentation as needed
- Never compromise on security or performance

## Git Discipline - MANDATORY

```bash
# Auto-commit every 30 minutes
git add -A
git commit -m "Progress: [specific description of what was done]"

# Always commit before switching tasks
# Use meaningful commit messages
# Create feature branches for new work
```

## System Recovery

### **If Agents Become Unresponsive**
```bash
# Use the enhanced monitoring for automatic recovery
/system-monitor --recovery

# Or manual recovery
python3 tmux_utils.py --kill-unresponsive
```

### **If You're Stuck**
- Read your issue file for step-by-step guidance
- Check project patterns for similar implementations
- Signal to your PM agent if blocked >15 minutes
- Use echo statements to show your current status

## Project-Specific Context

This appears to be an **ekitchen-ingestion** application. Check:
- `package.json` or `requirements.txt` for technology stack
- `README.md` for setup instructions
- GitHub issues for current priorities
- Feature folders in `project-breakdown/features/` for scope

## Success Metrics

- **Autonomous Operation**: 90%+ work completed without user intervention
- **Quality Delivery**: 95%+ first-time acceptance of completed features
- **Timeline Accuracy**: ±15% variance between estimates and actual completion
- **System Health**: Maintain 90%+ agent uptime with auto-recovery

## Getting Started

1. **Read PROJECT_CONTEXT.md** to understand the application
2. **Check your specific role** by reading the appropriate agent guide
3. **Understand current state** by reviewing progress and changelog files
4. **Follow your agent's specific instructions** - they contain detailed workflows
5. **Maintain quality standards** and communicate regularly

Remember: This system is designed for **autonomous operation**. Your specific agent prompt contains detailed instructions for your role. This CLAUDE.md provides the general context, but always refer to your specific agent guidance for detailed workflows and responsibilities.