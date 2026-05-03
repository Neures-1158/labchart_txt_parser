"""Tests for the low-level parser module."""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from labchart_parser.exceptions import FileParsingError
from labchart_parser.parser import parse_labchart_txt

# Path to the example data file
EXAMPLE_FILE = (
    Path(__file__).parent.parent / "examples" / "data" / "labchart_file.example.txt"
)
EXAMPLE_FILE_NEG_TIME = (
    Path(__file__).parent.parent / "examples" / "data" / "labchart_file_negTime.txt"
)


class TestParseLabchartTxt:
    """Tests for parse_labchart_txt function."""

    def test_parse_returns_dataframe_and_dict(self):
        """parse_labchart_txt should return a tuple of (DataFrame, dict)."""
        df, meta = parse_labchart_txt(str(EXAMPLE_FILE))
        assert isinstance(df, pd.DataFrame)
        assert isinstance(meta, dict)

    def test_dataframe_has_required_columns(self):
        """Parsed DataFrame should have Time, block, time_abs, time_block, Comment columns."""
        df, _ = parse_labchart_txt(str(EXAMPLE_FILE))
        required_cols = {"Time", "block", "time_abs", "time_block", "Comment"}
        assert required_cols.issubset(set(df.columns))

    def test_dataframe_has_channel_columns(self):
        """Parsed DataFrame should have at least one channel column."""
        df, _ = parse_labchart_txt(str(EXAMPLE_FILE))
        channel_cols = [
            c
            for c in df.columns
            if c not in ("Time", "time_block", "time_abs", "block", "Comment")
        ]
        assert len(channel_cols) > 0

    def test_block_column_is_integer(self):
        """Block column should contain integers."""
        df, _ = parse_labchart_txt(str(EXAMPLE_FILE))
        assert pd.api.types.is_integer_dtype(df["block"])

    def test_time_columns_are_float(self):
        """Time columns should be numeric (float)."""
        df, _ = parse_labchart_txt(str(EXAMPLE_FILE))
        assert pd.api.types.is_float_dtype(df["Time"])
        assert pd.api.types.is_float_dtype(df["time_abs"])
        assert pd.api.types.is_float_dtype(df["time_block"])

    def test_metadata_contains_interval(self):
        """Metadata should contain Interval if present in file."""
        _, meta = parse_labchart_txt(str(EXAMPLE_FILE))
        # Interval is typically present in LabChart exports
        assert "Interval" in meta or "Interval_s" in meta

    def test_time_block_starts_at_zero_for_each_block(self):
        """time_block should start at 0.0 for each block."""
        df, _ = parse_labchart_txt(str(EXAMPLE_FILE))
        for block in df["block"].unique():
            block_df = df[df["block"] == block]
            assert block_df["time_block"].iloc[0] == pytest.approx(0.0, abs=1e-9)

    def test_time_abs_is_strictly_monotonic(self):
        """time_abs must be strictly increasing — no duplicates at block boundaries."""
        df, _ = parse_labchart_txt(str(EXAMPLE_FILE))
        time_abs = df["time_abs"].to_numpy()
        diffs = np.diff(time_abs)
        assert np.all(diffs > 0), (
            "time_abs has non-strict steps "
            f"(min diff = {diffs.min()}); block-boundary stitching may have regressed"
        )

    def test_file_not_found_raises_error(self):
        """Parsing a non-existent file should raise an error."""
        with pytest.raises(FileNotFoundError):
            parse_labchart_txt("non_existent_file.txt")

    def test_negative_time_file_parses_correctly(self):
        """File with negative time values should parse without error."""
        if EXAMPLE_FILE_NEG_TIME.exists():
            df, meta = parse_labchart_txt(str(EXAMPLE_FILE_NEG_TIME))
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0


class TestParserEdgeCases:
    """Edge case tests for the parser."""

    def test_empty_comments_are_none(self):
        """Rows without comments should have Comment as None or NaN."""
        df, _ = parse_labchart_txt(str(EXAMPLE_FILE))
        # At least some rows should have no comment
        assert df["Comment"].isna().any()

    def test_blocks_are_one_indexed(self):
        """Block numbers should start at 1."""
        df, _ = parse_labchart_txt(str(EXAMPLE_FILE))
        assert df["block"].min() == 1

    def test_accepts_path_object(self):
        """parse_labchart_txt should accept a Path, not just a string."""
        df, _ = parse_labchart_txt(EXAMPLE_FILE)
        assert isinstance(df, pd.DataFrame)


class TestParserErrorPaths:
    """Tests for the parser's error paths."""

    def test_unsupported_extension_raises(self, tmp_path):
        bad = tmp_path / "recording.csv"
        bad.write_text("Time\tCh1\n0.0\t1.0\n")
        with pytest.raises(FileParsingError, match="Unsupported file extension"):
            parse_labchart_txt(str(bad))

    def test_empty_file_raises(self, tmp_path):
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        with pytest.raises(FileParsingError, match="empty"):
            parse_labchart_txt(str(empty))

    def test_no_data_section_raises(self, tmp_path):
        header_only = tmp_path / "header_only.txt"
        header_only.write_text(
            "Interval=\t0.001 s\n" "ChannelTitle=\tFlow\n" "UnitName=\tL/s\n"
        )
        with pytest.raises(FileParsingError, match="Data start not found"):
            parse_labchart_txt(str(header_only))

    def test_single_column_raises(self, tmp_path):
        single_col = tmp_path / "single.txt"
        single_col.write_text("0.0\n0.001\n0.002\n")
        with pytest.raises(FileParsingError, match="at least Time"):
            parse_labchart_txt(str(single_col))

    def test_unparseable_channel_becomes_nan(self, tmp_path):
        """Per-cell parse failures yield NaN; rows are not silently dropped (A2)."""
        path = tmp_path / "bad_cells.txt"
        path.write_text(
            "Interval=\t0.001 s\n"
            "ChannelTitle=\tFlow\n"
            "+0.000\toops\n"
            "+0.001\toops\n"
        )
        df, _ = parse_labchart_txt(str(path))
        assert len(df) == 2
        # Time column survives, channel column is NaN, Comment stays None
        # (the bad cell is no longer promoted into Comment).
        assert df["Time"].tolist() == [0.0, 0.001]
        assert df["Flow"].isna().all()
        assert df["Comment"].isna().all()

    def test_mid_row_bad_cell_preserves_other_channels(self, tmp_path):
        """A bad cell in a multi-channel row only NaNs that cell, not the row (A2)."""
        path = tmp_path / "mid_bad.txt"
        path.write_text(
            "Interval=\t0.001 s\n"
            "ChannelTitle=\tFlow\tPressure\tEMG\n"
            "0.000\t1.0\t2.0\t3.0\n"
            "0.001\t1.5\tBAD\t3.5\n"
            "0.002\t2.0\t4.0\t5.0\n"
        )
        df, _ = parse_labchart_txt(str(path))
        assert len(df) == 3
        # Pressure on row 1 should be NaN; the surrounding Flow / EMG must survive.
        assert df["Flow"].tolist() == [1.0, 1.5, 2.0]
        assert df["EMG"].tolist() == [3.0, 3.5, 5.0]
        assert df["Pressure"].iloc[0] == 2.0
        assert pd.isna(df["Pressure"].iloc[1])
        assert df["Pressure"].iloc[2] == 4.0


class TestParserBlockBoundaries:
    """A1: time_abs must advance by one sample interval at each block boundary."""

    def test_block_boundary_advances_by_interval(self, tmp_path):
        path = tmp_path / "two_block.txt"
        # Two blocks, 0.001 s sample interval, 3 samples each.
        # Block 1: t=0.000, 0.001, 0.002 ; Block 2: t=0.000, 0.001, 0.002 .
        path.write_text(
            "Interval=\t0.001 s\n"
            "TimeFormat=\tStartOfBlock\n"
            "ChannelTitle=\tFlow\n"
            "0.000\t1.0\n"
            "0.001\t2.0\n"
            "0.002\t3.0\n"
            "0.000\t4.0\n"
            "0.001\t5.0\n"
            "0.002\t6.0\n"
        )
        df, meta = parse_labchart_txt(str(path))
        assert len(df["block"].unique()) == 2
        time_abs = df["time_abs"].to_numpy()
        # Strictly monotonic, including at the block boundary.
        assert np.all(np.diff(time_abs) > 0)
        # First sample of block 2 = last sample of block 1 + interval.
        assert time_abs[3] == pytest.approx(time_abs[2] + meta["Interval_s"], abs=1e-12)


class TestParserEncoding:
    """B1: utf-8 first, latin-1 fallback. Bytes must not be silently dropped."""

    def test_latin1_fallback_preserves_french_comment(self, tmp_path):
        """A cp1252-encoded file containing 'Inspiration forcée' must round-trip."""
        path = tmp_path / "fr.txt"
        body = (
            "Interval=\t0.001 s\n"
            "ChannelTitle=\tFlow\n"
            "0.000\t1.0\n"
            "0.001\t2.0\tInspiration forcée\n"
            "0.002\t3.0\n"
        )
        # Write as cp1252 — utf-8 decoding will raise UnicodeDecodeError on 'é'.
        path.write_bytes(body.encode("cp1252"))
        df, _ = parse_labchart_txt(str(path))
        comments = df["Comment"].dropna().tolist()
        assert "Inspiration forcée" in comments


class TestParserTimeFormatWarning:
    """B2: warn when TimeFormat is not StartOfBlock (block detection degrades)."""

    def test_continuous_time_format_emits_warning(self, tmp_path):
        path = tmp_path / "continuous.txt"
        path.write_text(
            "Interval=\t0.001 s\n"
            "TimeFormat=\tContinuous\n"
            "ChannelTitle=\tFlow\n"
            "0.000\t1.0\n"
            "0.001\t2.0\n"
        )
        with pytest.warns(UserWarning, match="StartOfBlock"):
            parse_labchart_txt(str(path))

    def test_start_of_block_does_not_warn(self, tmp_path):
        path = tmp_path / "sob.txt"
        path.write_text(
            "Interval=\t0.001 s\n"
            "TimeFormat=\tStartOfBlock\n"
            "ChannelTitle=\tFlow\n"
            "0.000\t1.0\n"
            "0.001\t2.0\n"
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warning becomes a failure
            parse_labchart_txt(str(path))


class TestParserMetaBlocks:
    """A3: per-block metadata is exposed under meta["blocks"]."""

    def test_canonical_fixture_exposes_per_block_metadata(self):
        """The shipped multi-block fixture has 6 metadata sections (verified
        via ``grep -c ^Interval= examples/data/labchart_file.example.txt``)."""
        _, meta = parse_labchart_txt(str(EXAMPLE_FILE))
        assert isinstance(meta["blocks"], list)
        assert len(meta["blocks"]) == 6
        for entry in meta["blocks"]:
            assert "Interval" in entry
            assert "Interval_s" in entry
            # Per-block list metadata should also be preserved.
            assert "Range" in entry

    def test_per_block_intervals_when_blocks_differ(self, tmp_path):
        """Each metadata section's Interval is preserved per-block."""
        path = tmp_path / "mixed.txt"
        # Two blocks, with different sample intervals declared per section.
        path.write_text(
            "Interval=\t0.001 s\n"
            "TimeFormat=\tStartOfBlock\n"
            "ChannelTitle=\tFlow\n"
            "0.000\t1.0\n"
            "0.001\t2.0\n"
            "0.002\t3.0\n"
            "Interval=\t0.010 s\n"
            "TimeFormat=\tStartOfBlock\n"
            "ChannelTitle=\tFlow\n"
            "0.000\t4.0\n"
            "0.010\t5.0\n"
            "0.020\t6.0\n"
        )
        df, meta = parse_labchart_txt(str(path))
        assert len(meta["blocks"]) == 2
        assert meta["blocks"][0]["Interval_s"] == pytest.approx(0.001)
        assert meta["blocks"][1]["Interval_s"] == pytest.approx(0.010)
        # time_abs stitching uses each block's own interval at the boundary.
        time_abs = df["time_abs"].to_numpy()
        assert time_abs[3] == pytest.approx(time_abs[2] + 0.001, abs=1e-12)

    def test_time_jump_within_single_metadata_section_creates_block(self, tmp_path):
        """One header section but two time-reset runs → two blocks, shared meta."""
        path = tmp_path / "single_section.txt"
        path.write_text(
            "Interval=\t0.001 s\n"
            "TimeFormat=\tStartOfBlock\n"
            "ChannelTitle=\tFlow\n"
            "0.000\t1.0\n"
            "0.001\t2.0\n"
            "0.000\t3.0\n"
            "0.001\t4.0\n"
        )
        df, meta = parse_labchart_txt(str(path))
        assert len(meta["blocks"]) == 2
        assert df["block"].unique().tolist() == [1, 2]
        # Both blocks share the same Interval since metadata wasn't re-emitted.
        assert (
            meta["blocks"][0]["Interval"] == meta["blocks"][1]["Interval"] == "0.001 s"
        )

    def test_channel_title_mismatch_between_blocks_raises(self, tmp_path):
        """Different ChannelTitle per block produces a misaligned DataFrame."""
        path = tmp_path / "mismatch.txt"
        path.write_text(
            "Interval=\t0.001 s\n"
            "ChannelTitle=\tFlow\tPressure\n"
            "0.000\t1.0\t2.0\n"
            "Interval=\t0.001 s\n"
            "ChannelTitle=\tEMG\tVolume\n"
            "0.000\t3.0\t4.0\n"
        )
        with pytest.raises(FileParsingError, match="ChannelTitle differs"):
            parse_labchart_txt(str(path))


class TestParserBulk:
    """B4: smoke-test the bulk read_csv path on a moderately large file.

    No timing assertion (flaky in CI). Just confirms shape and block id."""

    def test_large_synthetic_file_parses(self, tmp_path):
        rows = 50_000
        path = tmp_path / "big.txt"
        with path.open("w") as f:
            f.write(
                "Interval=\t0.001 s\n"
                "TimeFormat=\tStartOfBlock\n"
                "ChannelTitle=\tA\tB\tC\tD\tE\n"
            )
            for i in range(rows):
                f.write(f"{i * 0.001:.6f}\t1.0\t2.0\t3.0\t4.0\t5.0\n")
        df, meta = parse_labchart_txt(str(path))
        assert df.shape == (
            rows,
            1 + 5 + 1 + 2 + 1,
        )  # Time+5ch+Comment+block+time_abs+time_block
        assert df["block"].unique().tolist() == [1]
        assert meta["Interval_s"] == pytest.approx(0.001)
