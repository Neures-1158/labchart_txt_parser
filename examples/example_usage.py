"""Example usage of the LabChart parser API.

This script demonstrates how to load a LabChart export, access its
metadata, channels, blocks and comments, and how to plot a single
channel from a specific block. The file path used here assumes the
exported text file is located in ``examples/data/labchart_file.example.txt``
relative to the project root.
"""

from labchart_parser import LabChartFile
import matplotlib.pyplot as plt
import pandas as pd

def main():
    # Load the exported file
    lc = LabChartFile.from_file("examples/data/labchart_file.example.txt")
    # lc = LabChartFile.from_file("examples/data/labchart_file_negTime.txt")


    # Display metadata and column preview
    print("Metadata:", lc.metadata)
    print("Channels:", lc.channels)
    print("Number of blocks:", len(lc.blocks))
    print("Comments:")
    print(lc.comments.head())

    # Get df from block 1
    df_bloc1 = lc.get_block_df(1)
    # Plot pressure (channel "Pressure") for block 1
    plt.figure(figsize=(5, 2))
    plt.grid(True)
    plt.plot(df_bloc1["Time"], df_bloc1["Flow"])


    # Get pressure (channel "Pressure") for block 1
    pressure_df = lc.get_channel(1, "Pressure")
    plt.figure(figsize=(5, 2))
    plt.plot(pressure_df["Time"], pressure_df["value"])
    plt.grid(True)
    plt.tight_layout()
    plt.show()
    
    
if __name__ == "__main__":
    main()
