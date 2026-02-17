import shlex

from invoke import task


@task(help={"pdf_dir": "Path to the directory containing PDF files"})
def coverup(ctx, pdf_dir):
    """Start coverup on a PDF directory."""
    ctx.run(f"pdm run coverup {shlex.quote(pdf_dir)}")


@task(help={})
def piky(ctx):
    """Launch the PDF tool UI (piky)."""
    ctx.run("pdm run python pdf_tool_ui.py")
