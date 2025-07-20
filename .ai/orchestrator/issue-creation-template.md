# Issue Creation Template

This template defines how the Master Agent should structure GitHub issues created through the issue-discovery process.

## GitHub Issue Structure

### Issue Title Format
```
[TYPE] Brief descriptive title (Priority: LEVEL)
```

**Examples:**
- `[FEATURE] Add user authentication system (Priority: High)`
- `[BUG] Fix login validation error (Priority: Critical)`
- `[REFACTOR] Optimize database queries (Priority: Medium)`

### Issue Description Template

```markdown
## Overview
{Brief description of the task and its purpose}

## Task Type
{Feature/Bug/Refactor/Documentation/etc.}

## Priority
{Critical/High/Medium/Low} - {Reason for priority level}

## Requirements

### Functional Requirements
{Detailed description of what needs to be implemented}

### Technical Requirements
{Technical specifications and constraints}

### Performance Requirements
{Speed, scalability, resource usage expectations}

### Security Requirements
{Authentication, authorization, data protection needs}

## Technical Context

### Affected Components
{List of codebase areas that will be modified}

### Technologies Involved
{Programming languages, frameworks, libraries}

### Dependencies
{External APIs, services, or internal components}

### Files to Modify
{Specific files, functions, or modules that need changes}

## Implementation Details

### Preferred Approach
{Architectural patterns, design preferences}

### Code Standards
{Coding conventions and patterns to follow}

### Integration Points
{How this connects to existing functionality}

### Constraints
{Technical limitations, resource constraints}

## Acceptance Criteria

### Success Criteria
{Specific, measurable criteria for completion}

- [ ] {Criterion 1}
- [ ] {Criterion 2}
- [ ] {Criterion 3}

### Testing Requirements
{Required testing types and coverage}

- [ ] Unit tests for core functionality
- [ ] Integration tests for API endpoints
- [ ] End-to-end tests for user workflows
- [ ] Performance tests for critical paths
- [ ] Security tests for authentication

### Edge Cases
{Unusual inputs, failure scenarios, boundary conditions}

## Dependencies

### Prerequisites
{Work that must be completed before this task}

### Dependents
{Tasks that are blocked until this is complete}

### Timeline
{Deadline or timeline expectations}

## Documentation

### Documentation Updates Required
{README, API docs, user guides, etc.}

### Stakeholder Communication
{Who should be notified upon completion}

## Definition of Done

### Completion Checklist
- [ ] All functional requirements implemented
- [ ] All acceptance criteria met
- [ ] Code follows project standards
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] Code reviewed and approved
- [ ] Deployed to staging environment
- [ ] Stakeholders notified

### Final Deliverables
{Code, tests, documentation, configuration}

### Post-Completion Steps
{Monitoring, user communication, follow-up tasks}

## Additional Context

### Background Information
{Why this task is needed, historical context}

### User Stories
{How users will benefit from this change}

### Business Impact
{Expected outcomes and benefits}

## Implementation Notes

### Helpful Resources
{Links to relevant documentation, examples, or references}

### Potential Pitfalls
{Common mistakes to avoid}

### Alternative Approaches
{Other ways this could be implemented}

---

**Created by Master Agent via issue-discovery process**
**Agent Assignment**: Ready for sub-agent pickup
**Estimated Effort**: {Small/Medium/Large based on complexity}
```

## Label Assignment Rules

### Task Type Labels
- `type:feature` - New functionality
- `type:bug` - Bug fixes
- `type:refactor` - Code improvements
- `type:documentation` - Documentation updates
- `type:performance` - Performance optimizations
- `type:security` - Security enhancements
- `type:test` - Testing improvements

### Priority Labels
- `priority:critical` - Blocking other work
- `priority:high` - Important for upcoming milestone
- `priority:medium` - Normal priority
- `priority:low` - Nice to have

### Component Labels
- `component:frontend` - UI/Frontend changes
- `component:backend` - Backend/API changes
- `component:database` - Database modifications
- `component:config` - Configuration changes
- `component:docs` - Documentation
- `component:tests` - Testing

### Effort Labels
- `effort:small` - 1-2 hours
- `effort:medium` - 3-8 hours
- `effort:large` - 1-2 days
- `effort:xl` - 3+ days

### Status Labels
- `status:ready` - Ready for development
- `status:blocked` - Blocked by dependencies
- `status:in-review` - Under review
- `status:needs-info` - Needs more information

## Project Board Placement

### Column Assignment Rules
- **To Do**: New issues ready for development
- **Backlog**: Issues that need refinement or are low priority
- **In Progress**: Issues assigned to agents
- **Review**: Issues awaiting code review
- **Done**: Completed issues

### Status Field Updates
Based on issue type and priority:
- Critical bugs → Move to "Ready" column
- High priority features → Move to "To Do" column
- Medium/Low priority → Move to "Backlog" column
- Documentation → Move to "To Do" column

## Quality Assurance

### Before Creating Issue
1. **Validate completeness** - All required fields filled
2. **Check consistency** - No contradictory requirements
3. **Verify feasibility** - Technical approach is sound
4. **Confirm clarity** - Sub-agent can understand without questions

### After Creating Issue
1. **Link dependencies** - Connect to related issues
2. **Assign labels** - Apply appropriate tags
3. **Set project fields** - Update project board fields
4. **Notify stakeholders** - Add relevant watchers

## Master Agent Instructions

When creating issues from discovery sessions:

1. **Use this template** as the base structure
2. **Fill in all relevant sections** based on discovery answers
3. **Skip irrelevant sections** if not applicable to task type
4. **Ensure completeness** - sub-agents should not need clarification
5. **Validate before submission** - review for consistency and clarity
6. **Confirm with user** - show final issue before creating
7. **Create and place** - add to project board in correct column