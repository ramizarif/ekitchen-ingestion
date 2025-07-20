# Engineer Guidance - PM Direction and Support

**Command Arguments**: #$ARGUMENTS

You are receiving **PM Guidance** to help you stay on track. Parse `#$ARGUMENTS` for guidance type and context.

## Guidance Processing

### 1. Parse Guidance Type
```bash
# Extract guidance details
GUIDANCE_TYPE=$(echo "#$ARGUMENTS" | grep -o '\--type [^ ]*' | cut -d' ' -f2)
GUIDANCE_CONTEXT=$(echo "#$ARGUMENTS" | grep -o '\--context "[^"]*"' | sed 's/--context "//; s/"//')
GUIDANCE_MESSAGE=$(echo "#$ARGUMENTS" | grep -o '\--message "[^"]*"' | sed 's/--message "//; s/"//')
PLAN_SECTION=$(echo "#$ARGUMENTS" | grep -o '\--plan-section "[^"]*"' | sed 's/--plan-section "//; s/"//')

echo "📢 PM GUIDANCE RECEIVED - Type: $GUIDANCE_TYPE"
echo "Context: $GUIDANCE_CONTEXT"
echo ""
```

### 2. Process Guidance Based on Type
```bash
case "$GUIDANCE_TYPE" in
  "TESTING_ISSUE")
    echo "🧪 TESTING GUIDANCE"
    echo "PM detected testing issues in your work. Focus on:"
    echo ""
    echo "1. **Debug failing tests first**:"
    echo "   - Run tests individually to isolate failures"
    echo "   - Check test output for specific error messages"
    echo "   - Verify your implementation matches test expectations"
    echo ""
    echo "2. **Common testing issues**:"
    echo "   - Import/module path problems"
    echo "   - Missing test data or fixtures"
    echo "   - Async/timing issues in tests"
    echo "   - Environment or dependency issues"
    echo ""
    echo "3. **Next steps**:"
    echo "   - Fix the failing tests before continuing implementation"
    echo "   - Commit test fixes: git commit -m \"fix: resolve test failures\""
    echo "   - Report progress in 30 minutes"
    ;;
    
  "DEPENDENCY_ISSUE")
    echo "📦 DEPENDENCY GUIDANCE"
    echo "PM detected dependency/import issues. Address:"
    echo ""
    echo "1. **Check imports and modules**:"
    echo "   - Verify all required packages are installed"
    echo "   - Check import paths are correct"
    echo "   - Look for circular import issues"
    echo ""
    echo "2. **Installation issues**:"
    echo "   - Run: npm install / pip install -r requirements.txt"
    echo "   - Check package.json / requirements.txt for missing deps"
    echo "   - Verify node/python version compatibility"
    echo ""
    echo "3. **If blocked**:"
    echo "   - Document exact error message"
    echo "   - List what you've tried"
    echo "   - Signal blocker in next status report"
    ;;
    
  "DESIGN_ISSUE")
    echo "🏗️ ARCHITECTURE GUIDANCE"
    echo "PM detected potential design/architecture concerns:"
    echo ""
    echo "1. **Review implementation plan**:"
    echo "   - Re-read your issue file's implementation section"
    echo "   - Ensure you're following the planned approach"
    echo "   - Check if you're overcomplicating the solution"
    echo ""
    echo "2. **Follow established patterns**:"
    echo "   - Read: project-breakdown/context/patterns.md"
    echo "   - Look at similar implementations in the codebase"
    echo "   - Keep solutions simple and consistent"
    echo ""
    echo "3. **If uncertain**:"
    echo "   - Reference the implementation plan step-by-step"
    echo "   - Focus on meeting acceptance criteria simply"
    echo "   - Ask for clarification in next status if still unclear"
    ;;
    
  "REALIGN")
    echo "🎯 REALIGNMENT GUIDANCE"
    echo "PM detected work may be off-track from implementation plan."
    echo ""
    echo "**Expected work for your current phase:**"
    echo "$PLAN_SECTION"
    echo ""
    echo "**Action required:**"
    echo "1. **Stop current work** and re-read implementation plan"
    echo "2. **Compare your recent work** to the plan section above"
    echo "3. **Refocus on plan requirements** - don't improvise"
    echo "4. **Follow plan step-by-step** - each phase builds on previous"
    echo ""
    echo "5. **If plan is unclear**:"
    echo "   - Request clarification in next status report"
    echo "   - Reference specific plan step you're confused about"
    echo ""
    echo "Remember: **Implementation plan is law** - follow it exactly."
    ;;
    
  "DEBUG_HELP")
    echo "🐛 DEBUG ASSISTANCE"
    echo "PM detected multiple errors in your terminal. Debug approach:"
    echo ""
    echo "1. **Stop and analyze errors**:"
    echo "   - Look at the most recent error first"
    echo "   - Don't continue coding until errors are resolved"
    echo "   - Copy exact error messages for analysis"
    echo ""
    echo "2. **Systematic debugging**:"
    echo "   - Isolate the failing component"
    echo "   - Test individual functions/methods"
    echo "   - Add debug logging if needed"
    echo ""
    echo "3. **Common error patterns**:"
    echo "   - Syntax errors: Check recent code changes"
    echo "   - Runtime errors: Verify data types and null checks"
    echo "   - Import errors: Check file paths and dependencies"
    echo ""
    echo "4. **Recovery steps**:"
    echo "   - Fix errors one at a time"
    echo "   - Test after each fix"
    echo "   - Commit working state: git commit -m \"fix: resolve [specific error]\""
    ;;
    
  "COMMIT_REMINDER")
    echo "💾 COMMIT REMINDER"
    echo "PM noticed no recent commits. Git discipline required:"
    echo ""
    echo "**Immediate action:**"
    echo "1. git add -A"
    echo "2. git commit -m \"wip: [describe current progress]\""
    echo ""
    echo "**Going forward:**"
    echo "- Commit every 30 minutes minimum"
    echo "- Commit after completing each implementation step"
    echo "- Use descriptive messages: \"feat:\", \"fix:\", \"test:\""
    echo ""
    echo "**Why this matters:**"
    echo "- Preserves work if session crashes"
    echo "- Allows PM to track real progress"
    echo "- Enables recovery if you need to backtrack"
    echo ""
    echo "Commit now, then continue with implementation."
    ;;
    
  "CLARIFY_STATUS")
    echo "❓ STATUS CLARIFICATION REQUEST"
    echo "PM needs clearer status information. Please provide:"
    echo ""
    echo "**Required status format:**"
    echo "\"Phase [X] - [percentage]% complete - [specific current task] - ETA: [time estimate]\""
    echo ""
    echo "**Examples:**"
    echo "- \"Phase 1 - 60% complete - implementing URL validation - ETA: 45 minutes\""
    echo "- \"Phase 2 - 90% complete - writing unit tests - ETA: 15 minutes\"" 
    echo "- \"Phase 3 - 25% complete - debugging cache integration - ETA: 2 hours\""
    echo ""
    echo "**Also include any blockers:**"
    echo "- \"Blocked: failing tests, investigating import issues\""
    echo "- \"No blockers, steady progress\""
    echo ""
    echo "Provide clearer status in your next report to PM."
    ;;
    
  "GENERAL_BLOCKER")
    echo "🚧 GENERAL BLOCKER SUPPORT"
    echo "PM detected you're blocked. Systematic approach:"
    echo ""
    echo "1. **Document the blocker clearly**:"
    echo "   - What specific task are you trying to complete?"
    echo "   - What error/issue is preventing progress?"
    echo "   - What have you already tried?"
    echo ""
    echo "2. **Self-recovery steps**:"
    echo "   - Re-read implementation plan for this step"
    echo "   - Check similar code in the codebase"
    echo "   - Review project patterns and best practices"
    echo "   - Search error messages online"
    echo ""
    echo "3. **If still blocked after 15 minutes**:"
    echo "   - Break the task into smaller pieces"
    echo "   - Try alternative approaches"
    echo "   - Document what didn't work"
    echo ""
    echo "4. **Escalate if necessary**:"
    echo "   - Provide detailed blocker description in next status"
    echo "   - Include what you've tried and error messages"
    echo "   - PM will provide targeted assistance"
    ;;
    
  *)
    echo "📝 GENERAL GUIDANCE"
    echo "Message from PM: $GUIDANCE_MESSAGE"
    echo ""
    echo "Please acknowledge and adjust your work accordingly."
    ;;
esac
```

### 3. Acknowledgment and Action
```bash
echo ""
echo "=== GUIDANCE RECEIVED ==="
echo "Type: $GUIDANCE_TYPE"
echo "Status: Acknowledged"
echo "Next action: Following PM guidance"
echo "Will report progress in next status update"
echo "========================="
```

## Guidance System Benefits

This command ensures:
- ✅ **Targeted guidance** based on specific issues detected
- ✅ **Actionable instructions** for different problem types  
- ✅ **Systematic debugging** approaches
- ✅ **Plan realignment** when engineers drift off-track
- ✅ **Clear next steps** for resolution
- ✅ **Escalation paths** when self-recovery fails

Engineers receive **specific, actionable guidance** instead of generic check-ins.