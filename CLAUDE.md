# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`labchart_parser` parses ADInstruments LabChart `.txt` exports into a pandas DataFrame. Small lab tool, `src/` layout, package
`labchart_parser`.

## Commands

```bash
pip install -e ".[dev]"                          # dev install
pytest                                            # all tests
pytest tests/test_parser.py::TestParserBulk -v   # one class / test
ruff check src/ tests/                            # lint
black --target-version py310 src/ tests/          # format
isort --profile black src/ tests/                 # imports
```

CI runs Linux/macOS/Windows × Python 3.10/3.11/3.12. Floor is **Python ≥3.10**;
keep `pyproject.toml`, `README.md`, `CONTRIBUTING.md`, and the CI matrix in sync.

## Architecture

Two layers: a stateless functional parser
([src/labchart_parser/parser.py](src/labchart_parser/parser.py)) and a thin
OOP wrapper ([src/labchart_parser/core.py](src/labchart_parser/core.py)).

### Parser pipeline

`parse_labchart_txt(path) -> (df, meta)` runs three phases — read the
helper functions, not just `parse_labchart_txt`:

1. **Read.** UTF-8 first, latin-1 fallback. `errors="ignore"` is **not**
   used (silently dropped bytes corrupted French/Spanish exports).
2. **Segment** (`_segment_into_blocks`). Single linear pass produces
   `list[{meta, data_lines}]`. Block boundaries:
   - Header line (`Interval=`, `ChannelTitle=`, `UnitName=`, `Range=`,
     `TopValue=`, `BottomValue=`, `ExcelDateTime=`, `TimeFormat=`,
     `DateFormat=`) appears after data lines.
   - `Time` resets within a contiguous data run (covers one-header /
     multi-block files; metadata is shallow-copied).
3. **Validate** (`_validate_channel_consistency`). `ChannelTitle` must
   match across blocks, otherwise `FileParsingError`.
4. **Bulk-parse each block** (`_parse_block_data`). Classification pass
   tags lines as full-width numeric / short comment / skip, then loads
   the numeric portion via one `pd.read_csv(StringIO(buf), dtype=str,
   na_values=["*"])` call. `pd.to_numeric(errors="coerce")` per column
   turns unparseable cells into `NaN` without dropping the row.
5. **Stitch.** `block` ids come from segmentation order. `time_abs`
   advances by each block's own `Interval_s` at boundaries (median of
   diffs as fallback) — strictly monotonic.

### Metadata shape

- Top-level `meta`: block 0's `Interval`, `Interval_s`, `TimeFormat`,
  `DateFormat`, `ExcelDateTime`, `UnitName`.
- `meta["blocks"]: list[dict]` — full per-block metadata.
- **Dropped** from top level: `ChannelTitle` (becomes columns),
  `Range` / `TopValue` / `BottomValue` (vary per block).

### Errors

- `FileNotFoundError`: missing path.
- `FileParsingError`: bad extension, empty file, no data section,
  <2 columns, ChannelTitle mismatch.
- `NoDataError`: segmentation succeeded, every block empty.
- `InvalidChannelError` (subclass of `KeyError`, raised by `core`):
  unknown channel.
- `UserWarning` if `TimeFormat` isn't `StartOfBlock`.

### Wrapper invariants

`LabChartFile._data` carries the parsed frame. `channels` excludes the
`_SYSTEM_COLS` set — **add new computed columns to that tuple** or they
leak into the user-visible channel list. `get_block_df` /
`get_channel` / `slice_time_abs` return slices of `_data` **without
resetting the index**. `slice_time_abs` is inclusive on both ends.

### Test data

Integration tests use real fixtures in [examples/data/](examples/data/):

- `labchart_file.example.txt` — canonical multi-block, multi-channel.
- `labchart_file_negTime.txt` — exercises negative-time `time_block`;
  do not delete (`test_negative_time_file_parses_correctly`).

For new behavior, synthesize tab-delimited fixtures via `tmp_path` —
see `TestParserErrorPaths`, `TestParserMetaBlocks`.

### Versioning

`__version__` reads from package metadata via
`importlib.metadata.version("labchart_parser")`. Bump the `version` field in `pyproject.toml` only.
