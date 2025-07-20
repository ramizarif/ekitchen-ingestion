# Autonomous Development System - Complete Guide

This is your comprehensive guide to the autonomous development system that combines Tmux Orchestrator patterns with your enhanced project management framework.

## 🏗️ **System Architecture Overview**

### **3-Tier Agent Hierarchy**
```
You (Human)
    ↓
┌─────────────────┐
│  Orchestrator   │ ← Your main interface (orchestrator:0)
│     Agent       │   • Coordinates multiple features
└─────────┬───────┘   • Spawns PM agents
          │           • Monitors resource allocation
          ▼
┌─────────────────┐     ┌─────────────────┐
│ Project Manager │     │ Project Manager │ ← Feature coordinators (pm-{feature}:0)
│  Agent (PM-1)   │     │  Agent (PM-2)   │   • Manage specific features
└─────────┬───────┘     └─────────┬───────┘   • Spawn Engineer agents
          │                       │           • Resolve dependencies
          ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   Engineer 1    │     │   Engineer 2    │ ← Issue implementers (eng-{feature}-{issue}:0)
│  (Issue #123)   │     │  (Issue #124)   │   • Implement specific issues
└─────────────────┘     └─────────────────┘   • Follow implementation plans
```

### **Tmux Session Architecture**
```bash
# Active Sessions Structure:
orchestrator:0          # Your main interface - Orchestrator Agent
pm-recipe-search:0      # PM Agent managing recipe search feature
pm-user-auth:0          # PM Agent managing user authentication feature
eng-recipe-search-123:0 # Engineer implementing issue #123
eng-recipe-search-124:0 # Engineer implementing issue #124
eng-user-auth-125:0     # Engineer implementing issue #125
```

## 🚀 **Complete Workflow Options**

### **Flow 1: Strategic Feature Development**
```bash
# Start: Strategic planning to autonomous execution
You → /new-feature-breakdown "I want users to search recipes by ingredients"
     ↓
   Enhanced Issue Discovery creates comprehensive feature plan with dependencies
     ↓
You → ./start-orchestrator.sh
     ↓ 
You → "/orchestrator --feature recipe-search"
     ↓
   System autonomously develops entire feature while you sleep
```

### **Flow 2: Targeted Issue Implementation**
```bash
# Start: Specific issue to autonomous completion
You → ./start-orchestrator.sh
     ↓
You → "/orchestrator --issue 123"
     ↓
   System spawns single Engineer agent for focused implementation
```

### **Flow 3: Multi-Feature Parallel Development**
```bash
# Start: Multiple features simultaneously
You → ./start-orchestrator.sh
     ↓
You → "/orchestrator --features 'recipe-search,user-profiles,social-sharing'"
     ↓
   System spawns multiple PM agents managing 3 features with coordinated engineers
```

### **Flow 4: Manual Issue Creation + Autonomous Execution**
```bash
# Start: Manual planning, autonomous execution
You → /issue-discovery (create detailed issues with implementation plans)
     ↓
   Multiple rounds of issue creation with dependencies
     ↓
You → ./start-orchestrator.sh → "/orchestrator --feature {feature-name}"
     ↓
   Autonomous execution of manually planned work
```

### **Flow 5: Real-Time Monitoring + Status Queries**
```bash
# Ongoing: Monitor autonomous development
Autonomous agents working in background
     ↓
You → /project-status (anytime)
You → /project-status --feature recipe-search
You → /orchestrator --status
     ↓
   Real-time progress reports without interrupting agents
```

### **Flow 6: Session Review + Continuation**
```bash
# End: Session completion and review
Agents complete work or you return from break
     ↓
You → /session-summary
     ↓
   Comprehensive report of accomplishments and decisions
     ↓
You → Continue with next features or adjust priorities
```

## 🤖 **Agent Spawning & Management Deep Dive**

### **1. Orchestrator Agent Spawning**

**How It Starts:**
```bash
# User runs:
./start-orchestrator.sh

# Script does:
1. tmux new-session -d -s "orchestrator"              # Creates tmux session
2. tmux send-keys -t "orchestrator:0" 'claude' Enter  # Starts Claude
3. Sends briefing message with orchestrator role
```

**Files the Orchestrator Reads:**
```bash
# Orchestrator Agent initialization sequence:
1. PROJECT_CONTEXT.md                    # Application overview
2. project-breakdown/master.md           # Project vision
3. .claude/commands/orchestrator.md      # Its role and capabilities
4. project-breakdown/context/patterns.md # Code patterns
5. project-breakdown/features/           # All feature contexts
```

**How Orchestrator Spawns PM Agents:**
```bash
# When you say: "/orchestrator --feature recipe-search"
# Orchestrator executes:

1. # Read feature context
   cat project-breakdown/features/recipe-search/feature-summary.md
   cat project-breakdown/features/recipe-search/progress.md
   cat project-breakdown/features/recipe-search/issues/*.md

2. # Create PM session
   tmux new-session -d -s pm-recipe-search

3. # Start Claude in PM session
   tmux send-keys -t pm-recipe-search:0 'claude' Enter

4. # Brief PM Agent with context
   ./send-claude-message.sh pm-recipe-search:0 "You are a Project Manager for the recipe-search feature. Read PROJECT_CONTEXT.md and project-breakdown/features/recipe-search/ then spawn engineers for ready issues. Schedule check-ins every 5 minutes."

5. # Schedule orchestrator check-in
   ./schedule_with_note.sh 5 "Orchestrator check: Monitor all features and coordinate resources"
```

### **2. PM Agent Spawning Engineers**

**Files PM Agent Reads:**
```bash
# PM Agent initialization sequence:
1. PROJECT_CONTEXT.md                                    # Application context
2. project-breakdown/features/{feature}/feature-summary.md   # Feature scope
3. project-breakdown/features/{feature}/progress.md         # Current status
4. project-breakdown/features/{feature}/issue-breakdown.md  # Issue overview
5. project-breakdown/features/{feature}/issues/*.md         # All issue details
6. project-breakdown/context/patterns.md                    # Code patterns
7. .ai/orchestrator/project-manager-agent.md               # PM role guide
```

**How PM Agent Spawns Engineers:**
```bash
# PM Agent dependency analysis and spawning process:

1. # Analyze all issues in feature
   for issue_file in project-breakdown/features/recipe-search/issues/*.md; do
     # Extract: status, dependencies, effort, priority
   done

2. # Build dependency graph
   # Identify issues with status="To Do" and all dependencies="Done"

3. # Prioritize ready issues (up to 3 simultaneously)
   ready_issues = [
     {issue: 123, priority: "High", effort: "Medium", blocks: [124, 125]},
     {issue: 126, priority: "Medium", effort: "Small", blocks: []},
     {issue: 127, priority: "Low", effort: "Large", blocks: []}
   ]

4. # Spawn engineers for top 3 priority issues
   for issue in ready_issues[:3]:
     # Create engineer session
     tmux new-session -d -s eng-recipe-search-${issue.number}
     
     # Start Claude
     tmux send-keys -t eng-recipe-search-${issue.number}:0 'claude' Enter
     
     # Brief engineer
     ./send-claude-message.sh eng-recipe-search-${issue.number}:0 "You are an Engineer assigned to implement issue #${issue.number}. Read PROJECT_CONTEXT.md and project-breakdown/features/recipe-search/issues/issue-${issue.number}.md for your implementation plan. Follow the step-by-step guidance, auto-sync progress to GitHub board, and update changelogs when complete."

5. # Schedule PM check-in
   ./schedule_with_note.sh 5 "PM check for recipe-search: Monitor engineers and coordinate resources"
```

### **3. Engineer Agent Implementation Process**

**Files Engineer Agent Reads:**
```bash
# Engineer Agent initialization sequence:
1. PROJECT_CONTEXT.md                                      # Application context
2. project-breakdown/features/{feature}/issues/{issue}.md  # Implementation plan
3. project-breakdown/features/{feature}/feature-summary.md # Feature context
4. project-breakdown/context/patterns.md                   # Code patterns to follow
5. project-breakdown/context/best-practices.md            # Quality standards
6. .ai/orchestrator/engineering-agent.md                  # Engineer role guide
```

**Engineer Implementation Flow:**
```bash
# Engineer follows this process:

1. # Parse implementation plan from issue file
   # Extract: Phase 1, 2, 3 steps, files to modify, patterns to follow

2. # Update status to "In Progress"
   # Edit local issue file: status = "In Progress"
   /board-sync --issue ${issue_number}  # Sync to GitHub

3. # Implement Phase 1
   # Follow step-by-step guidance from issue file
   # Apply patterns from project-breakdown/context/patterns.md
   # Commit every 30 minutes

4. # Report progress to PM
   ./send-claude-message.sh pm-${feature}:0 "Status update for issue #${issue_number}: Phase 1 complete, starting Phase 2, ETA: 2 hours"

5. # Continue through phases until complete

6. # Auto-sync completion
   # Update local issue file: status = "Done"
   /board-sync --issue ${issue_number}        # Close GitHub issue
   /changelog-add --type implementation --issue ${issue_number}  # Document work

7. # Notify PM of completion
   ./send-claude-message.sh pm-${feature}:0 "Issue #${issue_number} COMPLETED and synced. All systems updated, ready for next assignment."
```

## 🔄 **Agent Communication & Coordination**

### **Inter-Agent Communication Protocol**

**Orchestrator ↔ PM Agents:**
```bash
# Every 5 minutes, Orchestrator sends:
./send-claude-message.sh pm-recipe-search:0 "Status update: How many engineers active and what issues are they working on?"

# PM responds:
"recipe-search Status: 2/3 engineers active. Issue #123: Phase 2, ETA 3hrs. Issue #124: Phase 1, ETA 4hrs. Ready to assign Issue #126 when engineer available."

# Orchestrator coordinates resources:
"Based on workload, pm-recipe-search can spawn 1 more engineer. pm-user-auth should wait for current issue completion."
```

**PM Agent ↔ Engineer Agents:**
```bash
# Every 5 minutes, PM sends:
./send-claude-message.sh eng-recipe-search-123:0 "Status update: What progress have you made on your issue? Any blockers?"

# Engineer responds:
"Issue #123 progress: Phase 2 complete (80% done). Currently implementing API integration. Tests passing. ETA: 2 hours. No blockers."

# PM coordinates:
- Updates progress.md with engineer status
- Identifies newly ready issues when dependencies complete
- Spawns new engineers for ready issues
```

### **Self-Scheduling System**

**How Agents Schedule Themselves:**
```bash
# Each agent type schedules check-ins:

# Orchestrator (every 5 minutes):
./schedule_with_note.sh 5 "Orchestrator check: Monitor all features and coordinate resources"

# PM Agent (every 5 minutes):
./schedule_with_note.sh 5 "PM check for recipe-search: Monitor engineers and coordinate resources"

# The schedule script:
1. Calculates exact wake-up time
2. Uses nohup to detach background process
3. After delay, sends tmux message to agent
4. Agent wakes up, performs check-in, schedules next one
```

**Autonomous Check-in Process:**
```bash
# When scheduled check-in triggers:
1. Agent receives: "Time for orchestrator check! cat next_check_note.txt && /changelog-summary --compact"
2. Agent reads its context and current state
3. Agent performs its role-specific tasks:
   - Orchestrator: Coordinate all PM agents, allocate resources
   - PM: Check engineer progress, spawn new engineers, resolve blockers
   - Engineer: Continue implementation, report progress
4. Agent schedules next check-in: ./schedule_with_note.sh {interval} "{note}"
```

## 📊 **Progress Tracking & Synchronization**

### **Real-Time Progress Updates**

**Feature Progress Calculation:**
```javascript
// How feature completion is calculated:
function calculateFeatureProgress(feature) {
  const issues = loadAllIssueFiles(feature);
  const weights = { 'Small': 1, 'Medium': 2, 'Large': 3 };
  
  let totalWeight = 0;
  let completedWeight = 0;
  let inProgressWeight = 0;
  
  issues.forEach(issue => {
    const weight = weights[issue.effort];
    totalWeight += weight;
    
    if (issue.status === 'Done') {
      completedWeight += weight;
    } else if (issue.status === 'In Progress') {
      inProgressWeight += weight * 0.5; // 50% credit for in-progress
    }
  });
  
  return Math.round(((completedWeight + inProgressWeight) / totalWeight) * 100);
}
```

**Multi-System Synchronization:**
```bash
# When engineer completes issue, triggers cascade:

1. Engineer updates local issue file (status = "Done")
2. Engineer runs: /board-sync --issue 123
   - Moves GitHub issue to "Done" column
   - Closes GitHub issue
   - Updates issue labels
3. Engineer runs: /changelog-add --type implementation --issue 123
   - Documents implementation approach
   - Records technical decisions
   - Captures lessons learned
4. PM detects completion, runs: /feature-progress-update --feature recipe-search
   - Recalculates feature completion percentage
   - Updates ready issue list (dependencies may now be met)
   - Identifies new issues available for assignment
5. PM spawns new engineer for newly ready issue
```

### **Board Sync Integration**

**Bidirectional GitHub Synchronization:**
```bash
# Board sync maintains consistency between:
- GitHub project board columns (To Do, In Progress, In Review, Done)
- Local issue file status fields
- Feature progress calculations
- Agent coordination status

# Sync triggers:
1. Engineer completes issue → auto-sync to GitHub
2. Manual changes on GitHub → detected and synced to local files
3. PM status changes → propagated to board
4. User manual sync: /board-sync --feature recipe-search
```

## 🧠 **Decision Making & Dependency Resolution**

### **PM Agent Decision Logic**

**Issue Prioritization Algorithm:**
```javascript
function prioritizeReadyIssues(issues) {
  return issues
    .filter(issue => issue.status === 'To Do' && allDependenciesMet(issue))
    .sort((a, b) => {
      // 1. Critical path (blocks most other issues)
      if (a.blocksCount !== b.blocksCount) {
        return b.blocksCount - a.blocksCount;
      }
      
      // 2. Priority level (High > Medium > Low)
      const priorityOrder = {'High': 3, 'Medium': 2, 'Low': 1};
      if (a.priority !== b.priority) {
        return priorityOrder[b.priority] - priorityOrder[a.priority];
      }
      
      // 3. Effort (smaller tasks first for quick wins)
      const effortOrder = {'Small': 1, 'Medium': 2, 'Large': 3};
      return effortOrder[a.effort] - effortOrder[b.effort];
    });
}
```

**Dependency Resolution:**
```bash
# PM Agent builds dependency graph:
1. Parse all issue files in feature
2. Extract "Must Complete First" dependencies
3. Check dependency status (Done/In Progress/To Do)
4. Build dependency chain: Issue A → Issue B → Issue C
5. Identify critical path (longest dependency chain)
6. Only assign engineers to issues with all dependencies met
```

### **Resource Allocation Strategy**

**Engineer Capacity Management:**
```bash
# Orchestrator coordinates across features:
MAX_ENGINEERS_TOTAL = 3  # System constraint
active_engineers = count_active_engineer_sessions()

# PM Agent requests: "Need engineer for Issue #127"
if (active_engineers < MAX_ENGINEERS_TOTAL):
  allocate_engineer_to_pm()
else:
  queue_request_until_engineer_available()

# Priority allocation:
1. Critical path issues (block other work)
2. High priority issues
3. Small effort issues (quick wins)
```

## 📈 **Enhanced Status Reporting & Monitoring**

### **Programmatic Health Monitoring with tmux_utils.py**

Your system now includes advanced monitoring capabilities that surpass the original Tmux Orchestrator:

```bash
# Enhanced system monitoring capabilities:
- Real-time agent health detection from terminal content
- Automatic unresponsive agent detection and recovery
- Structured monitoring data for intelligent decision making
- Proactive issue detection across all agent tiers
```

**Key Monitoring Features:**
- **Health Analysis**: Agents are classified as `healthy`, `stuck`, `unresponsive`, or `error`
- **Content Monitoring**: Actual terminal output analysis, not just self-reporting
- **Auto-Recovery**: Unresponsive agents automatically killed and restarted
- **Resource Intelligence**: Real-time engineer utilization with smart allocation

### **Real-Time Status Queries**

**Project-Level Status:**
```bash
# User runs: /project-status
# System aggregates:
1. Scan all features in project-breakdown/features/
2. Calculate completion percentages from progress.md files
3. Count active tmux sessions (orchestrator, pm-*, eng-*)
4. Query agent status via send-claude-message.sh
5. Analyze recent changelog entries for velocity
6. Generate comprehensive status report
```

**Feature-Level Deep Dive:**
```bash
# User runs: /project-status --feature recipe-search
# System provides:
1. Feature completion percentage and issue breakdown
2. Active engineer assignments and progress
3. Dependency chain analysis
4. Recent achievements and next priorities
5. Timeline estimates based on current velocity
6. Quality metrics (tests, code review status)
```

**Autonomous Session Monitoring:**
```bash
# User runs: /project-status --autonomous
# System reports:
1. All active agent sessions and their current activities
2. Agent responsiveness (last check-in times)
3. Resource utilization (engineers per feature)
4. Session duration and productivity metrics
5. Any blockers or issues requiring attention
```

**Enhanced System Monitoring:**
```bash
# User runs: /system-monitor
# Comprehensive health analysis using tmux_utils.py:
1. Real-time agent health status (healthy/stuck/unresponsive/error)
2. Resource utilization percentages and capacity analysis
3. Recent activity detection from actual terminal content
4. Proactive issue identification requiring attention
5. Auto-recovery recommendations for stuck agents

# User runs: /system-monitor --agents
# Detailed Claude analysis with recommendations:
1. Full terminal content analysis for each agent
2. Behavioral pattern recognition for optimization
3. Specific action recommendations for improving performance
4. Resource reallocation suggestions based on actual workload

# User runs: /system-monitor --recovery
# Automated agent recovery procedures:
1. Detection and automatic restart of unresponsive agents
2. Health verification after recovery operations
3. Issue escalation for persistent problems
4. Resource rebalancing after agent recovery
```

## 🔧 **Advanced Features & Integrations**

### **Learning System Integration**

**Pattern Extraction from Autonomous Development:**
```bash
# After successful implementations:
1. Engineers document implementation approaches in issue files
2. PM agents capture coordination patterns that worked well
3. /learn:extract-patterns analyzes completed work
4. Updates project-breakdown/context/patterns.md with new insights
5. Future engineers receive better implementation guidance
```

**Decision Tracking:**
```bash
# Throughout autonomous development:
1. Engineers document technical decisions in issue files
2. PM agents record resource allocation decisions
3. Orchestrator captures cross-feature coordination decisions
4. /learn:track-decisions consolidates decision outcomes
5. Decision quality improves over time through feedback loops
```

### **Quality Assurance Integration**

**Automated Quality Gates:**
```bash
# Engineer completion requirements:
1. All acceptance criteria met ✓
2. Tests written and passing ✓
3. Code follows established patterns ✓
4. Integration successful ✓
5. Documentation updated ✓

# PM Agent verification:
1. Review engineer completion claims
2. Validate integration with other components
3. Approve for board sync and changelog
4. Spawn next engineer for ready issues
```

### **Session Continuity**

**Context Preservation Across Sessions:**
```bash
# When you return to development:
1. Read PROJECT_CONTEXT.md for application state
2. Check project-breakdown/changelog/{branch}.md for recent work
3. Review project-breakdown/features/*/progress.md for current status
4. /project-status provides immediate situational awareness
5. Continue autonomous development where agents left off
```

## 🎯 **Complete Usage Examples**

### **Example 1: Full Feature Development**

```bash
# Day 1: Strategic Planning
You: /new-feature-breakdown "I want users to search recipes by ingredients"
# System creates comprehensive feature plan with 8 issues and dependencies

You: /issue-discovery  # Enhance issues with implementation details
# System creates detailed implementation plans for each issue

# Day 1 Evening: Start Autonomous Development  
You: ./start-orchestrator.sh
You: "/orchestrator --feature recipe-search"
# System spawns PM agent, PM spawns 3 engineers for ready issues
# You go to sleep

# Day 2 Morning: Check Progress
You: /project-status --feature recipe-search
# Response: "Recipe search: 67% complete, 2 engineers active, 5 issues done, ETA: 8 hours"

You: /session-summary
# Comprehensive report of all work completed overnight
```

### **Example 2: Multi-Feature Coordination**

```bash
# Start multiple features
You: ./start-orchestrator.sh
You: "/orchestrator --features 'recipe-search,user-profiles,social-sharing'"

# System coordinates:
- pm-recipe-search:0 managing 2 engineers
- pm-user-profiles:0 managing 1 engineer  
- pm-social-sharing:0 waiting for engineer availability

# Real-time resource coordination ensures optimal utilization
```

### **Example 3: Targeted Issue Implementation**

```bash
# Fix specific critical bug
You: ./start-orchestrator.sh
You: "/orchestrator --issue 156"
# Single engineer spawned for focused implementation
# No PM overhead for single issue
```

## 🚨 **Error Handling & Recovery**

### **Agent Recovery Procedures**

**Unresponsive Agent Detection:**
```bash
# Orchestrator checks agent health:
./send-claude-message.sh pm-recipe-search:0 "Health check - please respond"
# Wait 2 minutes for response
# If no response: tmux kill-session -t pm-recipe-search
# Spawn replacement PM agent with same context
```

**Session Recovery:**
```bash
# If system crashes or tmux sessions lost:
1. ./start-orchestrator.sh  # Restart orchestrator
2. /project-status         # Assess current state
3. Resume development with: "/orchestrator --feature {feature-name}"
4. System reads progress.md and resumes where left off
```

### **Conflict Resolution**

**Resource Conflicts:**
```bash
# When multiple features compete for engineers:
1. Orchestrator analyzes priority across features
2. Allocates engineers to critical path issues first
3. Queues lower priority work until resources available
4. Maintains fairness across features over time
```

**Dependency Deadlocks:**
```bash
# When circular dependencies detected:
1. PM Agent identifies the dependency cycle
2. Reports to Orchestrator for resolution
3. Orchestrator may reassign engineers to break deadlock
4. User notification if manual intervention required
```

## 📋 **File Reference Guide**

### **Core System Files**
```bash
# Tmux Scripts
send-claude-message.sh              # Agent communication
schedule_with_note.sh               # Self-scheduling  
start-orchestrator.sh               # System launcher

# Agent Templates
.claude/commands/orchestrator.md                    # Orchestrator role
.ai/orchestrator/project-manager-agent.md          # PM Agent role
.ai/orchestrator/engineering-agent.md              # Engineer role

# Enhanced Framework
.claude/commands/issue-discovery.md                # Enhanced issue creation
.claude/commands/new-feature-breakdown.md          # Feature planning
.claude/commands/board-sync.md                     # GitHub integration
.claude/commands/changelog-add.md                  # Work documentation
.claude/commands/feature-progress-update.md        # Progress tracking
.claude/commands/project-status.md                 # Status reporting
.claude/commands/session-summary.md                # Session analysis

# Templates & Patterns
.ai/orchestrator/issue-file-template.md            # Issue file format
.ai/orchestrator/feature-progress-template.md      # Progress tracking format
.ai/orchestrator/changelog-template.md             # Changelog format

# Context & Configuration
PROJECT_CONTEXT.md                                 # Application overview
project-breakdown/master.md                        # Project vision
project-breakdown/context/patterns.md              # Code patterns
project-breakdown/context/best-practices.md        # Quality standards
```

### **Generated Files During Development**
```bash
# Feature Documentation
project-breakdown/features/{feature}/
├── feature-summary.md              # Feature scope and goals
├── issue-breakdown.md              # Issue overview
├── progress.md                     # Real-time progress tracking
├── decision-log.md                 # Architectural decisions
└── issues/
    ├── {issue-title-kebab-case}-issue123.md  # Detailed implementation plans
    └── {issue-title-kebab-case}-issue124.md

# Branch Documentation  
project-breakdown/changelog/{branch}.md     # All work on branch

# Session Notes
next_check_note.txt                         # Current check-in context
```

## 🎉 **Success Metrics**

### **System Performance Targets**
- **Engineer Utilization**: 90%+ of available engineering time productive
- **Issue Completion Rate**: 1-2 issues per engineer per day
- **First-time Success**: 95%+ issues completed without rework
- **Autonomous Operation**: 90%+ work completed without user intervention
- **Timeline Accuracy**: ±15% variance between estimates and actual completion

### **Quality Assurance**
- **Test Coverage**: 80%+ of new code covered by tests
- **Integration Success**: 95%+ successful integrations without conflicts
- **Code Quality**: 100% compliance with established patterns
- **Documentation**: All decisions and implementations documented

This autonomous development system provides the complete flow from strategic feature planning through autonomous implementation, with full transparency and control at every level.