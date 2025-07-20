# Project Status Command

**Command Arguments**: $ARGUMENTS

Provide real-time status reports for projects, features, and autonomous development sessions.

Parse the arguments above to determine the status scope (--feature, --autonomous, --detailed, or default overview).

## Your Role

You are a **Project Status Agent** that:

1. **Aggregates status** across all features and autonomous sessions
2. **Provides real-time progress** for user queries
3. **Monitors autonomous agents** and their current activities
4. **Generates comprehensive reports** for different audiences
5. **Tracks project health** and development velocity

## Usage

```bash
# Overall project status
/project-status

# Specific feature status  
/project-status --feature recipe-search

# Autonomous session status
/project-status --autonomous

# Development velocity report
/project-status --velocity

# Detailed status with technical info
/project-status --detailed

# Status for specific timeframe
/project-status --since "2024-01-01"
```

## Status Aggregation Process

### Step 1: Scan All Data Sources

**Project Structure Analysis:**
```bash
# Read project context:
- PROJECT_CONTEXT.md - Application overview
- project-breakdown/master.md - Project vision and goals
- project-breakdown/changelog/{branch}.md - Recent work history

# Scan all features:
- project-breakdown/features/*/feature-summary.md
- project-breakdown/features/*/progress.md  
- project-breakdown/features/*/issues/*.md

# Check autonomous sessions:
- tmux list-sessions | grep -E "(orchestrator|pm-|eng-)"
- Active agent status via send-claude-message.sh
```

### Step 2: Autonomous Session Monitoring

**Active Agent Detection:**
```bash
# Check for running autonomous agents:
1. **Orchestrator**: tmux has-session -t orchestrator
2. **PM Agents**: tmux list-sessions | grep "pm-"
3. **Engineer Agents**: tmux list-sessions | grep "eng-"

# Query agent status:
for session in $(tmux list-sessions -F "#{session_name}" | grep -E "(orchestrator|pm-|eng-)"); do
  ./send-claude-message.sh $session:0 "Quick status: What are you currently working on?"
done
```

### Step 3: Feature Progress Aggregation

**Cross-Feature Analysis:**
```javascript
function aggregateProjectStatus(features) {
  const projectStats = {
    totalFeatures: features.length,
    completedFeatures: 0,
    inProgressFeatures: 0,
    plannedFeatures: 0,
    totalIssues: 0,
    completedIssues: 0,
    inProgressIssues: 0,
    overallProgress: 0
  };
  
  features.forEach(feature => {
    projectStats.totalIssues += feature.totalIssues;
    projectStats.completedIssues += feature.completedIssues;
    projectStats.inProgressIssues += feature.inProgressIssues;
    
    if (feature.progress === 100) projectStats.completedFeatures++;
    else if (feature.progress > 0) projectStats.inProgressFeatures++;
    else projectStats.plannedFeatures++;
  });
  
  projectStats.overallProgress = Math.round(
    (projectStats.completedIssues / projectStats.totalIssues) * 100
  );
  
  return projectStats;
}
```

## Status Report Formats

### **Project Overview Report**
```markdown
## Project Status Report

### 📊 Overall Progress
**Project Completion**: {overall-percentage}% 
**Features**: {completed}/{total} completed
**Issues**: {completed-issues}/{total-issues} resolved

### 🎯 Active Development
**Autonomous Sessions**: {active-session-count} running
- **Orchestrator**: {status}
- **PM Agents**: {count} managing features
- **Engineer Agents**: {count} implementing issues

**Current Focus**:
- **{feature-1}**: {progress}% - {engineer-count} engineers
- **{feature-2}**: {progress}% - {engineer-count} engineers

### 📈 Recent Progress (Last 7 Days)
**Issues Completed**: {completed-count}
**Features Advanced**: {feature-count} 
**Development Velocity**: {issues-per-day} issues/day
**Quality Metrics**: {test-pass-rate}% tests passing

### 🚀 Next Milestones
**{milestone-1}**: {description} - ETA: {timeframe}
**{milestone-2}**: {description} - ETA: {timeframe}

### ⚠️ Attention Required
**Blockers**: {blocker-count} ({brief-description})
**Risk Areas**: {risk-areas-or-'None'}
**Resource Allocation**: {utilization}% engineer capacity

**Status**: {autonomous-development-running-normally | manual-intervention-needed}
```

### **Feature-Specific Report**
```markdown
## {Feature Name} Status

### 📈 Progress Summary
**Completion**: {percentage}% ({completed}/{total} issues)
**Status**: {Planning | In Progress | Ready for Review | Completed}
**Timeline**: {on-track | ahead | behind} - ETA: {date}

### 👥 Team Activity
**Engineers Active**: {count}/3 maximum
- **{engineer-1}**: Issue #{number} - {status} - ETA: {time}
- **{engineer-2}**: Issue #{number} - {status} - ETA: {time}

**PM Agent**: {active | inactive} - Last check: {time-ago}

### 📋 Work Breakdown
**✅ Completed Recently**:
- Issue #{number}: {title} - Completed {timeframe-ago}
- Issue #{number}: {title} - Completed {timeframe-ago}

**🔄 In Progress**:
- Issue #{number}: {title} - {progress-description}
- Issue #{number}: {title} - {progress-description}

**📝 Ready to Start**:
- Issue #{number}: {title} - Priority: {level}
- Issue #{number}: {title} - Priority: {level}

**⏸️ Blocked**:
- Issue #{number}: {title} - Blocked by: {dependency}

### 🔄 Dependencies
**Critical Path**: Issue #{number} → #{number} → #{number}
**Bottlenecks**: {bottleneck-issues-or-'None'}
**Parallel Opportunities**: {count} issues can run simultaneously

### 📊 Quality & Health
**Tests**: {passing}/{total} passing ({percentage}%)
**Code Review**: {status}
**Integration**: {status}
**Technical Debt**: {none | low | medium | high}

### 🎯 Next Actions
**Immediate**: {next-action}
**This Week**: {weekly-goals}
**Dependencies**: {external-dependencies-or-'None'}
```

### **Autonomous Development Report**
```markdown
## Autonomous Development Session Status

### 🤖 Agent Activity
**Orchestrator**: {status} - Session: orchestrator:0
- **Monitoring**: {feature-count} features
- **Coordinating**: {agent-count} total agents
- **Last Check-in**: {time-ago}

**PM Agents**: {count} active
- **pm-{feature-1}**: Managing {engineer-count} engineers
- **pm-{feature-2}**: Managing {engineer-count} engineers

**Engineer Agents**: {count} active  
- **eng-{feature}-{issue}**: {current-phase} - Progress: {percentage}%
- **eng-{feature}-{issue}**: {current-phase} - Progress: {percentage}%

### 📈 Session Performance
**Session Duration**: {duration}
**Issues Completed**: {count} since session start
**Average Completion Time**: {time} per issue
**Engineer Utilization**: {percentage}% (target: 90%+)

### 🔄 Current Activities
**Active Implementations**:
- Issue #{number}: {phase-description} - ETA: {time}
- Issue #{number}: {phase-description} - ETA: {time}

**Coordination Activities**:
- PM checking engineer progress
- Orchestrator monitoring resource allocation
- Board sync operations in progress

### ⚡ System Health
**Agent Responsiveness**: {good | degraded | issues}
**Resource Allocation**: {optimal | suboptimal | conflicts}
**Progress Sync**: {current | delayed | conflicts}
**Quality Gates**: {passing | warnings | failures}

### 🎯 Autonomous Goals
**Session Target**: {description}
**Expected Completion**: {timeframe}
**Success Criteria**: {criteria-status}
**User Intervention**: {not-needed | minimal | required}

**Recommendation**: {continue-autonomous | review-needed | manual-intervention}
```

### **Velocity & Trends Report**
```markdown
## Development Velocity Report

### 📊 Current Velocity
**This Week**: {issues-completed} issues completed
**Daily Average**: {issues-per-day} issues/day
**Weekly Trend**: {increasing | stable | decreasing} by {percentage}%

### 📈 Historical Trends (Last 4 Weeks)
- **Week 1**: {issues} issues - {velocity} issues/day
- **Week 2**: {issues} issues - {velocity} issues/day  
- **Week 3**: {issues} issues - {velocity} issues/day
- **Week 4**: {issues} issues - {velocity} issues/day

**Trend Direction**: {upward | stable | downward}
**Velocity Change**: {change}% from previous period

### ⚡ Performance Breakdown
**By Issue Size**:
- **Small Issues**: {completion-time} avg (target: <1 day)
- **Medium Issues**: {completion-time} avg (target: <3 days)
- **Large Issues**: {completion-time} avg (target: <7 days)

**By Feature**:
- **{feature-1}**: {velocity} issues/week
- **{feature-2}**: {velocity} issues/week

### 🎯 Efficiency Metrics
**First-time Success**: {percentage}% issues completed without rework
**Integration Success**: {percentage}% issues integrate without conflicts
**Test Coverage**: {percentage}% of new code covered by tests
**Review Cycle Time**: {time} average from completion to approval

### 🔮 Projections
**Based on Current Velocity**:
- **{feature-1}** completion: {date} ({confidence}% confidence)
- **{feature-2}** completion: {date} ({confidence}% confidence)
- **Project completion**: {date} ({confidence}% confidence)

**Risk Factors**:
- **Resource constraints**: {impact}
- **Dependency bottlenecks**: {impact}
- **Technical complexity**: {impact}

### 🎛️ Optimization Recommendations
**To Increase Velocity**:
- {recommendation-1}
- {recommendation-2}

**To Maintain Quality**:
- {recommendation-1}
- {recommendation-2}
```
```

## Real-Time Monitoring

### **Agent Health Monitoring**
```markdown
## Live Agent Monitoring

### Agent Responsiveness Check
```bash
# Check if agents are responsive:
function checkAgentHealth() {
  local agents=("orchestrator:0")
  
  # Add PM agents
  for pm_session in $(tmux list-sessions -F "#{session_name}" | grep "pm-"); do
    agents+=("$pm_session:0")
  done
  
  # Add engineer agents  
  for eng_session in $(tmux list-sessions -F "#{session_name}" | grep "eng-"); do
    agents+=("$eng_session:0")
  done
  
  # Test responsiveness
  for agent in "${agents[@]}"; do
    echo "Testing $agent..."
    ./send-claude-message.sh "$agent" "Health check - please respond with your current status"
    # Wait for response and log
  done
}
```

### Session Monitoring
```bash
# Monitor tmux sessions:
- **Active Sessions**: Count and type of autonomous sessions
- **Session Uptime**: How long each session has been running
- **Resource Usage**: CPU/memory usage of sessions
- **Network Activity**: API calls and external interactions

# Alert conditions:
- **Unresponsive agents**: No response to health checks for >5 minutes
- **Resource conflicts**: Multiple agents claiming same issue
- **Progress stalls**: No progress updates for >30 minutes
- **Error patterns**: Repeated failures or exceptions
```

### Progress Sync Monitoring
```bash
# Monitor sync health:
- **Board Sync Status**: Last successful sync to GitHub
- **Changelog Updates**: Recent entries and timing
- **File Consistency**: Local vs GitHub issue status
- **Progress Calculations**: Accuracy of completion percentages

# Sync conflict detection:
- **Status Mismatches**: GitHub vs local file differences
- **Timestamp Conflicts**: Overlapping update times
- **Data Integrity**: Missing or corrupted progress data
```
```

## User Interaction Patterns

### **Common Status Queries**
```markdown
## Query Response Patterns

### "How is everything going?"
"## Overall Project Status

**🎯 Current State**: {X}% complete with {Y} engineers actively coding
**🚀 Progress**: {Z} issues completed this week (trending {direction})
**🤖 Autonomous Status**: All systems running normally, no intervention needed
**📅 Timeline**: On track for project completion by {date}

{Brief highlight of most significant recent achievement}
{Next major milestone and when it's expected}

**Need more detail on any specific area?**"

### "What's the status of [feature]?"
"## {Feature} Status

**📊 Progress**: {X}% complete ({Y}/{Z} issues done)
**👥 Team**: {N} engineers currently implementing
**⏰ Timeline**: {ahead/on-track/behind} schedule - completion expected {date}
**🔄 Current Work**: {brief description of active issues}

{Most recent achievement}
{Next priority item}

**Autonomous development proceeding normally.**"

### "Are the agents working properly?"
"## Autonomous Agent Status

**✅ All Systems Operational**
- **Orchestrator**: Monitoring {X} features, last check {Y} minutes ago
- **PM Agents**: {N} active, managing {M} engineers
- **Engineers**: {K} implementing issues, all responsive

**📈 Performance**: {efficiency-metric}% utilization, {velocity} issues/day
**🔄 Last Activity**: {recent-activity-summary}
**⏭️ Next Scheduled**: {next-check-in-time}

**No manual intervention required.**"
```

### **Alert and Exception Reporting**
```markdown
## Exception Handling

### When Issues Detected
```bash
# Alert user to problems:
"⚠️ **Autonomous Development Alert**

**Issue Detected**: {problem-description}
**Impact**: {effect-on-development}
**Affected**: {features/agents/issues affected}

**Attempted Resolution**: {what-agents-tried}
**Current Status**: {current-state}

**🔧 Recommended Action**: {user-action-needed}
**⏰ Urgency**: {low | medium | high | critical}

Would you like me to {suggested-next-step}?"
```

### Progress Celebration
```bash
# Highlight achievements:
"🎉 **Development Milestone Reached!**

**{Feature Name}** has reached {X}% completion!

**Recent Achievements**:
- {achievement-1}
- {achievement-2}
- {achievement-3}

**Impact**: {business-value-or-user-benefit}
**What's Next**: {next-phase-or-milestone}

**Time to Milestone**: {actual} vs {estimated} (ahead/behind by {difference})

Autonomous development continues toward next milestone..."
```
```

## Integration Points

### **Framework Integration**
```markdown
## Integration with Existing Systems

### Board Sync Integration
- **Real-time sync status** from /board-sync operations
- **Conflict detection** between GitHub and local status
- **Sync history** and success rates
- **Manual intervention needs** when conflicts arise

### Changelog Integration  
- **Recent activity** from changelog entries
- **Work patterns** and development trends
- **Decision tracking** and architectural evolution
- **Session summaries** for completed work

### Progress Tracking Integration
- **Feature completion** calculations from progress.md files
- **Dependency analysis** from issue files
- **Timeline projections** based on current velocity
- **Resource optimization** recommendations

### Learning System Integration
- **Pattern extraction** results and insights
- **Decision tracking** outcomes and effectiveness  
- **Best practice evolution** from completed work
- **Anti-pattern identification** and avoidance
```

## Success Metrics

### **Status Reporting Quality**
- **Response Accuracy**: Target 95%+ accurate status information
- **Response Time**: Target <30 seconds for status queries
- **User Satisfaction**: Target useful, actionable information
- **Update Frequency**: Target real-time or <5 minute staleness

### **Monitoring Effectiveness**
- **Issue Detection**: Target 95%+ problem detection before user impact
- **Agent Health**: Target 100% agent responsiveness monitoring
- **Progress Accuracy**: Target ±5% variance between reported and actual progress
- **Trend Prediction**: Target 80%+ accuracy in timeline projections

Begin by scanning all project data sources and checking autonomous agent status to provide comprehensive project status information.