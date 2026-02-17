# pdftools

PDF processing tools powered by [coverup-pdf](https://pypi.org/project/coverup-pdf/).

## Prerequisites

- Python 3.14
- [PDM](https://pdm-project.org/) (Python package manager)
- Tk library for Python (required by coverup-pdf's GUI)

### Install Tk (macOS)

```bash
brew install python-tk@3.14
```

### Install Tk (Ubuntu/Debian)

```bash
sudo apt install python3-tk
```

## Setup

```bash
pdm install
```

## Usage

Start coverup on a directory of PDFs:

```bash
pdm run invoke coverup --pdf-dir /path/to/pdfs
```
