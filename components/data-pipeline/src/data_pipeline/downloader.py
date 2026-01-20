#!/usr/bin/env python3
"""Download ONLY clinical trial protocols from designated sources.

This module downloads protocol PDFs from public sources with strict filtering
to exclude amendments, deviations, violations, and unrelated documents.
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
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Iterator,
    Optional,
    Set,
    cast,
)

import aiohttp
from tenacity import (
    RetryError,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

JsonDict = dict[str, Any]
TaskResult = Optional[Path]

USER_AGENT = "gemma-hackathon-protocol-downloader/2.0"
SSL_CONTEXT = ssl.create_default_context()
if hasattr(ssl, "TLSVersion"):
    SSL_CONTEXT.minimum_version = ssl.TLSVersion.TLSv1_2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (
    aiohttp.ClientConnectionError,
    aiohttp.ServerTimeoutError,
    asyncio.TimeoutError,
    TimeoutError,
    ConnectionError,
    OSError,
)


@dataclass(frozen=True)
class SourceSpec:
    """Metadata for a protocol source."""

    name: str
    discovery_method: str
    identifier_type: str
    priority: str
    enabled_by_default: bool


@dataclass(frozen=True)
class DownloadConfig:
    """Configuration for the download run."""

    output_dir: Path
    include_journal_sources: bool
    sources: list[str] | None
    max_per_source: int
    max_total: int
    timeout: int
    sitemap_limit: int
    verbose: bool


class LinkExtractor(HTMLParser):
    """Collect anchors and meta tags from an HTML document."""

    def __init__(self) -> None:
        """Initialize an HTML link extractor."""
        super().__init__()
        self.links: list[str] = []
        self.meta: dict[str, str] = {}
        self._current_href: Optional[str] = None
        self._current_text: list[str] = []
        self.link_text: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track anchor and meta tags."""
        attrs_dict = dict(attrs)
        if tag == "a":
            href = attrs_dict.get("href")
            if href:
                self.links.append(href)
                self._current_href = href
                self._current_text = []
        if tag == "meta":
            name = attrs_dict.get("name") or attrs_dict.get("property")
            content = attrs_dict.get("content")
            if name and content:
                self.meta[name.lower()] = content

    def handle_endtag(self, tag: str) -> None:
        """Capture anchor text after closing tags."""
        if tag == "a" and self._current_href:
            text = " ".join(self._current_text).strip()
            if text:
                self.link_text[self._current_href] = text
            self._current_href = None
            self._current_text = []

    def handle_data(self, data: str) -> None:
        """Collect text inside anchors."""
        if self._current_href:
            self._current_text.append(data)


def _is_retryable_http_error(exc: BaseException) -> bool:
    """Check if an HTTP error is retryable (5xx, 408, 429)."""
    if isinstance(exc, aiohttp.ClientResponseError):
        code = exc.status
        return code >= 500 or code in (408, 429)
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS)
    | retry_if_exception(_is_retryable_http_error),
    reraise=True,
)
async def fetch_url(
    url: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    timeout: int = 30,
) -> bytes:
    """Fetch bytes from a URL with retry logic."""
    async with semaphore:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=timeout),
            ssl=SSL_CONTEXT,
        ) as response:
            if response.status >= 400:
                response.raise_for_status()
            return await response.read()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS)
    | retry_if_exception(_is_retryable_http_error),
    reraise=True,
)
async def fetch_json(
    url: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    params: Optional[dict[str, str]] = None,
    timeout: int = 30,
) -> JsonDict:
    """Fetch JSON from a URL with retry logic."""
    if params:
        query_string = urllib.parse.urlencode(params)
        url = f"{url}?{query_string}"
    data = await fetch_url(url, session=session, semaphore=semaphore, timeout=timeout)
    return cast(JsonDict, json.loads(data.decode("utf-8")))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS)
    | retry_if_exception(_is_retryable_http_error),
    reraise=True,
)
async def fetch_json_post(
    url: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    payload: JsonDict,
    timeout: int = 30,
) -> JsonDict:
    """POST JSON and return JSON response with retry logic."""
    async with semaphore:
        async with session.post(
            url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=timeout),
            ssl=SSL_CONTEXT,
        ) as response:
            if response.status >= 400:
                response.raise_for_status()
            data = await response.read()
            return cast(JsonDict, json.loads(data.decode("utf-8")))


def normalize_filename(url: str, suffix: str = ".pdf") -> str:
    """Generate a filesystem-safe filename for a URL."""
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
    """Create a directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def compute_concurrency_limit() -> int:
    """Compute a reasonable concurrency limit for downloads."""
    cpu_count = os.cpu_count() or 1
    return min(32, max(1, cpu_count * 2))


def parse_html_links(
    html: bytes, base_url: str
) -> tuple[Set[str], dict[str, str], dict[str, str]]:
    """Parse links and meta tags from HTML content."""
    parser = LinkExtractor()
    parser.feed(html.decode("utf-8", errors="ignore"))
    links = {urllib.parse.urljoin(base_url, link) for link in parser.links}
    link_text = {
        urllib.parse.urljoin(base_url, href): text
        for href, text in parser.link_text.items()
    }
    return links, parser.meta, link_text


def extract_pdf_links(html: bytes, base_url: str) -> list[str]:
    """Extract PDF links from HTML content."""
    links, meta, _ = parse_html_links(html, base_url)
    pdf_links: Set[str] = set()
    citation_pdf = meta.get("citation_pdf_url")
    if citation_pdf:
        pdf_links.add(urllib.parse.urljoin(base_url, citation_pdf))
    for link in links:
        if ".pdf" in link.lower():
            pdf_links.add(link)
    return sorted(pdf_links)


def _normalize_domain(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_same_domain(url: str, base_url: str) -> bool:
    """Check if a URL shares the same domain as base_url."""
    return _normalize_domain(url) == _normalize_domain(base_url)


def find_pdf_links(
    html: bytes,
    base_url: str,
    *,
    include_keywords: Optional[Set[str]] = None,
) -> list[str]:
    """Find PDF links in HTML, optionally filtered by keyword."""
    links, meta, link_text = parse_html_links(html, base_url)
    pdf_urls: Set[str] = set()
    citation_pdf = meta.get("citation_pdf_url")
    if citation_pdf:
        pdf_urls.add(urllib.parse.urljoin(base_url, citation_pdf))
    for link in links:
        lowered = link.lower()
        if ".pdf" in lowered or "/pdf" in lowered or "download" in lowered:
            pdf_urls.add(link)
    if include_keywords:
        filtered = set()
        for link in pdf_urls:
            text = link_text.get(link, "").lower()
            if any(keyword in text for keyword in include_keywords) or any(
                keyword in link.lower() for keyword in include_keywords
            ):
                filtered.add(link)
        if filtered:
            pdf_urls = filtered
    return [url for url in sorted(pdf_urls) if is_same_domain(url, base_url)]


def extract_isrctn_ids(xml_data: bytes) -> list[str]:
    """Extract ISRCTN identifiers from an XML payload."""
    ids: Set[str] = set()
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []
    for node in root.iter():
        tag = node.tag.lower()
        if (tag.endswith("isrctnid") or tag.endswith("isrctn")) and node.text:
            raw = node.text.strip()
            if raw.upper().startswith("ISRCTN"):
                ids.add(raw.upper())
            elif raw.isdigit():
                ids.add(f"ISRCTN{raw}")
    return sorted(ids)


def extract_isrctn_protocol_files(xml_data: bytes) -> list[tuple[str, str, str]]:
    """Extract protocol files from ISRCTN XML payloads."""
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}")[0].strip("{")
    ns = {"i": namespace} if namespace else {}
    results: list[tuple[str, str, str]] = []

    for trial in root.findall(".//i:trial", ns) if ns else root.iter("trial"):
        isrctn_node = trial.find(".//i:isrctn", ns) if ns else trial.find(".//isrctn")
        if isrctn_node is None or not isrctn_node.text:
            continue
        isrctn_id = f"ISRCTN{isrctn_node.text.strip()}"
        attached_files = (
            trial.findall(".//i:attachedFile", ns)
            if ns
            else trial.findall(".//attachedFile")
        )
        for file_node in attached_files:
            download_url = file_node.attrib.get("downloadUrl", "")
            description_node = (
                file_node.find("i:description", ns)
                if ns
                else file_node.find("description")
            )
            description = (
                description_node.text.strip()
                if description_node is not None and description_node.text
                else ""
            )
            if "protocol" in description.lower() and download_url:
                results.append((isrctn_id, download_url, description))

    return results


def _collect_ctis_links(payload: object) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    stack: list[object] = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            lower_keys = {k.lower(): k for k in value.keys()}
            url_key = next(
                (
                    lower_keys[k]
                    for k in ("url", "documenturl", "downloadurl", "fileurl")
                    if k in lower_keys
                ),
                None,
            )
            label_parts: list[str] = []
            for k in (
                "documentType",
                "documentTypeCode",
                "documentTitle",
                "title",
                "type",
                "name",
            ):
                if isinstance(value.get(k), str):
                    label_parts.append(value[k])
            if url_key and isinstance(value.get(url_key), str):
                url_value = value[url_key]
                label = " ".join(label_parts).strip()
                if label:
                    links.append((url_value, label))
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return links


def extract_ctis_protocol_links(payload: object) -> list[tuple[str, str]]:
    """Extract protocol document links from CTIS payloads."""
    protocol_links: list[tuple[str, str]] = []
    for url_value, label in _collect_ctis_links(payload):
        lowered = label.lower()
        if "protocol" in lowered and "synopsis" not in lowered and "icf" not in lowered:
            protocol_links.append((url_value, label))
    return protocol_links


def looks_like_protocol_text(text: str) -> bool:
    """Heuristic check for protocol-related text."""
    lowered = text.lower()
    if "protocol" not in lowered and "study protocol" not in lowered:
        return False
    if "statistical analysis plan" in lowered or "sap" in lowered:
        return False
    return True


def validate_protocol_pdf_content(data: bytes) -> Optional[bool]:
    """Inspect PDF content for protocol indicators when available."""
    try:
        from pypdf import PdfReader
    except Exception:
        logger.debug("pypdf not available; skipping content validation")
        return None

    try:
        from io import BytesIO

        reader = PdfReader(BytesIO(data))
        text_chunks: list[str] = []
        for page in reader.pages[:2]:
            extracted = page.extract_text() or ""
            if extracted:
                text_chunks.append(extracted)
        text = " ".join(text_chunks).strip()
        if len(text) < 200:
            logger.debug("PDF text extraction too sparse; skipping content validation")
            return None
        return looks_like_protocol_text(text)
    except Exception as exc:
        logger.debug("Failed to extract PDF text: %s", exc)
        return None


async def record_manifest_async(
    manifest_path: Path,
    source: str,
    url: str,
    path: Path,
    *,
    status: str,
    detail: Optional[str] = None,
    registry_id: Optional[str] = None,
    registry_type: Optional[str] = None,
    document_type: Optional[str] = None,
    lock: asyncio.Lock,
) -> None:
    """Record a manifest entry asynchronously."""
    async with lock:
        await asyncio.to_thread(
            record_manifest,
            manifest_path,
            source,
            url,
            path,
            status=status,
            detail=detail,
            registry_id=registry_id,
            registry_type=registry_type,
            document_type=document_type,
        )


def record_manifest(
    manifest_path: Path,
    source: str,
    url: str,
    path: Path,
    *,
    status: str,
    detail: Optional[str] = None,
    registry_id: Optional[str] = None,
    registry_type: Optional[str] = None,
    document_type: Optional[str] = None,
) -> None:
    """Record a manifest entry to JSONL."""
    record = {
        "timestamp": dt.datetime.now(dt.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "source": source,
        "url": url,
        "path": str(path),
        "status": status,
    }
    if detail:
        record["detail"] = detail
    if registry_id:
        record["registry_id"] = registry_id
    if registry_type:
        record["registry_type"] = registry_type
    if document_type:
        record["document_type"] = document_type
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def _pdf_error_detail(data: bytes, require_protocol: bool) -> Optional[str]:
    if len(data) < 100:
        return "File too small"
    if not data.startswith(b"%PDF"):
        return "Not a valid PDF"
    if require_protocol:
        is_protocol = validate_protocol_pdf_content(data)
        if is_protocol is False:
            return "PDF content missing protocol indicators"
    return None


async def _write_pdf(path: Path, data: bytes) -> Optional[str]:
    try:
        await asyncio.to_thread(path.write_bytes, data)
    except OSError:
        return "Write error"
    return None


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
    require_protocol: bool = False,
    registry_id: Optional[str] = None,
    registry_type: Optional[str] = None,
    document_type: Optional[str] = None,
) -> TaskResult:
    """Download a PDF file with validation and manifest logging."""
    ensure_dir(destination_dir)
    filename = normalize_filename(url)
    target = destination_dir / filename

    if target.exists():
        logger.debug("File already exists: %s", target)
        return target

    try:
        data = await fetch_url(
            url,
            session=session,
            semaphore=semaphore,
            timeout=timeout,
        )
    except RetryError:
        await record_manifest_async(
            manifest_path,
            source,
            url,
            target,
            status="failed",
            detail="Retry exhausted",
            registry_id=registry_id,
            registry_type=registry_type,
            document_type=document_type,
            lock=manifest_lock,
        )
        return None
    except aiohttp.ClientResponseError as exc:
        await record_manifest_async(
            manifest_path,
            source,
            url,
            target,
            status="failed",
            detail=f"HTTP {exc.status}",
            registry_id=registry_id,
            registry_type=registry_type,
            document_type=document_type,
            lock=manifest_lock,
        )
        return None
    except (aiohttp.ClientError, TimeoutError, ValueError, OSError) as exc:
        await record_manifest_async(
            manifest_path,
            source,
            url,
            target,
            status="failed",
            detail=str(exc),
            registry_id=registry_id,
            registry_type=registry_type,
            document_type=document_type,
            lock=manifest_lock,
        )
        return None

    detail = _pdf_error_detail(data, require_protocol)
    if detail:
        await record_manifest_async(
            manifest_path,
            source,
            url,
            target,
            status="failed",
            detail=detail,
            registry_id=registry_id,
            registry_type=registry_type,
            document_type=document_type,
            lock=manifest_lock,
        )
        return None

    write_error = await _write_pdf(target, data)
    if write_error:
        await record_manifest_async(
            manifest_path,
            source,
            url,
            target,
            status="failed",
            detail=write_error,
            registry_id=registry_id,
            registry_type=registry_type,
            document_type=document_type,
            lock=manifest_lock,
        )
        return None

    await record_manifest_async(
        manifest_path,
        source,
        url,
        target,
        status="downloaded",
        registry_id=registry_id,
        registry_type=registry_type,
        document_type=document_type,
        lock=manifest_lock,
    )
    logger.info("Downloaded: %s (%s bytes)", target.name, len(data))
    return target


def iter_protocol_docs(large_docs: Iterable[JsonDict]) -> Iterator[JsonDict]:
    """Yield actual study protocols, filtering out amendments/deviations."""
    exclude_terms = {"SAP", "ICF", "AMENDMENT", "DEVIATION", "VIOLATION", "CASE"}

    for doc in large_docs:
        filename = str(doc.get("filename") or "")
        if not filename:
            continue
        filename_upper = filename.upper()

        type_abbrev = str(doc.get("typeAbbrev") or "").upper()
        type_full = str(doc.get("type") or "").upper()
        label = str(doc.get("label") or "").upper()

        if any(
            exclude in filename_upper
            or exclude in type_abbrev
            or exclude in type_full
            or exclude in label
            for exclude in exclude_terms
        ):
            logger.debug(
                "Excluding non-protocol doc: %s (type=%s/%s, label=%s)",
                filename,
                type_abbrev,
                type_full,
                label,
            )
            continue

        if doc.get("hasProtocol") is True:
            yield doc
            continue

        if "PROTOCOL" in type_full or "STUDY PROTOCOL" in label:
            if "AMENDMENT" not in type_full and "DEVIATION" not in type_full:
                yield doc


def resolve_output_dir(output_root: Path, source: str) -> Path:
    """Resolve the output directory for a source."""
    spec = SOURCE_SPECS.get(source)
    if spec and spec.priority == "secondary":
        return output_root / "protocol_papers" / source
    return output_root / "crc_protocols" / source


async def _download_from_links(
    links: Iterable[str],
    *,
    destination_dir: Path,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    timeout: int,
    manifest_path: Path,
    source: str,
    manifest_lock: asyncio.Lock,
    max_items: int,
    document_type: Optional[str] = None,
    registry_id: Optional[str] = None,
    registry_type: Optional[str] = None,
) -> int:
    tasks: list[asyncio.Task[TaskResult]] = [
        asyncio.create_task(
            download_pdf(
                link,
                destination_dir,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
                manifest_path=manifest_path,
                source=source,
                manifest_lock=manifest_lock,
                require_protocol=True,
                document_type=document_type,
                registry_id=registry_id,
                registry_type=registry_type,
            )
        )
        for link in list(links)[:max_items]
    ]

    downloaded = 0
    for task in asyncio.as_completed(tasks):
        result = await task
        if result:
            downloaded += 1
        if downloaded >= max_items:
            break
    return downloaded


async def _process_journal_article(
    *,
    article_url: str,
    article_filter: Callable[[str], bool],
    destination_dir: Path,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    timeout: int,
    manifest_path: Path,
    source: str,
    manifest_lock: asyncio.Lock,
    include_keywords: Set[str],
    stats: dict[str, int],
) -> Optional[asyncio.Task[TaskResult]]:
    if not article_filter(article_url):
        stats["not_matching_pattern"] += 1
        return None

    try:
        html = await fetch_url(
            article_url,
            session=session,
            semaphore=semaphore,
            timeout=timeout,
        )
        stats["checked"] += 1
    except (aiohttp.ClientError, RetryError):
        stats["fetch_errors"] += 1
        return None

    try:
        pdf_urls = find_pdf_links(
            html,
            article_url,
            include_keywords=include_keywords,
        )
        stats["pdfs_found"] += len(pdf_urls)
    except Exception as exc:
        logger.debug("Error processing %s: %s", article_url, type(exc).__name__)
        return None

    if not pdf_urls:
        return None

    stats["download_attempts"] += 1
    return asyncio.create_task(
        download_pdf(
            pdf_urls[0],
            destination_dir,
            session=session,
            semaphore=semaphore,
            timeout=timeout,
            manifest_path=manifest_path,
            source=source,
            manifest_lock=manifest_lock,
            require_protocol=True,
            document_type="protocol_paper",
        )
    )


async def _download_journal_articles(
    *,
    source: str,
    sitemap: str,
    destination_dir: Path,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    manifest_lock: asyncio.Lock,
    max_items: int,
    timeout: int,
    manifest_path: Path,
    sitemap_limit: int,
    article_filter: Callable[[str], bool],
    include_keywords: Set[str],
) -> int:
    tasks: list[asyncio.Task[TaskResult]] = []
    downloaded = 0
    max_urls_to_check = max_items * 20

    stats = {
        "urls_received": 0,
        "not_matching_pattern": 0,
        "fetch_errors": 0,
        "checked": 0,
        "pdfs_found": 0,
        "download_attempts": 0,
    }

    article_urls = iter_sitemap_urls(
        sitemap,
        session=session,
        semaphore=semaphore,
        sitemap_limit=sitemap_limit,
        url_limit=max_urls_to_check,
        timeout=timeout,
    )

    async for article_url in article_urls:
        stats["urls_received"] += 1
        if len(tasks) >= max_items:
            break
        download_task = await _process_journal_article(
            article_url=article_url,
            article_filter=article_filter,
            destination_dir=destination_dir,
            session=session,
            semaphore=semaphore,
            timeout=timeout,
            manifest_path=manifest_path,
            source=source,
            manifest_lock=manifest_lock,
            include_keywords=include_keywords,
            stats=stats,
        )
        if download_task:
            tasks.append(download_task)

    for completed in asyncio.as_completed(tasks):
        result = await completed
        if result:
            downloaded += 1
        if downloaded >= max_items:
            break

    logger.info(
        "[%s] Stats: urls=%s, checked=%s, downloads=%s",
        source,
        stats["urls_received"],
        stats["checked"],
        downloaded,
    )

    return downloaded


async def iter_sitemap_urls(
    root_sitemap: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    sitemap_limit: int,
    url_limit: Optional[int],
    timeout: int,
) -> AsyncIterator[str]:
    """Iterate over URLs from a sitemap hierarchy."""
    logger.info("Fetching root sitemap: %s", root_sitemap)
    queue = await read_sitemap(
        root_sitemap,
        session=session,
        semaphore=semaphore,
        timeout=timeout,
    )

    if not queue:
        logger.warning("Empty sitemap: %s", root_sitemap)
        return

    sub_sitemaps = [
        url
        for url in queue
        if url.endswith((".xml", ".xml.gz")) or "sitemap" in url.lower()
    ]

    urls_yielded = 0
    if sub_sitemaps:
        for sitemap_url in sub_sitemaps[:sitemap_limit]:
            try:
                sitemap_urls = await read_sitemap(
                    sitemap_url,
                    session=session,
                    semaphore=semaphore,
                    timeout=timeout,
                )
            except (aiohttp.ClientError, ET.ParseError, RetryError) as exc:
                logger.warning(
                    "Skipping sub-sitemap %s: %s", sitemap_url, type(exc).__name__
                )
                continue
            for url in sitemap_urls:
                yield url
                urls_yielded += 1
                if url_limit is not None:
                    url_limit -= 1
                    if url_limit <= 0:
                        logger.info(
                            "Reached URL limit after yielding %s URLs", urls_yielded
                        )
                        return
    else:
        limit = url_limit or len(queue)
        logger.info("No sub-sitemaps found, yielding %s URLs", min(limit, len(queue)))
        for url in queue[:limit]:
            yield url
            urls_yielded += 1

    logger.info("Sitemap iteration complete: yielded %s URLs", urls_yielded)


async def read_sitemap(
    url: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    timeout: int = 30,
) -> list[str]:
    """Read and parse a sitemap XML file."""
    raw = await fetch_url(url, session=session, semaphore=semaphore, timeout=timeout)
    if url.endswith(".gz"):
        raw = gzip.decompress(raw)
    root = ET.fromstring(raw)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []
    for loc in root.findall(".//s:loc", ns):
        if loc.text:
            urls.append(loc.text.strip())
    if not urls:
        for loc in root.iter("loc"):
            if loc.text:
                urls.append(loc.text.strip())
    return urls


class ProtocolDownloader:
    """Downloader orchestration for protocol sources."""

    def __init__(self, config: DownloadConfig) -> None:
        """Initialize downloader with config."""
        self.config = config
        self.manifest_lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(compute_concurrency_limit())

    async def run(self) -> int:
        """Run the download pipeline across selected sources."""
        output_dir = self.config.output_dir
        ensure_dir(output_dir)
        ensure_dir(output_dir / "crc_protocols")
        ensure_dir(output_dir / "protocol_papers")

        manifest_path = output_dir / "manifest.jsonl"
        total_downloaded = 0
        source_results: dict[str, int] = {}

        async with aiohttp.ClientSession(
            headers={"User-Agent": USER_AGENT},
            connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
        ) as session:
            for source in self._selected_sources():
                if total_downloaded >= self.config.max_total:
                    logger.info("Reached max_total (%s)", self.config.max_total)
                    break

                handler = self._source_handlers()[source]
                remaining = self.config.max_total - total_downloaded
                per_source_limit = min(self.config.max_per_source, remaining)
                logger.info(
                    "Processing: %s (target: %s PDFs)", source, per_source_limit
                )

                downloaded = await handler(
                    session=session,
                    manifest_path=manifest_path,
                    max_items=per_source_limit,
                )
                source_results[source] = downloaded
                total_downloaded += downloaded
                logger.info(
                    "%s: %s PDFs (total: %s)",
                    source,
                    downloaded,
                    total_downloaded,
                )

                await asyncio.sleep(1)

        self._log_summary(total_downloaded, source_results, manifest_path)
        return total_downloaded

    def _selected_sources(self) -> list[str]:
        sources = [
            name for name, spec in SOURCE_SPECS.items() if spec.enabled_by_default
        ]
        if self.config.include_journal_sources:
            sources.extend(
                name
                for name, spec in SOURCE_SPECS.items()
                if spec.priority == "secondary"
            )
        requested = self.config.sources
        resolved = requested or sources
        return sorted(set(resolved))

    def _log_summary(
        self,
        total_downloaded: int,
        source_results: dict[str, int],
        manifest_path: Path,
    ) -> None:
        logger.info("=" * 60)
        logger.info("Complete: %s protocol PDFs downloaded", total_downloaded)
        logger.info("Results by source:")
        for source, count in source_results.items():
            logger.info("  %s: %s PDFs", source, count)
        logger.info("Output: %s", self.config.output_dir)
        logger.info("Manifest: %s", manifest_path)
        logger.info("=" * 60)
        print(
            f"Downloaded {total_downloaded} protocol PDFs into {self.config.output_dir}"
        )
        print(f"Manifest: {manifest_path}")

    def _source_handlers(self) -> dict[str, Callable[..., Awaitable[int]]]:
        return {
            "dac": self._download_from_dac,
            "clinicaltrials": self._download_from_clinicaltrials,
            "bmjopen": self._download_from_bmjopen,
            "jmir": self._download_from_jmir,
            "isrctn": self._download_from_isrctn,
            "ctis": self._download_from_ctis,
        }

    async def _download_from_dac(
        self,
        *,
        session: aiohttp.ClientSession,
        manifest_path: Path,
        max_items: int,
    ) -> int:
        source = "dac"
        url = "https://dac-trials.org/resources/protocol-library/protocol-registry/"
        destination_dir = resolve_output_dir(self.config.output_dir, source)

        try:
            html = await fetch_url(
                url,
                session=session,
                semaphore=self.semaphore,
                timeout=self.config.timeout,
            )
        except (aiohttp.ClientError, RetryError) as exc:
            logger.error("Failed to fetch DAC registry page: %s", exc)
            return 0

        try:
            links, _, link_text = parse_html_links(html, url)
            pdf_links = [link for link in links if ".pdf" in link.lower()]
            pdf_links = [link for link in pdf_links if is_same_domain(link, url)]
            keyword_hits = {
                link
                for link in pdf_links
                if "protocol" in link.lower() or "protocol" in link_text.get(link, "")
            }
            if keyword_hits:
                pdf_links = sorted(keyword_hits)
        except Exception as exc:
            logger.error("Failed to parse DAC registry page: %s", exc)
            return 0

        if not pdf_links:
            logger.warning("No protocol PDF links found in DAC registry")
            return 0

        return await _download_from_links(
            pdf_links,
            destination_dir=destination_dir,
            session=session,
            semaphore=self.semaphore,
            timeout=self.config.timeout,
            manifest_path=manifest_path,
            source=source,
            manifest_lock=self.manifest_lock,
            max_items=max_items,
            document_type="protocol",
        )

    async def _download_from_clinicaltrials(
        self,
        *,
        session: aiohttp.ClientSession,
        manifest_path: Path,
        max_items: int,
    ) -> int:
        source = "clinicaltrials"
        destination_dir = resolve_output_dir(self.config.output_dir, source)
        stats = {
            "studies_checked": 0,
            "studies_with_docs": 0,
            "protocol_docs_found": 0,
            "download_attempts": 0,
            "download_failures": 0,
            "fetch_errors": 0,
        }
        stats_lock = asyncio.Lock()
        limit_reached = asyncio.Event()
        download_lock = asyncio.Lock()
        downloaded = 0

        async def record_success() -> None:
            nonlocal downloaded
            async with download_lock:
                downloaded += 1
                if downloaded >= max_items:
                    limit_reached.set()

        nct_ids = await self._fetch_study_ids(session, max_items)
        tasks = [
            asyncio.create_task(
                self._process_clinicaltrials_study(
                    nct_id=nct_id,
                    session=session,
                    destination_dir=destination_dir,
                    manifest_path=manifest_path,
                    stats=stats,
                    stats_lock=stats_lock,
                    limit_reached=limit_reached,
                    record_success=record_success,
                )
            )
            for nct_id in nct_ids
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(
            "[%s] Stats: studies=%s, with_docs=%s, protocol_docs=%s, downloads=%s",
            source,
            stats["studies_checked"],
            stats["studies_with_docs"],
            stats["protocol_docs_found"],
            downloaded,
        )
        return downloaded

    async def _process_clinicaltrials_study(
        self,
        *,
        nct_id: str,
        session: aiohttp.ClientSession,
        destination_dir: Path,
        manifest_path: Path,
        stats: dict[str, int],
        stats_lock: asyncio.Lock,
        limit_reached: asyncio.Event,
        record_success: Callable[[], Awaitable[None]],
    ) -> None:
        if limit_reached.is_set():
            return
        study = await self._fetch_study(nct_id, session, stats, stats_lock)
        if study is None:
            return
        large_docs = (
            study.get("documentSection", {})
            .get("largeDocumentModule", {})
            .get("largeDocs", [])
            or []
        )
        if not large_docs:
            return
        async with stats_lock:
            stats["studies_with_docs"] += 1
        protocol_docs = list(iter_protocol_docs(large_docs))
        if not protocol_docs:
            return
        async with stats_lock:
            stats["protocol_docs_found"] += len(protocol_docs)

        for doc in protocol_docs:
            if limit_reached.is_set():
                return
            filename = doc.get("filename")
            if not filename:
                continue
            download_url = self._clinicaltrials_download_url(nct_id, str(filename))
            async with stats_lock:
                stats["download_attempts"] += 1
            result = await download_pdf(
                download_url,
                destination_dir,
                session=session,
                semaphore=self.semaphore,
                timeout=self.config.timeout,
                manifest_path=manifest_path,
                source="clinicaltrials",
                manifest_lock=self.manifest_lock,
                require_protocol=True,
                registry_id=nct_id,
                registry_type="nct",
                document_type="protocol",
            )
            if result:
                await record_success()
            else:
                async with stats_lock:
                    stats["download_failures"] += 1

    @staticmethod
    def _clinicaltrials_download_url(nct_id: str, filename: str) -> str:
        nct_digits = nct_id[3:]
        last_two = nct_digits[-2:]
        return (
            f"https://clinicaltrials.gov/ProvidedDocs/{last_two}/{nct_id}/{filename}"
        )

    async def _fetch_study(
        self,
        nct_id: str,
        session: aiohttp.ClientSession,
        stats: dict[str, int],
        stats_lock: asyncio.Lock,
    ) -> Optional[JsonDict]:
        try:
            study = await fetch_json(
                f"https://clinicaltrials.gov/api/v2/studies/{nct_id}",
                session=session,
                semaphore=self.semaphore,
                timeout=self.config.timeout,
            )
            async with stats_lock:
                stats["studies_checked"] += 1
            return study
        except (aiohttp.ClientError, RetryError) as exc:
            logger.warning("[%s] Fetch error: %s", nct_id, type(exc).__name__)
            async with stats_lock:
                stats["fetch_errors"] += 1
            return None

    async def _fetch_study_ids(
        self, session: aiohttp.ClientSession, max_items: int
    ) -> list[str]:
        search_terms = [
            "AREA[OverallStatus]Completed AND AREA[Phase]Phase 3",
            "AREA[OverallStatus]Completed AND AREA[Phase]Phase 4",
            "AREA[IsFDARegulatedDrug]true",
        ]
        max_studies_to_check = max_items * 50
        processed: set[str] = set()

        for search_term in search_terms:
            try:
                payload = await fetch_json(
                    "https://clinicaltrials.gov/api/v2/studies",
                    session=session,
                    semaphore=self.semaphore,
                    params={
                        "query.term": search_term,
                        "pageSize": str(min(100, max_studies_to_check)),
                        "fields": "protocolSection.identificationModule",
                    },
                    timeout=self.config.timeout,
                )
            except (aiohttp.ClientError, RetryError):
                continue

            studies = payload.get("studies", []) or []
            nct_ids = [
                study.get("protocolSection", {})
                .get("identificationModule", {})
                .get("nctId")
                for study in studies
            ]
            for nct_id in [n for n in nct_ids if n]:
                if nct_id in processed:
                    continue
                processed.add(nct_id)
                if len(processed) >= max_studies_to_check:
                    break
            if len(processed) >= max_studies_to_check:
                break
        return list(processed)

    async def _download_from_bmjopen(
        self,
        *,
        session: aiohttp.ClientSession,
        manifest_path: Path,
        max_items: int,
    ) -> int:
        source = "bmjopen"
        destination_dir = resolve_output_dir(self.config.output_dir, source)
        return await _download_journal_articles(
            source=source,
            sitemap="https://bmjopen.bmj.com/sitemap.xml",
            destination_dir=destination_dir,
            session=session,
            semaphore=self.semaphore,
            manifest_lock=self.manifest_lock,
            max_items=max_items,
            timeout=self.config.timeout,
            manifest_path=manifest_path,
            sitemap_limit=self.config.sitemap_limit,
            article_filter=lambda url: "/content/" in url,
            include_keywords={"protocol"},
        )

    async def _download_from_jmir(
        self,
        *,
        session: aiohttp.ClientSession,
        manifest_path: Path,
        max_items: int,
    ) -> int:
        source = "jmir"
        destination_dir = resolve_output_dir(self.config.output_dir, source)
        pattern = re.compile(r"researchprotocols\.org/\d{4}/\d+/e\d+/?$")
        return await _download_journal_articles(
            source=source,
            sitemap="https://www.researchprotocols.org/sitemap.xml",
            destination_dir=destination_dir,
            session=session,
            semaphore=self.semaphore,
            manifest_lock=self.manifest_lock,
            max_items=max_items,
            timeout=self.config.timeout,
            manifest_path=manifest_path,
            sitemap_limit=self.config.sitemap_limit,
            article_filter=lambda url: bool(pattern.search(url)),
            include_keywords={"protocol"},
        )

    async def _download_from_isrctn(
        self,
        *,
        session: aiohttp.ClientSession,
        manifest_path: Path,
        max_items: int,
    ) -> int:
        source = "isrctn"
        destination_dir = resolve_output_dir(self.config.output_dir, source)
        protocol_files = await self._collect_isrctn_protocol_files(session, max_items)
        if not protocol_files:
            logger.warning("No ISRCTN protocol files found")
            return 0
        return await self._download_isrctn_files(
            protocol_files,
            destination_dir=destination_dir,
            session=session,
            manifest_path=manifest_path,
            max_items=max_items,
        )

    async def _collect_isrctn_protocol_files(
        self, session: aiohttp.ClientSession, max_items: int
    ) -> dict[str, tuple[str, str]]:
        query_terms = ["clinical trial", "randomized", "protocol"]
        max_records = max_items * 10
        protocol_files: dict[str, tuple[str, str]] = {}

        for term in query_terms:
            if len(protocol_files) >= max_records:
                break
            url = (
                "https://www.isrctn.com/api/query/format/default?"
                + urllib.parse.urlencode({"q": term, "limit": str(max_records)})
            )
            try:
                xml_data = await fetch_url(
                    url,
                    session=session,
                    semaphore=self.semaphore,
                    timeout=self.config.timeout,
                )
            except (aiohttp.ClientError, RetryError):
                continue
            for isrctn_id, download_url, description in extract_isrctn_protocol_files(
                xml_data
            ):
                protocol_files.setdefault(isrctn_id, (download_url, description))
        return protocol_files

    async def _download_isrctn_files(
        self,
        protocol_files: dict[str, tuple[str, str]],
        *,
        destination_dir: Path,
        session: aiohttp.ClientSession,
        manifest_path: Path,
        max_items: int,
    ) -> int:
        tasks: list[asyncio.Task[TaskResult]] = []
        for isrctn_id, (download_url, description) in list(protocol_files.items())[
            : max_items * 5
        ]:
            pdf_url = (
                download_url
                if download_url.startswith("http")
                else urllib.parse.urljoin("https://www.isrctn.com/", download_url)
            )
            tasks.append(
                asyncio.create_task(
                    download_pdf(
                        pdf_url,
                        destination_dir,
                        session=session,
                        semaphore=self.semaphore,
                        timeout=self.config.timeout,
                        manifest_path=manifest_path,
                        source="isrctn",
                        manifest_lock=self.manifest_lock,
                        require_protocol=True,
                        registry_id=isrctn_id,
                        registry_type="isrctn",
                        document_type=description or "protocol",
                    )
                )
            )
            if len(tasks) >= max_items:
                break

        downloaded = 0
        for task in asyncio.as_completed(tasks):
            result = await task
            if result:
                downloaded += 1
            if downloaded >= max_items:
                break
        return downloaded

    async def _download_from_ctis(
        self,
        *,
        session: aiohttp.ClientSession,
        manifest_path: Path,
        max_items: int,
    ) -> int:
        destination_dir = resolve_output_dir(self.config.output_dir, "ctis")
        ct_numbers = await self._fetch_ctis_trials(session, max_items)
        if not ct_numbers:
            return 0
        return await self._download_ctis_files(
            ct_numbers,
            destination_dir=destination_dir,
            session=session,
            manifest_path=manifest_path,
            max_items=max_items,
        )

    async def _fetch_ctis_trials(
        self, session: aiohttp.ClientSession, max_items: int
    ) -> list[str]:
        search_payload = {
            "pagination": {"page": 1, "size": min(max_items * 5, 50)},
            "sort": {"property": "decisionDate", "direction": "DESC"},
            "searchCriteria": {"title": None, "number": None, "status": None},
        }
        try:
            search_results = await fetch_json_post(
                "https://euclinicaltrials.eu/ctis-public-api/search",
                session=session,
                semaphore=self.semaphore,
                payload=search_payload,
                timeout=self.config.timeout,
            )
        except (aiohttp.ClientError, RetryError):
            return []

        trials = search_results.get("data", []) or []
        return [trial.get("ctNumber") for trial in trials if trial.get("ctNumber")]

    async def _download_ctis_files(
        self,
        ct_numbers: list[str],
        *,
        destination_dir: Path,
        session: aiohttp.ClientSession,
        manifest_path: Path,
        max_items: int,
    ) -> int:
        tasks: list[asyncio.Task[TaskResult]] = []
        for ct_number in ct_numbers:
            if len(tasks) >= max_items:
                break
            detail = await self._fetch_ctis_detail(session, ct_number)
            if not detail:
                continue
            links = extract_ctis_protocol_links(detail)
            if not links:
                continue
            url_value, label = links[0]
            url_value = self._normalize_ctis_url(url_value)
            tasks.append(
                asyncio.create_task(
                    download_pdf(
                        url_value,
                        destination_dir,
                        session=session,
                        semaphore=self.semaphore,
                        timeout=self.config.timeout,
                        manifest_path=manifest_path,
                        source="ctis",
                        manifest_lock=self.manifest_lock,
                        require_protocol=True,
                        registry_id=ct_number,
                        registry_type="ctis_trial_id",
                        document_type=label or "protocol",
                    )
                )
            )

        downloaded = 0
        for task in asyncio.as_completed(tasks):
            result = await task
            if result:
                downloaded += 1
            if downloaded >= max_items:
                break
        return downloaded

    async def _fetch_ctis_detail(
        self, session: aiohttp.ClientSession, ct_number: str
    ) -> Optional[JsonDict]:
        try:
            return await fetch_json(
                f"https://euclinicaltrials.eu/ctis-public-api/retrieve/{ct_number}",
                session=session,
                semaphore=self.semaphore,
                timeout=self.config.timeout,
            )
        except (aiohttp.ClientError, RetryError):
            return None

    @staticmethod
    def _normalize_ctis_url(url_value: str) -> str:
        if url_value.startswith("http"):
            return url_value
        return urllib.parse.urljoin("https://euclinicaltrials.eu", url_value)


SOURCE_SPECS: dict[str, SourceSpec] = {
    "clinicaltrials": SourceSpec("clinicaltrials", "api", "nct", "primary", True),
    "dac": SourceSpec("dac", "html_crawl", "dac", "primary", True),
    "ctis": SourceSpec("ctis", "portal_scrape", "ctis_trial_id", "primary", True),
    "isrctn": SourceSpec("isrctn", "xml_api", "isrctn", "primary", True),
    "bmjopen": SourceSpec("bmjopen", "sitemap", "doi", "secondary", False),
    "jmir": SourceSpec("jmir", "sitemap", "doi", "secondary", False),
}


def build_config(args: argparse.Namespace) -> DownloadConfig:
    """Build a DownloadConfig from CLI args."""
    return DownloadConfig(
        output_dir=Path(args.output_dir).resolve(),
        include_journal_sources=args.include_journal_sources,
        sources=args.sources,
        max_per_source=args.max_per_source,
        max_total=args.max_total,
        timeout=args.timeout,
        sitemap_limit=args.sitemap_limit,
        verbose=args.verbose,
    )


async def main_async() -> int:
    """Async CLI entrypoint for downloading protocol PDFs."""
    parser = argparse.ArgumentParser(
        description="Download ONLY clinical trial protocol PDFs from specified sources."
    )
    parser.add_argument(
        "--output-dir",
        default="data/protocols",
        help="Directory to store downloaded PDFs.",
    )
    parser.add_argument(
        "--include-journal-sources",
        action="store_true",
        help="Include demoted journal sources (bmjopen, jmir).",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=sorted(SOURCE_SPECS.keys()),
        default=None,
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
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )

    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.info("Verbose logging enabled")

    config = build_config(args)
    downloader = ProtocolDownloader(config)
    return await downloader.run()


def main() -> int:
    """Sync CLI entrypoint."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
