# Multi-Agent Coordination File Template

This template defines the structure for branch-specific coordination files that track all agent activity, conflicts, and approvals.

## File Location

`.ai/agent-coordination/{branch-name}.md`

## Template Structure

```markdown
# Multi-Agent Coordination - Branch: {branch-name}

Generated: {timestamp}
Last Updated: {timestamp}

## Active Agents

### Agent-{timestamp} - Issue #{number}: {title}
**Status**: {status_emoji} {current_phase}
**Files being modified**: {comma_separated_files}
**Conflicts**: {conflict_status}
**Master Agent approval**: {approval_status}
**Next milestone**: {next_phase} (ETA: {estimated_time})
**Dependencies**: {dependency_details}
**Created**: {creation_timestamp}
**Last updated**: {update_timestamp}

## Coordination Status

### Implementation Plans Awaiting Coordination

#### Agent-{timestamp} - Issue #{number}: {title}
**Status**: 📋 Plan Ready for Peer Review
**Plan location**: `.ai/implementation-plans/{branch-name}/{plan-file}.md`
**Conflicts analyzed**: {yes_no}
**Potential conflicts**: {conflict_details}
**Dependencies**: {dependency_details}
**Ready since**: {timestamp}
**Coordination type**: Plan Review
**Risk level**: {low_medium_high}

### Phase Coordination Status

#### Agent-{timestamp} - Issue #{number}: {title}
**Status**: ⏳ Coordinating Phase Progression
**Current phase**: {current_phase}
**Next phase**: {next_phase}
**Phase completion**: {percentage}%
**Test results**: {test_status}
**Coordination since**: {timestamp}
**Coordination type**: Phase Progression

## Conflict Management

### Active Conflicts

#### Conflict-{timestamp}: {conflict_type}
**Type**: {file_access | service_overlap | database_migration | resource_contention}
**Agents involved**: Agent-{id1}, Agent-{id2}
**Resource**: {file_path | service_name | database_table | resource_name}
**Resolution strategy**: {serialization | alternative_approach | timing_coordination}
**Status**: {active | resolved | managed}
**Resolution**: {resolution_details}
**Created**: {timestamp}
**Resolved**: {timestamp}

### Predicted Conflicts

#### Predicted-{timestamp}: {conflict_type}
**Type**: {conflict_type}
**Agents involved**: Agent-{id1}, Agent-{id2}
**Probability**: {low | medium | high}
**Impact**: {low | medium | high}
**Prevention strategy**: {prevention_details}
**Monitoring**: {monitoring_approach}
**Created**: {timestamp}

## Completed Work

### Agent-{timestamp} - Issue #{number}: {title}
**Completed**: {completion_timestamp}
**Duration**: {duration}
**Commit hash**: {commit_hash}
**Pull request**: #{pr_number}
**Files modified**: {file_list}
**Tests added**: {test_count}
**Master Agent approvals**: {approval_count}
**Conflicts encountered**: {conflict_count}

## Branch Statistics

**Total agents spawned**: {count}
**Active agents**: {count}
**Completed issues**: {count}
**Pending approvals**: {count}
**Conflicts resolved**: {count}
**Average completion time**: {duration}
**Success rate**: {percentage}%

## System Health

**Last health check**: {timestamp}
**Coordination file integrity**: {healthy | corrupted | recovering}
**Agent communication**: {healthy | degraded | failed}
**GitHub integration**: {healthy | rate_limited | failed}
**Conflict detection**: {active | inactive}
**Peer coordination**: {active | limited | offline}
```

## Status Emoji Legend

| Emoji | Status | Description |
|-------|--------|-------------|
| 📋 | Planning | Creating implementation plan |
| ⏳ | Waiting | Waiting for approval/dependency |
| 🔄 | Implementation | Actively implementing |
| 🧪 | Testing | Running tests and validation |
| 📝 | Documentation | Writing documentation |
| 🔍 | Review | Code review phase |
| ✅ | Completed | Successfully completed |
| ❌ | Failed | Failed or terminated |
| ⚠️ | Blocked | Blocked by conflict or issue |
| 🔧 | Fixing | Fixing issues or conflicts |

## Phase Definitions

### Standard Phases

1. **Planning Phase**
   - Issue analysis
   - Implementation plan creation
   - Conflict analysis
   - Master Agent approval request

2. **Implementation Phase**
   - Code implementation
   - File modifications
   - Real-time coordination
   - Progress reporting

3. **Testing Phase**
   - Test execution
   - Validation
   - Bug fixes
   - Phase approval request

4. **Documentation Phase**
   - Code documentation
   - README updates
   - Comment additions

5. **Review Phase**
   - Code review
   - Master Agent review
   - Peer review (if applicable)

6. **Completion Phase**
   - Pull request creation
   - Issue linking
   - Final coordination update
   - Cleanup

## Coordination Status Values

| Status | Symbol | Description |
|--------|--------|-------------|
| Coordinating | ⏳ | Awaiting peer coordination |
| Coordinated | ✅ | Coordinated with other agents |
| Needs Attention | ⚠️ | Requires coordination review |
| Conflicts | ❌ | Has coordination conflicts |
| Expired | ⏰ | Coordination request expired |

## Conflict Types

### File Access Conflicts
- **Same file modification**: Multiple agents modifying the same file
- **Directory conflicts**: Agents creating conflicting directory structures
- **Configuration conflicts**: Conflicting configuration changes

### Service Conflicts
- **API endpoint conflicts**: Overlapping API implementations
- **Database schema conflicts**: Conflicting database changes
- **Service dependency conflicts**: Conflicting service dependencies

### Resource Conflicts
- **Test resource conflicts**: Shared test databases/services
- **Build conflicts**: Conflicting build configurations
- **Deployment conflicts**: Conflicting deployment scripts

### Timing Conflicts
- **Sequential dependencies**: Agent B depends on Agent A completion
- **Parallel conflicts**: Agents cannot run simultaneously
- **Release conflicts**: Conflicting release timelines

## Dependency Formats

### No Dependencies
```
**Dependencies**: None
```

### Agent Dependencies
```
**Dependencies**: Waiting for Agent-{id} Phase {phase}
```

### Multiple Dependencies
```
**Dependencies**: 
- Agent-{id1} Phase {phase1}
- Agent-{id2} Phase {phase2}
```

### External Dependencies
```
**Dependencies**: 
- External API deployment
- Database migration completion
- Third-party service update
```

## Update Procedures

### Agent Status Updates
1. Agent updates its own entry
2. Timestamp is updated
3. Other agents can review status
4. Conflicts are re-evaluated

### Peer Coordination Updates
1. Agents update coordination status
2. Coordination feedback provided
3. Conflict resolutions recorded
4. Timing coordination documented

### Conflict Resolution Updates
1. Conflict status updated
2. Resolution strategy recorded
3. Affected agents notified
4. Monitoring adjusted

## File Maintenance

### Cleanup Procedures
- Archive completed agents weekly
- Remove expired approval requests
- Consolidate conflict history
- Maintain performance metrics

### Backup Procedures
- Daily backup of coordination files
- Version control tracking
- Recovery procedures documented
- Integrity validation

This template ensures consistent coordination file structure across all branches and provides comprehensive tracking of multi-agent development activities.