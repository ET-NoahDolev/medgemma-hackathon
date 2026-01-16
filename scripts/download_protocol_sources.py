#!/usr/bin/env python3
"""Download protocol PDFs from the sources table in instructions/protocol_sources.md.

This script downloads protocol PDFs from multiple sources with retry logic and
graceful error handling.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import gzip
import hashlib
import json
import logging
import os
import re
import ssl
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable, Iterator, List, Optional, Set

import aiohttp
from tenacity import (
    RetryError,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


USER_AGENT = "gemma-hackathon-protocol-downloader/1.0"
SSL_CONTEXT = ssl.create_default_context()
if hasattr(ssl, "TLSVersion"):
    SSL_CONTEXT.minimum_version = ssl.TLSVersion.TLSv1_2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Retry configuration for network operations
RETRYABLE_EXCEPTIONS = (
    aiohttp.ClientConnectionError,
    aiohttp.ServerTimeoutError,
    asyncio.TimeoutError,
    TimeoutError,
    ConnectionError,
    OSError,  # Covers socket errors
)


class LinkExtractor(HTMLParser):
    """Collect anchors and meta tags from an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.links: List[str] = []
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "a":
            href = attrs_dict.get("href")
            if href:
                self.links.append(href)
        if tag == "meta":
            name = attrs_dict.get("name") or attrs_dict.get("property")
            content = attrs_dict.get("content")
            if name and content:
                self.meta[name.lower()] = content


def _is_retryable_http_error(exc: BaseException) -> bool:
    """Check if an HTTP error is retryable (5xx, 408, 429)."""
    if isinstance(exc, aiohttp.ClientResponseError):
        code = exc.status
        return code >= 500 or code in (408, 429)
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS) | retry_if_exception(_is_retryable_http_error),
    reraise=True,
)
async def fetch_url(
    url: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    timeout: int = 30,
) -> bytes:
    """Fetch bytes from a URL with a standard user agent and retry logic.

    Retries on network errors, timeouts, and retryable HTTP errors (5xx, 408, 429).
    Does not retry on client errors like 404.
    """
    try:
        async with semaphore:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=SSL_CONTEXT,
            ) as response:
                if response.status >= 400:
                    response.raise_for_status()
                return await response.read()
    except aiohttp.ClientResponseError as e:
        if 400 <= e.status < 500 and e.status not in (408, 429):
            logger.debug(f"Non-retryable HTTP error {e.status} for {url}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS) | retry_if_exception(_is_retryable_http_error),
    reraise=True,
)
async def fetch_json(
    url: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    params: Optional[dict] = None,
    timeout: int = 30,
) -> dict:
    """Fetch JSON from a URL with a standard user agent and retry logic."""
    if params:
        query_string = urllib.parse.urlencode(params)
        url = f"{url}?{query_string}"

    try:
        data = await fetch_url(url, session=session, semaphore=semaphore, timeout=timeout)
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from {url}: {e}")
        raise


def normalize_filename(url: str, suffix: str = ".pdf") -> str:
    parsed = urllib.parse.urlparse(url)
    basename = Path(parsed.path).name or "document"
    stem = Path(basename).stem or "document"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-") or "document"
    short_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]
    ext = Path(basename).suffix or suffix
    if not ext.startswith("."):
        ext = f".{ext}"
    return f"{safe_stem}-{short_hash}{ext}"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def compute_concurrency_limit() -> int:
    cpu_count = os.cpu_count() or 1
    return min(32, max(1, cpu_count * 2))


async def record_manifest_async(
    manifest_path: Path,
    source: str,
    url: str,
    path: Path,
    *,
    status: str,
    detail: Optional[str] = None,
    lock: asyncio.Lock,
) -> None:
    async with lock:
        await asyncio.to_thread(
            record_manifest,
            manifest_path,
            source,
            url,
            path,
            status=status,
            detail=detail,
        )


def parse_html_links(html: bytes, base_url: str) -> tuple[Set[str], dict[str, str]]:
    parser = LinkExtractor()
    parser.feed(html.decode("utf-8", errors="ignore"))
    links = {urllib.parse.urljoin(base_url, link) for link in parser.links}
    return links, parser.meta


def extract_pdf_links(html: bytes, base_url: str) -> List[str]:
    links, meta = parse_html_links(html, base_url)
    pdf_links: Set[str] = set()
    citation_pdf = meta.get("citation_pdf_url")
    if citation_pdf:
        pdf_links.add(urllib.parse.urljoin(base_url, citation_pdf))
    for link in links:
        if ".pdf" in link.lower():
            pdf_links.add(link)
    return sorted(pdf_links)


async def read_sitemap(
    url: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    timeout: int = 30,
) -> List[str]:
    """Read and parse a sitemap XML file.
    
    Args:
        url: URL of the sitemap.
        timeout: Request timeout in seconds.
        
    Returns:
        List of URLs found in the sitemap.
        
    Raises:
        aiohttp.ClientError: If the sitemap cannot be fetched.
        ET.ParseError: If the sitemap XML is invalid.
    """
    try:
        raw = await fetch_url(url, session=session, semaphore=semaphore, timeout=timeout)
        logger.debug(f"Fetched sitemap {url}: {len(raw)} bytes")
        if url.endswith(".gz"):
            raw = gzip.decompress(raw)
            logger.debug(f"Decompressed sitemap to {len(raw)} bytes")
        root = ET.fromstring(raw)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = []
        for loc in root.findall(".//s:loc", ns):
            if loc.text:
                urls.append(loc.text.strip())
        # Also try without namespace (some sitemaps don't use it)
        if not urls:
            logger.debug("No URLs found with namespace, trying without namespace")
            for loc in root.iter("loc"):
                if loc.text:
                    urls.append(loc.text.strip())
        logger.debug(f"Parsed sitemap {url}: found {len(urls)} URLs")
        return urls
    except aiohttp.ClientResponseError as e:
        logger.warning(f"HTTP error fetching sitemap {url}: {e.status} {e.message}")
        raise
    except (aiohttp.ClientError, RetryError) as e:
        logger.warning(f"Failed to fetch sitemap {url}: {type(e).__name__}: {e}")
        raise
    except ET.ParseError as e:
        logger.warning(f"Failed to parse sitemap XML {url}: {e}")
        raise


async def iter_sitemap_urls(
    root_sitemap: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    sitemap_limit: int,
    url_limit: Optional[int],
    timeout: int,
) -> AsyncIterator[str]:
    """Iterate over URLs from a sitemap hierarchy.
    
    Args:
        root_sitemap: Root sitemap URL.
        sitemap_limit: Maximum number of sub-sitemaps to process.
        url_limit: Maximum number of URLs to yield (None for unlimited).
        timeout: Request timeout in seconds.
        
    Yields:
        URLs from the sitemap.
    """
    logger.info(f"Fetching root sitemap: {root_sitemap}")
    try:
        queue = await read_sitemap(
            root_sitemap,
            session=session,
            semaphore=semaphore,
            timeout=timeout,
        )
    except (aiohttp.ClientError, ET.ParseError, RetryError) as e:
        logger.warning(f"Failed to read root sitemap {root_sitemap}: {type(e).__name__}: {e}")
        return
    
    if not queue:
        logger.warning(f"Empty sitemap (no URLs found): {root_sitemap}")
        return
    
    logger.info(f"Root sitemap returned {len(queue)} entries")
        
    # Detect sub-sitemaps: ends with .xml/.xml.gz OR contains "sitemap" in the URL
    sub_sitemaps = [url for url in queue if url.endswith((".xml", ".xml.gz")) or "sitemap" in url.lower()]
    urls_yielded = 0
    if sub_sitemaps:
        logger.info(f"Found {len(sub_sitemaps)} sub-sitemaps, processing up to {sitemap_limit}")
        for sitemap_url in sub_sitemaps[:sitemap_limit]:
            try:
                sitemap_urls = await read_sitemap(
                    sitemap_url,
                    session=session,
                    semaphore=semaphore,
                    timeout=timeout,
                )
                logger.info(f"Sub-sitemap {sitemap_url} returned {len(sitemap_urls)} URLs")
            except (aiohttp.ClientError, ET.ParseError, RetryError) as e:
                logger.warning(f"Skipping sub-sitemap {sitemap_url}: {type(e).__name__}: {e}")
                continue
            for url in sitemap_urls:
                yield url
                urls_yielded += 1
                if url_limit is not None:
                    url_limit -= 1
                    if url_limit <= 0:
                        logger.info(f"Reached URL limit after yielding {urls_yielded} URLs")
                        return
    else:
        logger.info(f"No sub-sitemaps found, yielding {min(url_limit or len(queue), len(queue))} URLs directly")
        for url in queue[: url_limit or len(queue)]:
            yield url
            urls_yielded += 1
    
    logger.info(f"Sitemap iteration complete: yielded {urls_yielded} URLs total")


async def download_pdf(
    url: str,
    destination_dir: Path,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    timeout: int,
    manifest_path: Path,
    source: str,
    manifest_lock: asyncio.Lock,
) -> Optional[Path]:
    """Download a PDF file with retry logic and error handling.
    
    Args:
        url: URL of the PDF to download.
        destination_dir: Directory to save the PDF.
        timeout: Request timeout in seconds.
        manifest_path: Path to manifest file for logging.
        source: Source identifier for the PDF.
        
    Returns:
        Path to downloaded file if successful, None otherwise.
    """
    try:
        ensure_dir(destination_dir)
        filename = normalize_filename(url)
        target = destination_dir / filename
        
        # Skip if already downloaded
        if target.exists():
            logger.debug(f"File already exists: {target}")
            return target
            
        # Fetch with retry logic (handled by fetch_url decorator)
        try:
            data = await fetch_url(
                url,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
            )
        except RetryError as e:
            # All retries exhausted
            logger.warning(f"Failed to download {url} after retries: {e.last_attempt.exception()}")
            await record_manifest_async(
                manifest_path,
                source,
                url,
                target,
                status="failed",
                detail=f"Retry exhausted: {e.last_attempt.exception()}",
                lock=manifest_lock,
            )
            return None
        except aiohttp.ClientResponseError as e:
            logger.debug(f"HTTP error {e.status} for {url}")
            await record_manifest_async(
                manifest_path,
                source,
                url,
                target,
                status="failed",
                detail=f"HTTP {e.status}: {e.message}",
                lock=manifest_lock,
            )
            return None
        except (aiohttp.ClientError, TimeoutError, ValueError, OSError) as exc:
            # Other errors (should be caught by retry, but handle gracefully)
            logger.warning(f"Error downloading {url}: {exc}")
            await record_manifest_async(
                manifest_path,
                source,
                url,
                target,
                status="failed",
                detail=str(exc),
                lock=manifest_lock,
            )
            return None
        
        # Validate PDF content (basic check)
        if len(data) < 100:  # PDFs should be larger than 100 bytes
            logger.warning(f"Downloaded file too small for {url}, may not be a valid PDF")
            await record_manifest_async(
                manifest_path,
                source,
                url,
                target,
                status="failed",
                detail="File too small, likely not a PDF",
                lock=manifest_lock,
            )
            return None
            
        # Check PDF magic bytes
        if not data.startswith(b"%PDF"):
            logger.warning(f"Downloaded file doesn't appear to be a PDF: {url}")
            await record_manifest_async(
                manifest_path,
                source,
                url,
                target,
                status="failed",
                detail="File doesn't have PDF magic bytes",
                lock=manifest_lock,
            )
            return None
        
        # Write file
        try:
            await asyncio.to_thread(target.write_bytes, data)
            await record_manifest_async(
                manifest_path,
                source,
                url,
                target,
                status="downloaded",
                lock=manifest_lock,
            )
            logger.info(f"Downloaded: {target.name} ({len(data)} bytes)")
            return target
        except OSError as e:
            logger.error(f"Failed to write file {target}: {e}")
            await record_manifest_async(
                manifest_path,
                source,
                url,
                target,
                status="failed",
                detail=f"Write error: {e}",
                lock=manifest_lock,
            )
            return None
            
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error downloading {url}: {e}", exc_info=True)
        await record_manifest_async(
            manifest_path,
            source,
            url,
            Path(destination_dir) / "unknown",
            status="failed",
            detail=f"Unexpected error: {e}",
            lock=manifest_lock,
        )
        return None


def record_manifest(
    manifest_path: Path,
    source: str,
    url: str,
    path: Path,
    *,
    status: str,
    detail: Optional[str] = None,
) -> None:
    record = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source,
        "url": url,
        "path": str(path),
        "status": status,
    }
    if detail:
        record["detail"] = detail
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


async def download_from_dac(
    output_dir: Path,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    manifest_lock: asyncio.Lock,
    max_items: int,
    timeout: int,
    manifest_path: Path,
) -> int:
    """Download PDFs from DAC protocol registry.
    
    Args:
        output_dir: Base output directory.
        max_items: Maximum number of PDFs to download.
        timeout: Request timeout in seconds.
        manifest_path: Path to manifest file.
        
    Returns:
        Number of PDFs successfully downloaded.
    """
    source = "dac"
    url = "https://dac-trials.org/resources/protocol-library/protocol-registry/"
    try:
        html = await fetch_url(url, session=session, semaphore=semaphore, timeout=timeout)
    except (aiohttp.ClientError, RetryError) as e:
        logger.error(f"Failed to fetch DAC registry page: {e}")
        return 0
        
    try:
        links, _ = parse_html_links(html, url)
        pdf_links = [link for link in links if ".pdf" in link.lower()]
    except Exception as e:
        logger.error(f"Failed to parse DAC registry page: {e}")
        return 0
    
    if not pdf_links:
        logger.warning("No PDF links found in DAC registry")
        return 0
        
    logger.info(f"Found {len(pdf_links)} PDF links in DAC registry, downloading up to {max_items}")
    downloaded = 0
    tasks = [
        asyncio.create_task(
            download_pdf(
                link,
                output_dir / source,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
                manifest_path=manifest_path,
                source=source,
                manifest_lock=manifest_lock,
            )
        )
        for link in pdf_links[:max_items]
    ]
    for task in asyncio.as_completed(tasks):
        result = await task
        if result:
            downloaded += 1
        if downloaded >= max_items:
            break
    if downloaded >= max_items:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return downloaded


async def search_studies(
    keyword: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    timeout: int,
    max_results: int = 200,
) -> List[str]:
    search_url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.term": keyword,
        "pageSize": max_results,
        "fields": "protocolSection.identificationModule",
    }
    payload = await fetch_json(
        search_url,
        session=session,
        semaphore=semaphore,
        params=params,
        timeout=timeout,
    )
    studies = payload.get("studies", []) or []
    nct_ids = []
    for study in studies:
        nct_id = (
            study.get("protocolSection", {})
            .get("identificationModule", {})
            .get("nctId")
        )
        if nct_id:
            nct_ids.append(nct_id)
    return nct_ids


async def get_large_docs(
    nct_id: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    timeout: int,
) -> List[dict]:
    """Fetch large document metadata for a study.
    
    Note: We don't use the `fields` parameter because the API may reject
    certain field paths. Instead, we fetch the full study record and extract
    what we need. This is slightly less efficient but more reliable.
    """
    study_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
    # Don't use fields param - API rejects some field paths with 400
    study = await fetch_json(
        study_url,
        session=session,
        semaphore=semaphore,
        timeout=timeout,
    )
    
    # Navigate the response structure to find large documents
    # IMPORTANT: documentSection is at the ROOT level, not inside protocolSection!
    # Correct structure: study.documentSection.largeDocumentModule.largeDocs
    
    doc_section = study.get("documentSection", {})
    large_doc_module = doc_section.get("largeDocumentModule", {})
    large_docs = large_doc_module.get("largeDocs", []) or []
    
    logger.debug(f"[{nct_id}] documentSection keys: {list(doc_section.keys())}, largeDocs count: {len(large_docs)}")
    
    return large_docs


def iter_protocol_docs(large_docs: List[dict]) -> Iterator[dict]:
    for doc in large_docs:
        filename = doc.get("filename")
        if not filename:
            continue
        if doc.get("hasProtocol"):
            yield doc
            continue
        type_abbrev = (doc.get("typeAbbrev") or "").upper()
        type_full = (doc.get("type") or "").upper()
        label = (doc.get("label") or "").upper()
        if "PROT" in type_abbrev or "PROTOCOL" in type_full or "PROTOCOL" in label:
            yield doc


def build_provided_docs_url(nct_id: str, filename: str) -> str:
    nct_digits = nct_id[3:]
    last_two = nct_digits[-2:]
    return f"https://clinicaltrials.gov/ProvidedDocs/{last_two}/{nct_id}/{filename}"


async def download_from_clinicaltrials(
    output_dir: Path,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    manifest_lock: asyncio.Lock,
    max_items: int,
    timeout: int,
    manifest_path: Path,
    sitemap_limit: int,  # Not used with API approach, but kept for compatibility
) -> int:
    source = "clinicaltrials"
    downloaded = 0
    download_lock = asyncio.Lock()
    limit_reached = asyncio.Event()
    
    # Diagnostic counters
    stats = {
        "studies_with_large_docs": 0,
        "studies_without_large_docs": 0,
        "protocol_docs_found": 0,
        "download_attempts": 0,
        "download_failures": 0,
        "fetch_errors": 0,
    }
    stats_lock = asyncio.Lock()

    async def record_success() -> int:
        nonlocal downloaded
        async with download_lock:
            downloaded += 1
            if downloaded >= max_items:
                limit_reached.set()
            return downloaded

    async def process_study(nct_id: str) -> None:
        if limit_reached.is_set():
            return
        try:
            large_docs = await get_large_docs(
                nct_id,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
            )
        except (aiohttp.ClientError, RetryError) as e:
            logger.warning(f"[{nct_id}] Failed to fetch large docs: {type(e).__name__}: {e}")
            async with stats_lock:
                stats["fetch_errors"] += 1
            return
        except Exception as e:
            logger.warning(f"[{nct_id}] Unexpected error fetching large docs: {type(e).__name__}: {e}")
            async with stats_lock:
                stats["fetch_errors"] += 1
            return

        if not large_docs:
            async with stats_lock:
                stats["studies_without_large_docs"] += 1
            logger.debug(f"[{nct_id}] No large documents (protocol/SAP/ICF) listed")
            return
        
        async with stats_lock:
            stats["studies_with_large_docs"] += 1
        
        protocol_docs = list(iter_protocol_docs(large_docs))
        if not protocol_docs:
            doc_types = [d.get("typeAbbrev", "?") for d in large_docs]
            logger.debug(f"[{nct_id}] Has {len(large_docs)} large docs (types: {doc_types}) but none are protocol-like")
            return
        
        logger.info(f"[{nct_id}] Found {len(protocol_docs)} protocol-like docs out of {len(large_docs)} total")
        
        async with stats_lock:
            stats["protocol_docs_found"] += len(protocol_docs)

        for doc in protocol_docs:
            if limit_reached.is_set():
                return
            filename = doc.get("filename")
            if not filename:
                continue
            download_url = build_provided_docs_url(nct_id, filename)
            async with stats_lock:
                stats["download_attempts"] += 1
            result = await download_pdf(
                download_url,
                output_dir / source,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
                manifest_path=manifest_path,
                source=source,
                manifest_lock=manifest_lock,
            )
            if result:
                count = await record_success()
                logger.info(f"[{nct_id}] Downloaded protocol: {filename}")
                if count >= max_items:
                    return
            else:
                async with stats_lock:
                    stats["download_failures"] += 1
                logger.warning(f"[{nct_id}] Failed to download: {filename}")
            await asyncio.sleep(0.2)

    # Search for studies more likely to have protocol documents attached
    # Studies with FDA oversight, phase 3/4 trials, and industry-sponsored trials
    # tend to have more documentation uploaded
    search_terms = [
        "AREA[OverallStatus]Completed AND AREA[Phase]Phase 3",
        "AREA[OverallStatus]Completed AND AREA[Phase]Phase 4", 
        "AREA[IsFDARegulatedDrug]true",
        "protocol AND randomized",
    ]
    max_studies_to_check = max_items * 100  # Increase pool since many studies lack docs
    processed_nct_ids: Set[str] = set()

    tasks: List[asyncio.Task] = []
    stop_scheduling = False
    for search_term in search_terms:
        if limit_reached.is_set() or stop_scheduling:
            break
        try:
            nct_ids = await search_studies(
                search_term,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
                max_results=min(100, max_studies_to_check),
            )
        except (aiohttp.ClientError, RetryError) as e:
            logger.warning(f"Failed to search ClinicalTrials.gov for '{search_term}': {type(e).__name__}: {e}")
            continue
        except Exception as e:
            logger.warning(f"Unexpected error searching ClinicalTrials.gov: {type(e).__name__}: {e}")
            continue

        if not nct_ids:
            logger.warning(f"No studies returned for search term '{search_term}'")
            continue

        logger.info(f"Found {len(nct_ids)} studies for search term '{search_term}'")
        for nct_id in nct_ids:
            if limit_reached.is_set():
                break
            if nct_id in processed_nct_ids:
                continue
            processed_nct_ids.add(nct_id)
            if len(processed_nct_ids) > max_studies_to_check:
                logger.info(f"Reached max studies to check ({max_studies_to_check})")
                stop_scheduling = True
                break
            tasks.append(asyncio.create_task(process_study(nct_id)))

    try:
        for task in asyncio.as_completed(tasks):
            await task
            if limit_reached.is_set():
                break
    finally:
        if limit_reached.is_set():
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    # Log diagnostic summary
    logger.info(
        f"[{source}] Stats: processed={len(processed_nct_ids)} studies, "
        f"with_large_docs={stats['studies_with_large_docs']}, "
        f"without_large_docs={stats['studies_without_large_docs']}, "
        f"protocol_docs_found={stats['protocol_docs_found']}, "
        f"download_attempts={stats['download_attempts']}, "
        f"download_failures={stats['download_failures']}, "
        f"fetch_errors={stats['fetch_errors']}"
    )
    logger.info(f"Downloaded {downloaded} PDFs from {source} (processed {len(processed_nct_ids)} studies)")
    return downloaded


async def download_from_bmjopen(
    output_dir: Path,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    manifest_lock: asyncio.Lock,
    max_items: int,
    timeout: int,
    manifest_path: Path,
    sitemap_limit: int,
) -> int:
    """Download PDFs from BMJ Open.
    
    Args:
        output_dir: Base output directory.
        max_items: Maximum number of PDFs to download.
        timeout: Request timeout in seconds.
        manifest_path: Path to manifest file.
        sitemap_limit: Maximum number of sitemaps to process.
        
    Returns:
        Number of PDFs successfully downloaded.
    """
    source = "bmjopen"
    sitemap = "https://bmjopen.bmj.com/sitemap.xml"
    downloaded = 0
    urls_processed = 0
    max_urls_to_check = max_items * 20
    
    # Diagnostic counters
    stats = {
        "sitemap_urls_received": 0,
        "urls_without_content": 0,
        "urls_not_protocol": 0,
        "fetch_errors": 0,
        "protocol_articles_found": 0,
        "pdf_links_found": 0,
        "download_attempts": 0,
    }
    
    try:
        article_urls = iter_sitemap_urls(
            sitemap,
            session=session,
            semaphore=semaphore,
            sitemap_limit=sitemap_limit,
            url_limit=max_urls_to_check,
            timeout=timeout,
        )
    except Exception as e:
        logger.error(f"Failed to read BMJ Open sitemap: {type(e).__name__}: {e}")
        return 0

    tasks: List[asyncio.Task] = []
    async for article_url in article_urls:
        stats["sitemap_urls_received"] += 1
        if "/content/" not in article_url:
            stats["urls_without_content"] += 1
            continue
        urls_processed += 1
        # Check URL or try fetching to check content
        if "protocol" not in article_url.lower():
            # Try fetching to check if it's a protocol article
            try:
                html = await fetch_url(
                    article_url,
                    session=session,
                    semaphore=semaphore,
                    timeout=timeout,
                )
                html_text = html.decode("utf-8", errors="ignore").lower()
                if "protocol" not in html_text[:5000]:  # Check first 5KB for performance
                    stats["urls_not_protocol"] += 1
                    continue
            except (aiohttp.ClientError, RetryError) as e:
                logger.warning(f"[{source}] Fetch error for {article_url}: {type(e).__name__}: {e}")
                stats["fetch_errors"] += 1
                continue
        else:
            try:
                html = await fetch_url(
                    article_url,
                    session=session,
                    semaphore=semaphore,
                    timeout=timeout,
                )
            except (aiohttp.ClientError, RetryError) as e:
                logger.warning(f"[{source}] Fetch error for {article_url}: {type(e).__name__}: {e}")
                stats["fetch_errors"] += 1
                continue
        
        stats["protocol_articles_found"] += 1
                
        try:
            # Try extracting PDFs from HTML
            pdf_urls = extract_pdf_links(html, article_url)
            # For BMJ Open, also try common PDF URL patterns
            if not pdf_urls and "/content/" in article_url:
                # Try common BMJ Open PDF URL patterns
                base_url = article_url.rstrip("/")
                potential_pdfs = [
                    f"{base_url}.full.pdf",
                    f"{base_url}/full.pdf",
                    f"{base_url}.pdf",
                ]
                pdf_urls.extend(potential_pdfs)
        except Exception as e:
            logger.warning(f"[{source}] Failed to extract PDF links from {article_url}: {type(e).__name__}: {e}")
            continue
        
        stats["pdf_links_found"] += len(pdf_urls)

        for pdf_url in pdf_urls:
            stats["download_attempts"] += 1
            tasks.append(
                asyncio.create_task(
                    download_pdf(
                        pdf_url,
                        output_dir / source,
                        session=session,
                        semaphore=semaphore,
                        timeout=timeout,
                        manifest_path=manifest_path,
                        source=source,
                        manifest_lock=manifest_lock,
                    )
                )
            )
                
        # Stop if we've checked enough URLs without finding PDFs
        if urls_processed >= max_urls_to_check and downloaded == 0:
            logger.warning(f"No PDFs found after checking {urls_processed} URLs from {source}")
            break

    for task in asyncio.as_completed(tasks):
        result = await task
        if result:
            downloaded += 1
        if downloaded >= max_items:
            logger.info(f"Reached max_items ({max_items}) for {source}")
            break

    if downloaded >= max_items:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    # Log diagnostic summary
    logger.info(
        f"[{source}] Stats: sitemap_urls={stats['sitemap_urls_received']}, "
        f"without_content={stats['urls_without_content']}, "
        f"not_protocol={stats['urls_not_protocol']}, "
        f"fetch_errors={stats['fetch_errors']}, "
        f"protocol_articles={stats['protocol_articles_found']}, "
        f"pdf_links={stats['pdf_links_found']}, "
        f"download_attempts={stats['download_attempts']}"
    )
    logger.info(f"Downloaded {downloaded} PDFs from {source} (checked {urls_processed} URLs)")
    return downloaded


async def download_from_jmir(
    output_dir: Path,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    manifest_lock: asyncio.Lock,
    max_items: int,
    timeout: int,
    manifest_path: Path,
    sitemap_limit: int,
) -> int:
    """Download PDFs from JMIR Research Protocols.
    
    Args:
        output_dir: Base output directory.
        max_items: Maximum number of PDFs to download.
        timeout: Request timeout in seconds.
        manifest_path: Path to manifest file.
        sitemap_limit: Maximum number of sitemaps to process.
        
    Returns:
        Number of PDFs successfully downloaded.
    """
    source = "jmir"
    sitemap = "https://www.researchprotocols.org/sitemap.xml"
    downloaded = 0
    urls_processed = 0
    pattern = re.compile(r"/\d{4}/\d+/e\d+/?$")
    max_urls_to_check = max_items * 15
    
    # Diagnostic counters
    stats = {
        "sitemap_urls_received": 0,
        "urls_not_matching_pattern": 0,
        "fetch_errors": 0,
        "articles_fetched": 0,
        "pdf_links_found": 0,
        "download_attempts": 0,
    }
    
    try:
        article_urls = iter_sitemap_urls(
            sitemap,
            session=session,
            semaphore=semaphore,
            sitemap_limit=sitemap_limit,
            url_limit=max_urls_to_check,
            timeout=timeout,
        )
    except Exception as e:
        logger.error(f"Failed to read JMIR sitemap: {type(e).__name__}: {e}")
        return 0

    tasks: List[asyncio.Task] = []
    async for article_url in article_urls:
        stats["sitemap_urls_received"] += 1
        if not pattern.search(article_url):
            stats["urls_not_matching_pattern"] += 1
            continue
        urls_processed += 1
        try:
            html = await fetch_url(
                article_url,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
            )
            stats["articles_fetched"] += 1
        except (aiohttp.ClientError, RetryError) as e:
            logger.warning(f"[{source}] Fetch error for {article_url}: {type(e).__name__}: {e}")
            stats["fetch_errors"] += 1
            continue
            
        try:
            pdf_urls = extract_pdf_links(html, article_url)
            stats["pdf_links_found"] += len(pdf_urls)
        except Exception as e:
            logger.warning(f"[{source}] Failed to extract PDF links from {article_url}: {type(e).__name__}: {e}")
            continue

        for pdf_url in pdf_urls:
            stats["download_attempts"] += 1
            tasks.append(
                asyncio.create_task(
                    download_pdf(
                        pdf_url,
                        output_dir / source,
                        session=session,
                        semaphore=semaphore,
                        timeout=timeout,
                        manifest_path=manifest_path,
                        source=source,
                        manifest_lock=manifest_lock,
                    )
                )
            )
                
        # Stop if we've checked enough URLs without finding PDFs
        if urls_processed >= max_urls_to_check and downloaded == 0:
            logger.warning(f"No PDFs found after checking {urls_processed} URLs from {source}")
            break

    for task in asyncio.as_completed(tasks):
        result = await task
        if result:
            downloaded += 1
        if downloaded >= max_items:
            logger.info(f"Reached max_items ({max_items}) for {source}")
            break

    if downloaded >= max_items:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    # Log diagnostic summary
    logger.info(
        f"[{source}] Stats: sitemap_urls={stats['sitemap_urls_received']}, "
        f"not_matching_pattern={stats['urls_not_matching_pattern']}, "
        f"fetch_errors={stats['fetch_errors']}, "
        f"articles_fetched={stats['articles_fetched']}, "
        f"pdf_links={stats['pdf_links_found']}, "
        f"download_attempts={stats['download_attempts']}"
    )
    logger.info(f"Downloaded {downloaded} PDFs from {source} (checked {urls_processed} URLs)")
    return downloaded


SOURCE_HANDLERS: dict[str, Callable[..., Awaitable[int]]] = {
    "dac": download_from_dac,
    "clinicaltrials": download_from_clinicaltrials,
    "bmjopen": download_from_bmjopen,
    "jmir": download_from_jmir,
}

async def main_async() -> int:
    parser = argparse.ArgumentParser(
        description="Download protocol PDFs from the sources table."
    )
    parser.add_argument(
        "--output-dir",
        default="data/protocols",
        help="Directory to store downloaded PDFs.",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=sorted(SOURCE_HANDLERS.keys()),
        default=sorted(SOURCE_HANDLERS.keys()),
        help="Which sources to download from.",
    )
    parser.add_argument(
        "--max-per-source",
        type=int,
        default=50,
        help="Maximum number of PDFs to download per source.",
    )
    parser.add_argument(
        "--max-total",
        type=int,
        default=200,
        help="Maximum number of PDFs to download overall.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Network timeout in seconds.",
    )
    parser.add_argument(
        "--sitemap-limit",
        type=int,
        default=2,
        help="Number of sitemap files to scan per source.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging for detailed diagnostics.",
    )
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.info("Verbose logging enabled")

    output_dir = Path(args.output_dir).resolve()
    try:
        ensure_dir(output_dir)
    except OSError as e:
        logger.error(f"Failed to create output directory {output_dir}: {e}")
        return 1

    manifest_path = output_dir / "manifest.jsonl"
    total_downloaded = 0
    source_results: dict[str, int] = {}
    concurrency_limit = compute_concurrency_limit()

    logger.info(
        "Starting download: max_total=%s, max_per_source=%s, concurrency=%s",
        args.max_total,
        args.max_per_source,
        concurrency_limit,
    )

    manifest_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(concurrency_limit)
    connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
    timeout = aiohttp.ClientTimeout(total=args.timeout)

    async with aiohttp.ClientSession(
        headers={"User-Agent": USER_AGENT},
        connector=connector,
        timeout=timeout,
    ) as session:
        for source in args.sources:
            if total_downloaded >= args.max_total:
                logger.info(f"Reached max_total ({args.max_total}), stopping")
                break

            handler = SOURCE_HANDLERS[source]
            remaining = args.max_total - total_downloaded
            per_source_limit = min(args.max_per_source, remaining)

            logger.info(f"Processing source: {source} (target: {per_source_limit} PDFs)")

            try:
                if source == "dac":
                    downloaded = await handler(
                        output_dir,
                        session=session,
                        semaphore=semaphore,
                        manifest_lock=manifest_lock,
                        max_items=per_source_limit,
                        timeout=args.timeout,
                        manifest_path=manifest_path,
                    )
                else:
                    downloaded = await handler(
                        output_dir,
                        session=session,
                        semaphore=semaphore,
                        manifest_lock=manifest_lock,
                        max_items=per_source_limit,
                        timeout=args.timeout,
                        manifest_path=manifest_path,
                        sitemap_limit=args.sitemap_limit,
                    )
                source_results[source] = downloaded
                total_downloaded += downloaded
                logger.info(
                    f"Source {source}: downloaded {downloaded} PDFs (total: {total_downloaded})"
                )
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(
                    f"Unexpected error processing source {source}: {e}", exc_info=True
                )
                source_results[source] = 0
                continue

            await asyncio.sleep(1)

    logger.info("=" * 60)
    logger.info(f"Download complete: {total_downloaded} total PDFs")
    logger.info("Results by source:")
    for source, count in source_results.items():
        logger.info(f"  {source}: {count} PDFs")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Manifest: {manifest_path}")
    logger.info("=" * 60)

    print(f"Downloaded {total_downloaded} protocol PDFs into {output_dir}")
    print(f"Manifest written to {manifest_path}")

    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
