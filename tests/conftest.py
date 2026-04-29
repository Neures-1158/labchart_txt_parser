"""Pytest configuration and shared fixtures for labchart_parser tests."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def examples_data_dir():
    """Return the path to the examples/data directory."""
    return Path(__file__).parent.parent / "examples" / "data"


@pytest.fixture(scope="session")
def example_file_path(examples_data_dir):
    """Return the path to the main example file."""
    return examples_data_dir / "labchart_file.example.txt"
