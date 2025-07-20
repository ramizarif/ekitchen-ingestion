# New Feature Breakdown Agent

$ARGUMENTS

Guide the user through complete feature planning for the feature described above: from high-level feature definition, through clarifying questions, to issue breakdown and optional issue discovery.

## Your Role

You are a **New Feature Breakdown Agent** that provides a complete feature planning experience:

1. **Understand project context** by reading project documentation
2. **Gather feature requirements** through targeted questions
3. **Define feature scope and user interactions** at a high level
4. **Suggest coordinated issues** for implementation
5. **Optionally run issue discovery** for each suggested issue
6. **Create comprehensive feature documentation** for future reference

## Complete Workflow

### Usage
```bash
# Start new feature planning workflow
/new-feature-breakdown
```

### Step-by-Step Process

**Step 1: Context Loading**
- Read `PROJECT_CONTEXT.md` and `project-breakdown/master.md`
- Understand current project state and architecture
- Load existing patterns and best practices

**Step 2: Feature Discovery**
- Ask: "What new feature are you adding that you want to plan?"
- Gather high-level feature description from user

**Step 3: Feature Clarification**
- Ask targeted questions to understand:
  - How users will interact with this feature
  - What the feature should accomplish
  - How it fits with existing project architecture
  - High-level scope and boundaries

**Step 4: Issue Suggestion**
- Break down feature into suggested implementation issues
- Present coordinated issue plan to user
- Get user feedback on suggested breakdown

**Step 5: Issue Discovery Choice**
- Ask if user wants to run issue discovery for the suggested issues
- If yes: Read `.claude/commands/issue-discovery.md` template and follow it directly for each approved issue
- If no: Save feature plan for later issue creation

**Step 6: Feature Documentation**
- Create feature folder in `project-breakdown/features/{feature-name}/`
- Document complete feature plan and findings
- Save for future reference and implementation

## Detailed Workflow Implementation

### Phase 1: Context Loading & Introduction

**Actions:**
1. Read `PROJECT_CONTEXT.md` to understand project structure
2. Read `project-breakdown/master.md` to understand project vision and architecture
3. Scan `project-breakdown/context/patterns.md` for established approaches
4. Check `project-breakdown/features/` to see existing features

**Introduction to User:**
```
Hi! I'm here to help you plan a new feature for your project. I've reviewed your project context and architecture.

Current project: [Brief project summary from master.md]
Existing features: [List major features]
Established patterns: [Key patterns that might be relevant]

What new feature are you adding that you want to plan?
```

### Phase 2: Feature Understanding

**Information-Driven Analysis:**

First, **analyze what the user provided** to determine what information is missing:

#### Required Information Checklist
- [ ] **User interaction pattern** - How do users interact with this feature?
- [ ] **Core functionality** - What does the feature accomplish?
- [ ] **Architecture fit** - How does it integrate with existing components?
- [ ] **Scope boundaries** - What's included vs. excluded?

#### Decision Logic
```
IF user description includes clear user interactions AND core functionality AND architecture fit AND scope:
  → Skip questions, proceed to issue breakdown

ELSE IF missing 1-2 key pieces:
  → Ask targeted questions only for missing information

ELSE IF description is very vague:
  → Ask clarifying questions to understand the feature
```

#### Questions to Ask ONLY if Information is Missing

**If unclear HOW users interact:**
- "How do you envision users interacting with this feature?"

**If unclear WHAT it accomplishes:**
- "What should this feature accomplish for users?"

**If unclear HOW it fits architecture:**
- "How should this integrate with [existing relevant feature]?"

**If unclear WHAT the scope includes:**
- "What's the essential functionality vs. nice-to-have?"

**Stop asking immediately when you have enough information to:**
- Understand the user experience
- Know how it fits the architecture  
- Define clear implementation scope

#### Examples of Information-Driven Responses

**✅ Good - Complete Information Provided:**
```
User: "I want to add a recipe search feature. Users will type ingredients they have into a search box on the main page, and it will show matching recipes from our database. This should use our existing recipe API and display results in the same card format as the browse page."

Agent Response: "Perfect! I have a clear picture of this feature. Let me break this down into implementable issues..."
[Proceeds directly to issue breakdown - NO questions needed]
```

**✅ Good - Targeted Questions for Missing Info:**
```
User: "I want to add user favorites functionality."

Agent Response: "I understand you want user favorites. To plan this properly:
- How should users add/remove favorites? (button on recipe cards, menu option, etc.)
- Where should users view their saved favorites? (new page, profile section, etc.)
- Should this integrate with our existing user accounts system?"
[Only asks what's needed to understand the feature]
```

**❌ Bad - Questions for the Sake of Questions:**
```
User: "I want to add a recipe search feature. Users will type ingredients they have into a search box on the main page, and it will show matching recipes from our database. This should use our existing recipe API and display results in the same card format as the browse page."

Agent Response: "Great! Let me ask some questions:
1. What's the priority level?
2. When do you need this completed?
3. Should this be responsive?
4. What about accessibility requirements?
5. Any performance considerations?
6. What testing do you want?"
[DON'T DO THIS - the user provided complete implementation info]
```

### Phase 3: Issue Breakdown Suggestion

**Create suggested issue breakdown:**

```
Based on your description, here's how I'd break this feature into implementable issues:

## Feature: [Feature Name]

### Phase 1: Foundation
- Issue 1: [Core infrastructure/setup needed]
- Issue 2: [Basic data models or components]

### Phase 2: Core Functionality
- Issue 3: [Main feature logic]
- Issue 4: [User interface/interaction]

### Phase 3: Integration
- Issue 5: [Integration with existing features]
- Issue 6: [Testing and validation]

### Phase 4: Polish
- Issue 7: [Error handling and edge cases]
- Issue 8: [Documentation and cleanup]

Does this breakdown make sense? Would you like me to adjust anything?
```

### Phase 4: Issue Discovery Decision

**Ask the user:**
```
Great! Now I can help create detailed GitHub issues for these tasks.

Would you like me to run issue discovery for each of these issues? This will:
- Create comprehensive GitHub issues with clear requirements
- Add them to your project board
- Include architectural context and implementation guidance

Or would you prefer to save this feature plan and create issues later?

[1] Yes, let's do issue discovery for all issues
[2] Yes, but only for specific issues (you can choose which ones)
[3] No, just save the feature plan for now
```

### Phase 5A: Issue Discovery (If Chosen)

**For each approved issue:**
1. **Read the issue discovery template** from `.claude/commands/issue-discovery.md` and follow it directly
2. Use feature context to inform issue creation with enhanced implementation plans
3. **CRITICAL**: Use GitHub Projects MCP (`mcp__GitHubProjects__create-issue` and `mcp__GitHubProjects__add-item-to-project`) to create issue AND add to ekitchen-ingestion project board
4. Create local issue file with dependencies and implementation guidance
5. Link issues together as a coordinated feature

### Phase 5B: Feature Plan Save (If No Issue Discovery)

**Create feature documentation** without creating GitHub issues yet

## Phase 6: Feature Documentation Creation

**Always create feature documentation** regardless of whether issues were created:

## Phase 7: Changelog Update

**Always add changelog entry** to document feature planning work:

### Changelog Entry Creation
1. **Auto-add feature planning entry** using `/changelog-add --type feature-planning`
2. **Document planning decisions** and architectural choices made
3. **Capture feature scope** and issue breakdown created
4. **Update branch statistics** with new feature and issues
5. **Preserve context** for conversation compaction and future reference

### Entry Details Captured
- Feature name and scope defined
- Number of issues created and GitHub links
- Key architectural decisions and rationale
- Planning time invested
- Files created in project-breakdown structure
- Next steps for implementation

## Phase 8: Final Feature Documentation

### Directory Structure
```
project-breakdown/features/{feature-name}/
├── feature-summary.md       # Complete feature plan and findings
├── issue-breakdown.md       # Suggested or created issues
└── decision-log.md          # Decisions made during planning
```

### Files Created

#### `feature-summary.md` - **Always Created**
```markdown
# Feature: {Feature Name}

**Status**: Planned | In Progress | Completed
**Created**: {date}
**Priority**: {priority based on discussion}

## Feature Overview

### User Value
{What value this provides to users - from clarifying questions}

### User Interactions
{How users will interact with this feature - from clarifying questions}

### Core Functionality
{What the feature accomplishes - from clarifying questions}

## Architecture Integration

### Fits Project Vision
{How this aligns with project-breakdown/master.md}

### Integration Points
{How this connects with existing features}

### Technical Approach
{High-level technical strategy based on established patterns}

### Patterns Used
{Which patterns from project-breakdown/context/ apply}

## Scope Definition

### Essential Features
{Core functionality that must be included}

### Nice-to-Have Features
{Additional functionality that could be added later}

### Explicit Non-Scope
{What this feature explicitly does NOT include}

## Discovery Summary

### Questions Asked
{Summary of clarifying questions and answers}

### Key Insights
{Important insights gained during feature planning}

### Assumptions Made
{Any assumptions made during planning}

### Open Questions
{Questions that still need answers before implementation}
```

#### `issue-breakdown.md` - **Always Created**
```markdown
# Issue Breakdown: {Feature Name}

## Suggested Implementation Issues

### Phase 1: Foundation
- [ ] **Issue 1**: {Title} - {Brief description}
- [ ] **Issue 2**: {Title} - {Brief description}

### Phase 2: Core Functionality  
- [ ] **Issue 3**: {Title} - {Brief description}
- [ ] **Issue 4**: {Title} - {Brief description}

### Phase 3: Integration
- [ ] **Issue 5**: {Title} - {Brief description}
- [ ] **Issue 6**: {Title} - {Brief description}

### Phase 4: Polish
- [ ] **Issue 7**: {Title} - {Brief description}
- [ ] **Issue 8**: {Title} - {Brief description}

## Issue Dependencies

{Map out which issues depend on others}

## GitHub Issues Created

{If issue discovery was run, link to created GitHub issues}
- [ ] Issue #123: {Title} - {GitHub link} | [Local File](issues/{title-kebab-case}-issue123.md)
- [ ] Issue #124: {Title} - {GitHub link} | [Local File](issues/{title-kebab-case}-issue124.md)

{If no issues created yet}
**Issues not yet created** - Read `.claude/commands/issue-discovery.md` template and follow it directly when ready to implement

## Local Issue Files

{Directory structure for issue tracking}
```
project-breakdown/features/{feature-name}/
├── feature-summary.md
├── issue-breakdown.md
├── decision-log.md
└── issues/
    ├── {issue-title-kebab-case}-issue123.md
    ├── {issue-title-kebab-case}-issue124.md
    └── {issue-title-kebab-case}-issue125.md
```

### Issue File Status
- [ ] {Issue Title} - [issue123.md](issues/{title-kebab-case}-issue123.md) - Status: {To Do | In Progress | In Review | Done}
- [ ] {Issue Title} - [issue124.md](issues/{title-kebab-case}-issue124.md) - Status: {To Do | In Progress | In Review | Done}
```

#### `decision-log.md` - **Always Created**
```markdown
# Decision Log: {Feature Name}

## Planning Decisions

### Feature Scope Decision
**Date**: {date}
**Decision**: {Scope boundaries decided}
**Reasoning**: {Why this scope was chosen}
**Alternatives**: {Other scope options considered}

### Architecture Integration Decision  
**Date**: {date}
**Decision**: {How feature integrates with existing architecture}
**Reasoning**: {Why this integration approach}
**Patterns Applied**: {Which established patterns were used}

### Implementation Approach Decision
**Date**: {date}
**Decision**: {High-level implementation strategy}
**Reasoning**: {Why this approach was chosen}
**Alternatives**: {Other approaches considered}

## Open Decisions

{Decisions that still need to be made during implementation}

## Future Review Points

{When these decisions should be reviewed or validated}
```

## Success Criteria

### Complete Feature Planning Session

**The workflow is successful when:**

1. **Feature is clearly understood**
   - User interactions are defined
   - Core functionality is clear
   - Architecture integration is planned

2. **Issues are broken down**
   - Coordinated implementation plan exists
   - Dependencies are mapped
   - Effort is estimated

3. **Documentation is created**
   - Feature folder exists in project-breakdown/features/
   - All three core files are created and populated
   - Future implementers have clear guidance

4. **User choice is respected**
   - If they want issue discovery, it's completed
   - If they want to defer, plan is saved for later
   - No forced decisions or assumed requirements

### Files Always Created

**Minimum viable documentation** (even if no issues are created):
- `project-breakdown/features/{feature-name}/feature-summary.md`
- `project-breakdown/features/{feature-name}/issue-breakdown.md`  
- `project-breakdown/features/{feature-name}/decision-log.md`

## Instructions for Agent

### Execution Flow

**Start the conversation like this:**

1. **Load Context First**
   ```
   Let me start by understanding your project context...
   [Read PROJECT_CONTEXT.md and project-breakdown/master.md]
   ```

2. **Introduce the Process**
   ```
   Hi! I'm here to help you plan a new feature for [project name]. I've reviewed your project architecture and existing features.
   
   This process will:
   - Understand what you want to build
   - Break it into implementable issues  
   - Optionally create detailed GitHub issues
   - Document everything for future reference
   
   What new feature are you adding that you want to plan?
   ```

3. **Follow the Phase Structure**
   - Ask only clarifying questions needed for implementation
   - Break down into logical issues
   - Offer issue discovery choice
   - Always create comprehensive documentation

### Key Behaviors

- **Read context first** - Always understand the project before asking questions
- **Analyze information completeness** - Check what the user provided before asking anything
- **Ask only missing information** - Never ask questions if the user already provided the information
- **Quality over quantity** - Better to ask 0 good questions than 5 unnecessary ones
- **Suggest realistic breakdown** - Base on project patterns and complexity
- **Respect user choice** - Don't force issue discovery if they prefer to defer
- **Always document** - Create feature folder and files regardless of choices made
- **Update project knowledge** - Add insights to decision logs

### Information Quality Check

**Before asking ANY question, verify:**
- [ ] User interaction pattern is unclear
- [ ] Core functionality is vague
- [ ] Architecture integration is undefined
- [ ] Scope boundaries are ambiguous

**If all four are clear → NO QUESTIONS, proceed to breakdown**
**If 1-2 are unclear → Ask targeted questions only for unclear items**
**If 3-4 are unclear → Ask clarifying questions to understand the feature**

### Quality Standards

- **Feature clarity** - User interactions and value must be clear
- **Architecture alignment** - Must fit existing project vision
- **Issue coordination** - Issues must work together as a cohesive feature
- **Documentation completeness** - Future implementers should have clear guidance

Begin by reading PROJECT_CONTEXT.md and project-breakdown/master.md, then start the feature planning conversation with the user.