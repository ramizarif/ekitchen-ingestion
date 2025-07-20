# Project Board Integration

Connect to and manage your GitHub project board.

## Primary Functions

### 1. Connect to Project Board
Use `mcp__GitHubProjects__list-projects` to find your project, then use `mcp__GitHubProjects__get-project` to get project details.

### 2. Load Available Issues
Use `mcp__GitHubProjects__get-project-items` to retrieve all issues from the project board. Focus on issues that are:
- Ready for development
- Not currently assigned to agents
- Have clear requirements and descriptions

### 3. Show Project Status
Display current project board status including:
- Total issues on the board
- Issues by status/column
- Issues available for assignment
- Issues currently assigned to agents

### 4. Update Issue Status
Use `mcp__GitHubProjects__update-project-item-field` to move issues through project columns as agents progress:
- **Planning** → **In Progress** → **Testing** → **Done**

### 5. Synchronize Agent Status
Keep the project board synchronized with agent activity:
- Move issues when agents start work
- Update status as agents progress through phases
- Mark issues complete when agents finish

## Instructions

1. **Always start by connecting to the project board**
2. **Load and display available issues** ready for assignment
3. **Provide issue recommendations** based on priority and complexity
4. **Keep project board updated** with agent progress
5. **Report project health** and completion status

## Output Format

Present project board information in a clear, organized format:

```
Project Board Status: Your Project Name
==========================================

Available Issues Ready for Assignment:
- Issue #123: Add user authentication (Priority: High)
- Issue #124: Fix login validation (Priority: Medium)
- Issue #125: Update documentation (Priority: Low)

Issues In Progress:
- Issue #121: Database optimization (Agent-1704123456000)
- Issue #122: API refactoring (Agent-1704123789000)

Completed Issues:
- Issue #120: Security fixes (Completed by Agent-1704123400000)
```

Focus on providing actionable information for the Master Agent to make coordination decisions.