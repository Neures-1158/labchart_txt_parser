# Contributing

Issues and PRs welcome.

## Setup

```bash
git clone https://github.com/Neures-1158/labchart_txt_parser.git
cd labchart_txt_parser
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
pre-commit install   # optional but recommended
```

Requires Python ≥3.10.

## Workflow

```bash
pytest                                                # run tests
pytest tests/test_parser.py::TestParserBulk -v        # one class
ruff check src/ tests/                                # lint
black src/ tests/ && isort --profile black src/ tests/  # format
```

CI runs the same checks across Linux/macOS/Windows × Python 3.10–3.12.

## Pull requests

- Branch from `main`, keep PRs small.
- Add a test for any behavior change in the parser. Synthesizing tiny
  tab-delimited fixtures via `tmp_path` is the standard pattern (see
  `tests/test_parser.py::TestParserErrorPaths`).
- Update [CHANGELOG.md](CHANGELOG.md) under `## [Unreleased]` for
  user-visible changes.
- Pre-commit must pass; CI must be green.

By contributing you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
