# Piky

PDF processing tools powered by coverup-pdf and pikepdf.

## Prerequisites

- Python 3.14
- [PDM](https://pdm-project.org/) (Python package manager)
- Tk library for Python (required by coverup-pdf's GUI)
- Poppler for preview

### Install package deps (macOS)

```bash
brew install python-tk@3.14
```

```bash
brew install poppler
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

Do common operations on PDFs:

```bash
pdm run invoke piky
```
