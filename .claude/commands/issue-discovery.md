# Issue Discovery Process

Launch an interactive issue discovery session to create comprehensive GitHub issues.

## Process Overview

You are now conducting an issue discovery session to create a well-defined GitHub issue. You will guide the user through a structured questionnaire to gather all necessary information for creating a comprehensive issue that sub-agents can implement without guesswork.

## Instructions

### Step 1: Load Questions and Template
1. **Check existing features**: `ls project-breakdown/features/` to show available features
2. Read the questionnaire from `.ai/orchestrator/issue-discovery-questions.md`
3. Load the issue template from `.ai/orchestrator/issue-creation-template.md`
4. Prepare to conduct a thorough discovery session

### Step 2: Conduct Discovery Session
Follow the structured phases from the questionnaire:

1. **Task Overview** - Understand the basic scope and nature
2. **Technical Context** - Identify affected components and technologies
3. **Functional Requirements** - Define what needs to be built
4. **Technical Requirements** - Establish constraints and specifications
5. **Quality and Testing** - Define testing approach and acceptance criteria
6. **Implementation Details** - Gather implementation preferences
7. **Dependencies and Sequencing** - Understand task relationships
8. **Documentation and Communication** - Plan documentation needs
9. **Definition of Done** - Establish completion criteria

### Step 3: Interactive Guidelines
- **Let user describe first** - Start with their vision, not a questionnaire
- **Analyze completeness before asking** - Check if you can implement based on their description
- **Ask only implementation-critical questions** - Not process questions
- **One question at a time** - Don't overwhelm with multiple questions
- **Stop immediately when implementation is clear** - Don't over-discover
- **Respect user boundaries** - Stop when they say "enough" or "assume the rest"

### Information Completeness Check
**Before asking ANY question, verify the user's description covers:**
- [ ] What functionality to implement
- [ ] How it should behave/work
- [ ] Where it fits in the codebase  
- [ ] How to know it's successful

**If complete → Create issue immediately, no questions**
**If 1-2 gaps → Ask targeted questions only for gaps**
**If very incomplete → Ask clarifying questions**

### Step 4: Create Issue Structure with Dependencies & Implementation Plan
Using the responses, create a comprehensive issue following the enhanced template structure:

**Feature Placement:**
1. **If existing feature**: Place issue file in `project-breakdown/features/{feature-name}/issues/`
2. **If new feature**: Create feature directory structure first:
   - `project-breakdown/features/{feature-name}/`
   - `project-breakdown/features/{feature-name}/issues/`
   - `project-breakdown/features/{feature-name}/feature-summary.md`
   - `project-breakdown/features/{feature-name}/progress.md`

**Issue File Structure:**
- Clear title with type and priority
- Detailed overview and requirements
- **Implementation Plan** - Step-by-step technical approach
- **Dependencies Analysis** - Which issues must be completed first
- **Technical specifications**

### Step 5: Create GitHub Issue
```bash
# Create the GitHub issue to get URL for linking
# Use: /create-issue --title "{title}" --body "{issue content}"
# Capture the issue number and URL returned
```

### Step 6: Update Feature Files
After creating the issue file and GitHub issue, update the feature tracking files:

**1. Update issue-breakdown.md**
```bash
# Add new issue to: project-breakdown/features/{feature-name}/issue-breakdown.md
# Add to appropriate sprint/priority section:
- [ ] **Issue #{number}**: [Title](GitHub-URL) - Status: To Do

# Update issue count totals
```

**2. Analyze Dependencies**
```bash
# Check existing issues in feature for dependencies:
# Read: project-breakdown/features/{feature-name}/issues/*.md
# Look for potential dependencies or blockers
# Update both new issue and existing issues if dependencies found
```

**3. Update progress.md**
```bash
# Add to: project-breakdown/features/{feature-name}/progress.md
# Update:
- Total issue count
- Current sprint backlog
- Ready vs blocked issue counts
- Overall completion percentage

# Example addition:
## Issue #{number}: {Title}
- **Status**: To Do
- **Priority**: {High/Medium/Low}
- **Effort**: {Small/Medium/Large}
- **Dependencies**: {List or None}
- **Assigned**: Unassigned
- **ETA**: TBD
```

**4. Update feature-summary.md (if scope changes)**
```bash
# Only if issue significantly changes feature scope:
# Update: project-breakdown/features/{feature-name}/feature-summary.md
# Add to scope or modify objectives if needed
```

### Step 7: Final Validation
```bash
# Verify all files are consistent:
1. Issue file created in correct feature directory
2. GitHub issue created and linked
3. issue-breakdown.md updated with new issue
4. progress.md reflects new total and status
5. Dependencies analyzed and documented
6. Feature scope updated if needed

# Commit all changes:
git add project-breakdown/features/{feature-name}/
git commit -m "feat: add issue #{number} - {title}"
```
- Acceptance criteria with checkboxes
- Testing requirements
- **Autonomous Engineering Guidance** - Context for engineering agents
- Documentation needs
- Definition of done

### Step 5: Review and Confirm
- Present the complete issue draft to the user
- Highlight key requirements and acceptance criteria
- Ask for confirmation or adjustments
- Ensure all details are accurate and complete

### Step 6: Create GitHub Issue & Local Issue File
**GitHub Issue Creation:**
- Use `mcp__GitHubProjects__create-issue` to create the issue in ekitchen-ingestion repo
- Apply appropriate labels (type, priority, component, effort)
- **CRITICAL**: Use `mcp__GitHubProjects__add-item-to-project` to add to the ekitchen-ingestion project board
- Place in the appropriate column (To Do/Backlog)
- Verify the issue appears on both the repo and the project board

**Local Issue File Creation:**
1. Create `issues/` directory in feature folder if it doesn't exist
2. Create issue file: `project-breakdown/features/{feature-name}/issues/{issue-title-kebab-case}-issue{number}.md`
3. Use issue file template from `.ai/orchestrator/issue-file-template.md`
4. Include GitHub issue link, status tracking, and feature context
5. Set initial status to "To Do" and board status to current GitHub column

**Issue Linking:**
1. Update feature's `issue-breakdown.md` with GitHub issue link AND local file link
2. Add issue to feature's issue tracking section with status
3. Ensure bidirectional linking between GitHub and local files
4. Update feature progress tracking with new issue

**Changelog Entry:**
1. **Auto-add issue discovery entry** using `/changelog-add --type issue-discovery`
2. **Document requirements captured** and acceptance criteria
3. **Link to GitHub issue and local file** created
4. **Update branch statistics** with new issue
5. **Preserve context** for future implementation reference

**Directory Structure Created:**
```
project-breakdown/features/{feature-name}/
├── feature-summary.md
├── issue-breakdown.md  
├── decision-log.md
└── issues/              ← Created if doesn't exist
    └── {issue-title-kebab-case}-issue{number}.md  ← New issue file
```

## Success Criteria

The resulting issue should be:
- **Complete** - All necessary information provided
- **Clear** - No ambiguity in requirements
- **Actionable** - Sub-agent can implement without questions
- **Testable** - Clear acceptance criteria and testing requirements
- **Documented** - Includes documentation and communication needs

## Example Flow

```
Master Agent: Let's create a comprehensive issue for your task. I'll guide you through a series of questions to ensure we capture all necessary details.

First, what is the main task or feature you want to implement? Please provide a brief, one-sentence description.

User: [Response]

Master Agent: Thank you. Now, what type of task is this? Is it:
- New feature implementation
- Bug fix
- Code refactoring
- Documentation update
- Performance optimization
- Testing improvement
- Security enhancement
- Configuration change
- Other

[Continue through all relevant questions...]

Master Agent: Based on your responses, I've created a comprehensive issue. Here's the complete issue I'll create:

[Show formatted issue]

Does this accurately capture your requirements? Any adjustments needed?

User: [Confirmation or adjustments]

Master Agent: Perfect! I'm now creating the GitHub issue and adding it to your project board...

Issue created successfully: #[number]
Added to project board in "To Do" column
Labels applied: [list of labels]
Ready for sub-agent assignment!
```

## Important Notes

- **Implementation-focused only** - Ask questions that affect how to build it, not process questions
- **Don't assume requirements** - If they didn't mention testing/docs/etc, don't add them
- **Follow user lead** - Let them define scope, don't expand it
- **Stop when ready** - Once you can implement their vision, stop asking
- **Confirm before creating** - Always show the final issue to the user for approval

Begin by reading PROJECT_CONTEXT.md and project-breakdown/master.md to understand the project context. Then start the discovery session by asking the user to describe what they want to implement, asking only clarifying questions needed for implementation. Add any issues created to the ekitchen-ingestion board using the github MCP. 