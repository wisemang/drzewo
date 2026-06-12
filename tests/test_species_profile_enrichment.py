from datetime import datetime, timezone

from scripts import enrich_species_profiles


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
