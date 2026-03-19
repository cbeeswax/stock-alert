# GitHub Copilot Skill: Feature Design & Test-Driven Development

**Skill Name**: `feature-design`

**Purpose**: Build new features cleanly using test-driven development (TDD) with design validation before coding.

**Best For**:
- New trading strategies
- New scanner components
- Data processing features
- API endpoints or integrations
- Any feature where correctness matters

---

## Skill Workflow

### Phase 1: Requirements & Design 📋

**Objective**: Be 100% clear on what you're building before writing code

```bash
@copilot-cli feature-design --feature="[Feature Name]" --phase=design
```

**Actions**:

1. **Define the Feature**
   - What does it do?
   - What goes in (inputs)?
   - What comes out (outputs)?
   - Example: "TradeHistory - append-only ledger of closed trades with P&L"

2. **Answer Design Questions**
   - What data structure (JSON, class, table)?
   - How does it persist?
   - How does it integrate with existing code?
   - What are edge cases?
   - What about error handling?

3. **Sketch the API**
   ```python
   class TradeHistory:
       def append_trade(ticker, entry_date, exit_date, entry_price, exit_price, strategy):
           """Add a closed trade to history"""
           
       def get_trades_by_strategy(strategy):
           """Query all trades for a strategy"""
           
       def get_p_and_l_summary(strategy):
           """Calculate total P&L by strategy"""
   ```

4. **Create Design Doc**
   - Purpose and goals
   - Data model (schema/class diagram)
   - API methods with signatures
   - Integration points (where does this connect?)
   - Example usage

**Output**:
- Feature design document (2-3 KB)
- Method signatures
- Integration diagram
- Test case ideas

---

### Phase 2: Test-Driven Development (TDD) 🧪

**Objective**: Write tests BEFORE implementation

```bash
@copilot-cli feature-design --feature="[Feature Name]" --phase=tests
```

**The TDD Pattern**:

```python
# STEP 1: Write tests that FAIL (Red Phase)
def test_append_trade():
    history = TradeHistory()
    history.append_trade("AAPL", "2024-01-01", "2024-01-15", 100, 110, "RS_Ranker")
    trades = history.get_all_trades()
    assert len(trades) == 1
    assert trades[0]["ticker"] == "AAPL"

def test_p_and_l_calculation():
    history = TradeHistory()
    history.append_trade("AAPL", "2024-01-01", "2024-01-15", 100, 110, "RS_Ranker", 10)  # 10 shares
    summary = history.get_p_and_l_summary()
    assert summary["total_pnl"] == 100  # (110-100) * 10

# STEP 2: Write minimal code to make tests PASS (Green Phase)
class TradeHistory:
    def __init__(self):
        self.trades = []
    
    def append_trade(self, ticker, entry_date, exit_date, entry_price, exit_price, strategy, shares):
        self.trades.append({
            "ticker": ticker,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "strategy": strategy,
            "shares": shares,
            "pnl": (exit_price - entry_price) * shares
        })
    
    def get_p_and_l_summary(self):
        return {"total_pnl": sum(t["pnl"] for t in self.trades)}

# STEP 3: Refactor to clean code (Refactor Phase)
# Improve readability, performance, error handling without changing tests
```

**TDD Benefits**:
1. Tests act as specification (you know exactly what works)
2. No untested code (100% coverage by design)
3. Refactoring is safe (tests catch breaking changes)
4. Easier to debug (test failure pinpoints the issue)

**Write Test Cases For**:
- Happy path (normal operation)
- Edge cases (empty inputs, single item, boundaries)
- Error handling (invalid inputs, missing data)
- Integration (how does it work with existing code?)

**Output**:
- Test file with 10+ test cases
- All tests passing (green)
- 100% code coverage

---

### Phase 3: Implementation 💻

**Objective**: Write clean code that passes all tests

```bash
@copilot-cli feature-design --feature="[Feature Name]" --phase=implement
```

**Actions**:

1. **Create the Core Class/Function**
   - Start with main functionality
   - Make tests pass
   - Keep it simple first

2. **Add Persistence Layer**
   - Save to JSON/database
   - Load on startup
   - Handle file I/O errors

3. **Integrate with Existing Code**
   - Find where this connects (e.g., backtester.py calls close_position())
   - Add calls to your new feature
   - Ensure backward compatibility

4. **Test Integration**
   - Run unit tests (your test file)
   - Run integration tests (with existing code)
   - Run full system test (backtest/production)

**Implementation Checklist**:
```
- [ ] All unit tests pass
- [ ] No breaking changes to existing code
- [ ] Error handling for all edge cases
- [ ] Logging at key points
- [ ] Code follows project style
- [ ] Docstrings on public methods
- [ ] Comments on complex logic only
```

**Output**:
- Implementation code (30-200 lines typically)
- All tests still passing
- Integrated with existing code

---

### Phase 4: Integration & Validation ✅

**Objective**: Ensure the feature works in the full system

```bash
@copilot-cli feature-design --feature="[Feature Name]" --phase=validate
```

**Actions**:

1. **Run All Tests**
   ```bash
   pytest tests/test_your_feature.py -v
   pytest tests/ -v  # All tests
   ```

2. **Run Backtester**
   ```bash
   python backtester_walkforward.py
   ```
   Check:
   - Does it complete without errors?
   - Do results look reasonable?
   - Did you break existing strategies?

3. **Run Production Scanner**
   ```bash
   python main.py --dry-run
   ```
   Check:
   - Does it scan without errors?
   - Are signals generated?
   - Is data being recorded?

4. **Create Test Report**
   ```
   ✅ Unit tests: 15/15 passed (100%)
   ✅ Integration test: Backtester completed successfully
   ✅ Production test: Scanner dry-run passed
   ✅ Backward compatibility: No breaking changes
   ✅ Code review: Meets style guide
   ```

**Output**:
- All tests passing
- Full system working
- Test report
- Ready to commit

---

### Phase 5: Documentation 📚

**Objective**: Make it usable and understandable

```bash
@copilot-cli feature-design --feature="[Feature Name]" --phase=document
```

**Create These Docs**:

1. **Feature Overview** (2 KB)
   ```markdown
   ## TradeHistory Feature
   
   **Purpose**: Track closed trades with P&L for analysis
   
   **Motivation**: Need to audit why trades profit/loss
   
   **Key Features**:
   - Append-only ledger (trades never deleted)
   - Query by strategy (see RS_Ranker trades only)
   - P&L calculations
   ```

2. **API Reference** (2-3 KB)
   ```markdown
   ## Methods
   
   ### append_trade()
   Add a closed trade to history.
   
   **Parameters**:
   - ticker (str): Stock symbol
   - entry_date (str): YYYY-MM-DD format
   - exit_date (str): YYYY-MM-DD format
   - strategy (str): Name of strategy that made the trade
   
   **Returns**: None (modifies state)
   
   **Example**:
   ```python
   history = TradeHistory()
   history.append_trade("AAPL", "2024-01-01", "2024-01-15", 100, 110, "RS_Ranker", 10)
   ```
   
   ### get_p_and_l_summary()
   Get P&L breakdown by strategy.
   
   **Returns**: Dictionary with win_count, loss_count, total_pnl, avg_r_multiple
   ```

3. **Usage Guide** (2-3 KB)
   ```markdown
   ## How to Use
   
   ### Load and Query Trades
   ```python
   from src.scanning.trade_history import TradeHistory
   
   history = TradeHistory()
   
   # Get all RS_Ranker trades
   rs_trades = history.get_trades_by_strategy("RS_Ranker")
   
   # Get P&L summary
   summary = history.get_p_and_l_summary("RS_Ranker")
   print(f"RS_Ranker total P&L: ${summary['total_pnl']}")
   ```
   ```

4. **Troubleshooting** (1-2 KB)
   ```markdown
   ## Common Issues
   
   ### "FileNotFoundError: trade_history.json not found"
   The trade_history.json file hasn't been created yet.
   **Solution**: Run backtester or production scanner once to create it.
   
   ### "P&L calculations don't match manual calculation"
   **Check**: Are all entries and pyramids included?
   **Debug**: Set debug=True in TradeHistory constructor
   ```

**Output**:
- 4 markdown files
- Clear, practical examples
- Covers common issues

---

## Command Usage

```bash
# Start full feature design
@copilot-cli feature-design --feature="TradeHistory System" --full=true

# Just the design phase
@copilot-cli feature-design --feature="TradeHistory System" --phase=design

# Just TDD phase (write tests)
@copilot-cli feature-design --feature="TradeHistory System" --phase=tests

# Implement only
@copilot-cli feature-design --feature="TradeHistory System" --phase=implement

# Validate integration
@copilot-cli feature-design --feature="TradeHistory System" --phase=validate

# Document only
@copilot-cli feature-design --feature="TradeHistory System" --phase=document --commits="abc123,def456"

# With specific requirements
@copilot-cli feature-design --feature="New Strategy" --requirements="Must beat 50% WR, use RSI+ADX, handle pyramiding"
```

---

## Real Example: What We Did

**Feature**: Trade History System

**Phase 1: Design**
```bash
@copilot-cli feature-design --feature="Trade History System" --phase=design
```
→ Designed append-only JSON ledger
→ Created method signatures
→ Identified integration points (backtester, production)

**Phase 2: TDD**
```bash
@copilot-cli feature-design --feature="Trade History System" --phase=tests
```
→ Wrote 15 test cases
→ Covered happy path, edge cases, error cases
→ All tests initially failing (RED)

**Phase 3: Implementation**
```bash
@copilot-cli feature-design --feature="Trade History System" --phase=implement
```
→ Created TradeHistory class (144 lines)
→ Added persistence layer (JSON)
→ Integrated with RSBoughtTracker
→ All tests passing (GREEN)

**Phase 4: Validation**
```bash
@copilot-cli feature-design --feature="Trade History System" --phase=validate
```
→ Unit tests: 15/15 ✅
→ Backtester: Passed, trade history created ✅
→ Production: Entry recording works ✅

**Phase 5: Documentation**
```bash
@copilot-cli feature-design --feature="Trade History System" --phase=document
```
→ Created 4 markdown files
→ API reference with examples
→ Usage guide for querying trades
→ Troubleshooting guide

---

## TDD Golden Rules

### Rule 1: Red → Green → Refactor
```
1. Write failing test (Red)
2. Write minimal code to pass test (Green)
3. Clean up code without changing tests (Refactor)
4. Repeat
```

### Rule 2: Test One Thing
```python
# ✅ GOOD: One thing per test
def test_append_trade():
    history = TradeHistory()
    history.append_trade(...)
    assert len(history.get_all_trades()) == 1

# ❌ BAD: Multiple things
def test_everything():
    history = TradeHistory()
    history.append_trade(...)
    history.append_trade(...)
    summary = history.get_p_and_l_summary()
    assert len(history.get_all_trades()) == 2 and summary['total_pnl'] > 0
```

### Rule 3: Happy Path + Edges + Errors
```python
# Happy path: Normal operation
def test_append_and_retrieve_trade(): ...

# Edge cases: Boundaries
def test_empty_history_returns_empty_list(): ...
def test_single_trade(): ...
def test_many_trades(): ...

# Error cases: Invalid inputs
def test_invalid_strategy_raises_error(): ...
def test_negative_price_raises_error(): ...
```

### Rule 4: Tests Are Specs
If your tests don't tell someone what the feature does, they're not clear enough.

```python
# ✅ CLEAR: Test name explains behavior
def test_get_pnl_by_strategy_returns_only_that_strategy():
    ...

# ❌ UNCLEAR: Vague name
def test_feature_works():
    ...
```

---

## TDD Anti-Patterns (Avoid)

❌ **Writing code first, tests later**
- Tests won't be comprehensive
- You'll skip edge cases
- Code will be harder to test

❌ **Skipping edge cases**
- "It works in the happy path"
- What about empty inputs? Zero? Negative?
- Tests should catch bugs before production

❌ **Tests that don't fail when code breaks**
- Tests that always pass are useless
- Modify code slightly, test should fail
- If test passes with wrong code, it's a bad test

❌ **Ignoring test failures**
- Red tests are telling you something
- Debug why it's failing
- Never commit red tests

---

## Integration Checklist

### Backtester Integration
- [ ] Feature doesn't break existing strategies
- [ ] New feature is used in backtester
- [ ] Results are reasonable (not obviously wrong)
- [ ] Logging shows feature is working

### Production Integration
- [ ] Feature doesn't break scanner
- [ ] Main.py calls new feature correctly
- [ ] Data is being recorded/saved
- [ ] No new errors in dry-run

### Code Quality
- [ ] All tests pass
- [ ] No unused code
- [ ] Docstrings on public methods
- [ ] Comments only on complex parts
- [ ] Follows project style

---

## Key Principles

### 1. Design First
Clear design saves days of implementation confusion.

### 2. Test-Driven (Not Test-After)
Writing tests first reveals design flaws early.

### 3. Minimal Implementation
Don't add features you think you might need. Add what tests require.

### 4. Integration Matters
Feature works great in isolation? Prove it works in the full system.

### 5. Document as You Go
You won't remember the decisions you made in 3 months.

---

## Success Metrics

After using this skill:
- ✅ Clear feature design documented
- ✅ Comprehensive tests (10+ cases)
- ✅ Clean implementation (40-200 lines)
- ✅ 100% test coverage
- ✅ Integrated with existing systems
- ✅ Full documentation
- ✅ Confident to ship

---

## Prompts to Use at Each Phase

### Phase 1: Design
```
I want to build this feature: [Feature Description]

Please help me design it by answering:
1. What data structure should it use?
2. What are the main operations (methods)?
3. How does it integrate with [existing code]?
4. What are potential edge cases?
5. What error cases should it handle?

Then create a design document with method signatures and integration diagram.
```

### Phase 2: TDD
```
Design: [Design Document]

Create a comprehensive test suite with:
1. Happy path (normal operation)
2. Edge cases (empty, single, many, boundaries)
3. Error handling (invalid inputs, missing data)
4. Integration (how it works with [existing code])

Write ~15 test cases that FAIL with no implementation.
```

### Phase 3: Implementation
```
Tests: [Test File]

Implement the feature to make these tests pass:
1. Create the main class/function
2. Add persistence layer if needed
3. Integrate with [existing code]
4. Keep code simple and clear
5. Ensure all tests pass

Show me the implementation.
```

### Phase 4: Validation
```
Implementation: [Code File]

Validate integration:
1. Do all unit tests still pass?
2. Does backtester complete successfully?
3. Does production scanner work?
4. Any breaking changes?
5. Code quality OK?

Create a test report.
```

### Phase 5: Documentation
```
Implementation: [Code File]
Tests: [Test File]

Create documentation:
1. Feature Overview (why we built it)
2. API Reference (methods and parameters)
3. Usage Guide (real examples)
4. Troubleshooting (common issues)

Each should be 2-3 KB and standalone.
```

---

## Extending This Skill

Future enhancements could include:
- Performance test templates (benchmark before/after)
- Database migration helpers
- Multi-version API compatibility
- Documentation generation from docstrings
- Code coverage analysis
- Load testing for scalability

---

## When NOT to Use This Skill

❌ Trivial features (add print statement)
❌ Bug fixes (use systematic-refactor instead)
❌ Quick one-off scripts
❌ Documentation updates only

## When TO Use This Skill

✅ New trading strategies
✅ New scanner features
✅ Data structures or models
✅ Complex business logic
✅ Anything that affects trading decisions
