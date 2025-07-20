# Session Summary Command

Generate comprehensive summaries of autonomous development sessions for review and context preservation.

## Your Role

You are a **Session Summary Agent** that:

1. **Analyzes autonomous development sessions** to capture what was accomplished
2. **Documents work completed** by PM and Engineer agents  
3. **Preserves decision context** and technical choices made
4. **Creates review-ready summaries** for user evaluation
5. **Maintains session continuity** for future development cycles

## Usage

```bash
# Summary of current active session
/session-summary

# Summary of specific feature development session
/session-summary --feature recipe-search

# Summary of completed autonomous session  
/session-summary --session pm-user-auth --completed

# Summary with technical details
/session-summary --detailed

# Summary for specific timeframe
/session-summary --since "2024-01-15 09:00"
```

## Summary Generation Process

### Step 1: Session Data Collection

**Autonomous Session Analysis:**
```bash
# Identify active/recent sessions:
1. **Active Sessions**: tmux list-sessions | grep -E "(orchestrator|pm-|eng-)"
2. **Session Logs**: Extract work logs from agent coordination files
3. **Tmux History**: Capture command history and interactions
4. **Agent Communication**: Parse messages between agents

# Collect work artifacts:
- **Code Changes**: Git commits during session timeframe
- **Issue Updates**: Status changes and completions
- **Board Activity**: GitHub project board movements
- **Changelog Entries**: Session-specific changelog additions
```

### Step 2: Work Product Analysis

**Implementation Analysis:**
```javascript
function analyzeSessionWork(sessionData) {
  const summary = {
    duration: calculateSessionDuration(sessionData),
    issuesWorked: extractIssuesWorked(sessionData),
    issuesCompleted: extractCompletedIssues(sessionData),
    codeChanges: analyzeGitCommits(sessionData),
    decisionsModel: extractDecisions(sessionData),
    blockers: identifyBlockersEncountered(sessionData),
    quality: assessQualityMetrics(sessionData)
  };
  
  return summary;
}
```

### Step 3: Context Preservation

**Decision Documentation:**
```bash
# Extract and document:
1. **Technical Decisions**: Architecture choices made during implementation
2. **Problem Solutions**: How blockers and challenges were resolved
3. **Pattern Applications**: Which existing patterns were used effectively
4. **New Patterns**: Novel approaches discovered during development
5. **Lessons Learned**: Insights gained that improve future work
```

## Summary Report Formats

### **Executive Session Summary**
```markdown
## Development Session Summary

### 📊 Session Overview
**Duration**: {start-time} to {end-time} ({total-duration})
**Scope**: {feature-names-or-'Multiple features'}
**Mode**: {Autonomous | Semi-autonomous | Manual}
**Completion Status**: {Completed | In Progress | Paused}

### 🎯 Accomplishments
**Issues Completed**: {completed-count}/{worked-count}
- Issue #{number}: {title} - {brief-implementation-summary}
- Issue #{number}: {title} - {brief-implementation-summary}

**Features Advanced**:
- **{feature-name}**: {start-progress}% → {end-progress}% ({change}% increase)
- **{feature-name}**: {start-progress}% → {end-progress}% ({change}% increase)

### 💻 Development Metrics
**Code Changes**: {files-modified} files, {lines-added}+ / {lines-removed}-
**Test Coverage**: {coverage-before}% → {coverage-after}% 
**Quality Gates**: {passing-count}/{total-count} passing
**Commit Frequency**: {commits} commits ({commits-per-hour} per hour)

### 🚀 Key Achievements
1. **{achievement-1}**: {description-and-impact}
2. **{achievement-2}**: {description-and-impact}
3. **{achievement-3}**: {description-and-impact}

### ⚡ Development Efficiency
**Autonomous Operation**: {percentage}% of work completed without intervention
**Velocity**: {issues-per-day} issues/day ({vs-target})
**Resource Utilization**: {engineer-hours} engineer hours ({efficiency}% utilization)
**Integration Success**: {percentage}% first-time integration success

### 📋 Session Health
**Agent Performance**: {excellent | good | adequate | issues}
**Progress Sync**: {current | minor-delays | sync-issues}
**Quality Maintenance**: {high | standard | needs-attention}
**User Intervention**: {minimal | moderate | frequent}

**Overall Assessment**: {highly-successful | successful | partially-successful | needs-improvement}
```

### **Technical Session Summary**
```markdown
## Technical Development Session Report

### 🛠️ Implementation Details

#### Issues Completed ({completed-count})
**Issue #{number}: {title}**
- **Implementation Approach**: {technical-approach-used}
- **Files Modified**: `{file-list}`
- **Key Technical Decisions**: {decisions-made}
- **Testing Added**: {test-types-and-coverage}
- **Integration Points**: {how-it-connects}
- **Time to Complete**: {duration} ({vs-estimate})

#### Issues In Progress ({in-progress-count})
**Issue #{number}: {title}**
- **Current Phase**: {phase-description}
- **Progress**: {percentage}% complete
- **Technical Approach**: {approach-being-used}
- **Next Steps**: {what-happens-next}
- **Blockers**: {current-blockers-or-'None'}

### 🏗️ Architecture & Design

#### Technical Decisions Made
1. **{decision-category}**: {decision-made}
   - **Rationale**: {why-this-choice}
   - **Alternatives Considered**: {other-options}
   - **Impact**: {effects-on-system}

#### Patterns Applied
- **{pattern-name}**: Used in {context} for {purpose}
- **{pattern-name}**: Applied to solve {problem}

#### New Patterns Discovered
- **{pattern-name}**: {description-and-context}
- **Applicability**: {where-else-this-could-be-used}

### 🔧 Code Quality Analysis

#### Code Changes Overview
```bash
Files Modified: {count}
├── {file-category-1}: {count} files
├── {file-category-2}: {count} files  
└── {file-category-3}: {count} files

Lines of Code:
├── Added: {lines}
├── Removed: {lines}
└── Net Change: {net-lines}
```

#### Quality Metrics
- **Test Coverage**: {previous}% → {current}% ({change})
- **Code Complexity**: {complexity-analysis}
- **Technical Debt**: {debt-added | debt-reduced | neutral}
- **Performance Impact**: {positive | neutral | negative | unknown}

#### Code Review Readiness
- **Style Compliance**: {percentage}% passing
- **Security Review**: {passing | needs-review | issues-found}
- **Performance Review**: {optimized | standard | needs-optimization}
- **Documentation**: {comprehensive | adequate | needs-improvement}

### 🧪 Testing & Validation

#### Test Development
- **Unit Tests**: {count} added, {coverage}% coverage
- **Integration Tests**: {count} added
- **End-to-End Tests**: {count} added
- **Test Quality**: {excellent | good | adequate}

#### Validation Results
- **All Tests**: {passing}/{total} passing ({percentage}%)
- **Performance Tests**: {within-targets | borderline | concerning}
- **Security Tests**: {passing | warnings | failures}
- **User Acceptance**: {criteria-met}/{total-criteria}

### 🔄 Integration & Deployment

#### Integration Status
- **Component Integration**: {successful | issues | incomplete}
- **API Integration**: {successful | issues | incomplete}
- **Database Integration**: {successful | issues | incomplete}
- **External Services**: {successful | issues | incomplete}

#### Deployment Readiness
- **Build Status**: {passing | failing | not-tested}
- **Deployment Pipeline**: {ready | needs-configuration | blocked}
- **Environment Compatibility**: {verified | assumed | unknown}
- **Rollback Plan**: {prepared | standard | not-applicable}
```

### **PM Agent Session Summary**
```markdown
## Project Management Session Report

### 👥 Resource Management

#### Engineer Allocation
**Session Peak**: {max-engineers} engineers simultaneously
**Average Utilization**: {average-engineers} engineers active
**Efficiency**: {utilization-percentage}% of available engineer time productive

**Engineer Performance**:
- **Highest Velocity**: {engineer-id} - {issues-completed} issues, {average-time} per issue
- **Quality Leader**: {engineer-id} - {quality-metrics}
- **Most Complex Work**: {engineer-id} - {complexity-description}

#### Resource Optimization
- **Parallel Work**: {parallel-issues} issues worked simultaneously
- **Dependency Management**: {dependencies-resolved} dependencies resolved
- **Bottleneck Resolution**: {bottlenecks-addressed} bottlenecks addressed
- **Resource Conflicts**: {conflicts-encountered} conflicts, {resolution-time} avg resolution

### 🎯 Coordination Effectiveness

#### Decision Making
**Decisions Made**: {total-decisions}
- **Resource Allocation**: {resource-decisions}
- **Priority Changes**: {priority-decisions}
- **Technical Guidance**: {technical-decisions}
- **Escalations**: {escalation-decisions}

**Decision Quality**: {excellent | good | adequate | needs-improvement}
**Decision Speed**: {fast | appropriate | slow} ({average-decision-time})

#### Issue Management
- **Issues Assigned**: {assigned-count}
- **Issues Completed**: {completed-count}
- **Issue Velocity**: {issues-per-hour} per engineer per hour
- **Quality Rate**: {percentage}% first-time completion success

#### Blocker Resolution
- **Blockers Encountered**: {total-blockers}
- **Average Resolution Time**: {average-time}
- **Escalation Rate**: {percentage}% required escalation
- **Self-Resolved**: {percentage}% resolved without escalation

### 📊 Progress Tracking

#### Feature Progress Management
**Features Managed**: {feature-count}
- **{feature-name}**: {start}% → {end}% ({change}% progress)
- **Milestone Progress**: {milestones-reached}/{target-milestones}

#### Sync Operations
- **Board Syncs**: {sync-count} operations
- **Changelog Updates**: {update-count} entries added  
- **Progress Updates**: {update-count} progress.md updates
- **Sync Success Rate**: {percentage}% successful

#### Timeline Management
- **Estimates vs Actual**: {accuracy-percentage}% accuracy
- **Schedule Adherence**: {on-time | ahead | behind | mixed}
- **Risk Mitigation**: {risks-identified} risks, {mitigation-actions} actions taken

### 🔄 Session Continuity

#### Handoff Preparation
- **Documentation Updated**: All progress and decisions documented
- **Next Priorities**: {next-priority-issues} ready for assignment
- **Resource Planning**: {future-resource-needs}
- **Risk Assessment**: {identified-risks-for-future}

#### Knowledge Transfer
- **Lessons Learned**: {insights-captured}
- **Process Improvements**: {improvements-identified}
- **Pattern Updates**: {patterns-refined-or-added}
- **Decision Log**: {decisions-documented}
```

### **Development Velocity Analysis**
```markdown
## Session Velocity Report

### ⚡ Performance Metrics

#### Overall Velocity
**Issues/Hour**: {issues-per-hour} ({vs-baseline})
**Issues/Day**: {issues-per-day} ({vs-target})
**Completion Rate**: {percentage}% of started issues completed
**Quality Rate**: {percentage}% completed without rework

#### Velocity by Issue Size
- **Small Issues**: {avg-time} average ({target-time} target)
- **Medium Issues**: {avg-time} average ({target-time} target)  
- **Large Issues**: {avg-time} average ({target-time} target)

#### Velocity Trends
- **Session Start**: {initial-velocity} issues/hour
- **Session Mid**: {mid-velocity} issues/hour
- **Session End**: {final-velocity} issues/hour
- **Trend**: {improving | stable | declining}

### 📈 Efficiency Analysis

#### Time Distribution
```bash
Total Session Time: {total-hours} hours
├── Active Development: {dev-hours} hours ({percentage}%)
├── Planning & Analysis: {planning-hours} hours ({percentage}%)
├── Testing & Validation: {test-hours} hours ({percentage}%)
├── Coordination: {coord-hours} hours ({percentage}%)
└── Blocked/Waiting: {blocked-hours} hours ({percentage}%)
```

#### Productivity Factors
**Positive Contributors**:
- {factor-1}: {impact-description}
- {factor-2}: {impact-description}

**Efficiency Barriers**:
- {barrier-1}: {impact-description}
- {barrier-2}: {impact-description}

#### Quality vs Speed Balance
- **Fast Completion**: {issues-count} issues ({quality-rate}% quality)
- **Standard Pace**: {issues-count} issues ({quality-rate}% quality)
- **Careful Implementation**: {issues-count} issues ({quality-rate}% quality)

**Optimal Balance**: {analysis-of-best-approach}

### 🎯 Session Goals Achievement

#### Goal Completion
**Primary Goals**: {completed}/{total} achieved
- **{goal-1}**: {achieved | partially-achieved | not-achieved}
- **{goal-2}**: {achieved | partially-achieved | not-achieved}

**Success Metrics**:
- **Feature Progress**: {actual}% vs {target}% target
- **Issue Completion**: {actual} vs {target} target
- **Quality Standards**: {actual}% vs {target}% target

#### Value Delivered
**Business Value**: {value-assessment}
**Technical Value**: {technical-improvements}
**Learning Value**: {insights-and-improvements}

**ROI Assessment**: {high | good | adequate | needs-improvement}
```
```

## Session Continuity

### **Context Preservation**
```markdown
## Session Context for Future Development

### 🧠 Knowledge Captured

#### Architecture Insights
- **Design Patterns**: {patterns-discovered-or-refined}
- **Integration Approaches**: {successful-integration-methods}
- **Performance Considerations**: {performance-insights}
- **Security Practices**: {security-approaches-used}

#### Implementation Learnings
- **Effective Approaches**: {what-worked-well}
- **Avoided Anti-patterns**: {problematic-approaches-avoided}
- **Tool Usage**: {tools-and-techniques-that-helped}
- **Process Refinements**: {process-improvements-discovered}

### 🔄 Handoff Information

#### For Next Development Session
**Immediate Priorities**:
1. {next-priority-task-1}
2. {next-priority-task-2}
3. {next-priority-task-3}

**Context for Next Team**:
- **Current Architecture State**: {state-description}
- **Recent Decisions**: {key-decisions-that-affect-future-work}
- **Known Issues**: {issues-to-be-aware-of}
- **Recommended Approaches**: {approaches-to-continue}

#### Resource Requirements
- **Engineer Skills Needed**: {skill-requirements}
- **Estimated Effort**: {effort-estimates}
- **Dependencies**: {external-dependencies}
- **Risk Areas**: {areas-requiring-careful-attention}

### 📋 Action Items Generated

#### Technical Tasks
- [ ] {technical-task-1}
- [ ] {technical-task-2}

#### Process Improvements
- [ ] {process-improvement-1}
- [ ] {process-improvement-2}

#### Documentation Updates
- [ ] {documentation-update-1}
- [ ] {documentation-update-2}

#### Follow-up Questions
- [ ] {question-or-investigation-1}
- [ ] {question-or-investigation-2}
```

## Integration with Framework

### **Framework Integration Points**
```markdown
## Integration with Existing Systems

### Changelog Integration
- **Session entries** automatically added to branch changelog
- **Decision documentation** integrated with decision tracking
- **Pattern updates** fed into learning system
- **Velocity data** captured for project planning

### Progress Tracking Integration
- **Feature progress** updated based on session accomplishments
- **Timeline estimates** refined based on actual completion times
- **Resource planning** informed by utilization metrics
- **Quality tracking** updated with test coverage and success rates

### Learning System Integration
- **Pattern extraction** from successful implementations
- **Anti-pattern identification** from challenges encountered
- **Best practice evolution** from effective approaches
- **Process optimization** from efficiency insights

### Board Sync Integration
- **Status synchronization** ensures GitHub board reflects session work
- **Issue lifecycle** properly tracked from assignment to completion
- **Progress visibility** maintained for stakeholders
- **Quality gates** reflected in issue status and labels
```

## Success Metrics

### **Summary Quality**
- **Completeness**: Target 95%+ of session work captured
- **Accuracy**: Target factual accuracy in all reported metrics
- **Usefulness**: Target actionable insights for future sessions
- **Context Preservation**: Target sufficient detail for session continuation

### **Value to Development Process**
- **Decision Documentation**: Target 100% of significant decisions captured
- **Learning Capture**: Target effective extraction of insights and patterns
- **Continuity Support**: Target seamless handoff between sessions
- **Process Improvement**: Target identification of optimization opportunities

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Enhance issue discovery to include dependency tracking and implementation plans", "status": "completed", "priority": "high", "id": "1"}, {"content": "Create feature progress tracking system with completion percentages", "status": "completed", "priority": "high", "id": "2"}, {"content": "Build orchestrator agent as user interface to autonomous coding", "status": "completed", "priority": "high", "id": "3"}, {"content": "Create project manager agent with dependency resolution and engineer spawning", "status": "completed", "priority": "high", "id": "4"}, {"content": "Build engineering agent template for autonomous issue implementation", "status": "completed", "priority": "high", "id": "5"}, {"content": "Integrate tmux orchestration with existing board sync and changelog systems", "status": "completed", "priority": "high", "id": "6"}, {"content": "Create status reporting system for real-time project/feature progress queries", "status": "completed", "priority": "medium", "id": "7"}, {"content": "Add session summary generation for PM agent end-of-session reports", "status": "completed", "priority": "medium", "id": "8"}]