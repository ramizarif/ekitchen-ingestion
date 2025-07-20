# Engineer Validation - Completion Verification

**Command Arguments**: #$ARGUMENTS

You are processing a **PM Validation Request**. Parse `#$ARGUMENTS` for validation requirements.

## Validation Requirements

### 1. Parse Validation Requirements
```bash
# Check what PM is requiring
REQUIRE_TESTING=$(echo "#$ARGUMENTS" | grep -q "\--require-testing" && echo "true" || echo "false")
REQUIRE_DOCS=$(echo "#$ARGUMENTS" | grep -q "\--require-docs" && echo "true" || echo "false") 
REQUIRE_SUMMARY=$(echo "#$ARGUMENTS" | grep -q "\--require-summary" && echo "true" || echo "false")

echo "🔍 PM VALIDATION REQUIRED - You must prove your work before completion"
echo "Required validations:"
[ "$REQUIRE_TESTING" = "true" ] && echo "- [ ] Full test suite execution"
[ "$REQUIRE_DOCS" = "true" ] && echo "- [ ] Documentation updates" 
[ "$REQUIRE_SUMMARY" = "true" ] && echo "- [ ] Change summary for PM"
echo ""
```

### 2. Testing Validation
```bash
if [ "$REQUIRE_TESTING" = "true" ]; then
  echo "=== TESTING VALIDATION REQUIRED ==="
  echo "1. Run the full test suite:"
  echo "   npm test  # (or appropriate test command for this project)"
  echo ""
  echo "2. Show ALL tests pass - if any fail, debug and fix first"
  echo ""
  echo "3. Manual functionality testing:"
  echo "   - Test each piece you implemented"
  echo "   - Verify it works as intended in real scenarios"
  echo "   - Test edge cases mentioned in acceptance criteria"
  echo ""
fi
```

Note: Make sure to update any user demos or test documentations if applicable.

### 3. Documentation Validation  
```bash
if [ "$REQUIRE_DOCS" = "true" ]; then
  echo "=== DOCUMENTATION VALIDATION REQUIRED ==="
  echo "1. Update any relevant documentation files"
  echo "2. Add usage examples if you created new functionality"
  echo "3. Update API documentation if you changed interfaces"
  echo "4. Verify README.md reflects any new features or setup steps"
  echo ""
fi
```

### 4. Change Summary Validation
```bash
if [ "$REQUIRE_SUMMARY" = "true" ]; then
  echo "=== CHANGE SUMMARY REQUIRED ==="
  echo "Provide a clear summary of what you implemented:"
  echo ""
  echo "Format your response as:"
  echo "/engineer-completion-summary --changes \"Brief description of what was implemented\" --files \"List of files modified/created\" --testing \"How you verified it works\" --usage \"How users can use the new functionality\""
  echo ""
  echo "Example:"
  echo "/engineer-completion-summary --changes \"Added search URL discovery with caching\" --files \"server.py, config.py, tests/test_discovery.py\" --testing \"All tests pass, manually verified 3 recipe sites\" --usage \"Discovery runs automatically when scraping recipes\""
  echo ""
fi
```

### 5. Acceptance Criteria Check
```bash
echo "=== ACCEPTANCE CRITERIA VERIFICATION ==="
echo "Go through each acceptance criteria in your issue file and confirm:"

# Find and display acceptance criteria
CURRENT_SESSION=$(tmux display-message -p '#S')
ISSUE_NUMBER=$(echo "$CURRENT_SESSION" | grep -o '[0-9]\+$' || echo "")
ISSUE_FILE=$(find project-breakdown/features/*/issues/ -name "*$ISSUE_NUMBER*" | head -1)

if [ -f "$ISSUE_FILE" ]; then
  echo "Your acceptance criteria:"
  grep -A 20 "## Acceptance Criteria" "$ISSUE_FILE" | grep -E "^- \[" | head -10
  echo ""
  echo "Verify EACH criteria is met before claiming completion."
else
  echo "Check your issue file for acceptance criteria and verify each one."
fi
```

### 6. Final Validation Response
```bash
echo ""
echo "=== ONCE ALL VALIDATIONS COMPLETE ==="
echo "Report back to PM with:"
echo ""
echo "/engineer-validated --tests-pass --docs-updated --summary-provided --criteria-met"
echo ""
echo "Only send this command when you have:"
echo "✅ All tests passing"
echo "✅ Documentation updated (if required)"
echo "✅ Change summary provided (if required)" 
echo "✅ All acceptance criteria verified"
echo ""
echo "If anything fails validation, debug and fix before reporting completion."
```

## Validation Workflow

This command ensures engineers:
- ✅ **Understand validation requirements** from PM
- ✅ **Run comprehensive testing** before claiming completion
- ✅ **Update documentation** as needed
- ✅ **Provide change summaries** for PM reporting
- ✅ **Verify acceptance criteria** individually
- ✅ **Report structured completion** back to PM

**No completion is accepted without proper validation.**