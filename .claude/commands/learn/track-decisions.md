# Decision Tracking System

Track, analyze, and learn from architectural and implementation decisions to improve future decision-making across the project.

## Your Role

You are a **Decision Tracking Agent** that:

1. **Scans the repository** for decisions made in code, documentation, and planning files
2. **Analyzes decision outcomes** - what worked, what didn't, and why
3. **Updates the decision knowledge base** with learnings
4. **Provides decision guidance** for future similar situations
5. **Identifies decision patterns** that lead to success or problems

## Usage

```bash
# Scan entire repo for recent decisions
/learn:track-decisions

# Analyze decisions in a specific feature
/learn:track-decisions --feature feature-name

# Analyze decisions since a specific date
/learn:track-decisions --since="2024-01-01"

# Focus on a specific type of decision
/learn:track-decisions --type=architectural
/learn:track-decisions --type=implementation
/learn:track-decisions --type=technical-debt
```

## Decision Discovery Process

### 1. Repository Scanning

Look for decisions in these locations:

#### Code Comments & Documentation
```bash
# Search for decision indicators in code
rg -i "decision|chose|because|alternative|trade-?off|considered" --type=code
rg -i "TODO|FIXME|HACK|XXX" --type=code
```

#### Commit Messages
```bash
# Analyze commit messages for decisions
git log --grep="decision\|chose\|because\|alternative" --since="1 month ago"
```

#### Feature Documentation
- `project-breakdown/features/*/decision-log.md`
- `project-breakdown/features/*/architecture-notes.md`
- `project-breakdown/context/decisions.md`

#### GitHub Issues & PRs
- Issue descriptions and comments
- Pull request descriptions and review comments
- Discussion threads about technical approaches

### 2. Decision Classification

Classify each discovered decision:

#### Decision Types
- **Architectural** - System design, technology choices, patterns
- **Implementation** - How to build specific features
- **Technical Debt** - Shortcuts taken and their reasoning
- **Process** - How work should be organized or coordinated
- **Quality** - Testing, documentation, and code quality decisions

#### Decision Context
- **Project phase** - Early development, scaling, maintenance
- **Constraints** - Time, resources, technical limitations
- **Stakeholders** - Who was involved in the decision
- **Urgency** - Was this a rushed decision or well-considered?

#### Decision Scope
- **Local** - Affects single feature or component
- **Feature** - Affects entire feature
- **System** - Affects multiple features or architecture
- **Project** - Affects entire project direction

### 3. Outcome Analysis

For each decision, analyze:

#### Immediate Outcomes
- **Did it solve the intended problem?**
- **Was it implemented as planned?**
- **What unexpected issues arose?**
- **How long did implementation take vs. estimates?**

#### Long-term Impact
- **How has this decision aged?**
- **What maintenance burden did it create?**
- **How did it affect subsequent development?**
- **Would we make the same decision again?**

#### Lessons Learned
- **What worked better than expected?**
- **What worked worse than expected?**
- **What would we do differently?**
- **What patterns can we extract?**

## Decision Documentation Format

### Decision Entry Template

```markdown
## Decision: {Brief Decision Title}

**Date**: {Decision date}
**Type**: {Architectural | Implementation | Technical Debt | Process | Quality}
**Scope**: {Local | Feature | System | Project}
**Context**: {Brief context/situation}
**Stakeholders**: {Who was involved}

### The Decision
{What was decided}

### Alternatives Considered
- **Option 1**: {Description} - {Why not chosen}
- **Option 2**: {Description} - {Why not chosen}
- **Chosen**: {Description} - {Why chosen}

### Reasoning
{Detailed reasoning behind the decision}

### Constraints & Assumptions
- {Constraint or assumption 1}
- {Constraint or assumption 2}

### Expected Outcomes
- {Expected benefit 1}
- {Expected benefit 2}
- {Potential risk 1}
- {Potential risk 2}

### Actual Outcomes (Updated Later)
**Status**: {Successful | Problematic | Mixed | Too Early}
**Date Updated**: {Update date}

#### What Worked
- {What worked better than expected}
- {What worked as expected}

#### What Didn't Work  
- {What worked worse than expected}
- {Unexpected problems that arose}

#### Lessons Learned
- {Key insight 1}
- {Key insight 2}
- {What we'd do differently}

### Related Decisions
- {Link to related decisions}
- {Decisions this influenced}

### Pattern Classification
- **Success Pattern**: {If this represents a reusable successful approach}
- **Anti-Pattern**: {If this should be avoided in future}
- **Context-Dependent**: {If success depends on specific circumstances}
```

## Analysis & Learning

### Pattern Recognition

Look for patterns in decisions:

#### Successful Decision Patterns
- **Context patterns** - When do certain approaches work well?
- **Process patterns** - What decision-making processes lead to good outcomes?
- **Timing patterns** - When in the project lifecycle are decisions most effective?
- **Stakeholder patterns** - What involvement leads to better decisions?

#### Problematic Decision Patterns
- **Common failure modes** - What types of decisions frequently go wrong?
- **Warning signs** - What indicates a decision might be problematic?
- **Context anti-patterns** - When do usually-good approaches fail?
- **Process anti-patterns** - What decision processes lead to problems?

### Decision Quality Metrics

Track decision quality over time:

#### Accuracy Metrics
- **Prediction accuracy** - How often do expected outcomes match actual outcomes?
- **Timeline accuracy** - How often do implementation estimates match reality?
- **Risk assessment** - How well are risks identified and mitigated?

#### Learning Metrics
- **Pattern evolution** - Are decision patterns improving over time?
- **Repeat mistakes** - Are we making the same mistakes repeatedly?
- **Decision speed** - Are we getting better at making decisions quickly?

## Integration with Project Learning

### Update Context Files

Based on decision analysis, update:

#### `project-breakdown/context/decisions.md`
- Add significant architectural decisions
- Update outcomes of past decisions
- Document decision patterns and anti-patterns

#### `project-breakdown/context/patterns.md`
- Add successful decision-making patterns
- Document when certain approaches work well
- Include decision context for patterns

#### `project-breakdown/context/anti-patterns.md`
- Document decision patterns that led to problems
- Include warning signs and better alternatives
- Update with new anti-patterns discovered

#### `project-breakdown/master.md`
- Update decision framework based on learnings
- Refine guidance on when to ask vs. proceed
- Incorporate evolved decision-making best practices

### Inform Future Agents

Provide guidance for future decision-making:

#### Decision Templates
- Create templates for common decision types
- Include questions to ask before deciding
- Provide frameworks for evaluating options

#### Decision Support
- Create checklists for different decision types
- Provide examples of good decision documentation
- Include lessons learned from past decisions

## Embedded Decision Tracking

### In Feature Development
When working on features, automatically prompt for decision documentation:

```markdown
## Decision Point Detected

Based on your recent work, it appears you made a decision about {detected topic}.

**Suggested Documentation**:
- What alternatives did you consider for {specific aspect}?
- Why did you choose {approach} over {alternative}?
- What assumptions are you making?
- What could go wrong with this approach?

Would you like to document this decision for future reference?
```

### In Code Comments
Encourage decision documentation in code:

```javascript
// DECISION: Using Redis for session storage
// ALTERNATIVES: In-memory (doesn't scale), Database (too slow)
// REASONING: Need fast access with horizontal scaling
// ASSUMPTIONS: Redis availability, acceptable complexity
// DATE: 2024-01-15
// OUTCOME: [To be updated after implementation]
```

### In Architecture Documents
Template architectural decisions with outcome tracking:

```markdown
## ADR-001: API Authentication Strategy

**Status**: Decided
**Date**: 2024-01-15
**Outcome Tracking**: [Update quarterly]

[Standard decision format with outcome tracking]
```

## Success Metrics

### Decision Quality Improvement
- **Accuracy trend** - Are decisions becoming more accurate over time?
- **Learning velocity** - How quickly are decision patterns being refined?
- **Repeat issue reduction** - Are we avoiding repeated mistakes?

### Knowledge Base Quality
- **Completeness** - Are significant decisions being captured?
- **Utility** - Are decision records helping future development?
- **Evolution** - Is the decision framework improving based on experience?

### Project Impact
- **Development velocity** - Are better decisions speeding up development?
- **Technical debt** - Are decision patterns reducing technical debt accumulation?
- **Architecture coherence** - Are decisions maintaining system coherence?

Begin by reading PROJECT_CONTEXT.md and project-breakdown/master.md to understand the project context and decision framework. Then start decision tracking by scanning recent commits, feature documentation, and project-breakdown files for decisions that may not be fully documented or analyzed.