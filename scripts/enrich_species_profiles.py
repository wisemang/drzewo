#!/usr/bin/env python3

import argparse
import json
import sys
from datetime import datetime, timezone
from os import environ
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from psycopg2.extras import Json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tree_loader

SOURCE_SYSTEM = "wikipedia"
METHOD_VERSION = "wikipedia-summary-v1"
LICENSE_NAME = "Creative Commons Attribution-ShareAlike 4.0 International"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
ATTRIBUTION = "Wikipedia contributors"
DEFAULT_USER_AGENT = (
    "drzewo-tree-enrichment/1.0 "
    "(https://treeseek.ca; contact: set DRZEWO_HTTP_USER_AGENT)"
)


def wikipedia_summary_api_url(wikipedia_url):
    """Return the Wikipedia REST summary URL for a checked-in article URL."""
    parsed = urlparse(wikipedia_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc.endswith("wikipedia.org"):
        raise ValueError(f"Unsupported Wikipedia URL: {wikipedia_url}")
    if not parsed.path.startswith("/wiki/"):
        raise ValueError(f"Unsupported Wikipedia article path: {wikipedia_url}")

    page_title = unquote(parsed.path.removeprefix("/wiki/"))
    if not page_title:
        raise ValueError(f"Missing Wikipedia page title: {wikipedia_url}")
    return f"https://{parsed.netloc}/api/rest_v1/page/summary/{quote(page_title, safe='')}"


def fetch_wikipedia_summary(wikipedia_url):
    """Fetch a compact Wikipedia summary payload."""
    request = Request(
        wikipedia_summary_api_url(wikipedia_url),
        headers={
            "Accept": "application/json",
            "User-Agent": environ.get("DRZEWO_HTTP_USER_AGENT", DEFAULT_USER_AGENT),
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def profile_from_wikipedia_payload(species_row, payload, retrieved_at=None):
    """Build a species_profile row from a species catalog row and Wikipedia summary."""
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    content_urls = payload.get("content_urls") or {}
    desktop_urls = content_urls.get("desktop") or {}
    canonical_url = desktop_urls.get("page") or species_row["wikipedia_url"]
    source_url = canonical_url or species_row["wikipedia_url"]
    taxonomy = {
        "canonical_botanical_name": species_row["canonical_botanical_name"],
        "display_common_name": species_row["display_common_name"],
    }
    for payload_key, taxonomy_key in (
        ("title", "wikipedia_title"),
        ("pageid", "wikipedia_page_id"),
        ("wikibase_item", "wikidata_id"),
        ("description", "wikipedia_description"),
    ):
        value = payload.get(payload_key)
        if value not in (None, ""):
            taxonomy[taxonomy_key] = value

    return {
        "species_id": species_row["id"],
        "summary": payload.get("extract"),
        "taxonomy": taxonomy,
        "canonical_url": canonical_url,
        "source_system": SOURCE_SYSTEM,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "method_version": METHOD_VERSION,
        "confidence": "source-derived",
        "license_name": LICENSE_NAME,
        "license_url": LICENSE_URL,
        "attribution": ATTRIBUTION,
    }


def fetch_species_targets(cursor, *, species_key=None, limit=None, refresh=False):
    """Return species rows with Wikipedia URLs that need profile enrichment."""
    where_clauses = ["species.wikipedia_url IS NOT NULL", "species.wikipedia_url <> ''"]
    params = [SOURCE_SYSTEM]
    if species_key:
        where_clauses.append("species.species_key = %s")
        params.append(species_key)
    if not refresh:
        where_clauses.append("profile.id IS NULL")

    limit_clause = ""
    if limit:
        limit_clause = "LIMIT %s"
        params.append(limit)

    cursor.execute(
        f"""
        SELECT
            species.id,
            species.species_key,
            species.canonical_botanical_name,
            species.display_common_name,
            species.wikipedia_url
        FROM species
        LEFT JOIN species_profile AS profile
            ON profile.species_id = species.id
            AND profile.source_system = %s
        WHERE {" AND ".join(where_clauses)}
        ORDER BY species.species_key
        {limit_clause};
        """,
        params,
    )
    return [
        {
            "id": row[0],
            "species_key": row[1],
            "canonical_botanical_name": row[2],
            "display_common_name": row[3],
            "wikipedia_url": row[4],
        }
        for row in cursor.fetchall()
    ]


def upsert_species_profile(cursor, profile):
    """Insert or update one sourced species profile."""
    cursor.execute(
        """
        INSERT INTO species_profile (
            species_id, summary, taxonomy, canonical_url, source_system, source_url,
            retrieved_at, method_version, confidence, license_name, license_url,
            attribution, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now()
        )
        ON CONFLICT (species_id, source_system) DO UPDATE SET
            summary = EXCLUDED.summary,
            taxonomy = EXCLUDED.taxonomy,
            canonical_url = EXCLUDED.canonical_url,
            source_url = EXCLUDED.source_url,
            retrieved_at = EXCLUDED.retrieved_at,
            method_version = EXCLUDED.method_version,
            confidence = EXCLUDED.confidence,
            license_name = EXCLUDED.license_name,
            license_url = EXCLUDED.license_url,
            attribution = EXCLUDED.attribution,
            updated_at = now();
        """,
        (
            profile["species_id"],
            profile["summary"],
            Json(profile["taxonomy"]),
            profile["canonical_url"],
            profile["source_system"],
            profile["source_url"],
            profile["retrieved_at"],
            profile["method_version"],
            profile["confidence"],
            profile["license_name"],
            profile["license_url"],
            profile["attribution"],
        ),
    )


def enrich_species_profiles(cursor, *, species_key=None, limit=None, refresh=False, dry_run=False):
    """Fetch and upsert Wikipedia profile summaries for species catalog rows."""
    targets = fetch_species_targets(
        cursor,
        species_key=species_key,
        limit=limit,
        refresh=refresh,
    )
    results = {"selected": len(targets), "updated": 0, "failed": 0}

    for species_row in targets:
        try:
            payload = fetch_wikipedia_summary(species_row["wikipedia_url"])
            profile = profile_from_wikipedia_payload(species_row, payload)
            if not dry_run:
                upsert_species_profile(cursor, profile)
            results["updated"] += 1
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            results["failed"] += 1
            print(f"Failed {species_row['species_key']}: {exc}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Populate species profiles from Wikipedia.")
    parser.add_argument("--species-key", help="Only enrich one species key")
    parser.add_argument("--limit", type=int, help="Maximum number of species to process")
    parser.add_argument("--refresh", action="store_true", help="Refresh existing profiles")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but do not write profiles")
    args = parser.parse_args()

    conn = tree_loader.connect_db()
    try:
        cursor = conn.cursor()
        tree_loader.ensure_species_tables(cursor)
        tree_loader.ensure_species_enrichment_tables(cursor)
        results = enrich_species_profiles(
            cursor,
            species_key=args.species_key,
            limit=args.limit,
            refresh=args.refresh,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
        print(
            "Species profile enrichment: "
            f"selected={results['selected']} updated={results['updated']} "
            f"failed={results['failed']}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
