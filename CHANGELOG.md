# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project follows [SemVer](https://semver.org).

## [Unreleased]

## [0.2.0] - 2026-04-29

- Per-block metadata exposed under `meta["blocks"]: list[dict]`. Top-level
  `meta` mirrors block 0 for back-compat, except `ChannelTitle` (now the
  DataFrame columns) and `Range`/`TopValue`/`BottomValue` (per-block only).
- `FileParsingError` raised if `ChannelTitle` differs between blocks.
- Parser rewritten around per-block segmentation + bulk `pd.read_csv`;
  ~320k rows/s on a synthetic 500k×5 file. Per-cell-NaN A2 behavior
  preserved via `pd.to_numeric(errors="coerce")`.
- `time_abs` stitching uses each block's own `Interval_s`.
- `LabChartFile.blocks` now returns `list[int]` (Python ints, not numpy scalars).
- `matplotlib` imported lazily inside `plot_channel()` to avoid import-time
  overhead and backend issues in headless environments.

## [0.1.2] - 2026-04-28

- `plot_channel()` method; matplotlib is a default dependency.
- `__version__` via `importlib.metadata`.
- `from_file()` / `parse_labchart_txt()` accept `os.PathLike`.
- `time_abs` strictly monotonic across block boundaries (advances by one
  sample interval).
- A single bad cell in a numeric row becomes `NaN` instead of nullifying
  the whole row.
- utf-8 read falls back to latin-1 instead of `errors="ignore"`.
- `UserWarning` when `TimeFormat` isn't `StartOfBlock`.
- Python ≥3.10 (was ≥3.8); CI on Linux/macOS/Windows × 3.10–3.12.
- Custom exceptions: `FileParsingError`, `NoDataError`, `InvalidChannelError`.
- Tests, pre-commit (black/ruff/isort/nbstripout), `[project.urls]`,
  centralized tool config in `pyproject.toml`.
- Type annotations modernized (PEP 604/585).
- All error messages translated to English.

## [0.1.1] - 2024-01-15

- `get_block_comments_excluding()`, `slice_time_abs()`.
- Multi-block file support.

## [0.1.0] - 2024-01-01

- Initial release: `LabChartFile`, `parse_labchart_txt()`, block /
  channel / comment extraction.

[Unreleased]: https://github.com/Neures-1158/labchart_txt_parser/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Neures-1158/labchart_txt_parser/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/Neures-1158/labchart_txt_parser/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Neures-1158/labchart_txt_parser/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Neures-1158/labchart_txt_parser/releases/tag/v0.1.0
