# Issue Discovery Questions

This file defines the **implementation-focused** questionnaire for issue discovery. Ask only questions that are necessary to build a clear implementation plan. **Do not ask questions for the sake of asking questions.**

## Discovery Principles

1. **Implementation-focused**: Only ask what's needed to implement the task
2. **User-driven**: Let the user describe their vision, don't assume
3. **Clarifying only**: Ask questions to clarify vague or unclear requirements
4. **Stop when clear**: Once you can build an implementation plan, stop asking
5. **User controls scope**: Ask until they tell you to stop or requirements are clear

## Essential Questions (Ask Only If Unclear)

### Core Task Understanding
**Only ask if the user's description is vague or unclear**

1. **What exactly needs to be implemented?**
   - Ask only if their description lacks specific implementation details

2. **What should the end result look like/do?**
   - Ask only if the expected behavior or outcome is unclear

3. **Are there specific technical requirements or constraints I should know about?**
   - Ask only if they haven't specified technical details that affect implementation

### Implementation Clarity Questions
**Ask only if needed for implementation planning**

4. **Which specific parts of the codebase need to change?**
   - Ask only if they haven't specified where the changes should go

5. **What specific data/inputs will this work with?**
   - Ask only if unclear what data structures or inputs are involved

6. **How should this integrate with existing functionality?**
   - Ask only if integration points are unclear

7. **Are there any specific technical approaches you want used?**
   - Ask only if they have preferences that affect implementation

### Completion Criteria Questions
**Ask only if success criteria are unclear**

8. **How will we know this is working correctly?**
   - Ask only if success criteria or expected behavior is unclear

9. **Are there any specific edge cases or error conditions to handle?**
   - Ask only if error handling requirements are unclear

10. **What testing should be done?**
    - Ask only if testing requirements are unclear

### Dependencies and Constraints
**Ask only if these affect implementation**

11. **Does this depend on any other work being done first?**
    - Ask only if dependencies aren't clear

12. **Are there any constraints or limitations I should know about?**
    - Ask only if there are technical, time, or resource constraints

## Discovery Flow

### Start with User Description
1. **Let user describe their task first** - Don't immediately jump to questions
2. **Analyze their description for completeness** - Check if you can implement based on what they provided
3. **Ask minimal clarifying questions** - Only for true implementation gaps
4. **Stop immediately when you can build a plan** - Don't over-engineer the discovery

### Information Completeness Check

**Before asking ANY question, check if the user's description includes:**
- [ ] **What to implement** - Clear description of the functionality
- [ ] **How it should work** - User interaction or behavior
- [ ] **Where it fits** - How it integrates with existing code
- [ ] **Success criteria** - How to know it's working

**If all four are clear → NO QUESTIONS, create the issue**
**If 1-2 are unclear → Ask targeted questions only for unclear items**  
**If 3-4 are unclear → Ask clarifying questions to understand the task**

### Question Guidelines
- **Only ask if truly needed** for implementation
- **One question at a time** - Don't overwhelm
- **Build on their description** - Reference what they've already said
- **Let them drive scope** - Don't assume additional requirements

### When to Stop Asking
- User says "that's enough" or "assume the rest"
- You have enough information to create a clear implementation plan
- User's description already covers the implementation details
- Further questions would be about nice-to-haves, not implementation necessities

### Red Flags (Don't Do This)
- ❌ Asking about documentation if they haven't mentioned it
- ❌ Asking about testing strategies if it's a simple change
- ❌ Asking about architecture if they've described a straightforward task
- ❌ Asking about deployment if it's code-only work
- ❌ Making the issue discovery longer than the actual implementation

## Success Criteria

After issue discovery, you should have enough information to:

1. **Create a clear GitHub issue** with:
   - Specific implementation requirements
   - Clear acceptance criteria  
   - Necessary technical details
   - Context for an agent to implement without guessing

2. **Know what NOT to include**:
   - Don't add requirements the user didn't specify
   - Don't assume testing needs beyond what they mentioned
   - Don't add documentation requirements they didn't request
   - Don't over-specify technical approaches they didn't define

## Agent Instructions

When conducting issue discovery:

1. **Start with user's description** - Let them explain their vision first
2. **Ask only clarifying questions** - Fill in implementation gaps, not nice-to-haves
3. **Respect user boundaries** - Stop when they indicate they're done
4. **Summarize understanding** - Confirm you can implement what they described
5. **Create focused issue** - Include what's needed, exclude assumptions

## Example Good Discovery

```
User: "I want to add a login form to the homepage"

Agent: "I understand you want a login form on the homepage. To implement this:
- What should happen when someone submits valid credentials?
- Should this integrate with an existing authentication system?
- Any specific validation requirements?"

User: "It should redirect to /dashboard and yes, use our existing JWT auth"

Agent: "Perfect! I have enough to implement this. Creating the issue now..."
```

## Example Bad Discovery

```
User: "I want to add a login form to the homepage"

Agent: "Great! Let me ask some questions:
1. What's the priority level?
2. What testing framework should I use?
3. Should this be responsive?
4. What about accessibility requirements?
5. Any deployment considerations?
6. Documentation updates needed?
... [20 more questions]
```

**The first example gets to implementation. The second example gets lost in process.**