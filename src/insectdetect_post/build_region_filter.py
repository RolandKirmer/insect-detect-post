"""Build per-country GBIF region-filter CSVs consumable by TreeOfLifeClassifier (pybioclip).

Source:   https://github.com/maxsitt/insect-detect-post
License:  GNU AGPLv3 (https://choosealicense.com/licenses/agpl-3.0/)
Author:   Maximilian Sittinger (https://github.com/maxsitt)
Docs:     https://maxsitt.github.io/insect-detect-docs/

Resolves which BioCLIP Tree of Life species have GBIF occurrence records in a given
country, by combining a TOL-to-GBIF taxon key mapping with GBIF's occurrence search
API. Results are cached per country so repeat runs need no network access.

Functions:
    load_tol_gbif_taxon_keys(): Load the TOL-to-GBIF taxon key mapping, downloading it on first use.
    get_country_taxon_keys():   Fetch all GBIF taxon keys with occurrence records in a country.
    build_region_filter_csv():  Resolve a species-list CSV for a country from cache or by querying GBIF.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from pathlib import Path

import polars as pl
from pygbif import occurrences
from requests.exceptions import HTTPError, RequestException

from insectdetect_post.asset_manager import ensure_asset
from insectdetect_post.constants import (
    FILTER_ASSETS_JSON,
    FILTERS_PATH,
    PHYLUM_FILTER,
    PHYLUM_TAXON_KEYS,
)

# Create module-level logger
logger = logging.getLogger(__name__)

# TOL-to-GBIF taxon key mapping, produced by filters/resolve_tol_gbif_species.py
_scope = PHYLUM_FILTER if PHYLUM_FILTER is not None else "all"
TOL_GBIF_TAXON_KEYS_CSV = FILTERS_PATH / f"tol_gbif_taxon_keys_{_scope}.csv"

# GBIF backbone taxonKey to restrict occurrence facet queries to
PHYLUM_TAXON_KEY: int | None = None
if PHYLUM_FILTER is not None:
    PHYLUM_TAXON_KEY = PHYLUM_TAXON_KEYS.get(PHYLUM_FILTER)
    if PHYLUM_TAXON_KEY is None:
        logger.warning(
            "PHYLUM_FILTER '%s' has no entry in PHYLUM_TAXON_KEYS -- occurrence facet "
            "queries will not be restricted by phylum.", PHYLUM_FILTER
        )

# GBIF occurrence facet query settings
FACET_PAGE_SIZE = 1000
MAX_RETRIES = 4
REQUEST_TIMEOUT_S = 30
MAX_BACKOFF_S = 20.0


def load_tol_gbif_taxon_keys(
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> pl.DataFrame:
    """Load the TOL-to-GBIF taxon key mapping, downloading it on first use.

    Args:
        progress_callback: Optional callback(current, total, message) for download progress.

    Raises:
        KeyError: If the mapping CSV is not a registered asset.
        ValueError: If the downloaded file fails checksum verification.

    Returns:
        DataFrame with (at least) columns 'species' and 'gbif_taxon_key' (nullable Int64).
    """
    ensure_asset(TOL_GBIF_TAXON_KEYS_CSV.name, FILTER_ASSETS_JSON, progress_callback=progress_callback)
    return pl.read_csv(TOL_GBIF_TAXON_KEYS_CSV).with_columns(
        pl.col("gbif_taxon_key").cast(pl.Int64, strict=False)
    )


def _backoff_seconds(error: Exception, attempt: int) -> float:
    """Compute the retry wait time.

    Honors a 'Retry-After' header if present, otherwise falls back to exponential backoff with jitter.
    """
    capped_wait = min(2 ** attempt, MAX_BACKOFF_S)
    if isinstance(error, HTTPError) and error.response is not None and error.response.status_code == 429:
        retry_after = error.response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(capped_wait, float(retry_after)) + random.uniform(0, 1)
            except ValueError:
                pass
    return random.uniform(0, capped_wait)


def _fetch_facet_page(country: str, offset: int, min_occurrence_count: int) -> dict:
    """Fetch a single page of the GBIF 'taxonKey' occurrence facet for a country.

    Retries transient failures (429/5xx or network errors) up to MAX_RETRIES times.
    A 4xx error other than 429 is treated as an invalid country code and raised
    immediately as a ValueError, not retried.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return occurrences.search(
                country=country, phylumKey=PHYLUM_TAXON_KEY, facet="taxonKey", limit=0,
                taxonKey_facetLimit=FACET_PAGE_SIZE, taxonKey_facetOffset=offset,
                facetMincount=min_occurrence_count,
                timeout=REQUEST_TIMEOUT_S,
            )
        except HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is not None and 400 <= status < 500 and status != 429:
                raise ValueError(
                    f"GBIF rejected country code '{country}' (HTTP {status}). "
                    "Verify it is a valid ISO 3166-1 alpha-2 code."
                ) from e
            last_error = e
        except RequestException as e:
            last_error = e
        if attempt < MAX_RETRIES - 1:
            time.sleep(_backoff_seconds(last_error, attempt))
    raise RuntimeError(
        f"Failed to fetch GBIF occurrence facet for country '{country}' "
        f"after {MAX_RETRIES} attempts: {last_error}"
    )


def get_country_taxon_keys(
    country: str,
    min_occurrence_count: int = 3,
    page_callback: Callable[[int, int], None] | None = None,
) -> set[int]:
    """Fetch all GBIF taxon keys with occurrence records in a country.

    Pages through GBIF's 'taxonKey' occurrence facet until a page returns fewer than
    FACET_PAGE_SIZE entries, restricted server-side to PHYLUM_TAXON_KEY if set. The
    facet still blends every taxonomic rank together within that scope, so it must be
    intersected against known species-level keys to be meaningful.

    Args:
        country: ISO 3166-1 alpha-2 country code.
        min_occurrence_count: Minimum occurrence records for a taxon to be included.
        page_callback: Optional callback(pages_fetched, taxa_found), invoked after each page.
            The total page count is unknown upfront, so callers have to estimate a percentage.

    Raises:
        ValueError: If GBIF rejects the country code as invalid.
        RuntimeError: If fetching fails after exhausting retries.

    Returns:
        Set of GBIF taxon keys observed anywhere in the country's occurrence facet.
    """
    taxon_keys: set[int] = set()
    offset = 0
    page_num = 0
    while True:
        page = _fetch_facet_page(country, offset, min_occurrence_count)
        counts = page["facets"][0]["counts"] if page.get("facets") else []
        taxon_keys.update(int(entry["name"]) for entry in counts)
        page_num += 1
        logger.debug("Country '%s': fetched %d facet entries at offset %d", country, len(counts), offset)
        if page_callback:
            page_callback(page_num, len(taxon_keys))
        if len(counts) < FACET_PAGE_SIZE:
            break
        offset += FACET_PAGE_SIZE
        time.sleep(0.2)  # basic rate limiting between pages
    return taxon_keys


def build_region_filter_csv(
    country: str = "DE",
    force_refresh: bool = False,
    min_occurrence_count: int = 3,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> Path:
    """Resolve a species-list CSV for a country from cache or by querying GBIF.

    The cached CSV has a single 'species' column, so it can be handed
    directly to pybioclip with no further processing.

    Args:
        country: ISO 3166-1 alpha-2 country code.
        force_refresh: If True, re-query GBIF even if a cached CSV already exists.
        min_occurrence_count: Minimum occurrence records for a taxon to be included.
        progress_callback: Optional callback(current, total, message), reporting 0-100% of this
            function's own work. Callers embedding it in a wider range should scale accordingly.

    Raises:
        KeyError: If the TOL-to-GBIF mapping is not a registered asset.
        ValueError: If GBIF rejects the country code, or no TOL species in the mapping have
                    any occurrence record in the given country.
        RuntimeError: If fetching from GBIF fails after exhausting retries.

    Returns:
        Path to the (now-cached) per-country species-list CSV.
    """
    country = country.upper()
    cache_path = FILTERS_PATH / f"tol_gbif_species_{_scope}_minocc{min_occurrence_count}_{country}.csv"
    if cache_path.exists() and not force_refresh:
        logger.info("Using cached region filter for '%s': '%s'", country, cache_path)
        return cache_path

    if progress_callback:
        progress_callback(
            0, 100,
            f"Building region filter for '{country}' from GBIF occurrence data "
            "-- this can take a few minutes..."
        )

    # Mapping download and GBIF query both report raw 0-100%, so each gets its own sub-range
    def download_progress(pct: int, _total: int, message: str) -> None:
        if progress_callback:
            progress_callback(int(pct / 10), 100, message)  # 0-10%

    mapping = load_tol_gbif_taxon_keys(download_progress)

    if progress_callback:
        progress_callback(10, 100, f"Querying GBIF for species recorded in country '{country}'...")
    logger.info("Querying GBIF for species recorded in country '%s'...", country)

    def query_progress(pages_fetched: int, taxa_found: int) -> None:
        if progress_callback:
            # Harmonic saturation keeps the bar advancing over the realistic page range
            pct = 10 + int(80 * pages_fetched / (pages_fetched + 30))
            progress_callback(
                pct, 100,
                f"Querying GBIF for country '{country}': page {pages_fetched} "
                f"({taxa_found} taxa found so far)..."
            )

    country_taxon_keys = get_country_taxon_keys(country, min_occurrence_count, query_progress)

    if progress_callback:
        progress_callback(90, 100, f"Matching species for country '{country}'...")

    matched = (
        mapping.filter(pl.col("gbif_taxon_key").is_in(list(country_taxon_keys)))
        .select("species")
        .unique()
        .sort("species")
    )
    if matched.is_empty():
        raise ValueError(
            f"No TOL species in the mapping have any GBIF occurrence record in country '{country}'."
        )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    matched.write_csv(cache_path)
    logger.info("Built region filter for '%s': %d species -> '%s'", country, matched.height, cache_path)

    if progress_callback:
        progress_callback(100, 100, f"Built region filter for '{country}': {matched.height} species")

    return cache_path
