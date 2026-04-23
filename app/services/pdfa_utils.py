import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PDFAConversionError(Exception):
    """Raised when PDF/A conversion fails."""


def _find_ghostscript() -> Optional[str]:
    for candidate in ("gs", "gswin64c", "gswin32c"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def convert_pdf_to_pdfa(input_path: str, output_path: str) -> None:
    """Convert a PDF file to PDF/A using Ghostscript."""
    gs_path = _find_ghostscript()
    if not gs_path:
        raise PDFAConversionError("Ghostscript (gs) not available for PDF/A conversion")

    input_file = str(Path(input_path))
    output_file = str(Path(output_path))

    command = [
        gs_path,
        "-dPDFA=2",
        "-dBATCH",
        "-dNOPAUSE",
        "-dNOOUTERSAVE",
        "-sDEVICE=pdfwrite",
        "-sProcessColorModel=DeviceRGB",
        "-sColorConversionStrategy=RGB",
        "-sColorConversionStrategyForImages=RGB",
        "-dPDFACompatibilityPolicy=1",
        f"-sOutputFile={output_file}",
        input_file,
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        if result.stderr:
            logger.info("Ghostscript PDF/A output: %s", result.stderr.strip())
    except subprocess.CalledProcessError as exc:
        error_text = (exc.stderr or exc.stdout or "").strip()
        raise PDFAConversionError(
            f"PDF/A conversion failed: {error_text or 'unknown error'}"
        ) from exc

    output = Path(output_file)
    if not output.exists() or output.stat().st_size == 0:
        raise PDFAConversionError("PDF/A conversion produced an empty file")
