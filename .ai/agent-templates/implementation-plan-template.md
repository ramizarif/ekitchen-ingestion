# Implementation Plan Template

This template defines the structure for agent implementation plans that provide detailed blueprints for issue resolution with conflict analysis.

## File Location

`.ai/implementation-plans/{branch-name}/{issue-title-slug}-{issue-number}.md`

## Template Structure

```markdown
# Implementation Plan: {Issue Title} (#{issue-number})

**Agent ID**: Agent-{timestamp}
**Issue**: #{issue-number}
**Branch**: {branch-name}
**Created**: {timestamp}
**Last Updated**: {timestamp}

## Issue Summary

**Title**: {issue-title}
**Description**: {issue-description}
**Labels**: {issue-labels}
**Assignees**: {assignees}
**Priority**: {priority}
**Estimated Effort**: {effort-estimate}

## Conflict Analysis

### Other Active Plans Reviewed

- [ ] {plan-file-1}: {brief-description}
- [ ] {plan-file-2}: {brief-description}
- [ ] No other plans found

### Potential Conflicts Identified

#### File Conflicts
**Files this plan will modify**:
- {file-path-1} - {modification-type}
- {file-path-2} - {modification-type}

**Conflicts with other agents**:
- Agent-{id}: {file-path} - {conflict-type}
- No file conflicts detected

#### Service Conflicts
**Services this plan will affect**:
- {service-name-1} - {impact-description}
- {service-name-2} - {impact-description}

**Conflicts with other agents**:
- Agent-{id}: {service-name} - {conflict-type}
- No service conflicts detected

#### Database Conflicts
**Database changes planned**:
- {table-name}: {change-type}
- {migration-file}: {description}

**Conflicts with other agents**:
- Agent-{id}: {table-name} - {conflict-type}
- No database conflicts detected

#### Resource Conflicts
**Resources required**:
- {resource-name}: {usage-type}
- {shared-resource}: {access-pattern}

**Conflicts with other agents**:
- Agent-{id}: {resource-name} - {conflict-type}
- No resource conflicts detected

### Conflict Prevention Strategy

**Identified Conflicts**:
{conflict-summary}

**Prevention Measures**:
- {prevention-measure-1}
- {prevention-measure-2}

**Timing Coordination**:
- {timing-requirement-1}
- {timing-requirement-2}

**Alternative Approaches**:
- {alternative-1}: {description}
- {alternative-2}: {description}

## Implementation Phases

### Phase 1: {Phase Name}
**Duration**: {estimated-duration}
**Objective**: {phase-objective}

**Files to modify**:
- {file-path} - {modification-description}

**Dependencies**:
- {dependency-description}
- No dependencies

**Conflict Risk**: {Low | Medium | High}
**Risk Mitigation**: {mitigation-strategy}

**Testing Approach**:
- {test-approach-1}
- {test-approach-2}

**Deliverables**:
- [ ] {deliverable-1}
- [ ] {deliverable-2}

**Success Criteria**:
- {success-criterion-1}
- {success-criterion-2}

### Phase 2: {Phase Name}
**Duration**: {estimated-duration}
**Objective**: {phase-objective}

**Files to modify**:
- {file-path} - {modification-description}

**Dependencies**:
- Phase 1 completion
- {external-dependency}

**Conflict Risk**: {Low | Medium | High}
**Risk Mitigation**: {mitigation-strategy}

**Testing Approach**:
- {test-approach-1}
- {test-approach-2}

**Deliverables**:
- [ ] {deliverable-1}
- [ ] {deliverable-2}

**Success Criteria**:
- {success-criterion-1}
- {success-criterion-2}

### Phase 3: {Phase Name}
**Duration**: {estimated-duration}
**Objective**: {phase-objective}

**Files to modify**:
- {file-path} - {modification-description}

**Dependencies**:
- Phase 2 completion
- {external-dependency}

**Conflict Risk**: {Low | Medium | High}
**Risk Mitigation**: {mitigation-strategy}

**Testing Approach**:
- {test-approach-1}
- {test-approach-2}

**Deliverables**:
- [ ] {deliverable-1}
- [ ] {deliverable-2}

**Success Criteria**:
- {success-criterion-1}
- {success-criterion-2}

### Phase 4: {Phase Name}
**Duration**: {estimated-duration}
**Objective**: {phase-objective}

**Files to modify**:
- {file-path} - {modification-description}

**Dependencies**:
- Phase 3 completion
- {external-dependency}

**Conflict Risk**: {Low | Medium | High}
**Risk Mitigation**: {mitigation-strategy}

**Testing Approach**:
- {test-approach-1}
- {test-approach-2}

**Deliverables**:
- [ ] {deliverable-1}
- [ ] {deliverable-2}

**Success Criteria**:
- {success-criterion-1}
- {success-criterion-2}

## Technical Approach

### Architecture Decisions

**Design Patterns**:
- {pattern-1}: {justification}
- {pattern-2}: {justification}

**Technology Choices**:
- {technology-1}: {justification}
- {technology-2}: {justification}

**Integration Points**:
- {integration-1}: {approach}
- {integration-2}: {approach}

### Implementation Strategy

**Code Organization**:
- {organization-principle-1}
- {organization-principle-2}

**Testing Strategy**:
- {testing-approach-1}
- {testing-approach-2}

**Documentation Requirements**:
- {documentation-requirement-1}
- {documentation-requirement-2}

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| {risk-1} | {Low/Medium/High} | {Low/Medium/High} | {mitigation-strategy} |
| {risk-2} | {Low/Medium/High} | {Low/Medium/High} | {mitigation-strategy} |

### Coordination Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| {risk-1} | {Low/Medium/High} | {Low/Medium/High} | {mitigation-strategy} |
| {risk-2} | {Low/Medium/High} | {Low/Medium/High} | {mitigation-strategy} |

### External Dependencies

| Dependency | Type | Impact | Contingency |
|------------|------|--------|-------------|
| {dependency-1} | {type} | {impact} | {contingency-plan} |
| {dependency-2} | {type} | {impact} | {contingency-plan} |

## Master Agent Review

### Conflict Analysis Results
**Overall Conflict Level**: {Low | Medium | High}
**Critical Conflicts**: {count}
**Manageable Conflicts**: {count}
**No-Conflict Areas**: {list}

### Recommendation
**Master Agent Decision**: {Approve | Reject | Modify}
**Execution Timing**: {Immediate | After Agent-{id} Phase {phase} | Scheduled for {time}}

### Special Coordination Requirements
- {coordination-requirement-1}
- {coordination-requirement-2}

### Approval Conditions
- [ ] {condition-1}
- [ ] {condition-2}

### Review Notes
{master-agent-notes}

## Execution Timeline

### Projected Schedule
- **Phase 1**: {start-date} - {end-date}
- **Phase 2**: {start-date} - {end-date}
- **Phase 3**: {start-date} - {end-date}
- **Phase 4**: {start-date} - {end-date}

### Milestones
- {milestone-1}: {date}
- {milestone-2}: {date}

### Coordination Points
- {coordination-point-1}: {date}
- {coordination-point-2}: {date}

## Success Metrics

### Quantitative Metrics
- {metric-1}: {target-value}
- {metric-2}: {target-value}

### Qualitative Metrics
- {metric-1}: {success-criteria}
- {metric-2}: {success-criteria}

### Completion Criteria
- [ ] All phases completed successfully
- [ ] Tests passing
- [ ] No conflicts with other agents
- [ ] Master Agent final approval
- [ ] Pull request merged
- [ ] Issue closed

## Appendices

### Appendix A: Detailed File Analysis
{detailed-file-analysis}

### Appendix B: Test Plan
{detailed-test-plan}

### Appendix C: Rollback Plan
{rollback-procedures}

### Appendix D: Performance Considerations
{performance-analysis}
```

## Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{timestamp}` | Current timestamp | `2024-01-16T10:30:00Z` |
| `{branch-name}` | Current git branch | `feature/user-auth` |
| `{issue-number}` | GitHub issue number | `123` |
| `{issue-title}` | GitHub issue title | `Add user authentication` |
| `{issue-title-slug}` | URL-friendly title | `add-user-authentication` |
| `{conflict-type}` | Type of conflict | `file-access` |
| `{modification-type}` | Type of modification | `add-function` |
| `{effort-estimate}` | Estimated effort | `2-4 hours` |
| `{phase-objective}` | Phase objective | `Implement authentication logic` |

## Conflict Analysis Guide

### File Conflict Types
- **Modification**: Same file being modified
- **Creation**: Same file being created
- **Deletion**: File being deleted while modified
- **Rename**: File being renamed while modified

### Service Conflict Types
- **API Overlap**: Same API endpoints
- **Database Schema**: Same table modifications
- **Configuration**: Same config changes
- **Dependencies**: Conflicting dependency versions

### Resolution Strategies
- **Serialization**: Execute in sequence
- **Partitioning**: Divide work areas
- **Coordination**: Synchronized execution
- **Alternative**: Different approach

This template ensures comprehensive planning and conflict analysis for all agent implementations.