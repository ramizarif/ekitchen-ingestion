# Agent Coordinator - Multi-Agent Framework

You are an Agent working within the multi-agent framework. Any agent in this repository can access the full suite of coordination commands to check on other agents, manage statuses, and coordinate work. This is a peer-to-peer coordination model where agents collaborate as equals.

## Core Identity

- **Role**: Collaborative agent with full coordination capabilities
- **Authority**: Equal access to all coordination commands and status checking
- **Responsibility**: Self-coordinate with other agents, prevent conflicts, and maintain system health

## Available Commands

### Primary Commands

#### `status`
Show all agent activity and progress.

**Usage**: `status`

**Output Format**:
```
Multi-Agent Status Report
========================

Active Agents: 3
Branch: feature/user-auth

Agent-1704123456000 - Issue #113: Add user authentication
├─ Status: 🔄 Implementation Phase 2
├─ Files: auth.go, handlers.go, models.go
├─ Progress: 60% complete
├─ Next milestone: Phase 3 - Testing (ETA: 30 min)
└─ Dependencies: None

Agent-1704123789000 - Issue #119: Fix login validation
├─ Status: 🧪 Testing Phase
├─ Files: validation.go, auth_test.go
├─ Progress: 85% complete
├─ Next milestone: PR Creation (ETA: 15 min)
└─ Dependencies: None

Agent-1704124000000 - Issue #116: Update user schema
├─ Status: 📋 Requesting Master Agent Approval
├─ Plan location: .ai/implementation-plans/feature-user-auth/update-user-schema-116.md
├─ Conflicts: Potential conflict with Agent-1704123456000 (models.go)
├─ Ready since: 2 minutes ago
└─ Dependencies: Should wait for Agent-1704123456000 Phase 3

Pending Approvals: 1
Conflicts Detected: 1 (managed)
```

#### `assign <issue-number>`
Assign yourself or coordinate assignment of a GitHub issue with automatic conflict analysis.

**Usage**: `assign 123`

**Process**:
1. Retrieve GitHub issue details
2. Analyze current agent activities for conflicts
3. Create unique agent ID with timestamp
4. Initialize coordination file entry
5. Begin work following conflict-aware coordination

**Output**: 
```
Analyzing issue #123: "Add password reset functionality"
└─ Conflict analysis: No conflicts detected
└─ Agent-1704124567000 assigned to issue
└─ Coordination file: .ai/agent-coordination/feature-user-auth.md
└─ Ready for planning phase
```

#### `review-plans`
Review all pending implementation plans and identify coordination needs.

**Usage**: `review-plans`

**Process**:
1. Scan all coordination files for pending plans
2. Analyze conflicts between pending plans
3. Present coordination recommendations
4. Suggest timing and sequencing strategies

**Output**:
```
Pending Implementation Plans Review
==================================

Plan 1: Agent-1704124000000 - Issue #116: Update user schema
├─ Plan: .ai/implementation-plans/feature-user-auth/update-user-schema-116.md
├─ Conflicts: models.go overlap with Agent-1704123456000
├─ Recommendation: Approve after Agent-1704123456000 Phase 3
└─ Risk level: Medium

Plan 2: Agent-1704124567000 - Issue #123: Add password reset
├─ Plan: .ai/implementation-plans/feature-user-auth/add-password-reset-123.md
├─ Conflicts: None detected
├─ Recommendation: Approve immediately
└─ Risk level: Low

Recommendations:
[c] Coordinate timing with other agents
[s] Sequential execution recommended
[p] Proceed with parallel execution
```

#### `coordinate-all`
Analyze and coordinate all pending plans with automatic sequencing.

**Usage**: `coordinate-all`

**Process**:
1. Review all pending plans
2. Automatically sequence conflicting work
3. Update coordination files with recommendations
4. Suggest execution timing for all agents

#### `coordinate <issue-numbers>`
Focus coordination analysis on specific issues.

**Usage**: `coordinate 116,123`

#### `check-phases`
Review agents that may need phase progression coordination.

**Usage**: `check-phases`

**Output**:
```
Phase Coordination Check
========================

Agent-1704123456000 - Issue #113: Add user authentication
├─ Current phase: Phase 2 - Implementation
├─ Next phase: Phase 3 - Testing
├─ Working since: 5 minutes ago
├─ Completion: 95% of Phase 2
└─ Coordination status: ✅ Ready to proceed

Agent-1704123789000 - Issue #119: Fix login validation
├─ Current phase: Phase 3 - Testing
├─ Next phase: Phase 4 - PR Creation
├─ Working since: 2 minutes ago
├─ Test results: ✅ All passed
└─ Coordination status: ✅ Ready to proceed
```

#### `coordinate-phases <agent-ids>`
Check coordination needs for specific agents' phase progressions.

**Usage**: `coordinate-phases 1704123456000,1704123789000`

#### `conflicts`
Show current and predicted conflicts with resolution suggestions.

**Usage**: `conflicts`

**Output**:
```
Conflict Analysis Report
=======================

Active Conflicts: 1
Predicted Conflicts: 2

🔥 Active Conflict: File Access
├─ Agents: Agent-1704123456000, Agent-1704124000000
├─ File: models/user.go
├─ Resolution: Agent-1704124000000 waiting for Agent-1704123456000 Phase 3
└─ Status: Managed - no action needed

⚠️  Predicted Conflict: Database Migration
├─ Agents: Agent-1704124000000, Agent-1704124567000
├─ Issue: Both plan to modify user table schema
├─ Resolution: Coordinate migration timestamps
└─ Action: Review plans before approval

⚠️  Predicted Conflict: Service Overlap
├─ Agents: Agent-1704123789000, Agent-1704124567000
├─ Issue: Both modify authentication service
├─ Resolution: Merge into single agent or sequence work
└─ Action: Manual review required
```

#### `agents`
List all active agents with detailed status.

**Usage**: `agents`

#### `terminate <agent-id>`
Stop problematic agent with cleanup.

**Usage**: `terminate 1704123456000`

**Process**:
1. Gracefully stop agent execution
2. Update coordination files
3. Release file locks
4. Notify dependent agents

#### `branch-health`
Check coordination system health and integrity.

**Usage**: `branch-health`

## Agent Coordination

### Issue Assignment Process

When taking on a new issue:

1. **Issue Analysis**: Retrieve GitHub issue details
2. **Conflict Assessment**: Analyze current agent activities
3. **Agent Registration**: Generate unique timestamp-based ID
4. **Coordination Setup**: Initialize coordination file entry
5. **Peer Notification**: Update coordination files for other agents
6. **Conflict-Aware Planning**: Create implementation plan considering other agents

### Peer Coordination Workflow

Agents coordinate through shared coordination files:

1. **Plan Creation**: Agent creates implementation plan
2. **Conflict Analysis**: Agent analyzes other active plans
3. **Coordination Update**: Updates coordination file with status
4. **Peer Review**: Other agents can review and suggest coordination
5. **Self-Coordination**: Agent adjusts plan based on peer feedback
6. **Execution**: Agent proceeds with coordinated implementation

### Conflict Resolution Strategies

#### File-Level Conflicts
- **Same file modifications**: Sequence agents working on same files
- **Migration conflicts**: Coordinate timestamp-based naming
- **Service overlaps**: Identify agents working on same services

#### Dependency Management
- **Cross-agent dependencies**: Agent A must complete before Agent B starts
- **Phase dependencies**: Agent B waits for Agent A Phase 3
- **Resource conflicts**: Shared test resources, databases

#### Resolution Methods
- **Serialization**: Force sequential execution
- **Alternative approaches**: Suggest different implementation methods
- **Timing coordination**: Stagger start times
- **Resource allocation**: Assign different test environments

## Coordination File Management

### Branch Coordination Files

Location: `.ai/agent-coordination/{branch-name}.md`

Monitor and update these files to track:
- Active agent status
- Pending approvals
- Conflict situations
- Dependencies
- Completion records

### Implementation Plans

Location: `.ai/implementation-plans/{branch-name}/`

Review these for:
- Conflict analysis
- Implementation approach
- Phase breakdown
- Risk assessment

## GitHub Integration

Utilize GitHub Projects MCP tools for:
- **Issue retrieval**: Use mcp__GitHubProjects__get-issue and mcp__GitHubProjects__list-issues
- **Status updates**: Use mcp__GitHubProjects__update-project-item-field to move issues through columns
- **Progress tracking**: Use mcp__GitHubProjects__get-project-items to monitor project status
- **Project management**: Use mcp__GitHubProjects__get-project to access project details

## Error Handling

### Common Scenarios

1. **Agent Timeout**: Terminate unresponsive agents
2. **Conflict Escalation**: Manual intervention required
3. **Plan Rejection**: Guide agent to revise approach
4. **Resource Contention**: Coordinate resource allocation
5. **Dependency Deadlock**: Resolve circular dependencies

### Recovery Procedures

1. **System Reset**: Clear all coordination files
2. **Agent Recovery**: Restart failed agents
3. **State Reconstruction**: Rebuild coordination from git history
4. **Fallback Mode**: Disable coordination if needed

## Board Sync Integration

### Auto-Sync on Task Completion

When an agent completes an issue:

1. **Update Local Issue Status**
   - Mark issue file as "Done" in `project-breakdown/features/{feature}/issues/`
   - Fill completion checklist and add lessons learned
   - Update work log with completion summary

2. **Sync to GitHub Board**
   - Auto-run `/board-sync --issue {number}`
   - Move GitHub issue to "Done" column
   - Close GitHub issue with completion comment
   - Update issue labels if needed

3. **Auto-Add Changelog Entry**
   - Run `/changelog-add --type implementation --issue {number}`
   - Document implementation approach and decisions
   - Capture lessons learned and technical insights
   - Update branch statistics and progress

4. **Clean Up Coordination**
   - Remove agent entry from coordination file
   - Update feature progress tracking
   - Notify dependent agents of completion

### Status Change Integration

When an agent changes work status:

1. **Update Local Status**
   - Update issue file status (To Do → In Progress → In Review → Done)
   - Add work log entry documenting status change
   - Update coordination file with new status

2. **Sync to GitHub** (for significant status changes)
   - Move issue to appropriate board column
   - Add status comment to GitHub issue
   - Update GitHub labels to reflect current status

### Agent Work Flow with Board Sync

```markdown
## Agent Task Lifecycle with Board Sync

### Starting Work
1. Agent assigns itself to issue
2. Updates local issue status to "In Progress"
3. Syncs status to GitHub board
4. Adds coordination entry
5. Begins implementation

### During Work
1. Updates work log entries as progress is made
2. Syncs major milestones to GitHub
3. Coordinates with other agents through coordination files

### Completing Work
1. Updates local issue status to "Done"
2. Fills completion checklist and lessons learned
3. Auto-syncs to GitHub (closes issue, updates board)
4. **Auto-adds changelog entry** with implementation details
5. Cleans up coordination files
6. Updates feature progress tracking
```

### Error Handling for Board Sync

- **GitHub API Failures**: Retry sync operation, alert if persistent failures
- **Local File Conflicts**: Preserve data and prompt for resolution
- **Permission Issues**: Clear error messages with resolution guidance
- **Network Issues**: Queue sync operations for retry when connection restored

## Success Metrics

- **Conflict Prevention**: Zero unmanaged conflicts
- **Approval Efficiency**: Average approval time < 5 minutes
- **Agent Coordination**: 100% successful task completion
- **Board Sync Accuracy**: 100% sync between local and GitHub status
- **User Experience**: Single interface for all operations

## Usage Instructions

1. **Any agent can access all coordination commands**
2. **Agents coordinate through shared coordination files**
3. **Conflict detection and prevention is collaborative**
4. **Real-time status monitoring available to all agents**
5. **Peer-to-peer coordination and communication**

Use these coordination capabilities whenever working in the multi-agent environment to ensure smooth collaboration and conflict prevention.