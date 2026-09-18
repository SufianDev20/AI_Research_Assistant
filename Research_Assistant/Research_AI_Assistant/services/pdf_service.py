"""
PDF extraction service for open-access papers.
Uses PyMuPDF4LLM to convert PDFs to LLM-ready Markdown.

References:
    https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html
    https://pymupdf.readthedocs.io/en/latest/document.html
"""

import ipaddress
import logging
import os
import re
import socket
import tempfile
from urllib.parse import urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

MAX_PDF_BYTES = 50 * 1024 * 1024
FETCH_TIMEOUT = 30
MAX_PDF_URL_LENGTH = 2000
ALLOWED_PDF_URL_SCHEMES = {"http", "https"}


class PDFExtractionError(Exception):
    pass


def _reject_unsafe_pdf_url(pdf_url: str, context_id: str) -> None:
    """
    Basic SSRF guard for a client-supplied PDF URL: both extract_pdf and
    multi_paper_qa accept a pdf_url straight from the request body and
    fetch it server-side with no login required, so this is the only
    checkpoint between an anonymous caller and an outbound request from
    this server. Rejects non-http(s) schemes and hostnames that resolve to
    a private, loopback, link-local, or otherwise non-public address
    (RFC 1918, localhost, link-local, cloud metadata ranges, etc.).

    Not a complete SSRF defense: the hostname is re-resolved at fetch time
    by `requests`, so a DNS answer that changes between this check and the
    actual GET (DNS rebinding) would slip through. Closing that gap needs
    fetching through a pinned IP (e.g. a custom requests transport that
    connects to the address resolved here) — left as follow-up work rather
    than adding request-layer plumbing under this fix.
    """
    if not pdf_url or len(pdf_url) > MAX_PDF_URL_LENGTH:
        raise PDFExtractionError(
            f"Invalid pdf_url for {context_id}: missing or too long."
        )

    parsed = urlparse(pdf_url)
    if parsed.scheme not in ALLOWED_PDF_URL_SCHEMES:
        raise PDFExtractionError(
            f"Invalid pdf_url for {context_id}: scheme '{parsed.scheme}' not allowed."
        )
    if not parsed.hostname:
        raise PDFExtractionError(f"Invalid pdf_url for {context_id}: no hostname.")

    try:
        addr_info = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise PDFExtractionError(
            f"Could not resolve pdf_url host for {context_id}: {exc}"
        ) from exc

    for _family, _type, _proto, _canon, sockaddr in addr_info:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise PDFExtractionError(
                f"Rejected pdf_url for {context_id}: host resolves to a "
                "non-public address."
            )


def fetch_pdf_bytes(pdf_url: str, context_id: str) -> bytes:
    """Download PDF bytes with a response-size guard."""
    _reject_unsafe_pdf_url(pdf_url, context_id)
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
                f"PDF too large for {context_id}: {content_length} bytes "
                f"(limit {MAX_PDF_BYTES})"
            )

        pdf_bytes = response.content
        if len(pdf_bytes) > MAX_PDF_BYTES:
            raise PDFExtractionError(
                f"PDF for {context_id} exceeds 50MB limit after download."
            )

        return pdf_bytes
    except requests.RequestException as exc:
        raise PDFExtractionError(f"Failed to fetch PDF for {context_id}: {exc}") from exc


class PDFService:
    """Fetch a PDF and extract LLM-ready markdown."""

    @staticmethod
    def fetch_and_extract(pdf_url: str, openalex_id: str) -> dict:
        """Fetch a PDF and extract its content into Markdown.

        Returns:
            dict with keys: markdown, page_count, image_paths, error
        """

        # 1) Fetch
        pdf_bytes = fetch_pdf_bytes(pdf_url, openalex_id)

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
                import fitz as pm

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
