# Board Sync Command

Synchronize GitHub project board status with local issue files bidirectionally.

## Your Role

You are a **Board Sync Agent** that maintains synchronization between:

1. **GitHub Project Board** - Issue status and column positions
2. **Local Issue Files** - Status tracking in feature directories  
3. **Project Context** - Overall feature and project status

## Usage

```bash
# Sync all issues between board and local files
/board-sync

# Sync specific issue by number
/board-sync --issue 123

# Sync all issues in a specific feature
/board-sync --feature recipe-search

# Force sync from GitHub to local (override local changes)
/board-sync --force-from-github

# Force sync from local to GitHub (override GitHub status)
/board-sync --force-to-github

# Dry run to see what would change
/board-sync --dry-run
```

## Sync Process

### Step 1: Load Current State

**GitHub Board State:**
1. Use `mcp__GitHubProjects__get-project-items` to get all issues from ekitchen-ingestion board
2. Get current column/status for each issue
3. Get issue details and metadata

**Local Issue State:**
1. Scan `project-breakdown/features/*/issues/*.md` for all issue files
2. Extract current local status from each file
3. Extract GitHub issue numbers and last sync dates

### Step 2: Detect Sync Conflicts

**Identify Issues Requiring Sync:**
- Issues with different status between GitHub board and local files
- Issues modified since last sync date
- Issues missing from either GitHub or local system

**Conflict Resolution Rules:**
- **Default**: Most recent change wins (based on timestamps)
- **--force-from-github**: GitHub board status overrides local
- **--force-to-github**: Local status overrides GitHub board
- **Manual conflicts**: Prompt user for resolution

### Step 3: Sync Operations

#### GitHub → Local Sync
```markdown
For each GitHub issue with newer status:

1. **Update Local Issue File**
   - Update status in front matter
   - Update "Board Status" section
   - Add sync entry to "Sync History"
   - Update "Last Synced" timestamp

2. **Add Work Log Entry**
   ```markdown
   **{date}**: Status synced from GitHub board - moved to {new-status}
   ```

3. **Update Feature References**
   - Update feature's issue-breakdown.md if needed
   - Reflect status changes in feature progress tracking
```

#### Local → GitHub Sync
```markdown
For each local issue with newer status:

1. **Update GitHub Board**
   - Use `mcp__GitHubProjects__update-project-item-field` to update status
   - Move issue to appropriate column based on local status mapping
   - Close issue if local status is "Done"

2. **Update Issue Labels**
   - Add/remove status-related labels
   - Update priority labels if changed locally

3. **Add Issue Comment**
   ```markdown
   Status updated from local development: {old-status} → {new-status}
   
   Synced from local issue file: project-breakdown/features/{feature}/issues/{issue-file}
   ```
```

### Step 4: Create Missing Issues

**Local Issues Missing from GitHub:**
- These should be rare, but handle gracefully
- Create GitHub issue using existing local issue content
- Add to project board in appropriate column

**GitHub Issues Missing Locally:**
- More common when issues are created directly on GitHub
- Create local issue file using GitHub issue content
- Place in appropriate feature directory (prompt for feature if unclear)

## Status Mapping

### Local Status → GitHub Board Column
- **To Do** → "To Do" or "Backlog" column
- **In Progress** → "In Progress" column
- **In Review** → "In Review" or "Review" column  
- **Done** → "Done" or "Completed" column

### GitHub Board Column → Local Status
- **To Do/Backlog** → "To Do"
- **In Progress** → "In Progress"
- **In Review/Review** → "In Review"
- **Done/Completed** → "Done"

## Detailed Sync Algorithm

### 1. Discovery Phase

```javascript
// Pseudo-code for sync logic
async function syncIssues() {
  // Get all GitHub issues
  const githubIssues = await getProjectIssues('ekitchen-ingestion');
  
  // Get all local issue files
  const localIssues = await scanLocalIssueFiles();
  
  // Create sync map
  const syncMap = createSyncMap(githubIssues, localIssues);
  
  return syncMap;
}

function createSyncMap(github, local) {
  const map = {
    needsGitHubUpdate: [],
    needsLocalUpdate: [],
    conflicts: [],
    missing: {
      github: [],  // Local issues not on GitHub
      local: []    // GitHub issues not in local files
    }
  };
  
  // Compare timestamps and statuses
  for (const issueNumber of allIssueNumbers) {
    const gh = github.find(i => i.number === issueNumber);
    const local = local.find(i => i.githubNumber === issueNumber);
    
    if (!gh && local) {
      map.missing.github.push(local);
    } else if (gh && !local) {
      map.missing.local.push(gh);
    } else if (gh && local) {
      const comparison = compareIssueStatus(gh, local);
      if (comparison.conflict) {
        map.conflicts.push({ github: gh, local: local });
      } else if (comparison.githubNewer) {
        map.needsLocalUpdate.push({ github: gh, local: local });
      } else if (comparison.localNewer) {
        map.needsGitHubUpdate.push({ github: gh, local: local });
      }
    }
  }
  
  return map;
}
```

### 2. Conflict Resolution

```markdown
## Sync Conflicts Detected

The following issues have conflicting status between GitHub and local files:

### Issue #123: Add User Authentication
**GitHub Status**: In Progress (updated 2 hours ago)
**Local Status**: Done (updated 1 hour ago)
**Conflict**: Local shows completion but GitHub still shows in progress

**Resolution Options**:
[1] Use local status (mark as Done on GitHub)
[2] Use GitHub status (revert local to In Progress)  
[3] Manual review - show me both versions

### Issue #124: Fix Database Connection
**GitHub Status**: Done (updated 3 hours ago)
**Local Status**: In Review (updated 30 minutes ago)
**Conflict**: GitHub shows complete but local shows still in review

**Resolution Options**:
[1] Use GitHub status (mark as Done locally)
[2] Use local status (revert GitHub to In Review)
[3] Manual review - show me both versions

Which resolution would you like for each issue?
```

### 3. Sync Execution

```markdown
## Sync Results

### GitHub → Local Updates (3 issues)
✅ Issue #125: Updated status To Do → In Progress
✅ Issue #126: Updated status In Progress → Done  
✅ Issue #127: Added sync entry and updated timestamps

### Local → GitHub Updates (2 issues)
✅ Issue #123: Moved to Done column, closed issue
✅ Issue #124: Moved to In Review column, added status comment

### Created Missing Issues (1 issue)
✅ Issue #128: Created GitHub issue from local file "implement-caching-issue128.md"

### Created Missing Local Files (1 issue)  
✅ Created local file for GitHub issue #129 in recipe-search feature

### Summary
- **Total Issues Synced**: 7
- **Conflicts Resolved**: 2
- **Missing Issues Created**: 2
- **Last Sync**: {timestamp}

All issues are now synchronized between GitHub board and local files.
```

## Integration with Agent Workflow

### Agent Task Completion

When an agent completes a task, it should:

1. **Update Local Issue Status**
   ```markdown
   ## Completion Process
   
   1. Update issue file status to "Done"
   2. Fill in completion checklist
   3. Add lessons learned section
   4. Update work log with completion notes
   ```

2. **Trigger Board Sync**
   ```markdown
   ## Auto-Sync on Completion
   
   After updating local status, automatically:
   - Run /board-sync --issue {number}
   - Move GitHub issue to Done column
   - Close GitHub issue
   - Add completion comment to GitHub issue
   ```

### Agent Work Coordination

```markdown
## Agent Coordination Integration

### When Starting Work
1. Update local issue to "In Progress"
2. Sync to GitHub board
3. Add coordination entry in .ai/agent-coordination/

### During Work  
1. Update work log entries
2. Sync status changes if significant
3. Coordinate with other agents through shared files

### When Completing Work
1. Update to "Done" locally
2. Auto-sync to GitHub (close issue, update board)
3. Clean up coordination files
4. Update feature progress tracking
```

## Error Handling

### GitHub API Issues
- **Rate limits**: Implement exponential backoff
- **Network errors**: Retry with timeout
- **Permission errors**: Clear error message and guidance

### Local File Issues  
- **Missing directories**: Create feature/issues directories as needed
- **Corrupt files**: Backup and repair with user confirmation
- **Permission errors**: Clear guidance on file permissions

### Sync Conflicts
- **Always preserve data**: Never delete without confirmation
- **Clear conflict resolution**: Show exactly what will change
- **Rollback capability**: Allow reverting sync operations

## Success Criteria

### Bidirectional Sync Working
- Changes in GitHub board reflect in local files within sync operation
- Changes in local files reflect on GitHub board when synced
- No data loss during sync operations

### Agent Integration Complete
- Agents automatically sync when completing tasks
- Board status stays current with actual work progress
- Feature progress tracking reflects real status

### Conflict Resolution Robust
- Clear conflict detection and resolution options
- User maintains control over conflict resolution
- Data integrity preserved during conflicts

Begin by reading PROJECT_CONTEXT.md and project-breakdown/master.md to understand the project context. Then scan for existing GitHub issues and local issue files to understand the current sync state.