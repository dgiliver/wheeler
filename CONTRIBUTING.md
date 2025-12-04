# Contributing to Wheeler

Thank you for your interest in contributing to Wheeler! This document provides guidelines and instructions for contributing.

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/wheeler.git
   cd wheeler
   ```
3. **Set up development environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install pre-commit pytest pytest-cov
   pre-commit install
   ```

## 📝 Development Workflow

1. **Create a branch** for your feature:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following our code style

3. **Run tests** to ensure nothing is broken:
   ```bash
   pytest tests/ -v
   ```

4. **Run pre-commit hooks**:
   ```bash
   pre-commit run --all-files
   ```

5. **Commit your changes**:
   ```bash
   git add -A
   git commit -m "feat: add your feature description"
   ```

6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request** on GitHub

## 📋 Code Style

We use **Ruff** for linting and formatting. The pre-commit hooks will automatically:
- Format code with `ruff format`
- Lint with `ruff`
- Check for security issues with `bandit`
- Fix trailing whitespace and EOF issues

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:
```
feat(strategy): add RSI divergence detection
fix(alpaca): handle rate limit errors gracefully
docs(readme): update installation instructions
```

## 🧪 Testing

- Write tests for new features
- Ensure all tests pass before submitting PR
- Aim for good test coverage

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_strategy_analyzer.py -v
```

## 🐛 Bug Reports

When reporting bugs, please include:
- Python version (`python --version`)
- OS and version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Relevant logs

## 💡 Feature Requests

We welcome feature requests! Please:
- Check existing issues first
- Describe the use case
- Explain why it would be valuable
- Consider if you'd like to implement it

## 📚 Areas for Contribution

- **New strategies**: Add different options strategies
- **Brokers**: Add support for other brokers (TD Ameritrade, Interactive Brokers)
- **Analysis**: Improve technical analysis (more indicators, ML predictions)
- **UI**: Build a web dashboard for monitoring
- **Documentation**: Improve docs, add tutorials
- **Testing**: Increase test coverage

## ❓ Questions?

Open an issue with the `question` label or start a discussion.

Thank you for contributing! 🙏
