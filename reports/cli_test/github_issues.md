# CodeGuardian Issues

### 1. [MEDIUM] Long Function
- **Location**: `src/main.py:73`
- **Description**: Function 'review' is 61 lines long (>50). Long functions are harder to understand and test.
- **Recommendation**: Extract helper functions from 'review'. Aim for functions under 20 lines.

### 2. [MEDIUM] Too Many Parameters
- **Location**: `src/main.py:73`
- **Description**: Function 'review' has 9 parameters (>5). Hard to use correctly without documentation.
- **Recommendation**: Consider using a parameter object or kwargs pattern for 'review'.

### 3. [MEDIUM] No Test Coverage
- **Location**: `src/main.py:1`
- **Description**: File 'src\main.py' has no test coverage detected. No tests exercise this code.
- **Recommendation**: Add unit tests for 'src\main.py'. Aim for >80% coverage.
