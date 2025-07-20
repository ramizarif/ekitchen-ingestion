# Feature Progress Update Command

Update feature progress tracking by scanning issue statuses and calculating completion percentages.

## Your Role

You are a **Feature Progress Agent** that:

1. **Scans issue statuses** for a specific feature or all features
2. **Calculates completion percentages** based on issue weights  
3. **Updates progress.md files** with current status
4. **Generates progress reports** for PM agents and users
5. **Identifies ready issues** for PM agent assignment

## Usage

```bash
# Update specific feature progress
/feature-progress-update --feature recipe-search

# Update all features
/feature-progress-update --all

# Generate progress report only (no updates)
/feature-progress-update --feature recipe-search --report-only

# Update and show ready issues for assignment
/feature-progress-update --feature recipe-search --show-ready
```

## Progress Calculation Process

### Step 1: Scan Feature Issues

**Load All Issue Files:**
```bash
# For specified feature:
project-breakdown/features/{feature-name}/issues/*.md

# Extract from each issue file:
- Current status (To Do | In Progress | In Review | Done)
- Effort level (Small=1, Medium=2, Large=3)  
- Dependencies and dependency status
- GitHub issue number and board status
```

### Step 2: Calculate Completion Percentage

**Weighted Progress Formula:**
```javascript
function calculateFeatureProgress(issues) {
  const weights = { 'Small': 1, 'Medium': 2, 'Large': 3 };
  
  const totalWeight = issues.reduce((sum, issue) => 
    sum + weights[issue.effort], 0);
  
  const completedWeight = issues
    .filter(issue => issue.status === 'Done')
    .reduce((sum, issue) => sum + weights[issue.effort], 0);
  
  const inProgressWeight = issues
    .filter(issue => issue.status === 'In Progress')
    .reduce((sum, issue) => sum + (weights[issue.effort] * 0.5), 0);
    
  return Math.round(((completedWeight + inProgressWeight) / totalWeight) * 100);
}
```

### Step 3: Analyze Dependencies

**Dependency Status Analysis:**
```bash
# For each issue, determine:
- **Ready**: All dependencies completed, status = "To Do"
- **Blocked**: Has incomplete dependencies  
- **In Progress**: Currently being worked on
- **Done**: Implementation complete

# Create dependency chain visualization:
Issue #123 (Backend API) → Issue #124 (Frontend) → Issue #125 (Integration)
```

### Step 4: Update Progress File

**Update project-breakdown/features/{feature-name}/progress.md:**
```markdown
# Feature Progress: {Feature Name}

**Overall Progress**: {calculated-percentage}% Complete
**Last Updated**: {current-timestamp}
**Status**: {Planning | In Progress | Ready for Review | Completed}

## Completion Overview
- **Total Issues**: {total-count}
- **Completed**: {completed-count} ({percentage}%)
- **In Progress**: {in-progress-count}
- **Ready to Start**: {ready-count}  
- **Blocked**: {blocked-count}

## Issue Breakdown by Status

### ✅ Completed Issues ({completed-count}/{total-count})
{List of completed issues with completion dates}

### 🔄 In Progress Issues ({in-progress-count})
{List of in-progress issues with engineer assignments and ETAs}

### 📋 Ready to Start ({ready-count})
{List of ready issues prioritized by dependency chain}

### ⏸️ Blocked Issues ({blocked-count})
{List of blocked issues with blocking dependencies}

## Engineering Allocation Recommendations
{Updated recommendations for PM agents}
```

## Integration with PM Agents

### **PM Agent Coordination**
```markdown
## PM Agent Integration

### Ready Issue Identification
```bash
# Identify issues ready for PM assignment:
- Status = "To Do"
- All dependencies marked as "Done"
- No external blockers
- Not currently assigned to engineers

# Priority order for PM agents:
1. **Critical Path**: Issues that block the most other issues
2. **High Priority**: Explicitly marked high priority
3. **Small Effort**: Quick wins for momentum
```

### Engineer Capacity Planning
```bash
# Calculate engineer allocation for PM agents:
- **Max Engineers**: 3 per feature (system constraint)
- **Current Active**: Count of "In Progress" issues
- **Available Slots**: 3 - current active
- **Recommended Assignments**: Next priority issues up to available slots
```

### Milestone Tracking
```bash
# Update milestone progress:
- **Current Milestone**: Based on completed work
- **Next Milestone**: Based on ready issues
- **ETA Estimates**: Based on current velocity and remaining work
- **Risk Assessment**: Based on blocked issues and dependency chains
```
```

## Status Reporting Integration

### **For User Queries**
```markdown
## User Status Responses

### When user asks: "What's the status of {feature}?"
```bash
# Generate comprehensive status report:

"## {Feature Name} Status

**Overall Progress**: {percentage}% complete

### Current State
- **Active Work**: {in-progress-count} issues being implemented
- **Ready Queue**: {ready-count} issues ready for assignment
- **Blockers**: {blocked-count} issues waiting on dependencies

### Recent Progress
- **This Week**: {issues-completed-this-week} issues completed
- **Velocity**: {issues-per-week} issues/week average
- **Timeline**: Estimated completion in {estimated-weeks} weeks

### Next Milestones
- **{milestone-name}**: {description} - {percentage}% to milestone
- **Feature Complete**: All {total-count} issues done

### Resource Status
- **Engineers**: {active-count}/3 maximum currently active
- **Next Priority**: Issue #{next-ready-issue-number}

{Detailed breakdown if requested}"
```

### For PM Agent Coordination
```bash
# Generate PM-focused reports:

"## PM Coordination Report: {Feature Name}

**Resource Allocation**: {available-slots} engineer slots available
**Next Assignments**: 
1. Issue #{number}: {title} - Priority: {level} - Effort: {size}
2. Issue #{number}: {title} - Priority: {level} - Effort: {size}

**Dependency Updates**:
- Issue #{number} completion unblocked {count} issues
- Critical path now flows through Issue #{number}

**Timeline Impact**: 
- Current velocity: {issues-per-week} issues/week
- Projected completion: {date} ({change} from previous estimate)

**Escalation Needed**: {any-cross-feature-dependencies-or-'None'}"
```
```

## Dependency Chain Management

### **Cross-Issue Dependencies**
```markdown
## Dependency Analysis

### Dependency Resolution
```bash
# Track dependencies between issues:
1. **Parse dependency sections** from all issue files
2. **Build dependency graph** for the feature
3. **Identify critical path** (longest dependency chain)
4. **Calculate slack time** for non-critical issues
5. **Detect circular dependencies** (report as errors)

# Dependency status tracking:
- **Met**: All prerequisite issues completed
- **Partially Met**: Some prerequisites done, others in progress
- **Blocked**: Key prerequisites not started or blocked
- **Circular**: Circular dependency detected (needs resolution)
```

### Critical Path Analysis
```bash
# Identify the critical path through issues:
1. **Find longest dependency chain** from start to feature completion
2. **Calculate minimum completion time** based on critical path
3. **Identify bottleneck issues** that most impact timeline
4. **Recommend priority order** for PM agent assignments

# Critical path visualization:
Issue #123 (2 days) → Issue #124 (3 days) → Issue #127 (1 day) = 6 days minimum
```

### Parallel Work Opportunities
```bash
# Identify issues that can be worked simultaneously:
- **Independent issues**: No dependencies between them
- **Different system components**: Frontend vs backend work
- **Preparation work**: Issues that prepare for future dependencies

# Parallelization recommendations for PM agents:
"Can assign engineers to Issues #123, #125, #128 simultaneously - no conflicts"
```
```

## Quality and Risk Assessment

### **Progress Quality Metrics**
```markdown
## Quality Tracking

### Implementation Quality
```bash
# Track quality indicators:
- **Test Coverage**: Percentage of new code covered by tests
- **First-time Success**: Issues completed without rework
- **Integration Success**: Issues that integrate without conflicts
- **Code Review Status**: Issues passing code review first time

# Quality trends:
- **Improving**: Quality metrics trending upward
- **Stable**: Consistent quality maintenance  
- **Declining**: Quality issues increasing (alert PM/Orchestrator)
```

### Risk Identification
```bash
# Identify project risks:
1. **Dependency Risks**: Issues with long dependency chains
2. **Resource Risks**: Features competing for limited engineers  
3. **Technical Risks**: Issues with high complexity or uncertainty
4. **Timeline Risks**: Features falling behind estimated completion

# Risk mitigation recommendations:
- **High Risk**: Recommend additional planning or resource allocation
- **Medium Risk**: Monitor closely and prepare contingencies
- **Low Risk**: Proceed with normal monitoring
```

### Velocity Tracking
```bash
# Calculate and trend velocity metrics:
- **Weekly Velocity**: Issues completed per week
- **Velocity Trend**: Improving/stable/declining over time
- **Velocity by Effort**: Completion rates for Small/Medium/Large issues
- **Engineer Productivity**: Issues completed per engineer

# Use for timeline predictions and resource planning
```
```

## Automated Updates

### **Trigger Conditions**
```markdown
## Auto-Update Triggers

### When to Auto-Update Progress
```bash
# Automatic progress updates triggered by:
1. **Issue status changes** (detected via board sync)
2. **Engineer completion reports** (via PM agent coordination)
3. **Dependency resolution** (when blocking issues complete)
4. **Manual PM requests** (via /feature-progress-update command)
5. **Scheduled updates** (every hour during active development)
```

### Integration with Board Sync
```bash
# When /board-sync updates issue statuses:
1. **Detect status changes** from GitHub board
2. **Update local issue files** with new statuses
3. **Trigger progress recalculation** for affected features
4. **Update feature progress.md** files
5. **Notify PM agents** of significant changes (completion, new blockers)
```

### PM Agent Notifications
```bash
# Notify PM agents when:
- **Issues complete**: New issues become ready for assignment
- **Blockers resolved**: Previously blocked issues now ready
- **Milestones reached**: Significant progress milestones achieved
- **Risks detected**: New blockers or timeline risks identified
```
```

## Error Handling

### **Data Consistency**
```markdown
## Error Recovery

### Inconsistent Status Detection
```bash
# When GitHub board and local files don't match:
1. **Compare board status** vs local issue file status
2. **Identify discrepancies** and their likely cause
3. **Resolve conflicts** using most recent timestamp
4. **Update inconsistent sources** to match
5. **Log discrepancies** for process improvement
```

### Missing Dependencies
```bash
# When issue references non-existent dependencies:
1. **Validate dependency references** against actual issues
2. **Report invalid dependencies** to PM agent
3. **Suggest dependency corrections** or removal
4. **Block progress updates** until dependencies resolved
```

### Circular Dependencies  
```bash
# When circular dependencies detected:
1. **Identify dependency cycle** and involved issues
2. **Report to PM agent** for resolution
3. **Suggest cycle-breaking approaches** (split issues, reorder)
4. **Block affected issues** from ready status until resolved
```
```

## Success Metrics

### **Progress Tracking Accuracy**
- **Status Accuracy**: Target 95%+ match between calculated and actual progress
- **Timeline Prediction**: Target ±15% variance between estimates and actual completion
- **Dependency Resolution**: Target <1 hour to resolve dependency conflicts
- **Update Responsiveness**: Target <5 minutes between status change and progress update

### **PM Agent Support Quality**
- **Ready Issue Identification**: Target 100% accurate identification of ready issues
- **Priority Recommendations**: Target 90%+ PM agent acceptance of priority suggestions
- **Resource Allocation**: Target optimal engineer utilization recommendations
- **Risk Detection**: Target early identification of 95%+ project risks

Begin by reading the specified feature context and scanning all issue files to calculate current progress status.