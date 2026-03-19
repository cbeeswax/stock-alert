# GitHub Copilot Skill: Systematic Architecture Refactoring

**Skill Name**: `systematic-refactor`

**Purpose**: Systematically diagnose state/architecture issues, design solutions, implement with multi-environment validation, and document comprehensively.

**Best For**: 
- Complex bugs that span multiple components
- State corruption or persistence issues
- Features that work in one environment but not another
- Systems with both testing and production modes

---

## Skill Workflow

### Phase 1: Systematic Diagnosis 🔍

**Objective**: Isolate root cause without guessing

```bash
@copilot-cli systematic-refactor --phase=diagnose --issue="[Problem Statement]"
```

**Actions**:
1. **Understand the Symptom**
   - What's NOT working? (e.g., "WDC trades not appearing")
   - When did it start?
   - What changed?

2. **Create Diagnostic Tests**
   - Write minimal reproducers for each hypothesis
   - Test one variable at a time
   - Log output to files for comparison
   
3. **Build a Diagnosis Tree**
   ```
   Symptom: X not working
   ├─ Is the input data correct? (Test 1)
   ├─ Is the business logic correct? (Test 2)
   ├─ Is state being persisted? (Test 3)
   ├─ Is state being read correctly? (Test 4)
   └─ Is it a multi-environment issue? (Test 5)
   ```

4. **Document Findings**
   - Create a troubleshooting guide with findings
   - Show root cause with evidence
   - Link to code locations

**Output**: 
- Diagnostic scripts (phase1a, phase1b, phase1c, ...)
- Root cause identified with proof
- Troubleshooting guide markdown

---

### Phase 2: Architecture Evaluation 🏗️

**Objective**: Design the fix at architectural level (not band-aids)

```bash
@copilot-cli systematic-refactor --phase=design --root-cause="[Cause]"
```

**Actions**:
1. **Understand Current Architecture**
   - Map data flow: input → processing → storage → output
   - Identify all touch points (backtester, production, scripts)
   - Find assumptions that broke

2. **Identify Architectural Problems**
   - State mixing (active vs closed in same file?)
   - Persistence issues (when does data save/load?)
   - Multi-environment divergence (backtest ≠ production logic?)

3. **Design the Solution**
   - Separation of concerns: split mixed state
   - Add strategy/metadata tracking where missing
   - Ensure both environments use identical logic
   
4. **Create Design Document**
   - Before/after comparison
   - How it fixes the root cause
   - What changes where and why

**Output**:
- Architecture design doc (word diagram or ASCII)
- Refactor plan with file-by-file changes
- Risk assessment ("Very Low" if logic unchanged)

---

### Phase 3: Implementation 💻

**Objective**: Implement cleanly with minimal changes

```bash
@copilot-cli systematic-refactor --phase=implement --design="[Design Doc Path]"
```

**Actions**:
1. **New Classes/Files First**
   - Create new functionality (e.g., TradeHistory class)
   - Fully test in isolation
   - No dependencies on existing code yet

2. **Update Existing Files**
   - Add new fields minimally (e.g., strategy parameter)
   - Integration points only where needed
   - Default values for backward compatibility

3. **Validate Both Environments**
   - Backtester: Does it still work?
   - Production: Does it still work?
   - Can they run side-by-side?

4. **Write Clean Commits**
   ```
   [Commit 1] New feature: TradeHistory class
   [Commit 2] Integrate feature: RSBoughtTracker calls TradeHistory
   [Commit 3] Fix production: Record entries to tracker
   ```

**Output**:
- All changes committed and pushed
- No breaking changes
- Both environments functional

---

### Phase 4: Comprehensive Documentation 📚

**Objective**: Make it understandable to future developers (and yourself)

```bash
@copilot-cli systematic-refactor --phase=document --implementation="[Commits]"
```

**Create These Docs**:

1. **Architecture Summary** (3-5 KB)
   - Problem it solved
   - Before/after diagrams
   - Key decisions and why

2. **User Guide** (5-10 KB)
   - How to use the feature
   - Real example walkthrough
   - Common gotchas

3. **API Reference** (2-3 KB)
   - All public methods
   - Parameters and returns
   - Usage patterns

4. **Troubleshooting Guide** (3-5 KB)
   - If X goes wrong, check Y
   - Common issues
   - Debug steps

**Output**:
- 4-5 markdown files
- Comprehensive but not overwhelming
- Every file has one clear purpose

---

## Command Usage

```bash
# Start a systematic refactor project
@copilot-cli systematic-refactor --issue="WDC trades not appearing" --environment="backtest+production"

# Get help at each phase
@copilot-cli systematic-refactor --phase=diagnose --help

# Run diagnostic only
@copilot-cli systematic-refactor --phase=diagnose --issue="[Issue]" --output=diagnostics/

# Design only (if you already know root cause)
@copilot-cli systematic-refactor --phase=design --root-cause="Tracker mixes active+closed" 

# Implement from design
@copilot-cli systematic-refactor --phase=implement --design=refactor_plan.md

# Document after implementation
@copilot-cli systematic-refactor --phase=document --commits="2aa6776,1297788,98183f6"

# Full workflow (all phases)
@copilot-cli systematic-refactor --issue="[Issue]" --auto-phase=true
```

---

## Real Example: What We Did

**Initial Problem**:
```
WDC not appearing in trades despite passing filters
```

**Phase 1: Diagnosis**
```bash
@copilot-cli systematic-refactor --phase=diagnose --issue="WDC missing from trades"
```
→ Created 6 diagnostic scripts (phase1a-1e)
→ Found root causes:
  - Tracker JSON corrupted (WDC stuck "bought")
  - Production doesn't record exits to tracker

**Phase 2: Design**
```bash
@copilot-cli systematic-refactor --phase=design --root-cause="Tracker mixes active+closed trades"
```
→ Designed split: rs_ranker_bought.json (active) + rs_ranker_trade_history.json (closed)
→ Added strategy tracking and P&L calculations

**Phase 3: Implementation**
```bash
@copilot-cli systematic-refactor --phase=implement --design=tracker_refactor_plan.md
```
→ Created TradeHistory class
→ Updated RSBoughtTracker
→ Fixed main.py entry recording
→ 3 commits, all tested

**Phase 4: Documentation**
```bash
@copilot-cli systematic-refactor --phase=document --commits="2aa6776,1297788,98183f6"
```
→ Created 4 comprehensive guides explaining everything

---

## Key Principles

### 1. **One Problem at a Time**
Don't try to fix everything. Isolate and fix one root cause.

### 2. **Design Before Coding**
Spend time on architecture; implementation is fast.

### 3. **Backward Compatible**
Old code keeps working while new code integrates.

### 4. **Both Environments**
If it works in backtest but not production (or vice versa), that's a clue!

### 5. **Document Generously**
Someone will thank you later (probably you).

### 6. **Commit Narratively**
Each commit tells part of the story. Read them together and you understand the full refactor.

---

## Prompts to Use at Each Phase

### Phase 1: Diagnosis
```
You are a debugging expert. Help me diagnose this issue systematically:

[Issue Description]

Environment: [backtest/production/both]
Symptom appears: [when/under what conditions]
Suspected areas: [components that might be involved]

Create a diagnosis plan:
1. What tests should we run?
2. In what order (to isolate one variable at a time)?
3. How do we prove/disprove each hypothesis?

Then create the actual test scripts.
```

### Phase 2: Design
```
Based on this root cause: [Root Cause Description]

Design an architectural solution that:
1. Fixes the root cause
2. Works in both [env1] and [env2]
3. Doesn't break existing code
4. Adds minimal complexity

Show:
- Data flow before/after (ASCII diagram OK)
- File changes needed
- New classes/methods
- Integration points
- Risk assessment
```

### Phase 3: Implementation
```
Implement this design: [Design Description]

For each file change:
1. Show the change
2. Explain why it fixes the root cause
3. Ensure backward compatibility
4. Test in both environments

Create clean commits that tell the story.
```

### Phase 4: Documentation
```
Document this implementation: [Commits and Changes]

Create 4 guides:
1. Architecture Overview (why this design)
2. User Guide (how to use it)
3. API Reference (methods and parameters)
4. Troubleshooting (when things go wrong)

Each should be 3-5 KB and stand alone.
```

---

## Checklist: Did You Do It Right?

### Diagnosis Phase
- [ ] Created 3+ diagnostic scripts
- [ ] Root cause identified and proven
- [ ] Documented findings in a guide
- [ ] No assumptions, only evidence

### Design Phase
- [ ] Architecture documented with diagrams
- [ ] Before/after flow clear
- [ ] Risk assessment done
- [ ] Both environments considered

### Implementation Phase
- [ ] New classes tested in isolation first
- [ ] Integration points identified
- [ ] Backward compatible
- [ ] Clean, narrative commits
- [ ] Both environments validated

### Documentation Phase
- [ ] 4+ markdown files created
- [ ] Each file has one clear purpose
- [ ] Real examples shown
- [ ] Troubleshooting included
- [ ] Someone new could understand it

---

## When NOT to Use This Skill

❌ Simple bugs (use grep + direct fix)
❌ Feature additions without state issues
❌ Performance tuning
❌ Refactoring for style only

## When TO Use This Skill

✅ State corruption or data loss
✅ Multi-environment divergence
✅ Complex root causes requiring diagnosis
✅ Architectural redesigns
✅ Changes affecting production + testing

---

## Common Patterns in This Skill

### Pattern 1: Separating Mixed State
```
Problem: File A has both active and closed items
Solution: Split into File A (active) + File B (closed)
Benefit: Closed items never block re-entry
```

### Pattern 2: Adding Metadata
```
Problem: Can't track which strategy made a trade
Solution: Add strategy field to all records
Benefit: Can analyze performance by strategy
```

### Pattern 3: Environment Parity
```
Problem: Backtest and production use different logic
Solution: Make them use the same tracker classes
Benefit: No surprises when deploying
```

### Pattern 4: Persistence + Querying
```
Problem: Data stored but hard to query/analyze
Solution: Add query methods (get_by_strategy, summary stats)
Benefit: Easy reporting and auditing
```

---

## Success Metrics

After using this skill:
- ✅ Root cause is clear and documented
- ✅ Architecture design is clean
- ✅ Implementation is minimal and focused
- ✅ Both environments work identically
- ✅ Future developers understand it
- ✅ Changes are easy to review and test

---

## Future Enhancements

This skill could be extended with:
- Automated test generation
- Database schema migration helpers
- Multi-version compatibility checking
- Performance regression detection
- Automated documentation from code
