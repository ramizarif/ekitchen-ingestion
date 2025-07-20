# Changelog Summary Command

Generate concise summaries of branch work for conversation compaction, context loading, and progress reporting.

## Your Role

You are a **Changelog Summary Agent** that:

1. **Reads branch changelog** to understand all work completed
2. **Generates concise summaries** for different use cases
3. **Provides context for conversation compaction** when conversations get too long
4. **Creates progress reports** for stakeholders
5. **Helps new agents understand** recent work and decisions

## Usage

```bash
# Generate summary for current branch
/changelog-summary

# Generate summary for specific branch
/changelog-summary --branch feature-user-auth

# Generate summary since specific date
/changelog-summary --since "2024-01-01"

# Generate summary for conversation compaction
/changelog-summary --compact

# Generate summary for specific audience
/changelog-summary --for stakeholders
/changelog-summary --for new-agent
/changelog-summary --for code-review

# Generate summary of specific work types
/changelog-summary --type implementation
/changelog-summary --type feature-planning
/changelog-summary --type learning
```

## Summary Types

### 1. Conversation Compaction Summary
**Purpose**: Preserve essential context when conversations get too long
**Audience**: Future AI agents continuing work
**Focus**: Decisions, current state, next steps

### 2. Progress Report Summary  
**Purpose**: Communicate progress to stakeholders
**Audience**: Project managers, other developers
**Focus**: Achievements, timelines, deliverables

### 3. New Agent Onboarding Summary
**Purpose**: Help new agents understand recent work
**Audience**: Fresh AI agents starting work
**Focus**: Architecture changes, patterns, current priorities

### 4. Code Review Summary
**Purpose**: Provide context for code reviews
**Audience**: Code reviewers
**Focus**: Implementation decisions, testing, technical debt

## Summary Generation Process

### Step 1: Load Changelog Data

**Read Current Branch Changelog:**
1. Determine current branch: `git branch --show-current`
2. Load `project-breakdown/changelog/{branch-name}.md`
3. Parse all entries by type and date
4. Extract statistics and current state

**Date Filtering (if specified):**
- Filter entries to specified date range
- Recalculate statistics for filtered period
- Focus summary on recent work only

### Step 2: Analyze Work Patterns

**Categorize Work:**
```javascript
const workAnalysis = {
  featurePlanning: {
    count: entries.filter(e => e.type === 'feature-planning').length,
    features: extractFeatureNames(entries),
    decisions: extractKeyDecisions(entries)
  },
  implementation: {
    count: entries.filter(e => e.type === 'implementation').length,
    issuesCompleted: extractCompletedIssues(entries),
    technicalDecisions: extractTechnicalDecisions(entries)
  },
  learning: {
    patterns: extractPatterns(entries),
    antiPatterns: extractAntiPatterns(entries),
    insights: extractInsights(entries)
  }
};
```

**Identify Themes:**
- Major features developed
- Technical challenges overcome
- Architectural changes made
- Learning insights gained

### Step 3: Generate Targeted Summary

#### Conversation Compaction Summary

```markdown
# Branch Context Summary: {branch-name}

## Essential Context for AI Agents

### Branch Purpose
{One-sentence description of branch goal}

### Current State
- **Status**: {In Progress | Ready for Review | Completed}
- **Last Activity**: {date of most recent work}
- **Active Issues**: {list of in-progress issues}
- **Next Priority**: {what should happen next}

### Major Achievements (Last {timeframe})
- {Achievement 1 with brief context}
- {Achievement 2 with brief context}
- {Achievement 3 with brief context}

### Key Architectural Decisions
**{Decision 1}**: {Brief description and rationale}
**{Decision 2}**: {Brief description and rationale}
**{Decision 3}**: {Brief description and rationale}

### Current Architecture State
{How the system has evolved - what's different from when work started}

### Implementation Patterns Established
- **{Pattern 1}**: {Where used and why}
- **{Pattern 2}**: {Where used and why}

### Technical Debt & TODOs
- {Important debt that affects future work}
- {Open questions that need resolution}

### Files Most Important for Context
- `{file-path}` - {why this file is important}
- `{file-path}` - {why this file is important}

### Next Steps
1. {Immediate next action}
2. {Medium-term goal}
3. {Longer-term consideration}

---
*This summary preserves essential context for continuing work after conversation compaction.*
```

#### Progress Report Summary

```markdown
# Progress Report: {branch-name}

## Executive Summary
{2-3 sentences describing overall progress and current status}

## Work Completed ({timeframe})

### Features Developed
- **{Feature 1}**: {Status} - {Brief description of value delivered}
- **{Feature 2}**: {Status} - {Brief description of value delivered}

### Issues Resolved
- **{count} issues completed** across {feature-count} features
- **Key completions**: {most significant issue completions}

### Quality & Testing
- **Tests**: {test coverage or count}
- **Code Quality**: {quality metrics or observations}
- **Documentation**: {documentation updates made}

## Key Achievements
1. **{Achievement 1}**: {Impact and value}
2. **{Achievement 2}**: {Impact and value}
3. **{Achievement 3}**: {Impact and value}

## Technical Highlights
- **Architecture**: {significant architectural improvements}
- **Performance**: {performance improvements made}
- **Technical Debt**: {debt resolved or managed}

## Timeline & Effort
- **Total Time Invested**: {total time from changelog}
- **Planning Time**: {time spent on planning}
- **Implementation Time**: {time spent coding}
- **Review/Testing Time**: {time spent on quality}

## Current Status & Next Steps
- **Current Status**: {where we stand now}
- **Immediate Next Steps**: {what's happening next}
- **Upcoming Milestones**: {what to expect soon}

## Challenges & Resolutions
- **Challenge**: {challenge faced} → **Resolution**: {how resolved}
- **Challenge**: {challenge faced} → **Resolution**: {how resolved}

---
*Report generated from branch changelog on {date}*
```

#### New Agent Onboarding Summary

```markdown
# New Agent Onboarding: {branch-name}

## Welcome to {branch-name}!

### What This Branch Is About
{Clear explanation of branch purpose and goals}

### Recent Work Context
**Last {timeframe} Summary**: {what's been happening recently}
**Current Priority**: {what's most important right now}
**Your Role**: {what a new agent should focus on}

### Architecture You Should Know About

#### Recent Changes Made
- **{Change 1}**: {what changed and why}
- **{Change 2}**: {what changed and why}

#### Current Architecture State
{Description of how systems are organized now}

#### Patterns We're Using
- **{Pattern 1}**: {description and where it's used}
- **{Pattern 2}**: {description and where it's used}

#### Patterns We Avoid (Anti-patterns)
- **{Anti-pattern 1}**: {why we don't do this}
- **{Anti-pattern 2}**: {why we don't do this}

### Key Files to Understand
- `{file-path}` - {what this file does and why it's important}
- `{file-path}` - {what this file does and why it's important}
- `{file-path}` - {what this file does and why it's important}

### Features You Should Know About
#### {Feature 1} - {Status}
- **Purpose**: {what this feature does}
- **Status**: {current implementation state}
- **Issues**: {related GitHub issues}

#### {Feature 2} - {Status}
- **Purpose**: {what this feature does}
- **Status**: {current implementation state}
- **Issues**: {related GitHub issues}

### Current Work Items
- **In Progress**: {what's actively being worked on}
- **Ready to Start**: {what's ready for implementation}
- **Blocked**: {what's waiting on something else}

### Important Decisions Made
{Key decisions that affect how you should work}

### Best Practices Learned
{What we've learned works well}

### Getting Started Recommendations
1. **Read**: {specific files to read first}
2. **Understand**: {key concepts to grasp}
3. **Start with**: {good first issues or tasks}

---
*Onboarding summary current as of {date}*
```

## Summary Customization

### Audience-Specific Adjustments

**For Stakeholders:**
- Focus on business value and deliverables
- Minimize technical jargon
- Emphasize timelines and progress
- Highlight user-facing improvements

**For Technical Team:**
- Include detailed technical decisions
- Cover architecture changes thoroughly
- Mention performance implications
- Discuss technical debt management

**For Code Reviewers:**
- Focus on implementation decisions
- Highlight testing approach
- Mention potential risk areas
- Include context for unusual patterns

### Time-Based Filtering

**Recent Work (Last Week):**
- Focus on immediate context
- Highlight active work
- Show current blockers and priorities

**Sprint/Milestone Summary:**
- Cover planned vs. actual progress
- Highlight scope changes
- Show milestone achievement

**Full Branch Summary:**
- Complete evolution narrative
- All major decisions and changes
- Full achievement overview

## Auto-Summary Triggers

### When to Auto-Generate Summaries

**Conversation Length Triggers:**
- When conversation approaches token limits
- Before major context switches
- When starting new work sessions

**Time-Based Triggers:**
- Weekly progress summaries
- Sprint/milestone completions
- Before branch merges

**Event-Based Triggers:**
- After major feature completions
- After significant architectural changes
- Before handoffs to other teams

## Integration with Other Commands

### With Conversation Compaction
```markdown
## Conversation Compaction Support

When conversations get too long:
1. **Auto-generate compact summary** of recent work
2. **Preserve essential context** for new conversation
3. **Include decision rationale** for ongoing work
4. **Highlight current state** and immediate next steps
```

### With Project Health Checks
```markdown
## Project Health Integration

Include changelog insights in project health:
- **Velocity trends** from completion statistics
- **Quality indicators** from testing and review entries
- **Technical debt trends** from implementation entries
- **Learning velocity** from pattern extraction frequency
```

## Success Criteria

### Context Preservation
- Essential information survives conversation compaction
- New agents can quickly understand recent work
- Decision context is preserved across sessions

### Communication Quality
- Stakeholders get clear progress visibility
- Technical teams understand implementation context
- Code reviewers have sufficient background

### Efficiency Gains
- Reduced onboarding time for new agents
- Faster context switches between work items
- Improved knowledge transfer across conversations

Begin by reading PROJECT_CONTEXT.md and the current branch's changelog to understand the work context, then generate an appropriate summary based on the requested type and audience.