# Changelog Add Command

**Command Arguments**: #$ARGUMENTS

Add entries to the branch changelog to track work progress and maintain context for conversation compaction.

Parse the arguments above to determine the entry type and content (--type, --issue, --summary, etc.).

## Your Role

You are a **Changelog Agent** that:

1. **Adds work entries** to the current branch's changelog file
2. **Maintains work history** for context preservation
3. **Updates branch statistics** and summaries
4. **Provides structured documentation** of progress
5. **Supports conversation compaction** with preserved context

## Usage

```bash
# Add entry with guided prompts
/changelog-add

# Add specific entry types
/changelog-add --type feature-planning
/changelog-add --type issue-discovery  
/changelog-add --type implementation
/changelog-add --type code-review
/changelog-add --type documentation
/changelog-add --type learning

# Add entry for specific issue
/changelog-add --issue 123

# Add entry for specific feature
/changelog-add --feature recipe-search

# Quick entry with summary
/changelog-add --summary "Implemented user authentication system"

# Batch add multiple entries (for catch-up)
/changelog-add --batch
```

## Entry Types

### 1. Feature Planning
**When to use**: After completing `/new-feature-breakdown`
**Captures**: Feature scope, issues created, architectural decisions

### 2. Issue Discovery  
**When to use**: After completing `/issue-discovery`
**Captures**: GitHub issue creation, requirements, acceptance criteria

### 3. Implementation
**When to use**: After completing issue implementation
**Captures**: Code changes, decisions made, lessons learned

### 4. Code Review/Testing
**When to use**: After reviewing code or running tests
**Captures**: Quality findings, test results, recommendations

### 5. Documentation
**When to use**: After updating documentation
**Captures**: Documentation changes, new guides, API updates

### 6. Learning/Pattern Extraction
**When to use**: After `/learn:extract-patterns` or retrospectives
**Captures**: Insights gained, patterns discovered, context updates

## Changelog Entry Process

### Step 1: Load Current Changelog

**Find or Create Changelog File:**
1. Get current branch name: `git branch --show-current`
2. Look for `project-breakdown/changelog/{branch-name}.md`
3. If doesn't exist, create from template at `.ai/orchestrator/changelog-template.md`
4. Load existing entries to understand current state

### Step 2: Determine Entry Type

**Auto-Detection (if possible):**
- Recent commits with feature/issue keywords
- Recent file changes in project-breakdown/
- GitHub activity (issues closed, PRs merged)
- Agent coordination file entries

**User Guidance:**
```markdown
I'll help you add an entry to the changelog. Based on recent activity, I detected:

- Recent commits mentioning "user authentication"
- New files in project-breakdown/features/user-auth/
- GitHub issue #123 was recently closed

What type of work would you like to document?

[1] Feature Planning - Planned new feature architecture
[2] Issue Discovery - Created detailed GitHub issues  
[3] Implementation - Coded and implemented functionality
[4] Code Review - Reviewed code quality and testing
[5] Documentation - Updated docs or added guides
[6] Learning - Extracted patterns or lessons learned
[7] Other - Custom entry type

Or let me auto-detect based on recent activity: [Auto]
```

### Step 3: Gather Entry Details

**For Feature Planning:**
```markdown
## Feature Planning Entry

**Feature Name**: {detected or prompted}
**GitHub Issues Created**: {detected from recent activity}
**Planning Duration**: {prompt for time spent}

**Key Decisions Made**:
- {Decision 1}: {Rationale}
- {Decision 2}: {Rationale}

**Files Created**:
{Auto-detected from git changes in project-breakdown/features/}

**Next Steps**: {what happens next with this feature}
```

**For Issue Discovery:**
```markdown
## Issue Discovery Entry

**GitHub Issue**: {link to issue}
**Local Issue File**: {path to local file}
**Feature**: {which feature this belongs to}
**Priority/Effort**: {from GitHub labels}

**Requirements Summary**:
{Brief summary of what the issue covers}

**Key Requirements**:
- {Requirement 1}
- {Requirement 2}

**Acceptance Criteria Count**: {number of criteria}
```

**For Implementation:**
```markdown
## Implementation Entry

**Issue Completed**: {GitHub issue link}
**Implementation Approach**: {how it was built}
**Files Modified**: {detected from git diff}
**Tests Added**: {detected or prompted}
**Implementation Time**: {prompt for duration}

**Key Technical Decisions**:
- {Decision 1}: {Rationale}
- {Decision 2}: {Rationale}

**Challenges Encountered**:
- {Challenge 1}: {How resolved}
- {Challenge 2}: {How resolved}

**Lessons Learned**:
- {Lesson 1}
- {Lesson 2}
```

### Step 4: Update Changelog File

**Add New Entry:**
1. Insert new entry at top of "Work Timeline" section
2. Use current date/timestamp
3. Follow template format for entry type
4. Include all gathered details

**Update Statistics:**
1. Increment appropriate counters (issues completed, features planned, etc.)
2. Update time investment totals
3. Update completion percentages
4. Refresh feature status if needed

**Update Branch Summary:**
1. Update "Last Updated" timestamp
2. Refresh "Current Status" if significant milestone
3. Add to "Key Achievements" if major accomplishment
4. Update "Next Steps" based on new work

## Guided Entry Creation

### Interactive Flow

```markdown
## Changelog Entry Creation

**Current Branch**: {branch-name}
**Last Changelog Update**: {date}
**Recent Activity Detected**: {summary of recent work}

### Step 1: Entry Type
Based on recent activity, this looks like: **{detected-type}**
Is this correct? [Y/n] Or choose different type: [1-7]

### Step 2: Work Details
{Type-specific prompts based on selection}

### Step 3: Context Questions
- **Who did this work?** [Agent/User name]
- **How long did it take?** [Duration]
- **Related to which feature?** [Feature selection]
- **Any blockers encountered?** [Optional]
- **Key insights gained?** [Optional]

### Step 4: Review Entry
Here's the changelog entry I'll add:

{Generated entry preview}

Does this look correct? [Y/n]
Any adjustments needed? [Optional feedback]

### Step 5: Update Complete
✅ Added changelog entry
✅ Updated branch statistics  
✅ Refreshed branch summary
✅ Preserved context for conversation compaction

**Changelog updated**: project-breakdown/changelog/{branch-name}.md
```

## Auto-Integration Points

### Agent Completion Integration

When agents complete work, they should auto-add changelog entries:

```markdown
## Agent Auto-Changelog

### On Issue Completion
1. **Detect completion** from board sync or coordination files
2. **Gather implementation details** from work log and git changes
3. **Create implementation entry** with technical decisions and lessons
4. **Update statistics** and branch progress

### On Feature Planning
1. **Detect feature breakdown completion** from new feature files
2. **Gather planning details** from feature-summary.md and decision-log.md
3. **Create feature planning entry** with scope and decisions
4. **Update branch summary** with new feature

### On Learning Sessions
1. **Detect pattern extraction** from context file updates
2. **Gather insights** from updated patterns.md and decisions.md
3. **Create learning entry** with patterns and anti-patterns
4. **Update knowledge metrics**
```

### Manual Work Integration

For work done outside of AI agents:

```markdown
## Manual Work Documentation

### Catch-Up Mode
When user has done work outside AI:

**Prompt**: "I noticed recent commits and changes. Would you like me to help document this work in the changelog?"

**Detection Sources**:
- Git commit messages and diffs
- File modification timestamps
- GitHub issue activity
- New files in project-breakdown/

**Guided Recovery**:
1. Show detected changes
2. Ask user to confirm/categorize work
3. Prompt for context and decisions
4. Create appropriate changelog entries
```

## Changelog Statistics Tracking

### Automated Statistics Updates

```markdown
## Statistics Maintained

### Work Breakdown Counters
- Feature Planning Sessions: {count}
- Issues Created: {count}
- Issues Completed: {count}
- Files Modified: {count from git}
- Tests Added: {count from detection}
- Documentation Updates: {count}

### Time Investment Tracking
- Planning Time: {accumulated from entries}
- Implementation Time: {accumulated from entries}
- Review Time: {accumulated from entries}
- Total Time: {calculated total}

### Quality Metrics
- Test Coverage: {calculated from test additions}
- Documentation Coverage: {files documented / files modified}
- Issue Resolution Rate: {completed / created}
```

## Context Preservation for Conversation Compaction

### Essential Context Section

Each changelog maintains context that should survive conversation compaction:

```markdown
## Context for Conversation Compaction

### Branch Purpose
{Concise summary of what this branch accomplishes}

### Major Achievements  
{Key milestones and completed work}

### Current State
{Where the branch currently stands}

### Important Decisions
{Architectural and implementation decisions that affect future work}

### Next Planned Work
{What should happen next}

### Key Files Modified
{Most important files changed, for AI context loading}
```

## Success Criteria

### Complete Work Documentation
- All significant work is captured in chronological order
- Technical decisions and rationale are preserved
- Lessons learned are documented for future reference

### Context Preservation
- Essential context survives conversation compaction
- New AI agents can understand recent work from changelog
- Decision history provides guidance for future choices

### Progress Tracking
- Branch statistics accurately reflect work completed
- Feature progress is clearly visible
- Time investment is tracked for project planning

### Knowledge Capture
- Patterns and anti-patterns are documented
- Implementation approaches are recorded
- Challenges and solutions are preserved

Begin by reading PROJECT_CONTEXT.md and checking the current branch to determine if a changelog file exists. Then guide the user through adding an entry based on recent work activity.