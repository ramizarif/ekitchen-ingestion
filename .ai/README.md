# Multi-Agent Framework - Distributed Model

This framework enables multiple Claude Code agents to collaborate on GitHub issues using a **peer-to-peer coordination model**. Unlike traditional centralized approaches, any agent in this repository has full access to coordination commands and can work independently while maintaining system-wide coordination.

## Key Features

### 🔄 Distributed Coordination
- **No central Master Agent** - All agents are equals
- **Peer-to-peer collaboration** through shared coordination files
- **Full command access** for every agent
- **Self-coordination** capabilities

### 🛡️ Conflict Prevention
- **Automatic conflict detection** between agents
- **Real-time coordination** through file updates
- **Collaborative conflict resolution**
- **Timing coordination** for sequential work

### 📋 Issue Management
- **Interactive issue discovery** process
- **Comprehensive issue creation** with all requirements
- **GitHub Projects integration**
- **Automatic project board updates**

## Quick Start

### For Any Agent

1. **Enter Agent Mode**
   ```
   /agent
   ```

2. **Check System Status**
   ```
   status
   ```

3. **Assign Yourself to an Issue**
   ```
   assign 123
   ```

4. **Review Other Agents**
   ```
   agents
   ```

5. **Check for Conflicts**
   ```
   conflicts
   ```

## Available Commands

Every agent has access to the full command suite:

### Status & Monitoring
- `status` - Show all agent activity and progress
- `agents` - List all active agents with detailed status
- `conflicts` - Show current and predicted conflicts
- `branch-health` - Check coordination system health

### Issue & Plan Management
- `assign <issue-number>` - Assign yourself to a GitHub issue
- `review-plans` - Review all pending implementation plans
- `coordinate-all` - Analyze and coordinate all pending plans
- `coordinate <issue-numbers>` - Focus coordination on specific issues

### Phase Coordination
- `check-phases` - Review agents needing phase coordination
- `coordinate-phases <agent-ids>` - Check coordination for specific agents

### Project Board Integration
- `project-status` - Show project board status
- `available-issues` - List issues ready for assignment
- `sync-project` - Synchronize agent status with project board
- `issue-discovery` - Create comprehensive GitHub issues

## Architecture

### Directory Structure
```
.ai/
├── orchestrator/
│   ├── agent-coordinator.md          # Agent coordination guide
│   ├── issue-discovery-questions.md  # Issue discovery questionnaire
│   └── issue-creation-template.md    # GitHub issue template
├── agent-templates/
│   ├── agent-template.md             # Unified agent template
│   ├── implementation-plan-template.md
│   ├── coordination-file-template.md
│   └── conflict-prevention-logic.md
├── agent-coordination/
│   └── {branch-name}.md              # Branch coordination files
└── implementation-plans/
    └── {branch-name}/                # Agent implementation plans

.claude/
├── commands/
│   ├── agent.md                      # Main agent command
│   ├── issue-discovery.md            # Issue discovery command
│   ├── agent/
│   │   ├── spawn.md                  # Issue assignment
│   │   └── status.md                 # Status checking
│   └── project/
│       ├── board.md                  # Project board integration
│       ├── health.md                 # System health check
│       └── reset.md                  # System reset
└── settings.local.json               # Claude Code permissions
```

### Coordination Flow

1. **Agent Assignment**
   - Agent assigns itself to an issue
   - Creates implementation plan
   - Updates coordination file

2. **Peer Review**
   - Other agents can review plans
   - Conflicts are identified automatically
   - Coordination suggestions provided

3. **Collaborative Execution**
   - Agents coordinate timing
   - File conflicts prevented
   - Real-time status updates

4. **Completion**
   - Pull request creation
   - Project board updates
   - Coordination cleanup

## Coordination Files

### Branch Coordination File
Location: `.ai/agent-coordination/{branch-name}.md`

Tracks:
- Active agents and their status
- Implementation plans awaiting review
- Active and predicted conflicts
- Completed work history

### Implementation Plans
Location: `.ai/implementation-plans/{branch-name}/`

Contains:
- Detailed implementation approach
- Conflict analysis
- Phase breakdown
- Risk assessment

## Benefits of Distributed Model

### ✅ Advantages
- **No bottleneck** - No central coordination required
- **Scalable** - Any number of agents can participate
- **Resilient** - No single point of failure
- **Flexible** - Agents can work independently
- **Efficient** - Direct peer coordination

### 🎯 Use Cases
- **Large development teams** with multiple parallel work streams
- **Complex projects** requiring coordination across components
- **Distributed development** with agents working in different time zones
- **Rapid iteration** with frequent conflict potential

## Best Practices

### For Agents
1. **Always check status** before starting work
2. **Review coordination files** regularly
3. **Update status** frequently during work
4. **Coordinate phase transitions** with other agents
5. **Resolve conflicts** collaboratively

### For System Health
1. **Run health checks** periodically
2. **Clean up** completed coordination entries
3. **Monitor** for orphaned agents
4. **Backup** coordination files regularly

## Getting Started

1. **Initialize** by running `/agent` in any Claude Code session
2. **Check system status** with `status` command
3. **Create or assign issues** using available commands
4. **Coordinate with other agents** through shared files
5. **Monitor progress** and resolve conflicts as needed

This distributed approach ensures efficient, conflict-free collaboration while maintaining the flexibility and independence that makes Claude Code powerful.