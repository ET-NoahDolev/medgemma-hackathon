#!/usr/bin/env python3

"""Download ONLY clinical trial protocols from designated sources.

This revised script implements strict filtering to download only actual study
protocols, not amendments, deviations, violations, or unrelated documents.

Key improvements:
1. ClinicalTrials.gov: Filter by hasProtocol=true AND typeAbbrev match specific patterns
2. BMJ Open: Only fetch articles explicitly tagged as "research protocol" or "study protocol"
3. JMIR: Only fetch articles from "Research Protocols" section with validation
4. DAC: Validate document metadata before download
5. All sources: PDF validation with magic bytes and content checks
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
    name: str
    discovery_method: str
    identifier_type: str
    priority: str
    enabled_by_default: bool


class LinkExtractor(HTMLParser):
    """Collect anchors and meta tags from an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.links: List[str] = []
        self.meta: dict[str, str] = {}
        self._current_href: Optional[str] = None
        self._current_text: List[str] = []
        self.link_text: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
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
        if tag == "a" and self._current_href:
            text = " ".join(self._current_text).strip()
            if text:
                self.link_text[self._current_href] = text
            self._current_href = None
            self._current_text = []

    def handle_data(self, data: str) -> None:
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
        raise


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
    params: Optional[dict] = None,
    timeout: int = 30,
) -> dict:
    """Fetch JSON from a URL with retry logic."""
    if params:
        query_string = urllib.parse.urlencode(params)
        url = f"{url}?{query_string}"
    try:
        data = await fetch_url(
            url, session=session, semaphore=semaphore, timeout=timeout
        )
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from {url}: {e}")
        raise


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
    payload: dict,
    timeout: int = 30,
) -> dict:
    """POST JSON and return JSON response with retry logic."""
    try:
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


def resolve_output_dir(output_root: Path, source: str) -> Path:
    spec = SOURCE_SPECS.get(source)
    if spec and spec.priority == "secondary":
        return output_root / "protocol_papers" / source
    return output_root / "crc_protocols" / source


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


def parse_html_links(
    html: bytes, base_url: str
) -> tuple[Set[str], dict[str, str], dict[str, str]]:
    parser = LinkExtractor()
    parser.feed(html.decode("utf-8", errors="ignore"))
    links = {urllib.parse.urljoin(base_url, link) for link in parser.links}
    link_text = {
        urllib.parse.urljoin(base_url, href): text
        for href, text in parser.link_text.items()
    }
    return links, parser.meta, link_text


def extract_pdf_links(html: bytes, base_url: str) -> List[str]:
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
    return _normalize_domain(url) == _normalize_domain(base_url)


def find_pdf_links(
    html: bytes,
    base_url: str,
    *,
    include_keywords: Optional[Set[str]] = None,
) -> List[str]:
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


def extract_isrctn_ids(xml_data: bytes) -> List[str]:
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


def extract_isrctn_protocol_files(xml_data: bytes) -> List[tuple[str, str, str]]:
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}")[0].strip("{")
    ns = {"i": namespace} if namespace else {}
    results: List[tuple[str, str, str]] = []

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
            if description_node is not None and description_node.text:
                description = description_node.text.strip()
            else:
                description = ""
            if "protocol" in description.lower() and download_url:
                results.append((isrctn_id, download_url, description))

    return results


def extract_ctis_protocol_links(payload: object) -> List[tuple[str, str]]:
    links: List[tuple[str, str]] = []

    def walk(value: object) -> None:
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
            label_parts: List[str] = []
            for k in (
                "documentType",
                "documentTypeCode",
                "documentTitle",
                "title",
                "type",
                "name",
            ):
                if k in value and isinstance(value[k], str):
                    label_parts.append(value[k])
            if url_key and isinstance(value.get(url_key), str):
                url_value = value[url_key]
                label = " ".join(label_parts).strip()
                if label:
                    links.append((url_value, label))
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    protocol_links: List[tuple[str, str]] = []
    for url_value, label in links:
        lowered = label.lower()
        if "protocol" in lowered and "synopsis" not in lowered and "icf" not in lowered:
            protocol_links.append((url_value, label))
    return protocol_links


def looks_like_protocol_text(text: str) -> bool:
    lowered = text.lower()
    if "protocol" not in lowered and "study protocol" not in lowered:
        return False
    if "statistical analysis plan" in lowered or "sap" in lowered:
        return False
    return True


def validate_protocol_pdf_content(data: bytes) -> Optional[bool]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except Exception:
        logger.debug("pypdf not available; skipping content validation")
        return None

    try:
        from io import BytesIO

        reader = PdfReader(BytesIO(data))
        text_chunks: List[str] = []
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


async def read_sitemap(
    url: str,
    *,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    timeout: int = 30,
) -> List[str]:
    """Read and parse a sitemap XML file."""
    try:
        raw = await fetch_url(
            url, session=session, semaphore=semaphore, timeout=timeout
        )
        logger.debug(f"Fetched sitemap {url}: {len(raw)} bytes")
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
        logger.debug(f"Parsed sitemap {url}: found {len(urls)} URLs")
        return urls
    except aiohttp.ClientResponseError as e:
        logger.warning(f"HTTP error fetching sitemap {url}: {e.status}")
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
    """Iterate over URLs from a sitemap hierarchy."""
    logger.info(f"Fetching root sitemap: {root_sitemap}")
    try:
        queue = await read_sitemap(
            root_sitemap,
            session=session,
            semaphore=semaphore,
            timeout=timeout,
        )
    except (aiohttp.ClientError, ET.ParseError, RetryError) as e:
        logger.warning(
            f"Failed to read root sitemap {root_sitemap}: {type(e).__name__}"
        )
        return

    if not queue:
        logger.warning(f"Empty sitemap: {root_sitemap}")
        return

    logger.info(f"Root sitemap returned {len(queue)} entries")

    sub_sitemaps = [
        url
        for url in queue
        if url.endswith((".xml", ".xml.gz")) or "sitemap" in url.lower()
    ]
    urls_yielded = 0

    if sub_sitemaps:
        logger.info(
            f"Found {len(sub_sitemaps)} sub-sitemaps, processing up to {sitemap_limit}"
        )
        for sitemap_url in sub_sitemaps[:sitemap_limit]:
            try:
                sitemap_urls = await read_sitemap(
                    sitemap_url,
                    session=session,
                    semaphore=semaphore,
                    timeout=timeout,
                )
                logger.info(f"Sub-sitemap returned {len(sitemap_urls)} URLs")
            except (aiohttp.ClientError, ET.ParseError, RetryError) as e:
                logger.warning(
                    f"Skipping sub-sitemap {sitemap_url}: {type(e).__name__}"
                )
                continue

            for url in sitemap_urls:
                yield url
                urls_yielded += 1
                if url_limit is not None:
                    url_limit -= 1
                    if url_limit <= 0:
                        logger.info(
                            f"Reached URL limit after yielding {urls_yielded} URLs"
                        )
                        return
    else:
        logger.info(
            f"No sub-sitemaps found, yielding {min(url_limit or len(queue), len(queue))} URLs"
        )
        for url in queue[: url_limit or len(queue)]:
            yield url
            urls_yielded += 1

    logger.info(f"Sitemap iteration complete: yielded {urls_yielded} URLs")


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
) -> Optional[Path]:
    """Download a PDF file with validation."""
    try:
        ensure_dir(destination_dir)
        filename = normalize_filename(url)
        target = destination_dir / filename

        if target.exists():
            logger.debug(f"File already exists: {target}")
            return target

        try:
            data = await fetch_url(
                url,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
            )
        except RetryError:
            logger.warning(f"Failed to download {url} after retries")
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
        except aiohttp.ClientResponseError as e:
            logger.debug(f"HTTP error {e.status} for {url}")
            await record_manifest_async(
                manifest_path,
                source,
                url,
                target,
                status="failed",
                detail=f"HTTP {e.status}",
                registry_id=registry_id,
                registry_type=registry_type,
                document_type=document_type,
                lock=manifest_lock,
            )
            return None
        except (aiohttp.ClientError, TimeoutError, ValueError, OSError) as exc:
            logger.warning(f"Error downloading {url}: {exc}")
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

        if len(data) < 100:
            logger.warning(f"Downloaded file too small for {url}")
            await record_manifest_async(
                manifest_path,
                source,
                url,
                target,
                status="failed",
                detail="File too small",
                registry_id=registry_id,
                registry_type=registry_type,
                document_type=document_type,
                lock=manifest_lock,
            )
            return None

        if not data.startswith(b"%PDF"):
            logger.warning(f"Downloaded file doesn't have PDF magic bytes: {url}")
            await record_manifest_async(
                manifest_path,
                source,
                url,
                target,
                status="failed",
                detail="Not a valid PDF",
                registry_id=registry_id,
                registry_type=registry_type,
                document_type=document_type,
                lock=manifest_lock,
            )
            return None

        if require_protocol:
            is_protocol = validate_protocol_pdf_content(data)
            if is_protocol is False:
                logger.warning("Downloaded PDF does not look like a protocol: %s", url)
                await record_manifest_async(
                    manifest_path,
                    source,
                    url,
                    target,
                    status="failed",
                    detail="PDF content missing protocol indicators",
                    registry_id=registry_id,
                    registry_type=registry_type,
                    document_type=document_type,
                    lock=manifest_lock,
                )
                return None

        try:
            await asyncio.to_thread(target.write_bytes, data)
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
                detail="Write error",
                registry_id=registry_id,
                registry_type=registry_type,
                document_type=document_type,
                lock=manifest_lock,
            )
            return None

    except Exception as e:
        logger.error(f"Unexpected error downloading {url}: {e}")
        return None


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
    """Download PDFs from DAC protocol registry with validation."""
    source = "dac"
    url = "https://dac-trials.org/resources/protocol-library/protocol-registry/"
    destination_dir = resolve_output_dir(output_dir, source)

    try:
        html = await fetch_url(
            url, session=session, semaphore=semaphore, timeout=timeout
        )
    except (aiohttp.ClientError, RetryError) as e:
        logger.error(f"Failed to fetch DAC registry page: {e}")
        return 0

    try:
        links, _, link_text = parse_html_links(html, url)
        pdf_links = [link for link in links if ".pdf" in link.lower()]
        pdf_links = [link for link in pdf_links if is_same_domain(link, url)]
        keyword_hits: Set[str] = set()
        for link in pdf_links:
            text = link_text.get(link, "").lower()
            if "protocol" in link.lower() or "protocol" in text:
                keyword_hits.add(link)
        if keyword_hits:
            pdf_links = sorted(keyword_hits)
    except Exception as e:
        logger.error(f"Failed to parse DAC registry page: {e}")
        return 0

    if not pdf_links:
        logger.warning("No protocol PDF links found in DAC registry")
        return 0

    logger.info(f"Found {len(pdf_links)} protocol PDFs in DAC registry")

    downloaded = 0
    tasks = [
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
                document_type="protocol",
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

    return downloaded


def iter_protocol_docs(large_docs: List[dict]) -> Iterator[dict]:
    """Yield ONLY actual study protocols, filtering out amendments/deviations/violations."""

    exclude_terms = {"SAP", "ICF", "AMENDMENT", "DEVIATION", "VIOLATION", "CASE"}

    for doc in large_docs:
        filename = doc.get("filename", "")
        if not filename:
            continue
        filename_upper = filename.upper()

        type_abbrev = (doc.get("typeAbbrev") or "").upper()
        type_full = (doc.get("type") or "").upper()
        label = (doc.get("label") or "").upper()

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


async def download_from_clinicaltrials(
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
    """Download protocols from ClinicalTrials.gov with strict filtering."""
    source = "clinicaltrials"
    destination_dir = resolve_output_dir(output_dir, source)
    downloaded = 0
    download_lock = asyncio.Lock()
    limit_reached = asyncio.Event()

    stats = {
        "studies_checked": 0,
        "studies_with_docs": 0,
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
            study_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
            study = await fetch_json(
                study_url,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
            )

            async with stats_lock:
                stats["studies_checked"] += 1

            doc_section = study.get("documentSection", {})
            large_doc_module = doc_section.get("largeDocumentModule", {})
            large_docs = large_doc_module.get("largeDocs", []) or []

            if not large_docs:
                return

            async with stats_lock:
                stats["studies_with_docs"] += 1

            protocol_docs = list(iter_protocol_docs(large_docs))
            if not protocol_docs:
                logger.debug(
                    "[%s] No protocol-like docs found among %s documents",
                    nct_id,
                    len(large_docs),
                )
                return

            logger.info("[%s] Found %s protocol docs", nct_id, len(protocol_docs))
            async with stats_lock:
                stats["protocol_docs_found"] += len(protocol_docs)

            for doc in protocol_docs:
                if limit_reached.is_set():
                    return

                filename = doc.get("filename")
                if not filename:
                    continue

                nct_digits = nct_id[3:]
                last_two = nct_digits[-2:]
                download_url = f"https://clinicaltrials.gov/ProvidedDocs/{last_two}/{nct_id}/{filename}"

                async with stats_lock:
                    stats["download_attempts"] += 1

                result = await download_pdf(
                    download_url,
                    destination_dir,
                    session=session,
                    semaphore=semaphore,
                    timeout=timeout,
                    manifest_path=manifest_path,
                    source=source,
                    manifest_lock=manifest_lock,
                    require_protocol=True,
                    registry_id=nct_id,
                    registry_type="nct",
                    document_type="protocol",
                )

                if result:
                    count = await record_success()
                    logger.info("[%s] Downloaded: %s", nct_id, filename)
                    if count >= max_items:
                        return
                else:
                    async with stats_lock:
                        stats["download_failures"] += 1

        except (aiohttp.ClientError, RetryError) as e:
            logger.warning("[%s] Fetch error: %s", nct_id, type(e).__name__)
            async with stats_lock:
                stats["fetch_errors"] += 1
        except Exception as e:
            logger.warning("[%s] Error: %s: %s", nct_id, type(e).__name__, e)
            async with stats_lock:
                stats["fetch_errors"] += 1

    search_terms = [
        "AREA[OverallStatus]Completed AND AREA[Phase]Phase 3",
        "AREA[OverallStatus]Completed AND AREA[Phase]Phase 4",
        "AREA[IsFDARegulatedDrug]true",
    ]

    max_studies_to_check = max_items * 50
    processed_nct_ids: Set[str] = set()
    tasks: List[asyncio.Task] = []

    for search_term in search_terms:
        if limit_reached.is_set():
            break

        try:
            payload = await fetch_json(
                "https://clinicaltrials.gov/api/v2/studies",
                session=session,
                semaphore=semaphore,
                params={
                    "query.term": search_term,
                    "pageSize": min(100, max_studies_to_check),
                    "fields": "protocolSection.identificationModule",
                },
                timeout=timeout,
            )

            studies = payload.get("studies", []) or []
            nct_ids = [
                study.get("protocolSection", {})
                .get("identificationModule", {})
                .get("nctId")
                for study in studies
            ]
            nct_ids = [nct_id for nct_id in nct_ids if nct_id]

            logger.info("Found %s studies for '%s'", len(nct_ids), search_term)

            for nct_id in nct_ids:
                if limit_reached.is_set():
                    break
                if nct_id in processed_nct_ids:
                    continue

                processed_nct_ids.add(nct_id)
                if len(processed_nct_ids) > max_studies_to_check:
                    break

                tasks.append(asyncio.create_task(process_study(nct_id)))

        except (aiohttp.ClientError, RetryError) as e:
            logger.warning("Search error for '%s': %s", search_term, type(e).__name__)
            continue

    try:
        for task in asyncio.as_completed(tasks):
            await task
            if limit_reached.is_set():
                break
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
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
    """Download ONLY research protocols from BMJ Open (strict filtering)."""
    source = "bmjopen"
    sitemap = "https://bmjopen.bmj.com/sitemap.xml"
    destination_dir = resolve_output_dir(output_dir, source)
    downloaded = 0
    urls_processed = 0
    max_urls_to_check = max_items * 20

    stats = {
        "urls_received": 0,
        "no_content_path": 0,
        "fetch_errors": 0,
        "checked": 0,
        "not_protocol": 0,
        "pdfs_found": 0,
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
        logger.error("Failed to read BMJ Open sitemap: %s", type(e).__name__)
        return 0

    tasks: List[asyncio.Task] = []

    async for article_url in article_urls:
        stats["urls_received"] += 1

        if "/content/" not in article_url:
            stats["no_content_path"] += 1
            continue

        urls_processed += 1

        try:
            html = await fetch_url(
                article_url,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
            )
            stats["checked"] += 1
        except (aiohttp.ClientError, RetryError):
            logger.debug("Fetch error: %s", article_url)
            stats["fetch_errors"] += 1
            continue

        html_text = html.decode("utf-8", errors="ignore").lower()

        is_protocol = False
        if (
            'article-type="research-article"' in html_text
            or 'content="research-article"' in html_text
        ):
            if "protocol" in html_text[:5000] and "study protocol" in html_text[:5000]:
                is_protocol = True

        if not is_protocol:
            stats["not_protocol"] += 1
            logger.debug("Not a protocol article: %s", article_url)
            continue

        try:
            pdf_urls = find_pdf_links(html, article_url, include_keywords={"protocol"})
            stats["pdfs_found"] += len(pdf_urls)

            if not pdf_urls:
                base_url = article_url.rstrip("/")
                potential = [
                    f"{base_url}.full.pdf",
                    f"{base_url}/full.pdf",
                    f"{base_url}.pdf",
                ]
                pdf_urls = [
                    url for url in potential if is_same_domain(url, article_url)
                ]

            if not pdf_urls:
                logger.debug("No PDFs found in %s", article_url)
                continue

            for pdf_url in pdf_urls[:1]:
                if len(tasks) >= max_items:
                    break
                stats["download_attempts"] += 1
                tasks.append(
                    asyncio.create_task(
                        download_pdf(
                            pdf_url,
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
                )

        except Exception as e:
            logger.debug("Error processing %s: %s", article_url, type(e).__name__)
            continue

        if urls_processed >= max_urls_to_check:
            break
        if len(tasks) >= max_items:
            break

    for task in asyncio.as_completed(tasks):
        result = await task
        if result:
            downloaded += 1
        if downloaded >= max_items:
            break

    logger.info(
        "[%s] Stats: urls=%s, checked=%s, not_protocol=%s, downloads=%s",
        source,
        stats["urls_received"],
        stats["checked"],
        stats["not_protocol"],
        downloaded,
    )

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
    """Download ONLY research protocols from JMIR (strict filtering)."""
    source = "jmir"
    sitemap = "https://www.researchprotocols.org/sitemap.xml"
    destination_dir = resolve_output_dir(output_dir, source)
    downloaded = 0
    urls_processed = 0

    pattern = re.compile(r"researchprotocols\.org/\d{4}/\d+/e\d+/?$")
    max_urls_to_check = max_items * 15

    stats = {
        "urls_received": 0,
        "not_matching_pattern": 0,
        "fetch_errors": 0,
        "checked": 0,
        "pdfs_found": 0,
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
        logger.error("Failed to read JMIR sitemap: %s", type(e).__name__)
        return 0

    tasks: List[asyncio.Task] = []

    async for article_url in article_urls:
        stats["urls_received"] += 1

        if not pattern.search(article_url):
            stats["not_matching_pattern"] += 1
            continue

        urls_processed += 1

        try:
            html = await fetch_url(
                article_url,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
            )
            stats["checked"] += 1
        except (aiohttp.ClientError, RetryError):
            logger.debug("Fetch error: %s", article_url)
            stats["fetch_errors"] += 1
            continue

        try:
            pdf_urls = find_pdf_links(html, article_url, include_keywords={"protocol"})
            stats["pdfs_found"] += len(pdf_urls)

            if not pdf_urls:
                logger.debug("No PDFs found in %s", article_url)
                continue

            for pdf_url in pdf_urls[:1]:
                if len(tasks) >= max_items:
                    break
                stats["download_attempts"] += 1
                tasks.append(
                    asyncio.create_task(
                        download_pdf(
                            pdf_url,
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
                )

        except Exception as e:
            logger.debug("Error processing %s: %s", article_url, type(e).__name__)
            continue

        if urls_processed >= max_urls_to_check:
            break
        if len(tasks) >= max_items:
            break

    for task in asyncio.as_completed(tasks):
        result = await task
        if result:
            downloaded += 1
        if downloaded >= max_items:
            break

    logger.info(
        "[%s] Stats: urls=%s, checked=%s, pattern_filtered=%s, downloads=%s",
        source,
        stats["urls_received"],
        stats["checked"],
        stats["not_matching_pattern"],
        downloaded,
    )

    return downloaded


async def download_from_isrctn(
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
    """Download protocols from ISRCTN registry using XML API."""
    del sitemap_limit
    source = "isrctn"
    destination_dir = resolve_output_dir(output_dir, source)
    downloaded = 0
    tasks: List[asyncio.Task] = []

    query_terms = ["clinical trial", "randomized", "protocol"]
    max_records = max_items * 10
    protocol_files: dict[str, tuple[str, str]] = {}

    for term in query_terms:
        if len(protocol_files) >= max_records:
            break
        params = {"q": term, "limit": str(max_records)}
        query_string = urllib.parse.urlencode(params)
        url = f"https://www.isrctn.com/api/query/format/default?{query_string}"
        try:
            xml_data = await fetch_url(
                url,
                session=session,
                semaphore=semaphore,
                timeout=timeout,
            )
        except (aiohttp.ClientError, RetryError) as exc:
            logger.warning("ISRCTN query failed for %s: %s", term, type(exc).__name__)
            continue
        for isrctn_id, download_url, description in extract_isrctn_protocol_files(
            xml_data
        ):
            if isrctn_id not in protocol_files:
                protocol_files[isrctn_id] = (download_url, description)

    if not protocol_files:
        logger.warning("No ISRCTN protocol files found")
        return 0

    for isrctn_id, (download_url, description) in list(protocol_files.items())[
        : max_items * 5
    ]:
        pdf_url = download_url
        if not pdf_url.startswith("http"):
            pdf_url = urllib.parse.urljoin("https://www.isrctn.com/", pdf_url)
        tasks.append(
            asyncio.create_task(
                download_pdf(
                    pdf_url,
                    destination_dir,
                    session=session,
                    semaphore=semaphore,
                    timeout=timeout,
                    manifest_path=manifest_path,
                    source=source,
                    manifest_lock=manifest_lock,
                    require_protocol=True,
                    registry_id=isrctn_id,
                    registry_type="isrctn",
                    document_type=description or "protocol",
                )
            )
        )
        if len(tasks) >= max_items:
            break

    for task in asyncio.as_completed(tasks):
        result = await task
        if result:
            downloaded += 1
        if downloaded >= max_items:
            break

    return downloaded


async def download_from_ctis(
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
    """Download protocols from CTIS public portal."""
    del sitemap_limit
    source = "ctis"
    destination_dir = resolve_output_dir(output_dir, source)
    downloaded = 0
    tasks: List[asyncio.Task] = []

    search_payload = {
        "pagination": {"page": 1, "size": min(max_items * 5, 50)},
        "sort": {"property": "decisionDate", "direction": "DESC"},
        "searchCriteria": {"title": None, "number": None, "status": None},
    }

    try:
        search_results = await fetch_json_post(
            "https://euclinicaltrials.eu/ctis-public-api/search",
            session=session,
            semaphore=semaphore,
            payload=search_payload,
            timeout=timeout,
        )
    except (aiohttp.ClientError, RetryError) as exc:
        logger.warning("CTIS search failed: %s", type(exc).__name__)
        return 0

    trials = search_results.get("data", []) or []
    ct_numbers = [trial.get("ctNumber") for trial in trials if trial.get("ctNumber")]
    if not ct_numbers:
        logger.warning("No CTIS trial IDs found")
        return 0

    for ct_number in ct_numbers:
        if len(tasks) >= max_items:
            break
        try:
            detail = await fetch_json(
                f"https://euclinicaltrials.eu/ctis-public-api/retrieve/{ct_number}",
                session=session,
                semaphore=semaphore,
                timeout=timeout,
            )
        except (aiohttp.ClientError, RetryError) as exc:
            logger.debug(
                "CTIS detail fetch failed %s: %s", ct_number, type(exc).__name__
            )
            continue
        links = extract_ctis_protocol_links(detail)
        if not links:
            continue
        url_value, label = links[0]
        if not url_value.startswith("http"):
            url_value = urllib.parse.urljoin("https://euclinicaltrials.eu", url_value)
        tasks.append(
            asyncio.create_task(
                download_pdf(
                    url_value,
                    destination_dir,
                    session=session,
                    semaphore=semaphore,
                    timeout=timeout,
                    manifest_path=manifest_path,
                    source=source,
                    manifest_lock=manifest_lock,
                    require_protocol=True,
                    registry_id=ct_number,
                    registry_type="ctis_trial_id",
                    document_type=label or "protocol",
                )
            )
        )

    for task in asyncio.as_completed(tasks):
        result = await task
        if result:
            downloaded += 1
        if downloaded >= max_items:
            break

    return downloaded


SOURCE_HANDLERS: dict[str, Callable[..., Awaitable[int]]] = {
    "dac": download_from_dac,
    "clinicaltrials": download_from_clinicaltrials,
    "bmjopen": download_from_bmjopen,
    "jmir": download_from_jmir,
    "isrctn": download_from_isrctn,
    "ctis": download_from_ctis,
}

SOURCE_SPECS: dict[str, SourceSpec] = {
    "clinicaltrials": SourceSpec("clinicaltrials", "api", "nct", "primary", True),
    "dac": SourceSpec("dac", "html_crawl", "dac", "primary", True),
    "ctis": SourceSpec("ctis", "portal_scrape", "ctis_trial_id", "primary", True),
    "isrctn": SourceSpec("isrctn", "xml_api", "isrctn", "primary", True),
    "bmjopen": SourceSpec("bmjopen", "sitemap", "doi", "secondary", False),
    "jmir": SourceSpec("jmir", "sitemap", "doi", "secondary", False),
}


def default_sources(include_journal_sources: bool) -> List[str]:
    sources = [
        name
        for name, spec in SOURCE_SPECS.items()
        if spec.enabled_by_default and name in SOURCE_HANDLERS
    ]
    if include_journal_sources:
        sources.extend(
            name
            for name, spec in SOURCE_SPECS.items()
            if spec.priority == "secondary" and name in SOURCE_HANDLERS
        )
    return sorted(set(sources))


async def main_async() -> int:
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
        choices=sorted(SOURCE_HANDLERS.keys()),
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

    output_dir = Path(args.output_dir).resolve()

    try:
        ensure_dir(output_dir)
        ensure_dir(output_dir / "crc_protocols")
        ensure_dir(output_dir / "protocol_papers")
    except OSError as e:
        logger.error(f"Failed to create output directory: {e}")
        return 1

    manifest_path = output_dir / "manifest.jsonl"
    total_downloaded = 0
    source_results: dict[str, int] = {}

    concurrency_limit = compute_concurrency_limit()
    logger.info(
        "Starting protocol download: max_total=%s, max_per_source=%s, concurrency=%s",
        args.max_total,
        args.max_per_source,
        concurrency_limit,
    )

    manifest_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(concurrency_limit)
    connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
    timeout = aiohttp.ClientTimeout(total=args.timeout)

    selected_sources = args.sources or default_sources(args.include_journal_sources)

    async with aiohttp.ClientSession(
        headers={"User-Agent": USER_AGENT},
        connector=connector,
        timeout=timeout,
    ) as session:
        for source in selected_sources:
            if total_downloaded >= args.max_total:
                logger.info("Reached max_total (%s)", args.max_total)
                break

            handler = SOURCE_HANDLERS[source]
            remaining = args.max_total - total_downloaded
            per_source_limit = min(args.max_per_source, remaining)

            logger.info("Processing: %s (target: %s PDFs)", source, per_source_limit)

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
                    "%s: %s PDFs (total: %s)", source, downloaded, total_downloaded
                )

            except KeyboardInterrupt:
                logger.info("Interrupted")
                break
            except Exception as e:
                logger.error("Error processing %s: %s", source, e, exc_info=True)
                source_results[source] = 0

            await asyncio.sleep(1)

    logger.info("=" * 60)
    logger.info("Complete: %s protocol PDFs downloaded", total_downloaded)
    logger.info("Results by source:")
    for source, count in source_results.items():
        logger.info("  %s: %s PDFs", source, count)
    logger.info("Output: %s", output_dir)
    logger.info("Manifest: %s", manifest_path)
    logger.info("=" * 60)

    print(f"Downloaded {total_downloaded} protocol PDFs into {output_dir}")
    print(f"Manifest: {manifest_path}")

    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
