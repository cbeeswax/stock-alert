# Contributing to Stock Alert

Thank you for your interest in contributing to Stock Alert! This document provides guidelines for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Adding New Features](#adding-new-features)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

Be respectful, inclusive, and professional. We're here to learn from each other.

## Getting Started

### Prerequisites

- Python 3.8+
- pip or conda for package management
- Git for version control

### Setup Development Environment

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/stock-alert.git
   cd stock-alert
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-cov pytest-xdist  # Dev dependencies
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run tests to verify setup**
   ```bash
   pytest tests/ -v
   ```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
# Or for bug fixes:
git checkout -b fix/issue-description
```

**Branch naming conventions:**
- `feature/feature-name` - New features
- `fix/bug-name` - Bug fixes
- `docs/what` - Documentation
- `test/what` - Tests
- `refactor/what` - Code refactoring

### 2. Make Changes

- Make focused, atomic commits
- Write clear commit messages
- Test your changes locally
- Update documentation as needed

### 3. Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_strategies.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### 4. Code Quality Checks

```bash
# Run linter
flake8 src/ tests/ --max-line-length=100

# Check type hints
mypy src/

# Format code
black src/ tests/
```

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a PR on GitHub.

## Code Style

### Python Style Guide

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with these adjustments:

- **Line length**: 100 characters (not 79)
- **Indentation**: 4 spaces
- **Naming**:
  - Classes: `CamelCase`
  - Functions/variables: `snake_case`
  - Constants: `UPPER_CASE`

### Code Quality Standards

**Docstrings** (Google style):
```python
def run_backtest(start_date: datetime, end_date: datetime) -> dict:
    """
    Run historical backtest of trading strategies.
    
    Args:
        start_date: Backtest start date
        end_date: Backtest end date
        
    Returns:
        dict: Results with keys 'total_return_pct', 'win_rate', etc.
        
    Raises:
        ValueError: If start_date >= end_date
    """
    pass
```

**Type Hints**:
```python
from typing import List, Dict, Optional, Tuple

def get_signals(
    tickers: List[str],
    date: Optional[datetime] = None
) -> Dict[str, List[dict]]:
    """Get trading signals for tickers."""
    pass
```

**Comments**:
- Explain WHY, not WHAT (code shows what)
- Use sparingly (good code is self-documenting)
- Update comments when code changes

### File Organization

```
src/module_name/
├── __init__.py          # Export public API
├── module.py            # Main implementation
├── utils.py             # Helpers (if needed)
└── constants.py         # Module constants
```

## Testing

### Testing Philosophy

- Write tests for new code (TDD preferred)
- Tests document expected behavior
- Aim for 80%+ code coverage
- Unit tests should be fast
- Integration tests can be slower

### Test Structure

```
tests/
├── unit/                # Fast tests, mocked dependencies
│   ├── test_strategies.py
│   ├── test_scanner.py
│   └── ...
├── integration/         # Slower tests, real components
│   ├── test_backtest.py
│   └── ...
├── fixtures/            # Shared test data and mocks
│   ├── sample_data.py
│   ├── mocks.py
│   └── __init__.py
├── conftest.py          # Pytest configuration
└── __init__.py
```

### Writing Tests

**Unit Test Example:**
```python
import pytest
from src.indicators.technical import calculate_sma

def test_sma_calculation():
    """Test SMA calculates correctly."""
    prices = [1, 2, 3, 4, 5]
    result = calculate_sma(prices, period=2)
    
    assert len(result) == 5
    assert result[-1] == 4.5  # (4 + 5) / 2

def test_sma_with_invalid_period():
    """Test SMA raises on invalid period."""
    prices = [1, 2, 3]
    
    with pytest.raises(ValueError):
        calculate_sma(prices, period=0)
```

**Using Fixtures:**
```python
from tests.fixtures import sample_ohlcv_data, mock_market_data

def test_strategy_with_fixture(sample_ohlcv_data):
    """Test strategy with sample data."""
    strategy = MyStrategy()
    signals = strategy.scan(sample_ohlcv_data)
    
    assert len(signals) >= 0
```

**Mocking External Dependencies:**
```python
from unittest.mock import patch, MagicMock

@patch('src.data.market.get_historical_data')
def test_scanner_with_mocked_data(mock_get_data):
    """Test scanner without network calls."""
    mock_get_data.return_value = sample_data_df
    
    signals = run_scan(['AAPL'])
    assert mock_get_data.called
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific directory
pytest tests/unit/

# Run specific test
pytest tests/unit/test_strategies.py::test_strategy_entry

# Run with markers
pytest tests/ -m "not slow"

# Run in parallel
pytest tests/ -n 4

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

## Submitting Changes

### Commit Message Guidelines

Follow [conventional commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding/modifying tests
- `perf`: Performance improvement

**Examples:**
```
feat(scanning): add support for custom strategy parameters

fix(strategies): handle NaN values in momentum calculation

docs(api): add backtest function documentation

test(position_tracker): add tests for position limits
```

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Changes
- Specific change 1
- Specific change 2

## Testing
- [ ] Tests added/updated
- [ ] All tests passing
- [ ] Code coverage maintained

## Checklist
- [ ] Code follows style guide
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Ready for review
```

### Code Review Process

1. Automated checks (linting, tests) must pass
2. At least one approving review required
3. Address feedback and push updates
4. Squash and merge after approval

## Adding New Features

### Adding a New Strategy

1. **Create strategy file**
   ```python
   # src/strategies/my_strategy.py
   from src.strategies.base import Strategy
   
   class MyStrategy(Strategy):
       """Description of strategy."""
       
       def __init__(self, **params):
           self.params = params
       
       def scan(self, data, ticker=None, as_of_date=None):
           """Generate signals from data."""
           signals = []
           # Implementation
           return signals
   ```

2. **Register strategy**
   ```python
   # src/scanning/scanner.py
   from src.strategies.my_strategy import MyStrategy
   
   STRATEGIES = [
       RelativeStrengthRanker(),
       High52WeekBreakout(),
       BigBaseBreakout(),
       MyStrategy(),  # Add here
   ]
   ```

3. **Add configuration**
   ```python
   # src/config/strategies.py
   STRATEGIES_CONFIG = {
       'MyStrategy': {
           'lookback_weeks': 52,
           # Other parameters
       }
   }
   ```

4. **Add tests**
   ```python
   # tests/unit/test_my_strategy.py
   def test_my_strategy_scan():
       """Test strategy scan."""
       strategy = MyStrategy()
       signals = strategy.scan(sample_data)
       assert len(signals) >= 0
   ```

### Adding a New Indicator

1. **Create indicator function**
   ```python
   # src/indicators/technical.py
   def calculate_my_indicator(data, period=20):
       """Calculate custom indicator."""
       return result
   ```

2. **Add tests**
   ```python
   def test_my_indicator():
       """Test indicator calculation."""
       result = calculate_my_indicator(prices)
       assert len(result) == len(prices)
   ```

3. **Use in strategies**
   ```python
   from src.indicators.technical import calculate_my_indicator
   
   # In strategy
   indicator = calculate_my_indicator(data['Close'])
   ```

### Adding Configuration Options

1. **Add to settings.py**
   ```python
   # src/config/settings.py
   MY_NEW_SETTING = os.getenv('MY_NEW_SETTING', 'default_value')
   ```

2. **Document in .env.example**
   ```
   # My new setting
   MY_NEW_SETTING=value
   ```

3. **Update documentation**

## Reporting Issues

### Bug Reports

Include:
- Python version
- Operating system
- Exact steps to reproduce
- Expected behavior
- Actual behavior
- Error messages/stack traces
- Code samples

**Template:**
```markdown
## Description
Brief description of bug

## Steps to Reproduce
1. Run command X
2. Do action Y
3. Bug occurs

## Expected
System should do Z

## Actual
System does W

## Environment
- Python: 3.9
- OS: Windows 10
- Branch: main
```

### Feature Requests

Include:
- Clear description of desired feature
- Motivation (why needed)
- Example usage
- Potential implementation approach

**Template:**
```markdown
## Feature
Brief title

## Motivation
Why this feature is needed

## Description
Detailed description

## Example Usage
```python
# How it would be used
```

## Alternative Approaches
Other ways to solve this
```

## Development Tips

### Debugging

```python
# Use print debugging
print(f"Debug: {variable} = {value}")

# Or use pdb
import pdb; pdb.set_trace()

# Or use logging
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Message: {value}")
```

### Performance Profiling

```bash
# Time a script
time python scripts/backtest.py

# Or use cProfile
python -m cProfile -s cumulative scripts/backtest.py

# Profile specific function
import cProfile
cProfile.run('my_function()')
```

### Useful Tools

- **Black**: Code formatter
  ```bash
  black src/ tests/
  ```

- **Flake8**: Linter
  ```bash
  flake8 src/
  ```

- **mypy**: Type checker
  ```bash
  mypy src/
  ```

- **pytest**: Test runner
  ```bash
  pytest tests/ -v
  ```

## Getting Help

- **Documentation**: See `docs/` directory
- **Issues**: GitHub Issues for bugs/features
- **Discussions**: GitHub Discussions for questions
- **Code Examples**: See `examples/` directory

## License

By contributing, you agree that your contributions will be licensed under the project's license.

---

Thank you for contributing! Your help makes Stock Alert better. 🚀
