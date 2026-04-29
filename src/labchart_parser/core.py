"""High-level API: ``LabChartFile`` wraps the parsed DataFrame + metadata."""

from __future__ import annotations

import os
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from .exceptions import InvalidChannelError
from .parser import parse_labchart_txt

_SYSTEM_COLS = ("Time", "time_block", "time_abs", "block", "Comment")


class LabChartFile:
    """Parsed LabChart text export. Construct with ``LabChartFile.from_file(path)``."""

    def __init__(self, df: pd.DataFrame, meta: dict[str, Any]) -> None:
        self._data = df
        self._metadata = meta

    @classmethod
    def from_file(cls, path: str | os.PathLike[str]) -> LabChartFile:
        """Parse a LabChart ``.txt`` export."""
        df, meta = parse_labchart_txt(path)
        return cls(df, meta)

    @property
    def metadata(self) -> dict[str, Any]:
        return self._metadata

    @property
    def channels(self) -> list[str]:
        """Channel names — every column in ``_data`` except the system columns.

        If you add a new computed column, add it to ``_SYSTEM_COLS`` too,
        otherwise it leaks into the user-visible channel list.
        """
        return [c for c in self._data.columns if c not in _SYSTEM_COLS]

    @property
    def blocks(self) -> list[int]:
        return list(self._data["block"].unique())

    @property
    def comments(self) -> pd.DataFrame:
        """Rows with a non-null ``Comment``, columns: ``Time, time_block, time_abs, block, Comment``."""
        return self._data[self._data["Comment"].notna()][
            ["Time", "time_block", "time_abs", "block", "Comment"]
        ].reset_index(drop=True)

    def get_block_comments_excluding(
        self, block: int, exclude_values: list
    ) -> list[str]:
        """Comments in ``block``, with case-insensitive exclusion of ``exclude_values``."""
        comments = self.comments
        comments_block = comments[comments["block"] == block]
        excluded = {str(v).strip().casefold() for v in exclude_values}
        norm = comments_block["Comment"].str.strip().str.casefold()
        return comments_block.loc[~norm.isin(excluded), "Comment"].tolist()

    def get_block_df(self, b: int) -> pd.DataFrame:
        """Slice of ``_data`` where ``block == b``. Index is **not** reset."""
        return self._data.loc[
            self._data["block"] == b,
            ["Time", "time_block", "time_abs", "Comment", *self.channels],
        ]

    def get_channel(self, b: int, channel: str) -> pd.DataFrame:
        """Slice for one ``channel`` in block ``b``. Channel column is renamed to ``value``."""
        if channel not in self.channels:
            raise InvalidChannelError(f"Unknown channel: {channel}")
        d = self._data.loc[
            self._data["block"] == b,
            ["Time", "time_block", "time_abs", "Comment", channel],
        ].copy()
        d.rename(columns={channel: "value"}, inplace=True)
        return d

    def slice_time_abs(self, tmin: float, tmax: float) -> pd.DataFrame:
        """Rows with ``tmin <= time_abs <= tmax`` (both ends inclusive)."""
        m = (self._data["time_abs"] >= tmin) & (self._data["time_abs"] <= tmax)
        return self._data.loc[
            m, ["Time", "time_block", "time_abs", "block", "Comment", *self.channels]
        ]

    def plot_channel(
        self,
        channel: str,
        block: int | None = None,
        time_col: str = "time_block",
        ax: Any | None = None,
        figsize: tuple = (10, 4),
        title: str | None = None,
        xlabel: str | None = None,
        ylabel: str | None = None,
        grid: bool = True,
        **kwargs,
    ) -> Any:
        """Plot ``channel`` (one block or all). Returns the ``Axes``.

        ``time_col`` is one of ``"Time"``, ``"time_block"``, ``"time_abs"``.
        Extra ``**kwargs`` are forwarded to ``ax.plot``.
        """
        if channel not in self.channels:
            raise InvalidChannelError(f"Unknown channel: {channel}")

        if block is not None:
            df = self.get_block_df(block)
            block_label = f"Block {block}"
        else:
            df = self._data
            block_label = "All blocks"

        if ax is None:
            _, ax = plt.subplots(figsize=figsize)

        ax.plot(df[time_col], df[channel], **kwargs)
        ax.set_title(title or f"{channel} – {block_label}")
        ax.set_xlabel(
            xlabel
            or {
                "Time": "Time (s)",
                "time_block": "Time in block (s)",
                "time_abs": "Absolute time (s)",
            }.get(time_col, time_col)
        )
        ax.set_ylabel(ylabel or channel)
        if grid:
            ax.grid(True)
        ax.figure.tight_layout()
        return ax
