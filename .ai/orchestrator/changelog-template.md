# Branch Changelog Template

Template for tracking all work done on a specific branch to provide context for conversation compaction and recent change summaries.

## Changelog File Format

### File Location
`project-breakdown/changelog/{branch-name}.md`

Examples:
- `project-breakdown/changelog/development.md`
- `project-breakdown/changelog/feature-user-auth.md`
- `project-breakdown/changelog/hotfix-database-connection.md`

### Template Structure

```markdown
# Changelog: {Branch Name}

**Branch**: {branch-name}
**Created**: {branch-creation-date}
**Last Updated**: {last-update-timestamp}
**Status**: {Active | Merged | Abandoned}

## Branch Summary

### Purpose
{High-level description of what this branch is for}

### Key Achievements
- {Major milestone 1}
- {Major milestone 2}
- {Major milestone 3}

### Current Status
{Where the branch currently stands}

## Work Timeline

### {Date} - Feature Planning
**Type**: Feature Breakdown
**Agent/User**: {who did the work}
**Summary**: {brief description}

**Details**:
- Feature: [{feature-name}](../features/{feature-name}/feature-summary.md)
- Issues Created: {number} issues
- GitHub Issues: #{issue1}, #{issue2}, #{issue3}
- Planning Time: {time spent}

**Files Created/Modified**:
- `project-breakdown/features/{feature-name}/feature-summary.md`
- `project-breakdown/features/{feature-name}/issue-breakdown.md`
- `project-breakdown/features/{feature-name}/decision-log.md`

**Key Decisions**:
- {Decision 1 and rationale}
- {Decision 2 and rationale}

---

### {Date} - Issue Discovery
**Type**: Issue Creation
**Agent/User**: {who did the work}
**Summary**: {brief description}

**Details**:
- GitHub Issue: [#{issue-number}: {title}]({github-url})
- Local File: [{title-kebab-case}-issue{number}.md](../features/{feature}/issues/{file-name})
- Priority: {High | Medium | Low}
- Estimated Effort: {Small | Medium | Large}

**Requirements Captured**:
- {Requirement 1}
- {Requirement 2}
- {Requirement 3}

**Acceptance Criteria**:
- {Criteria 1}
- {Criteria 2}

---

### {Date} - Implementation Work
**Type**: Issue Implementation
**Agent/User**: {who did the work}
**Summary**: {brief description}

**Details**:
- Issue: [#{issue-number}: {title}]({github-url})
- Status: {To Do → In Progress → In Review → Done}
- Implementation Time: {time spent}
- Files Modified: {number} files
- Tests Added: {Yes/No}

**Implementation Approach**:
{Brief description of how it was implemented}

**Files Changed**:
- `{file-path}` - {what was changed}
- `{file-path}` - {what was changed}

**Key Implementation Decisions**:
- {Decision 1 and rationale}
- {Decision 2 and rationale}

**Lessons Learned**:
- {What worked well}
- {What could be improved}
- {Patterns discovered}

---

### {Date} - Code Review/Testing
**Type**: Quality Assurance
**Agent/User**: {who did the work}
**Summary**: {brief description}

**Details**:
- Issues Reviewed: #{issue1}, #{issue2}
- Tests Status: {All Passing | Some Failing | Not Run}
- Code Quality: {Good | Needs Improvement | Excellent}
- Performance Impact: {None | Positive | Negative | Unknown}

**Review Findings**:
- {Finding 1}
- {Finding 2}
- {Recommendations}

---

### {Date} - Documentation Update
**Type**: Documentation
**Agent/User**: {who did the work}
**Summary**: {brief description}

**Details**:
- Documentation Type: {API | User Guide | Architecture | Comments}
- Files Updated: {number} files
- New Documentation: {Yes/No}

**Documentation Changes**:
- `{file-path}` - {what was documented}
- `{file-path}` - {what was documented}

---

### {Date} - Learning/Pattern Extraction
**Type**: Knowledge Capture
**Agent/User**: {who did the work}
**Summary**: {brief description}

**Details**:
- Patterns Extracted: {number}
- Context Files Updated: {which files}
- Anti-patterns Identified: {number}

**Key Insights**:
- {Insight 1}
- {Insight 2}
- {Insight 3}

**Context Updates**:
- Updated `project-breakdown/context/patterns.md` with {what}
- Updated `project-breakdown/context/decisions.md` with {what}

---

## Branch Statistics

### Work Breakdown
- **Feature Planning Sessions**: {number}
- **Issues Created**: {number}
- **Issues Completed**: {number}
- **Files Modified**: {number}
- **Tests Added**: {number}
- **Documentation Updates**: {number}

### Time Investment
- **Planning Time**: {total hours/days}
- **Implementation Time**: {total hours/days}
- **Review/Testing Time**: {total hours/days}
- **Documentation Time**: {total hours/days}
- **Total Time**: {total hours/days}

### Quality Metrics
- **Tests Passing**: {percentage}
- **Code Review Score**: {rating}
- **Documentation Coverage**: {percentage}
- **Issue Resolution Rate**: {percentage}

## Features Developed

### [{Feature Name}](../features/{feature-name}/feature-summary.md)
**Status**: {Planned | In Progress | Completed}
**Issues**: {completed}/{total}
**Key Achievements**:
- {Achievement 1}
- {Achievement 2}

### [{Feature Name}](../features/{feature-name}/feature-summary.md)
**Status**: {Planned | In Progress | Completed}
**Issues**: {completed}/{total}
**Key Achievements**:
- {Achievement 1}
- {Achievement 2}

## Issues Completed

### Completed Issues
- [#{number}: {title}]({github-url}) - [{local-file}](../features/{feature}/issues/{file}) - {completion-date}
- [#{number}: {title}]({github-url}) - [{local-file}](../features/{feature}/issues/{file}) - {completion-date}

### In Progress Issues
- [#{number}: {title}]({github-url}) - [{local-file}](../features/{feature}/issues/{file}) - Started: {start-date}

### Planned Issues
- [#{number}: {title}]({github-url}) - [{local-file}](../features/{feature}/issues/{file}) - Created: {creation-date}

## Technical Debt & Improvements

### Technical Debt Added
- {Description of debt and rationale}
- {Description of debt and rationale}

### Technical Debt Resolved
- {Description of debt resolved}
- {Description of debt resolved}

### Performance Improvements
- {Improvement description and impact}
- {Improvement description and impact}

## Architectural Changes

### New Patterns Introduced
- **Pattern**: {pattern-name}
- **Usage**: {where it's used}
- **Rationale**: {why it was chosen}

### Architecture Decisions
- **Decision**: {decision-summary}
- **Rationale**: {reasoning}
- **Impact**: {effects on system}
- **Alternatives**: {what was considered}

## Knowledge Gained

### Successful Patterns
- {Pattern that worked well}
- {Pattern that worked well}

### Anti-patterns Discovered
- {Pattern that didn't work}
- {Pattern that didn't work}

### Best Practices Evolved
- {Practice that emerged}
- {Practice that emerged}

### Lessons for Future Work
- {Lesson learned}
- {Lesson learned}

## Branch Context for AI

### Key Files Modified
{List of most important files changed, for AI context loading}
- `{file-path}` - {purpose/importance}
- `{file-path}` - {purpose/importance}

### Important Decisions Made
{Decisions that future AI agents should be aware of}
- {Decision and context}
- {Decision and context}

### Current Architecture State
{Brief description of how the architecture has evolved}

### Next Steps
{What should happen next on this branch}
- {Next step 1}
- {Next step 2}

### Context for Conversation Compaction
{Information that should be preserved when conversations are compacted}

**Branch Purpose**: {concise summary}
**Major Achievements**: {key accomplishments}
**Current State**: {where things stand}
**Key Context**: {essential information for future work}
```

## Entry Types and Templates

### Feature Planning Entry
```markdown
### {Date} - Feature Planning
**Type**: Feature Breakdown
**Agent/User**: {name}
**Summary**: Planned {feature-name} with {number} issues

**Details**:
- Feature: [{feature-name}](../features/{feature-name}/feature-summary.md)
- Issues Created: {number} issues
- GitHub Issues: #{issue1}, #{issue2}, #{issue3}
- Planning Time: {duration}

**Key Decisions**:
- {Decision 1}
- {Decision 2}
```

### Issue Discovery Entry
```markdown
### {Date} - Issue Discovery
**Type**: Issue Creation
**Agent/User**: {name}
**Summary**: Created detailed issue for {task-description}

**Details**:
- GitHub Issue: [#{number}: {title}]({url})
- Local File: [{file-name}](../features/{feature}/issues/{file-name})
- Priority: {level}
- Estimated Effort: {size}

**Requirements**: {brief summary of requirements}
```

### Implementation Entry
```markdown
### {Date} - Implementation Work
**Type**: Issue Implementation
**Agent/User**: {name}
**Summary**: Implemented {feature/fix description}

**Details**:
- Issue: [#{number}: {title}]({url})
- Status: Done
- Files Modified: {count}
- Tests: {status}

**Key Changes**:
- {Change 1}
- {Change 2}

**Lessons Learned**: {insights}
```

### Learning Entry
```markdown
### {Date} - Learning/Pattern Extraction
**Type**: Knowledge Capture
**Agent/User**: {name}
**Summary**: Extracted {number} patterns from recent work

**Insights**:
- {Insight 1}
- {Insight 2}

**Context Updates**: Updated patterns.md and decisions.md
```

## Usage Guidelines

### When to Add Entries
- **Feature planning completion** - After `/new-feature-breakdown`
- **Issue creation** - After `/issue-discovery`
- **Issue completion** - When agent finishes implementation
- **Manual work completion** - When user completes work outside AI
- **Learning sessions** - After pattern extraction or retrospectives
- **Architecture changes** - When making significant structural changes
- **Major decisions** - When making choices that affect future work

### Entry Quality Standards
- **Concise but complete** - Capture essential info without verbosity
- **Context-rich** - Include rationale and decision-making context
- **Forward-looking** - Consider what future agents/users need to know
- **Linked** - Reference related files, issues, and features
- **Timestamped** - Include accurate dates and durations

### Maintenance
- **Regular updates** - Add entries as work progresses
- **Branch statistics** - Update statistics section periodically
- **Context preservation** - Ensure key context survives conversation compaction
- **Archive completed** - Move completed branch changelogs to archive when merged