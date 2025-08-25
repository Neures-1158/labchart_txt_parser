from .parser import parse_labchart_txt
from .exceptions import FileParsingError, InvalidChannelError

class LabChartFile:
    def __init__(self, df, meta):
        self._data = df
        self._metadata = meta

    @classmethod
    def from_file(cls, path: str) -> "LabChartFile":
        df, meta = parse_labchart_txt(path)
        return cls(df, meta)

    @property
    def metadata(self):
        return self._metadata

    @property
    def channels(self):
        return [c for c in self._data.columns
                if c not in ("Time", "time_block", "time_abs", "block", "Comment")]

    @property
    def blocks(self):
        return list(self._data["block"].unique())

    @property
    def comments(self):
        return self._data[self._data["Comment"].notna()][["Time", "time_block", "time_abs", "block", "Comment"]].reset_index(drop=True)

    def get_block_df(self, b: int):
        return self._data.loc[self._data["block"] == b, ["Time", "time_block", "time_abs", "Comment", *self.channels]]

    def get_channel(self, b: int, channel: str):
        if channel not in self.channels:
            raise InvalidChannelError(f"Canal inconnu: {channel}")
        d = self._data.loc[self._data["block"] == b, ["Time", "time_block", "time_abs", "Comment", channel]].copy()
        d.rename(columns={channel: "value"}, inplace=True)
        return d

    def slice_time_abs(self, tmin: float, tmax: float):
        m = (self._data["time_abs"] >= tmin) & (self._data["time_abs"] <= tmax)
        return self._data.loc[m, ["Time", "time_block", "time_abs", "block", "Comment", *self.channels]]