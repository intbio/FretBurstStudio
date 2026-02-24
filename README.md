# FretBurstStudio

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.x-blue)](https://www.python.org/)

FretBurstStudio is a software tool for analyzing single-molecule FRET (Förster Resonance Energy Transfer) data using a burst analysis approach. This repository contains the source code and related resources for the application.

## About

**FretBurstStudio** aims to provide a graphical user interface (GUI) for the analysis of single-molecule fluorescence data, specifically focusing on identifying bursts and calculating FRET efficiencies.

The project is built primarily with **Python (98.7%)** and is developed by contributors from the intbio group.

## Key Features (Inferred from Structure)

*   **Graphical User Interface:** Located in the `src/fretGUI` directory, suggesting a user-friendly interface for data analysis.
*   **Burst Analysis:** The name implies functionality for identifying and analyzing single-molecule bursts from fluorescence data.
*   **Modular Design:** The code structure with nodes (e.g., `bg node`, `AbstractContentNode`) points towards a modular, pipeline-based analysis workflow.
*   **Sample Data:** Includes `samle_files/lsm510` (note: "samle" is a typo in the original path) with example data for testing or demonstration.
*   **Windows Executable:** The `pyinstaller` directory contains scripts to build a standalone Windows executable, making it easier to run without a Python environment.

## Installation

You can run FretBurstStudio from source or use the provided scripts to build an executable.

### From Source

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/intbio/FretBurstStudio.git
    cd FretBurstStudio
    ```
2.  **Set up the environment:**
    It is recommended to use conda with the provided `environment.yml` file:
    ```bash
    conda env create -f environment.yml
    conda activate fretburststudio
    ```
    Alternatively, you can install dependencies using pip:
    ```bash
    pip install -r requirements.txt
    ```

### Building Executable (Windows)

To build a standalone Windows executable, navigate to the `pyinstaller` directory and run the appropriate script. This bundles the application so it can be run without a Python installation.

## Usage

After installation, you can run the application by executing the main script from the `src` directory.
```bash
python3 src/fretGUI/main.py
