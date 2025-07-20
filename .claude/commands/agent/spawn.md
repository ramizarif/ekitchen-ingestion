# Agent Issue Assignment

Assign yourself to work on a GitHub issue with full coordination capabilities.

Usage: `/agent:spawn <issue-number>`

You are now an Agent working on GitHub issue #$ARGUMENTS with full coordination access. Follow the agent template workflow:

1. **Retrieve the assigned GitHub issue details** using mcp__GitHubProjects__get-issue
2. **Create implementation plan** in `.ai/implementation-plans/{branch}/issue-$ARGUMENTS.md`
3. **Analyze conflicts** with other active agents by reading existing coordination files
4. **Coordinate with other agents** via coordination file updates
5. **Begin implementation** following peer coordination guidelines
6. **Use all available coordination commands** as needed throughout the process

Your issue number: #$ARGUMENTS

You have access to all coordination commands (status, conflicts, review-plans, etc.). Begin by retrieving the issue details and creating your implementation plan. Remember to coordinate with other agents through shared coordination files.