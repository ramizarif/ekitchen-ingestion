# Project Context for Claude Agents

This file provides essential context for any Claude agent working on this project. **Read this file first** before executing any commands or making changes.

## Project Overview

**Project**: eKitchen AI Agent Ecosystem for Conversational Data Processing  
**Purpose and Architecture**: 
Revolutionary approach to data ingestion that replaces traditional pipelines with AI agent orchestration. Instead of building rigid ETL pipelines, we create specialized MCP (Model Context Protocol) tools that AI agents combine conversationally to achieve complex outcomes.

**What It Does**: An AI agent ecosystem that enables conversations like "Find 500 Mediterranean recipes and fully process them into my database" where Claude intelligently orchestrates multiple MCP tools (Playwright for extraction, Recipe Discovery for scraping, Spoonacular for nutrition, PostgreSQL for storage) without any pipeline code.
Why You Need It
Your eKitchen app needs rich, structured recipe data to be valuable to users, but:

Manual data entry is impossible at scale (thousands of recipes needed)
Recipe websites have inconsistent formats that break traditional scrapers
Nutritional data and ingredient categorization require external APIs and intelligence
You're a solo developer who can't build and maintain complex data pipelines

Why This Approach
Traditional Approach: Build complex microservice pipelines with queues, workers, and orchestration

❌ 4-6 weeks development time
❌ Complex infrastructure to maintain
❌ Rigid parsing that breaks with format changes
❌ Manual intervention for edge cases

Your AI Agent Ecosystem Approach: Conversational data processing with MCP tool orchestration

✅ 2-3 weeks development time (75% faster)
✅ Zero infrastructure overhead (runs locally)
✅ AI handles format variations and orchestration naturally
✅ Intelligent error recovery and workflow decisions
✅ Natural language control: "Fix those failed ingredient enrichments"

The Core Innovation
Instead of building rigid ETL pipelines, you're creating **AI agent toolkits** - where you build focused MCP tools and AI agents orchestrate complex multi-step workflows through natural reasoning. It's like having a smart data engineer assistant who can intelligently combine your tools to handle any processing complexity while you focus on building excellent individual capabilities.

**Bottom Line**: Build tools for AI agents instead of pipelines. Get production-ready recipe data faster, cheaper, and with less complexity by letting AI handle the intelligent orchestration and decision-making.

## Directory Structure & Purpose

### `.ai/` - Agent Framework
The AI coordination and workflow framework. Agents should reference these files for:
- **Coordination logic** - How to work with other agents
- **Templates** - Structured approaches for implementation
- **Active coordination** - Current agent activities and conflicts

Key files:
- `.ai/orchestrator/agent-coordinator.md` - Main coordination guide
- `.ai/agent-templates/agent-template.md` - How to work as an agent
- `.ai/agent-coordination/{branch}.md` - Active agent coordination

### `project-breakdown/` - Project Architecture & Learning
The living architecture and institutional knowledge. **Always check this before major decisions.**

#### `project-breakdown/master.md` - **READ FIRST**
The master project plan containing:
- Project vision and architecture
- Established patterns and best practices  
- Decision framework for when to ask vs. proceed
- Learning from past implementations

#### `project-breakdown/context/` - Institutional Knowledge
- `patterns.md` - Proven successful approaches
- `anti-patterns.md` - Approaches that failed, avoid these
- `best-practices.md` - Evolved practices from experience
- `decisions.md` - Past decisions and their outcomes

#### `project-breakdown/features/` - Feature Architecture
- Each feature has its own directory with architectural decisions
- Check existing features before creating new ones
- Look for integration patterns and dependencies

#### `project-breakdown/learning/` - Analysis & Evolution
- Post-implementation analysis and pattern extraction
- How the project's understanding has evolved
- Lessons learned from completed work

## Agent Workflow Guidelines

### Before Starting Any Work

1. **Read `project-breakdown/master.md`** - Understand project vision and current architecture
2. **Check `project-breakdown/context/patterns.md`** - Use established successful patterns
3. **Review `project-breakdown/context/anti-patterns.md`** - Avoid known problematic approaches
4. **Check existing features** in `project-breakdown/features/` for similar work
5. **Read coordination files** in `.ai/agent-coordination/` for current agent activities

### During Work

1. **Follow established patterns** unless there's a clear reason to deviate
2. **Ask questions** when patterns don't fit or requirements are unclear
3. **Document decisions** as you make them (update decision logs)
4. **Coordinate with other agents** through coordination files
5. **Update your progress** in real-time for other agents

### After Completing Work

1. **Update relevant context files** with new patterns or learnings
2. **Document decisions made** and their reasoning
3. **Clean up coordination files** 
4. **Contribute to institutional knowledge** for future agents

## Decision Framework

### When to Ask Questions
- **Architecture changes** - If this requires changing the master architecture
- **Pattern deviations** - If established patterns don't fit the situation
- **Unclear requirements** - If implementation path is ambiguous
- **Integration complexity** - If coordination with other systems is complex
- **Conflicting information** - If project context seems contradictory

### When to Proceed Confidently
- **Clear alignment** - Work clearly fits existing architecture
- **Established patterns** - Can use proven approaches from context/patterns.md
- **Well-defined scope** - Requirements are clear and bounded
- **Minimal dependencies** - Doesn't require major coordination with other work

### Decision Documentation
**Always document significant decisions** by:
- Adding to feature decision-log.md files
- Updating project-breakdown/context/decisions.md for architectural decisions
- Recording reasoning and alternatives considered
- Noting lessons learned for future reference

## Quality Standards

### Code Quality
- Follow patterns established in project-breakdown/context/patterns.md
- Avoid anti-patterns documented in project-breakdown/context/anti-patterns.md
- Write tests according to established testing patterns
- Document code according to project standards

### Architecture Quality
- Ensure alignment with project-breakdown/master.md architecture
- Consider long-term maintainability and evolution
- Document architectural decisions and trade-offs
- Think about how this will integrate with future features

### Learning Quality
- Contribute insights and patterns discovered during implementation
- Document what worked well and what didn't
- Update best practices based on real experience
- Help future agents by improving institutional knowledge

## Common Agent Commands

### Issue & Feature Work
- `/new-feature-breakdown` - Complete feature planning workflow (big ideas → issues)
- `/issue-discovery` - Create well-defined GitHub issues  
- `/agent` - Enter agent mode with full coordination capabilities
- `/agent:spawn <issue-number>` - Assign yourself to a specific issue

### Learning & Context
- `/learn:extract-patterns` - Analyze completed work for reusable patterns
- `/learn:retrospective` - Conduct post-implementation learning sessions
- `/learn:synthesize` - Update best practices based on accumulated experience

### Project Management
- `/project:health` - Check overall project and coordination health
- `/project:board` - Interact with GitHub project board
- `status` - See all current agent activities and progress

## Integration Points

### GitHub Integration
- Issues should reference appropriate project-breakdown files
- Project board should reflect feature breakdown structure
- Pull requests should link to architectural decisions

### Learning Integration
- Every completed feature should contribute to pattern extraction
- Decision outcomes should be tracked and analyzed
- Best practices should evolve based on real project experience

## Success Metrics

### Technical Success
- Code follows established patterns
- Architecture remains coherent and maintainable
- Integration points work smoothly
- Performance and quality standards met

### Learning Success
- Institutional knowledge grows over time
- Patterns become more refined and useful
- Decision quality improves with experience
- Development velocity increases due to learned efficiencies

### Coordination Success
- Agents work together without conflicts
- Knowledge is shared effectively across agents
- Context is preserved and accessible
- Decision rationale is clear and traceable

---

## Quick Start for New Agents

1. **Read project-breakdown/master.md** (5 minutes)
2. **Scan project-breakdown/context/patterns.md** (3 minutes)  
3. **Check current agent coordination** in .ai/agent-coordination/ (2 minutes)
4. **Begin work** following established patterns and decision framework

**Remember**: This project gets smarter over time. Your work should contribute to that learning process by documenting insights, patterns, and decisions for future agents.