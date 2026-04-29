"""Parse ADInstruments LabChart ``.txt`` exports into a pandas DataFrame."""

from __future__ import annotations

import io
import os
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from .exceptions import FileParsingError, NoDataError

FLOAT_START = re.compile(r"^\s*[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?\s*$")

_HEADER_KEYS_SCALAR = ("Interval=", "ExcelDateTime=", "TimeFormat=", "DateFormat=")
_HEADER_KEYS_LIST = (
    "ChannelTitle=",
    "UnitName=",
    "Range=",
    "TopValue=",
    "BottomValue=",
)
_ALL_HEADER_PREFIXES = _HEADER_KEYS_SCALAR + _HEADER_KEYS_LIST


def parse_labchart_txt(
    path: str | os.PathLike[str],
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Parse a LabChart text export. Returns ``(df, meta)``.

    ``df`` columns: ``Time``, one column per channel, ``Comment``, ``block``,
    ``time_abs``, ``time_block``. ``meta`` mirrors block 0's metadata at the
    top level and exposes the per-block list under ``meta["blocks"]``.

    Raises ``FileNotFoundError``, ``FileParsingError`` (bad extension /
    empty file / no data section / <2 columns / ChannelTitle mismatch),
    or ``NoDataError`` (segmentation succeeded but every block was empty).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if p.suffix.lower() not in (".txt", ".text"):
        raise FileParsingError(
            f"Unsupported file extension: {p.suffix}. "
            "Please use a .txt file exported from LabChart."
        )

    # utf-8 strictly first, then latin-1. errors="ignore" silently drops
    # bytes from cp1252 exports — don't go back to that.
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = p.read_text(encoding="latin-1")
        except OSError as e:
            raise FileParsingError(f"Unable to read file: {e}") from e
    except OSError as e:
        raise FileParsingError(f"Unable to read file: {e}") from e
    lines = text.splitlines()
    if not lines:
        raise FileParsingError("The file is empty.")

    blocks = _segment_into_blocks(lines)
    if not blocks:
        raise FileParsingError(
            "Data start not found. Please verify that the file is a valid "
            "LabChart export with tab-delimited numeric data."
        )

    _validate_channel_consistency(blocks)

    chan_titles = blocks[0]["meta"].get("ChannelTitle")
    if chan_titles:
        n_cols = 1 + len(chan_titles)
    else:
        n_cols = len(blocks[0]["data_lines"][0].split("\t"))
    if n_cols < 2:
        raise FileParsingError(
            f"The file contains only {n_cols} column(s). "
            "A valid LabChart export must contain at least Time + 1 channel."
        )

    if chan_titles:
        channel_cols: list[str] = ["Time"] + chan_titles
    else:
        channel_cols = ["Time"] + [f"Ch{i}" for i in range(1, n_cols)]

    time_format = blocks[0]["meta"].get("TimeFormat")
    if time_format and time_format != "StartOfBlock":
        warnings.warn(
            f"TimeFormat={time_format!r} (expected 'StartOfBlock'). "
            "Block detection relies on negative time jumps; with this "
            "format the file will be parsed as a single block. Re-export "
            "from LabChart with 'Start from Block' selected.",
            stacklevel=2,
        )

    block_dfs = [
        _parse_block_data(b["data_lines"], channel_cols, n_cols) for b in blocks
    ]
    nonempty = [(b, d) for b, d in zip(blocks, block_dfs, strict=True) if len(d) > 0]
    if not nonempty:
        raise NoDataError(
            "No valid data lines found after parsing. "
            "Please verify that the file contains numeric data."
        )
    blocks = [b for b, _ in nonempty]
    block_dfs = [d for _, d in nonempty]

    df = pd.concat(block_dfs, ignore_index=True)

    block_ids = np.empty(len(df), dtype=int)
    pos = 0
    for b_idx, df_b in enumerate(block_dfs, start=1):
        block_ids[pos : pos + len(df_b)] = b_idx
        pos += len(df_b)
    df["block"] = block_ids

    # time_abs: each block shifted by the cumulative offset, advanced by
    # one sample interval at every boundary so consecutive samples in
    # different blocks never share a time_abs.
    time_abs = np.empty(len(df), dtype=float)
    offset = 0.0
    pos = 0
    for b, df_b in zip(blocks, block_dfs, strict=True):
        sz = len(df_b)
        tb = df_b["Time"].to_numpy(float)
        tb0 = tb - tb[0]
        time_abs[pos : pos + sz] = tb0 + offset
        block_interval = b["meta"].get("Interval_s")
        if block_interval is None:
            block_interval = float(np.median(np.diff(tb0))) if len(tb0) > 1 else 0.0
        offset += tb0[-1] + block_interval
        pos += sz
    df["time_abs"] = time_abs
    df["time_block"] = df["Time"] - df.groupby("block")["Time"].transform("first")

    meta: dict[str, object] = dict(blocks[0]["meta"])
    # ChannelTitle becomes the columns; Range/TopValue/BottomValue vary
    # per block and live under meta["blocks"].
    for k in ("ChannelTitle", "Range", "TopValue", "BottomValue"):
        meta.pop(k, None)
    unit_names = blocks[0]["meta"].get("UnitName")
    if not (unit_names and len(unit_names) == n_cols - 1):
        meta.pop("UnitName", None)
    meta["blocks"] = [b["meta"] for b in blocks]

    return df, meta


def _parse_header_line(ln: str, target: dict[str, object]) -> bool:
    """Write a recognized ``Key=...`` header into ``target``. Returns True iff matched."""
    for prefix in _HEADER_KEYS_SCALAR:
        if ln.startswith(prefix):
            target[prefix.rstrip("=")] = (
                ln.split("\t", 1)[1].strip() if "\t" in ln else ""
            )
            return True
    for prefix in _HEADER_KEYS_LIST:
        if ln.startswith(prefix):
            target[prefix.rstrip("=")] = [c.strip() for c in ln.split("\t")[1:]]
            return True
    return False


def _finalize_block_meta(meta: dict[str, object]) -> None:
    """Add ``Interval_s`` derived from ``Interval`` if present and parseable."""
    if "Interval" in meta and "Interval_s" not in meta:
        try:
            meta["Interval_s"] = float(str(meta["Interval"]).split()[0])
        except (ValueError, IndexError, AttributeError):
            pass


def _segment_into_blocks(lines: list[str]) -> list[dict[str, object]]:
    """Split ``lines`` into per-block ``{meta, data_lines}`` dicts.

    Block boundaries: (a) header line after data lines, (b) ``Time`` resets
    inside a contiguous data run. On (b), metadata is shallow-copied so
    the sub-block carries the parent section's metadata.
    """
    blocks: list[dict[str, object]] = []
    current_meta: dict[str, object] = {}
    current_data: list[str] = []
    last_time: float | None = None
    in_data = False

    for ln in lines:
        if ln.startswith(_ALL_HEADER_PREFIXES):
            if in_data:
                _finalize_block_meta(current_meta)
                blocks.append({"meta": current_meta, "data_lines": current_data})
                current_meta = {}
                current_data = []
                last_time = None
                in_data = False
            _parse_header_line(ln, current_meta)
            continue

        if not ln.strip():
            continue

        first_token = ln.split("\t", 1)[0]
        if not FLOAT_START.match(first_token):
            continue
        try:
            t = float(first_token)
        except ValueError:
            continue

        if in_data and last_time is not None and t < last_time:
            _finalize_block_meta(current_meta)
            blocks.append({"meta": dict(current_meta), "data_lines": current_data})
            current_data = []

        current_data.append(ln)
        last_time = t
        in_data = True

    if in_data:
        _finalize_block_meta(current_meta)
        blocks.append({"meta": current_meta, "data_lines": current_data})

    return blocks


def _validate_channel_consistency(blocks: list[dict[str, object]]) -> None:
    """Raise FileParsingError if ``ChannelTitle`` differs between blocks."""
    ref = blocks[0]["meta"].get("ChannelTitle")
    if ref is None:
        return
    for i, b in enumerate(blocks[1:], start=2):
        ct = b["meta"].get("ChannelTitle")
        if ct is not None and ct != ref:
            raise FileParsingError(
                "ChannelTitle differs between blocks "
                f"(block 1: {ref}; block {i}: {ct}). "
                "Cannot align channels into a single DataFrame."
            )


def _parse_block_data(
    data_lines: list[str],
    cols: list[str],
    n_cols: int,
) -> pd.DataFrame:
    """Bulk-parse one block's data lines into a DataFrame.

    Classification pass identifies full-width numeric rows, short comment
    rows (``time + comment text``, narrower than a data row), and skips
    out-of-place lines. The numeric portion is loaded with one
    ``pd.read_csv`` call; ``pd.to_numeric(errors="coerce")`` per column
    then turns any unparseable cell into ``NaN`` without dropping the row.
    """
    numeric_lines: list[str] = []
    comments: list[str | None] = []

    for ln in data_lines:
        parts = ln.split("\t")

        if len(parts) < n_cols:
            try:
                float(parts[0])
            except ValueError:
                continue
            c = "\t".join(parts[1:]).strip()
            if c.startswith("#*"):
                c = c[2:].lstrip()
            numeric_lines.append("\t".join([parts[0]] + [""] * (n_cols - 1)))
            comments.append(c or None)
            continue

        first_val = parts[0].strip()
        if first_val in ("*", ""):
            continue
        try:
            float(first_val)
        except ValueError:
            continue

        numeric_lines.append("\t".join(parts[:n_cols]))
        extras = parts[n_cols:]
        if extras:
            c = "\t".join(extras).strip()
            if c.startswith("#*"):
                c = c[2:].lstrip()
            comments.append(c or None)
        else:
            comments.append(None)

    if not numeric_lines:
        return pd.DataFrame({c: [] for c in (*cols, "Comment")})

    df = pd.read_csv(
        io.StringIO("\n".join(numeric_lines)),
        sep="\t",
        header=None,
        names=cols,
        dtype=str,
        na_values=["*"],
    )
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["Comment"] = comments
    return df


__all__ = ["parse_labchart_txt"]
