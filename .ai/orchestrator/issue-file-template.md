# Issue File Template

Template for local issue files that sync with GitHub issues and project board status.

## Issue File Format

### File Naming Convention
`{issue-title-kebab-case}-issue{number}.md`

Examples:
- `add-user-authentication-issue123.md`
- `implement-recipe-search-issue124.md`
- `fix-database-connection-issue125.md`

### File Location
`project-breakdown/features/{feature-name}/issues/{issue-file-name}.md`

### Template Structure

```markdown
# Issue #{github-issue-number}: {Issue Title}

**GitHub Issue**: [#{github-issue-number}]({github-issue-url})
**Feature**: [{feature-name}](../feature-summary.md)
**Status**: {status} | **Board Status**: {board-status}
**Priority**: {High | Medium | Low} | **Effort**: {Small | Medium | Large}
**Created**: {date} | **Updated**: {last-update-date}

## Dependencies & Implementation Plan

### Dependencies
**Must Complete First**:
- [ ] Issue #{number}: {title} - {status}
- [ ] Issue #{number}: {title} - {status}

**Blocks These Issues**:
- Issue #{number}: {title}
- Issue #{number}: {title}

**Dependency Status**: {Ready | Blocked | Partially Ready}

### Implementation Plan
**Engineering Agent Guidance**:

1. **Phase 1: {phase-name}**
   - {Step 1 with technical details}
   - {Step 2 with technical details}
   - **Files to modify**: `{file-paths}`
   - **Patterns to follow**: {reference to project-breakdown/context/patterns.md}

2. **Phase 2: {phase-name}**
   - {Step 1 with technical details}
   - {Step 2 with technical details}
   - **Integration points**: {how this connects to other components}

3. **Phase 3: {phase-name}**
   - {Step 1 with technical details}
   - **Testing approach**: {specific tests to write}
   - **Validation criteria**: {how to verify success}

**Autonomous Engineering Notes**:
- **Architecture context**: {how this fits in the bigger picture}
- **Key decisions**: {important implementation choices}
- **Potential blockers**: {what might cause issues}
- **Success indicators**: {how to know when done}

## Status Tracking

### Local Status
- [ ] **To Do** - Issue created and planned
- [ ] **In Progress** - Actively being worked on
- [ ] **In Review** - Implementation complete, under review
- [ ] **Done** - Completed and verified

### GitHub Board Status
**Current**: {current-board-status}
**Last Synced**: {last-sync-date}

## Issue Details

### Summary
{Brief description of what needs to be implemented}

### Feature Context
**Related to**: [{feature-name}](../feature-summary.md)
**Architecture Impact**: {how this affects the feature architecture}
**Dependencies**: {other issues this depends on}

### Requirements
{Detailed requirements from GitHub issue}

### Acceptance Criteria
{Acceptance criteria from GitHub issue}

### Technical Notes
{Any technical implementation notes specific to this issue}

## Implementation Progress

### Work Log
{Track progress as work is done}

**{date}**: {progress update}
**{date}**: {progress update}

### Decisions Made
{Document any implementation decisions}

### Blockers & Questions
{Track any blockers or questions that arise}

## Completion

### Definition of Done
- [ ] {completion criteria 1}
- [ ] {completion criteria 2}
- [ ] Code reviewed and merged
- [ ] Tests passing
- [ ] Documentation updated
- [ ] GitHub issue closed
- [ ] Board status updated

### Final Notes
{Any final notes about the implementation}

### Lessons Learned
{What was learned during implementation}

---

## Sync Information

**GitHub Issue ID**: {github-issue-id}
**Project Board**: ekitchen-ingestion
**Board Column**: {current-column}
**Labels**: {comma-separated-labels}

### Sync History
- **{date}**: Issue created, added to board
- **{date}**: Status updated to {status}
- **{date}**: Moved to {board-column}
```

## Status Definitions

### Local Status Values
- **To Do** - Issue planned but not started
- **In Progress** - Actively being worked on by an agent or developer
- **In Review** - Implementation complete, waiting for review/testing
- **Done** - Completed, tested, and verified

### GitHub Board Status Values
- **To Do** - Backlog items not yet started
- **In Progress** - Currently being worked on
- **In Review** - Code review or testing phase
- **Done** - Completed items

## Sync Rules

### Local → GitHub Board
When local status changes:
- **To Do** → Move to "To Do" column
- **In Progress** → Move to "In Progress" column  
- **In Review** → Move to "In Review" column
- **Done** → Move to "Done" column and close GitHub issue

### GitHub Board → Local
When board status changes:
- **To Do** → Update local status to "To Do"
- **In Progress** → Update local status to "In Progress"
- **In Review** → Update local status to "In Review"
- **Done** → Update local status to "Done"

## Agent Integration

### When Agents Start Work
1. Update local status to "In Progress"
2. Update GitHub board status
3. Add entry to work log
4. Coordinate through agent coordination files

### When Agents Complete Work
1. Update local status to "Done"
2. Move GitHub issue to "Done" column
3. Close GitHub issue
4. Update completion checklist
5. Add lessons learned section

### Sync Commands
- `/board-sync` - Sync all local issues with GitHub board
- `/board-sync --issue {number}` - Sync specific issue
- `/board-sync --feature {name}` - Sync all issues in a feature