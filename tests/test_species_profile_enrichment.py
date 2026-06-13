from datetime import datetime, timezone

from scripts import enrich_species_profiles


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchall(self):
        return self.rows


def species_target_row(
    *,
    species_id=12,
    species_key="acer_rubrum",
    wikipedia_url="https://en.wikipedia.org/wiki/Acer_rubrum",
    existing_profile=None,
):
    profile_values = (
        (None,) * 12
        if existing_profile is None
        else (
            existing_profile.get("id", 99),
            existing_profile.get("summary"),
            existing_profile.get("taxonomy"),
            existing_profile.get("canonical_url"),
            existing_profile.get("source_system"),
            existing_profile.get("source_url"),
            existing_profile.get("retrieved_at"),
            existing_profile.get("method_version"),
            existing_profile.get("confidence"),
            existing_profile.get("license_name"),
            existing_profile.get("license_url"),
            existing_profile.get("attribution"),
        )
    )
    return (
        species_id,
        species_key,
        "Acer rubrum",
        "Red Maple",
        wikipedia_url,
        *profile_values,
    )


def wikipedia_payload(summary="Acer rubrum is a deciduous tree."):
    return {
        "title": "Acer rubrum",
        "pageid": 123,
        "wikibase_item": "Q159460",
        "description": "species of plant",
        "extract": summary,
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Acer_rubrum"}},
    }


def stored_profile(summary="Acer rubrum is a deciduous tree."):
    return {
        "id": 99,
        "summary": summary,
        "taxonomy": {
            "canonical_botanical_name": "Acer rubrum",
            "display_common_name": "Red Maple",
            "wikipedia_title": "Acer rubrum",
            "wikipedia_page_id": 123,
            "wikidata_id": "Q159460",
            "wikipedia_description": "species of plant",
        },
        "canonical_url": "https://en.wikipedia.org/wiki/Acer_rubrum",
        "source_system": "wikipedia",
        "source_url": "https://en.wikipedia.org/wiki/Acer_rubrum",
        "retrieved_at": datetime(2026, 6, 12, tzinfo=timezone.utc),
        "method_version": "wikipedia-summary-v1",
        "confidence": "source-derived",
        "license_name": "Creative Commons Attribution-ShareAlike 4.0 International",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "attribution": "Wikipedia contributors",
    }


def test_wikipedia_summary_api_url_uses_article_host_and_title():
    result = enrich_species_profiles.wikipedia_summary_api_url(
        "https://en.wikipedia.org/wiki/Acer_%C3%97_freemanii"
    )

    assert result == "https://en.wikipedia.org/api/rest_v1/page/summary/Acer_%C3%97_freemanii"


def test_profile_from_wikipedia_payload_adds_provenance_and_taxonomy():
    retrieved_at = datetime(2026, 6, 12, tzinfo=timezone.utc)
    species_row = {
        "id": 12,
        "species_key": "acer_rubrum",
        "canonical_botanical_name": "Acer rubrum",
        "display_common_name": "Red Maple",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Acer_rubrum",
    }
    payload = {
        "title": "Acer rubrum",
        "pageid": 123,
        "wikibase_item": "Q159460",
        "description": "species of plant",
        "extract": "Acer rubrum is a deciduous tree.",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Acer_rubrum"}},
    }

    profile = enrich_species_profiles.profile_from_wikipedia_payload(
        species_row, payload, retrieved_at
    )

    assert profile["species_id"] == 12
    assert profile["summary"] == "Acer rubrum is a deciduous tree."
    assert profile["source_system"] == "wikipedia"
    assert profile["source_url"] == "https://en.wikipedia.org/wiki/Acer_rubrum"
    assert profile["retrieved_at"] == retrieved_at
    assert profile["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert profile["taxonomy"] == {
        "canonical_botanical_name": "Acer rubrum",
        "display_common_name": "Red Maple",
        "wikipedia_title": "Acer rubrum",
        "wikipedia_page_id": 123,
        "wikidata_id": "Q159460",
        "wikipedia_description": "species of plant",
    }


def test_enrich_species_profiles_creates_missing_profile(monkeypatch):
    cursor = FakeCursor([species_target_row()])
    written_profiles = []

    monkeypatch.setattr(
        enrich_species_profiles, "fetch_wikipedia_summary", lambda _url: wikipedia_payload()
    )
    monkeypatch.setattr(
        enrich_species_profiles,
        "upsert_species_profile",
        lambda _cursor, profile: written_profiles.append(profile),
    )

    results = enrich_species_profiles.enrich_species_profiles(cursor)

    assert results == {
        "checked": 1,
        "created": 1,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "errors": 0,
    }
    assert len(written_profiles) == 1


def test_enrich_species_profiles_leaves_unchanged_profile_unwritten(monkeypatch):
    cursor = FakeCursor([species_target_row(existing_profile=stored_profile())])
    written_profiles = []

    monkeypatch.setattr(
        enrich_species_profiles, "fetch_wikipedia_summary", lambda _url: wikipedia_payload()
    )
    monkeypatch.setattr(
        enrich_species_profiles,
        "upsert_species_profile",
        lambda _cursor, profile: written_profiles.append(profile),
    )

    results = enrich_species_profiles.enrich_species_profiles(cursor)

    assert results["unchanged"] == 1
    assert results["created"] == 0
    assert results["updated"] == 0
    assert written_profiles == []


def test_enrich_species_profiles_updates_changed_profile(monkeypatch):
    cursor = FakeCursor([species_target_row(existing_profile=stored_profile("Old summary."))])
    written_profiles = []

    monkeypatch.setattr(
        enrich_species_profiles, "fetch_wikipedia_summary", lambda _url: wikipedia_payload()
    )
    monkeypatch.setattr(
        enrich_species_profiles,
        "upsert_species_profile",
        lambda _cursor, profile: written_profiles.append(profile),
    )

    results = enrich_species_profiles.enrich_species_profiles(cursor)

    assert results["updated"] == 1
    assert len(written_profiles) == 1


def test_enrich_species_profiles_refresh_updates_unchanged_profile(monkeypatch):
    cursor = FakeCursor([species_target_row(existing_profile=stored_profile())])
    written_profiles = []

    monkeypatch.setattr(
        enrich_species_profiles, "fetch_wikipedia_summary", lambda _url: wikipedia_payload()
    )
    monkeypatch.setattr(
        enrich_species_profiles,
        "upsert_species_profile",
        lambda _cursor, profile: written_profiles.append(profile),
    )

    results = enrich_species_profiles.enrich_species_profiles(cursor, refresh=True)

    assert results["updated"] == 1
    assert results["unchanged"] == 0
    assert len(written_profiles) == 1


def test_enrich_species_profiles_dry_run_counts_without_writing(monkeypatch):
    cursor = FakeCursor([species_target_row()])
    written_profiles = []

    monkeypatch.setattr(
        enrich_species_profiles, "fetch_wikipedia_summary", lambda _url: wikipedia_payload()
    )
    monkeypatch.setattr(
        enrich_species_profiles,
        "upsert_species_profile",
        lambda _cursor, profile: written_profiles.append(profile),
    )

    results = enrich_species_profiles.enrich_species_profiles(cursor, dry_run=True)

    assert results["created"] == 1
    assert written_profiles == []


def test_enrich_species_profiles_skips_missing_wikipedia_url(monkeypatch):
    cursor = FakeCursor([species_target_row(wikipedia_url=None)])

    def fail_fetch(_url):
        raise AssertionError("missing URLs should not be fetched")

    monkeypatch.setattr(enrich_species_profiles, "fetch_wikipedia_summary", fail_fetch)

    results = enrich_species_profiles.enrich_species_profiles(cursor)

    assert results == {
        "checked": 1,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 1,
        "errors": 0,
    }


def test_enrich_species_profiles_counts_fetch_errors(monkeypatch):
    cursor = FakeCursor([species_target_row()])

    def fail_fetch(_url):
        raise TimeoutError("request timed out")

    monkeypatch.setattr(enrich_species_profiles, "fetch_wikipedia_summary", fail_fetch)

    results = enrich_species_profiles.enrich_species_profiles(cursor)

    assert results["errors"] == 1
    assert results["created"] == 0


def test_format_enrichment_summary_reports_clear_dry_run_counts():
    output = enrich_species_profiles.format_enrichment_summary(
        {
            "checked": 3,
            "created": 1,
            "updated": 1,
            "unchanged": 0,
            "skipped": 1,
            "errors": 0,
        },
        dry_run=True,
    )

    assert "DRY RUN: no database changes written." in output
    assert "Would create: 1 profiles" in output
    assert "Would skip: 1" in output
