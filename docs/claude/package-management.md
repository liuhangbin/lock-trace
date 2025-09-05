# UV Package Management

## Installation
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Common Commands
- `uv sync` - Install and sync dependencies
- `uv add <package>` - Add new dependency
- `uv remove <package>` - Remove dependency
- `uv run <command>` - Run command in environment
- `uv build` - Build package

## Configuration
- Dependencies defined in `pyproject.toml`
- Lock file: `uv.lock`
- Python version: `.python-version`

## Best Practices
- Pin Python version in `.python-version`
- Use dependency groups for different environments
- Regular `uv sync` to stay updated
