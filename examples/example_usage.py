"""Example usage of the LabChart parser API.

Demonstrates loading a LabChart export, inspecting metadata, channels,
blocks, and comments, and plotting a channel with the high-level
``plot_channel`` method. The path used here assumes the exported text
file is at ``examples/data/labchart_file.example.txt`` relative to the
project root.
"""

import matplotlib.pyplot as plt
from labchart_parser import LabChartFile


def main():
    lc = LabChartFile.from_file("examples/data/labchart_file.example.txt")

    print("Metadata:", lc.metadata)
    print("Channels:", lc.channels)
    print("Number of blocks:", len(lc.blocks))
    print("Comments:")
    print(lc.comments.head())

    event = lc.get_block_comments_excluding(1, exclude_values=["INSPI", "EXPI"])[0]
    print("First comment in block 1 excluding INSPI/EXPI:", event)

    # Plot a single channel from a single block — replaces the manual
    # plt.figure / plt.plot pair from earlier versions.
    lc.plot_channel("Flow", block=1, figsize=(8, 3))
    lc.plot_channel("Pressure", block=1, color="tomato", figsize=(8, 3))

    plt.show()


if __name__ == "__main__":
    main()
