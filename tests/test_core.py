"""Tests for the LabChartFile class in core module."""

from pathlib import Path

import pandas as pd
import pytest

from labchart_parser.core import LabChartFile
from labchart_parser.exceptions import InvalidChannelError

# Path to the example data file
EXAMPLE_FILE = (
    Path(__file__).parent.parent / "examples" / "data" / "labchart_file.example.txt"
)


@pytest.fixture
def lab_file():
    """Fixture providing a loaded LabChartFile instance."""
    return LabChartFile.from_file(str(EXAMPLE_FILE))


class TestLabChartFileLoading:
    """Tests for LabChartFile loading and initialization."""

    def test_from_file_returns_instance(self, lab_file):
        """from_file should return a LabChartFile instance."""
        assert isinstance(lab_file, LabChartFile)

    def test_from_file_nonexistent_raises_error(self):
        """from_file with non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            LabChartFile.from_file("nonexistent_file.txt")


class TestLabChartFileProperties:
    """Tests for LabChartFile properties."""

    def test_metadata_is_dict(self, lab_file):
        """metadata property should return a dictionary."""
        assert isinstance(lab_file.metadata, dict)

    def test_channels_is_list(self, lab_file):
        """channels property should return a list."""
        assert isinstance(lab_file.channels, list)

    def test_channels_contains_strings(self, lab_file):
        """channels should contain string channel names."""
        for ch in lab_file.channels:
            assert isinstance(ch, str)

    def test_channels_excludes_system_columns(self, lab_file):
        """channels should not include Time, block, time_abs, time_block, Comment."""
        system_cols = {"Time", "block", "time_abs", "time_block", "Comment"}
        assert not any(ch in system_cols for ch in lab_file.channels)

    def test_blocks_is_list(self, lab_file):
        """blocks property should return a list."""
        assert isinstance(lab_file.blocks, list)

    def test_blocks_contains_integers(self, lab_file):
        """blocks should contain integer block numbers."""
        for b in lab_file.blocks:
            assert isinstance(b, int)

    def test_canonical_fixture_has_multiple_blocks(self, lab_file):
        """The canonical fixture is multi-block; regression guard for block detection."""
        assert len(lab_file.blocks) > 1

    def test_comments_is_dataframe(self, lab_file):
        """comments property should return a DataFrame."""
        assert isinstance(lab_file.comments, pd.DataFrame)

    def test_comments_has_required_columns(self, lab_file):
        """comments DataFrame should have Time, time_block, time_abs, block, Comment columns."""
        required = {"Time", "time_block", "time_abs", "block", "Comment"}
        assert required == set(lab_file.comments.columns)


class TestLabChartFileGetBlockDf:
    """Tests for get_block_df method."""

    def test_get_block_df_returns_dataframe(self, lab_file):
        """get_block_df should return a DataFrame."""
        df = lab_file.get_block_df(1)
        assert isinstance(df, pd.DataFrame)

    def test_get_block_df_contains_all_channels(self, lab_file):
        """get_block_df should include all channel columns."""
        df = lab_file.get_block_df(1)
        for ch in lab_file.channels:
            assert ch in df.columns

    def test_get_block_df_filters_correct_block(self, lab_file):
        """get_block_df should only return rows whose block matches the request."""
        df = lab_file.get_block_df(1)
        assert len(df) > 0
        # Cross-reference against the underlying frame: same row count as block==1.
        expected_len = int((lab_file._data["block"] == 1).sum())
        assert len(df) == expected_len

    def test_get_block_df_includes_time_columns(self, lab_file):
        """get_block_df should include Time, time_block, time_abs columns."""
        df = lab_file.get_block_df(1)
        assert "Time" in df.columns
        assert "time_block" in df.columns
        assert "time_abs" in df.columns


class TestLabChartFileGetChannel:
    """Tests for get_channel method."""

    def test_get_channel_returns_dataframe(self, lab_file):
        """get_channel should return a DataFrame."""
        if lab_file.channels:
            df = lab_file.get_channel(1, lab_file.channels[0])
            assert isinstance(df, pd.DataFrame)

    def test_get_channel_has_value_column(self, lab_file):
        """get_channel should rename the channel column to 'value'."""
        if lab_file.channels:
            df = lab_file.get_channel(1, lab_file.channels[0])
            assert "value" in df.columns

    def test_get_channel_invalid_raises_error(self, lab_file):
        """get_channel with invalid channel name should raise InvalidChannelError."""
        with pytest.raises(InvalidChannelError):
            lab_file.get_channel(1, "NonExistentChannel")

    def test_get_channel_includes_time_columns(self, lab_file):
        """get_channel should include Time, time_block, time_abs, Comment columns."""
        if lab_file.channels:
            df = lab_file.get_channel(1, lab_file.channels[0])
            assert "Time" in df.columns
            assert "time_block" in df.columns
            assert "time_abs" in df.columns
            assert "Comment" in df.columns


class TestLabChartFileSliceTimeAbs:
    """Tests for slice_time_abs method."""

    def test_slice_time_abs_returns_dataframe(self, lab_file):
        """slice_time_abs should return a DataFrame."""
        df = lab_file.slice_time_abs(0.0, 1.0)
        assert isinstance(df, pd.DataFrame)

    def test_slice_time_abs_filters_correctly(self, lab_file):
        """slice_time_abs should only include rows within the time range."""
        df = lab_file.slice_time_abs(0.0, 1.0)
        if len(df) > 0:
            assert df["time_abs"].min() >= 0.0
            assert df["time_abs"].max() <= 1.0

    def test_slice_time_abs_empty_range_returns_empty(self, lab_file):
        """slice_time_abs with out-of-range times should return empty DataFrame."""
        df = lab_file.slice_time_abs(999999.0, 999999.1)
        assert len(df) == 0


class TestLabChartFileGetBlockCommentsExcluding:
    """Tests for get_block_comments_excluding method."""

    def test_returns_list(self, lab_file):
        """get_block_comments_excluding should return a list."""
        result = lab_file.get_block_comments_excluding(1, [])
        assert isinstance(result, list)

    def test_excludes_specified_values(self, lab_file):
        """get_block_comments_excluding should exclude specified values."""
        # Get all comments first
        all_comments = lab_file.get_block_comments_excluding(1, [])
        if all_comments:
            # Exclude the first comment
            excluded = lab_file.get_block_comments_excluding(1, [all_comments[0]])
            assert all_comments[0] not in excluded

    def test_case_insensitive_exclusion(self, lab_file):
        """Exclusion should be case-insensitive."""
        all_comments = lab_file.get_block_comments_excluding(1, [])
        if all_comments:
            # Try excluding with different case
            first_upper = all_comments[0].upper()
            excluded = lab_file.get_block_comments_excluding(1, [first_upper])
            # The original comment should not be in the result
            assert all_comments[0].strip().casefold() not in [
                c.strip().casefold() for c in excluded
            ]


class TestLabChartFilePlotChannel:
    """Tests for plot_channel method (uses the non-interactive Agg backend)."""

    def test_plot_channel_returns_axes(self, lab_file):
        matplotlib = pytest.importorskip("matplotlib")
        matplotlib.use("Agg", force=True)
        from matplotlib.axes import Axes

        ax = lab_file.plot_channel(lab_file.channels[0], block=1)
        assert isinstance(ax, Axes)

    def test_plot_channel_invalid_raises(self, lab_file):
        pytest.importorskip("matplotlib")
        from labchart_parser.exceptions import InvalidChannelError

        with pytest.raises(InvalidChannelError):
            lab_file.plot_channel("NonExistentChannel", block=1)


class TestLabChartFilePathInput:
    """Test that the API accepts Path-like inputs (not just str)."""

    def test_from_file_accepts_path(self):
        from pathlib import Path

        lc = LabChartFile.from_file(Path(EXAMPLE_FILE))
        assert isinstance(lc, LabChartFile)
