# Engineer Status Report

**Command Arguments**: #$ARGUMENTS

Provide a quick status update to your PM and send recent terminal context for review.

## What to do:

1. **Create status update** - Brief summary of what you're working on
2. **Get last 200 lines** - Capture recent terminal activity 
3. **Send to PM** - Use the exact command below

## Status Update Format:
```
ENGINEER STATUS:
- Current task: [what you're doing now]
- Progress: [percentage or phase]
- Blockers: [any issues or "None"]
- ETA: [time estimate]

RECENT TERMINAL (last 200 lines):
[terminal output]
```

## Send to PM Command:
```bash
./scripts/send-claude-message.sh "#$ARGUMENTS" "[your status update and terminal output]"
```

## After sending:
Alert PM to review with this exact command:
```bash
./scripts/send-claude-message.sh "#$ARGUMENTS" "/pm-review-engineer-status $(tmux display-message -p '#{session_name}')"
```

That's it. Keep it simple and focused.