# Testing Strategy

## Test Framework
- Use pytest for unit and integration tests
- Use pytest-cov for coverage reporting
- Use pytest-mock for mocking

## Test Organization
- Place tests in `tests/` directory
- Mirror source code structure
- Use descriptive test names

## Test Categories
- **Unit Tests**: Test individual functions/classes
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows

## Coverage Requirements
- Aim for >90% code coverage
- Focus on critical business logic
- Test both happy paths and error cases
