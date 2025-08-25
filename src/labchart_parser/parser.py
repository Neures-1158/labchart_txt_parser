"""Low-level parser for LabChart text exports.

This module defines a single function, :func:`parse_labchart_txt`, which
reads a tab-delimited text file exported from ADInstruments LabChart and
returns a pandas DataFrame and a dictionary of metadata.  The DataFrame
contains one row per sample and includes a ``Comment`` column that
captures annotation text for lines containing comments. Numeric sample
lines have ``Comment`` set to ``None``.

Additionally, the following columns are computed:

* ``block`` identifies the block of recording (starting at 1).
* ``time_abs`` provides continuous time across all blocks by stitching
  together relative times.
* ``time_block`` is the time within each block, re-based to start at 0.0
  for the first sample of the block (useful to align comment times exactly
  from zero within a block).
"""

from __future__ import annotations

import re
import math
from pathlib import Path
from typing import Tuple, Dict, List, Optional

import numpy as np
import pandas as pd

# Regular expression to detect a numeric field (float) in the first column
FLOAT_START = re.compile(r"^\s*[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?\s*$")


def parse_labchart_txt(path: str) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Parse an exported LabChart text file.

    The export must be tab-delimited and include a ``Time`` column. If
    comments were included during export, this parser will capture them in
    the resulting DataFrame.

    Parameters
    ----------
    path : str
        Path to the LabChart text file to parse.

    Returns
    -------
    Tuple[pandas.DataFrame, dict]
        A tuple ``(df, meta)`` where ``df`` contains the parsed data and
        ``meta`` holds the parsed metadata. ``df`` includes the columns:

        * ``Time`` – relative time within each block.
        * one column per channel detected in the header.
        * ``Comment`` – annotation text (``None`` on numeric rows).
        * ``block`` – block index (1-based).
        * ``time_abs`` – continuous time across blocks.

    Raises
    ------
    ValueError
        If the file cannot be parsed or if no data lines are found.
    """
    p = Path(path)
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()

    meta: Dict[str, object] = {}
    chan_titles: Optional[List[str]] = None
    unit_names: Optional[List[str]] = None
    first_data_idx: Optional[int] = None

    # Parse metadata lines before the data section
    for i, ln in enumerate(lines):
        if ln.startswith("Interval="):
            meta["Interval"] = ln.split("\t", 1)[1].strip()
        elif ln.startswith("ExcelDateTime="):
            meta["ExcelDateTime"] = ln.split("\t", 1)[1].strip()
        elif ln.startswith("TimeFormat="):
            meta["TimeFormat"] = ln.split("\t", 1)[1].strip()
        elif ln.startswith("DateFormat="):
            meta["DateFormat"] = ln.split("\t", 1)[1].strip()
        elif ln.startswith("ChannelTitle="):
            chan_titles = [c.strip() for c in ln.split("\t")[1:]]
        elif ln.startswith("UnitName="):
            unit_names = [c.strip() for c in ln.split("\t")[1:]]
        elif (ln and ln[0].isdigit()) or ln.startswith(("+", "-", ".")):
            # Potentially a data line; check first token is numeric
            if FLOAT_START.match(ln.split("\t", 1)[0]):
                first_data_idx = i
                break

    if first_data_idx is None:
        raise ValueError("Début des données introuvable.")

    # Determine number of columns from first data row
    first_row = lines[first_data_idx].split("\t")
    n_cols = len(first_row)

    data: List[List[object]] = []
    for ln in lines[first_data_idx:]:
        if not ln.strip():
            continue
        parts = ln.split("\t")

        # Identify the numeric part and any trailing comment part
        numeric_parts = parts[:n_cols]
        extra_parts = parts[n_cols:]

        # Try to parse the numeric fields; treat '*' and empty fields as NaN
        numeric_row: List[Optional[float]] = []
        is_numeric = True
        for x in numeric_parts:
            val = x.strip()
            if val in ("*", ""):
                numeric_row.append(math.nan)
            else:
                try:
                    numeric_row.append(float(val))
                except ValueError:
                    is_numeric = False
                    break

        # Assemble any extra fields into a comment string
        comment_text: Optional[str] = None
        if extra_parts:
            comment_text = "\t".join(extra_parts).strip()
            # Remove '#*' marker if present at the start of the comment
            if comment_text.startswith("#*"):
                comment_text = comment_text[2:].lstrip()

        if is_numeric:
            # Numeric row (with or without a trailing comment)
            numeric_row.append(comment_text)
            data.append(numeric_row)
        else:
            # Pure comment row: use time value and fill numeric columns with NaN
            try:
                t = float(parts[0])
            except ValueError:
                continue
            c_text = "\t".join(parts[1:]).strip()
            if c_text.startswith("#*"):
                c_text = c_text[2:].lstrip()
            row = [t] + [math.nan] * (n_cols - 1) + [c_text]
            data.append(row)

    if not data:
        raise ValueError("Aucune ligne de données valide après parsing.")

    # Construct DataFrame with appropriate column names
    if chan_titles and len(chan_titles) == (n_cols - 1):
        cols = ["Time"] + chan_titles
    else:
        cols = ["Time"] + [f"Ch{i}" for i in range(1, n_cols)]
    cols.append("Comment")
    df = pd.DataFrame(data, columns=cols)

    # Compute block indices and continuous time
    t = df["Time"].to_numpy(float)
    jumps = np.where(np.diff(t) < 0)[0] + 1
    starts = np.r_[0, jumps]
    ends = np.r_[jumps, len(df)]
    block_ids = np.empty(len(df), dtype=int)
    time_abs = np.empty(len(df), dtype=float)
    offset = 0.0
    for b, (s, e) in enumerate(zip(starts, ends), start=1):
        block_ids[s:e] = b
        tb = t[s:e]
        tb0 = tb - tb[0]
        time_abs[s:e] = tb0 + offset
        offset += tb0[-1] if len(tb0) else 0.0

    df["block"] = block_ids
    df["time_abs"] = time_abs
    # Zero-based time within each block (starts at 0.0 for every block)
    df["time_block"] = df["time_abs"] - df.groupby("block")["time_abs"].transform("min")

    # Additional metadata: convert interval to seconds if possible
    try:
        meta["Interval_s"] = float(str(meta.get("Interval", "")).split()[0])
    except Exception:
        pass
    if unit_names and len(unit_names) == (n_cols - 1):
        meta["UnitName"] = unit_names

    return df, meta