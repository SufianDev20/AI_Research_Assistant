"""
PDF extraction service for open-access papers.
Uses PyMuPDF4LLM to convert PDFs to LLM-ready Markdown.

References:
    https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html
    https://pymupdf.readthedocs.io/en/latest/document.html
"""

import logging
import os
import re
import tempfile

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

MAX_PDF_BYTES = 50 * 1024 * 1024
FETCH_TIMEOUT = 30


class PDFExtractionError(Exception):
    pass


class PDFService:
    """Fetch a PDF and extract LLM-ready markdown."""

    @staticmethod
    def fetch_and_extract(pdf_url: str, openalex_id: str) -> dict:
        """Fetch a PDF and extract its content into Markdown.

        Returns:
            dict with keys: markdown, page_count, image_paths, error
        """

        # 1) Fetch
        try:
            response = requests.get(
                pdf_url,
                timeout=FETCH_TIMEOUT,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                    "Accept": "application/pdf,*/*",
                },
                stream=True,
            )
            response.raise_for_status()

            content_length = int(response.headers.get("Content-Length", 0))
            if content_length > MAX_PDF_BYTES:
                raise PDFExtractionError(
                    f"PDF too large: {content_length} bytes (limit {MAX_PDF_BYTES})"
                )

            pdf_bytes = response.content
            if len(pdf_bytes) > MAX_PDF_BYTES:
                raise PDFExtractionError("PDF exceeds 50MB limit after download.")

        except requests.RequestException as exc:
            raise PDFExtractionError(f"Failed to fetch PDF: {exc}") from exc

        # 2) Prepare output dirs + temp file
        safe_id = re.sub(
            r"[^A-Za-z0-9_-]", "_", openalex_id.split("/")[-1]
        )  # This turns https://openalex.org/W4362579589 into W4362579589, which is shorter, cleaner, and avoids any character-escaping edge cases entirely.
        image_dir = os.path.join(settings.MEDIA_ROOT, "paper_images", safe_id)
        os.makedirs(image_dir, exist_ok=True)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            # 3) Extract (single backend: pymupdf4llm)
            try:
                import pymupdf4llm as pm4
            except ModuleNotFoundError as exc:
                raise PDFExtractionError(
                    "No PDF backend available. Install `pymupdf4llm`."
                ) from exc

            md_content = pm4.to_markdown(
                tmp_path,
                write_images=True,
                force_text=True,
                image_path=image_dir,
                image_format="png",
                dpi=160,
            )
            media_root_str = str(settings.MEDIA_ROOT).replace("\\", "/")
            md_content = md_content.replace("\\", "/")
            md_content = md_content.replace(media_root_str + "/", "")
            # Page count is best-effort.
            page_count = 0
            try:
                import pymupdf as pm

                doc = pm.open(tmp_path)
                page_count = doc.page_count
                doc.close()
            except Exception:
                page_count = md_content.count("\n") or 0

            image_paths = []
            if os.path.exists(image_dir):
                image_paths = [
                    os.path.join("paper_images", safe_id, f)
                    for f in os.listdir(image_dir)
                    if f.lower().endswith(".png")
                ]

            return {
                "markdown": md_content,
                "page_count": page_count,
                "image_paths": sorted(image_paths),
                "error": None,
            }

        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
