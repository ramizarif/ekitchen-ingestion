# eKitchen Ingestion - Autonomous AI Development System

An advanced autonomous development framework built on enhanced Tmux Orchestrator patterns, featuring intelligent agent coordination, real-time health monitoring, and GitHub project board integration.

## 🚀 What This Is

This repository showcases a **fully autonomous AI development system** that can:

- **Spawn coordinated AI agents** (Orchestrator → PM → Engineers) across tmux sessions
- **Work autonomously for hours** with intelligent health monitoring and auto-recovery
- **Integrate with GitHub project boards** for seamless issue tracking and status sync
- **Enforce quality standards** with automated git workflow management
- **Provide real-time feedback** based on architectural patterns and project context

## 🏗️ System Architecture

### 3-Tier Agent Hierarchy
```
Human User
    ↓
┌─────────────────┐
│  Orchestrator   │ ← Main coordination (/orchestrator command)
│     Agent       │   • Spawns and monitors PM agents
└─────────┬───────┘   • Enforces git discipline
          │           • Provides architectural guidance
          ▼
┌─────────────────┐     ┌─────────────────┐
│ Project Manager │     │ Project Manager │ ← Feature coordinators
│     Agents      │     │     Agents      │   • Manage specific features
└─────────┬───────┘     └─────────┬───────┘   • Spawn and monitor engineers
          │                       │           • Handle dependencies
          ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   Engineer      │     │   Engineer      │ ← Implementation specialists
│    Agents       │     │    Agents       │   • Follow detailed plans
└─────────────────┘     └─────────────────┘   • Auto-sync to boards
```

## 🧠 Enhanced Monitoring System

### Programmatic Agent Health Detection
- **Real-time terminal content analysis** using `utils/tmux_utils.py`
- **Intelligent health classification**: healthy/stuck/unresponsive/error
- **Automatic agent recovery** when unresponsive agents are detected
- **Structured monitoring data** for advanced decision making

### Smart Resource Management
- **Max 3 engineers system-wide** with intelligent allocation
- **Dynamic check-in intervals** (5 min active, 15 min idle)
- **Cross-feature coordination** prevents resource conflicts

## 📁 Repository Structure

```
├── recipe_discovery_mcp/            # Recipe Discovery MCP Server
│   ├── server.py                    # Main FastMCP server
│   ├── config.py                    # Configuration management
│   ├── models.py                    # Data models (RecipeData, etc.)
│   └── utils/                       # Error handling & logging
├── tests/                           # Comprehensive test suite
│   ├── unit/                        # Unit tests for components
│   └── integration/                 # Integration tests
├── scripts/                          # Autonomous system scripts
│   ├── send-claude-message.sh       # Inter-agent communication
│   ├── schedule_with_note.sh        # Self-scheduling system
│   └── start-orchestrator.sh        # System launcher
├── utils/                            # Enhanced monitoring utilities
│   └── tmux_utils.py                # Programmatic health detection
├── .claude/commands/                 # Claude Code slash commands
│   ├── orchestrator.md              # Main coordination interface
│   ├── system-monitor.md            # Advanced health monitoring
│   ├── project-status.md            # Progress tracking
│   ├── issue-discovery.md           # Issue creation with board integration
│   └── board-sync.md                # GitHub project board sync
├── .ai/orchestrator/                 # Agent behavior definitions
│   ├── project-manager-agent.md     # PM agent workflows
│   ├── engineering-agent.md         # Engineer agent behaviors
│   └── issue-file-template.md       # Implementation plan templates
├── project-breakdown/               # Project structure and tracking
│   ├── features/                    # Feature-based organization
│   ├── context/                     # Patterns and best practices
│   └── changelog/                   # Work documentation
├── docs/                            # System documentation
│   ├── AUTONOMOUS_DEVELOPMENT_GUIDE.md  # Complete workflow guide
│   └── MONITORING_COMPARISON.md     # Enhanced monitoring features
├── CLAUDE.md                        # Agent context and guidelines
├── PROJECT_CONTEXT.md              # Application-specific context
├── requirements.txt                 # Python dependencies
└── .env.example                     # Configuration template
```

## 🚀 Quick Start

### 1. Setup Recipe Discovery MCP
```bash
# Install Python dependencies
pip install -r requirements.txt

# Copy configuration template
cp .env.example .env

# Test the MCP server
python -m recipe_discovery_mcp.server
```

### 2. Launch the Autonomous System
```bash
./scripts/start-orchestrator.sh
```

### 3. Start Autonomous Development
```bash
# For specific issue implementation
/orchestrator --issue 5

# For entire feature development
/orchestrator --feature recipe-discovery-mcp

# For multiple features
/orchestrator --features "feature1,feature2"
```

### 4. Monitor Real-Time Progress
```bash
# Quick health check
/system-monitor --health

# Comprehensive status
/system-monitor

# Detailed agent analysis
/system-monitor --agents

# Auto-recovery of stuck agents
/system-monitor --recovery
```

## 🔥 Key Features

### **Intelligent Agent Coordination**
- **Autonomous spawning** of PM and Engineer agents based on workload
- **Context-aware briefings** with project patterns and architectural guidance
- **Intelligent resource allocation** prevents overloading and conflicts

### **Advanced Git Workflow Management**
- **Mandatory branch safety checks** prevent commits to main/development
- **Automated commit reminders** every 30 minutes with progress tracking
- **Feature branch creation** for all issue work

### **GitHub Project Board Integration**
- **Bidirectional synchronization** between local files and GitHub boards
- **Automatic status updates** (To Do → In Progress → Done)
- **Issue creation with board placement** using GitHub Projects MCP

### **Quality Assurance Automation**
- **Architectural pattern enforcement** from project context
- **Implementation plan adherence** with step-by-step guidance
- **Automated testing and validation** requirements

### **Self-Healing System**
- **Unresponsive agent detection** and automatic restart
- **Health-based feedback** provides contextual guidance to stuck agents
- **Smart scheduling** adapts check-in frequency based on activity

## 🛠️ Advanced Usage

### Feature Discovery and Planning
```bash
# Create comprehensive feature breakdown
/new-feature-breakdown "Your feature description here"

# Generate detailed implementation issues
/issue-discovery

# Check overall project status
/project-status
```

### Monitoring and Management
```bash
# Watch agents work in real-time
tmux attach-session -t eng-issue-4:0

# Get structured analysis for optimization
/system-monitor --agents

# Sync local changes with GitHub board
/board-sync --feature feature-name
```

## 🔧 System Requirements

- **tmux** - Session management
- **jq** - JSON processing for monitoring
- **Python 3** - Enhanced monitoring utilities
- **GitHub CLI** (optional) - Advanced GitHub integration
- **Claude Code** - AI agent coordination

## 📊 Success Metrics

- **90%+ autonomous operation** without human intervention
- **95%+ first-time acceptance** of completed features
- **±15% timeline accuracy** between estimates and completion
- **90%+ agent uptime** with auto-recovery

## 🎯 Perfect For

- **Autonomous development sessions** while you're away
- **Complex feature implementations** requiring coordination
- **Quality-focused development** with automated standards enforcement
- **Teams wanting to scale** AI-assisted development

## 🤝 Contributing

This system demonstrates advanced autonomous AI development patterns. Feel free to:
- Study the agent coordination patterns
- Adapt the monitoring system for your projects
- Extend the GitHub integration capabilities
- Improve the quality assurance automation

---

**Built with Claude Code** • **Enhanced Tmux Orchestrator** • **Autonomous AI Development**
