from datetime import datetime, timezone

from scripts import enrich_species_benefits


class FakeCursor:
    pass


def species_directory():
    return {
        "by_key": {
            "acer_rubrum": {
                "id": 12,
                "species_key": "acer_rubrum",
                "canonical_botanical_name": "Acer rubrum",
                "display_common_name": "Red Maple",
            }
        },
        "by_scientific_name": {
            "acer rubrum": {
                "id": 12,
                "species_key": "acer_rubrum",
                "canonical_botanical_name": "Acer rubrum",
                "display_common_name": "Red Maple",
            }
        },
    }


def valid_seed_row():
    return {
        "species_key": "acer_rubrum",
        "scientific_name": "Acer rubrum",
        "common_name": "Red Maple",
        "metric_type": "pollinator_support",
        "note": "Can provide early-season floral resources for some pollinating insects.",
        "scope": "species",
        "region": None,
        "source_system": "usda_plants",
        "source_title": "USDA NRCS PLANTS Database / Plant Guide",
        "source_url": "https://plants.usda.gov/home",
        "attribution": "U.S. Department of Agriculture, Natural Resources Conservation Service",
        "license_name": "Public domain; USDA attribution requested",
        "license_url": "https://www.usda.gov/about-usda/policies-and-links",
        "confidence": "medium",
        "retrieved_at": "2026-06-15",
        "observed_at": None,
        "method_version": "benefits_seed_usda_plants_v1",
        "claim_key": "acer_rubrum_pollinator_support_001",
        "_line_number": 1,
    }


def test_load_seed_rows_reads_jsonl(tmp_path):
    seed_path = tmp_path / "benefits_seed.jsonl"
    seed_path.write_text(
        "\n".join(
            [
                '{"species_key":"acer_rubrum","metric_type":"pollinator_support"}',
                "",
                '{"species_key":"acer_rubrum","metric_type":"wildlife_habitat"}',
            ]
        ),
        encoding="utf-8",
    )

    rows = enrich_species_benefits.load_seed_rows(seed_path)

    assert len(rows) == 2
    assert rows[0]["_line_number"] == 1
    assert rows[1]["_line_number"] == 3


def test_build_species_benefit_maps_metric_type_to_label():
    benefit = enrich_species_benefits.build_species_benefit(valid_seed_row(), species_directory())

    assert benefit["species_id"] == 12
    assert benefit["metric_type"] == "pollinator_support"
    assert benefit["label"] == "Pollinator support"
    assert (
        benefit["text"]
        == "Can provide early-season floral resources for some pollinating insects."
    )
    assert benefit["retrieved_at"] == datetime(2026, 6, 15, tzinfo=timezone.utc)


def test_build_species_benefit_rejects_missing_provenance():
    seed_row = valid_seed_row()
    seed_row["source_url"] = " "

    try:
        enrich_species_benefits.build_species_benefit(seed_row, species_directory())
    except enrich_species_benefits.ValidationError as exc:
        assert str(exc) == "source_url is required"
    else:
        raise AssertionError("expected ValidationError")


def test_build_species_benefit_rejects_unresolved_species():
    seed_row = valid_seed_row()
    seed_row["species_key"] = "unknown_species"

    try:
        enrich_species_benefits.build_species_benefit(seed_row, species_directory())
    except enrich_species_benefits.ValidationError as exc:
        assert str(exc) == "species_key does not resolve: unknown_species"
    else:
        raise AssertionError("expected ValidationError")


def test_build_species_benefit_rejects_unsupported_metric_type():
    seed_row = valid_seed_row()
    seed_row["metric_type"] = "shade_cooling"

    try:
        enrich_species_benefits.build_species_benefit(seed_row, species_directory())
    except enrich_species_benefits.ValidationError as exc:
        assert str(exc) == "unsupported metric_type: shade_cooling"
    else:
        raise AssertionError("expected ValidationError")


def test_build_species_benefit_rejects_estimate_fields():
    seed_row = valid_seed_row()
    seed_row["value"] = 1200

    try:
        enrich_species_benefits.build_species_benefit(seed_row, species_directory())
    except enrich_species_benefits.ValidationError as exc:
        assert str(exc) == "value is not allowed for qualitative species benefits"
    else:
        raise AssertionError("expected ValidationError")


def test_enrich_species_benefits_inserts_valid_row(monkeypatch):
    cursor = FakeCursor()
    inserted_benefits = []
    updated_benefits = []

    monkeypatch.setattr(
        enrich_species_benefits, "load_seed_rows", lambda _path: [valid_seed_row()]
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "load_species_directory",
        lambda _cursor: species_directory(),
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "fetch_existing_benefit",
        lambda _cursor, _benefit: None,
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "insert_species_benefit",
        lambda _cursor, benefit: inserted_benefits.append(benefit),
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "update_species_benefit",
        lambda _cursor, _benefit_id, benefit: updated_benefits.append(benefit),
    )

    results = enrich_species_benefits.enrich_species_benefits(cursor)

    assert results == {
        "rows_read": 1,
        "inserted": 1,
        "updated": 0,
        "skipped": 0,
        "rejected": 0,
        "species_touched": 1,
    }
    assert len(inserted_benefits) == 1
    assert updated_benefits == []


def test_enrich_species_benefits_updates_changed_row(monkeypatch):
    cursor = FakeCursor()
    inserted_benefits = []
    updated_benefits = []
    existing_benefit = {
        "id": 91,
        "label": "Pollinator support",
        "text": "Old note.",
        "confidence": "medium",
        "source_system": "usda_plants",
        "source_url": "https://plants.usda.gov/home",
        "retrieved_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "license_name": "Public domain; USDA attribution requested",
        "license_url": "https://www.usda.gov/about-usda/policies-and-links",
        "attribution": "U.S. Department of Agriculture, Natural Resources Conservation Service",
    }

    monkeypatch.setattr(
        enrich_species_benefits, "load_seed_rows", lambda _path: [valid_seed_row()]
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "load_species_directory",
        lambda _cursor: species_directory(),
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "fetch_existing_benefit",
        lambda _cursor, _benefit: existing_benefit,
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "insert_species_benefit",
        lambda _cursor, benefit: inserted_benefits.append(benefit),
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "update_species_benefit",
        lambda _cursor, benefit_id, benefit: updated_benefits.append((benefit_id, benefit)),
    )

    results = enrich_species_benefits.enrich_species_benefits(cursor)

    assert results["updated"] == 1
    assert inserted_benefits == []
    assert updated_benefits[0][0] == 91


def test_enrich_species_benefits_skips_unchanged_row(monkeypatch):
    cursor = FakeCursor()
    inserted_benefits = []
    updated_benefits = []
    benefit = enrich_species_benefits.build_species_benefit(valid_seed_row(), species_directory())
    existing_benefit = {
        "id": 91,
        "label": benefit["label"],
        "text": benefit["text"],
        "confidence": benefit["confidence"],
        "source_system": benefit["source_system"],
        "source_url": benefit["source_url"],
        "retrieved_at": benefit["retrieved_at"],
        "license_name": benefit["license_name"],
        "license_url": benefit["license_url"],
        "attribution": benefit["attribution"],
    }

    monkeypatch.setattr(
        enrich_species_benefits, "load_seed_rows", lambda _path: [valid_seed_row()]
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "load_species_directory",
        lambda _cursor: species_directory(),
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "fetch_existing_benefit",
        lambda _cursor, _benefit: existing_benefit,
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "insert_species_benefit",
        lambda _cursor, benefit: inserted_benefits.append(benefit),
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "update_species_benefit",
        lambda _cursor, benefit_id, benefit: updated_benefits.append((benefit_id, benefit)),
    )

    results = enrich_species_benefits.enrich_species_benefits(cursor)

    assert results["skipped"] == 1
    assert inserted_benefits == []
    assert updated_benefits == []


def test_enrich_species_benefits_dry_run_counts_without_writing(monkeypatch):
    cursor = FakeCursor()
    inserted_benefits = []

    monkeypatch.setattr(
        enrich_species_benefits, "load_seed_rows", lambda _path: [valid_seed_row()]
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "load_species_directory",
        lambda _cursor: species_directory(),
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "fetch_existing_benefit",
        lambda _cursor, _benefit: None,
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "insert_species_benefit",
        lambda _cursor, benefit: inserted_benefits.append(benefit),
    )

    results = enrich_species_benefits.enrich_species_benefits(cursor, dry_run=True)

    assert results["inserted"] == 1
    assert inserted_benefits == []


def test_enrich_species_benefits_rejects_duplicate_seed_identity(monkeypatch):
    cursor = FakeCursor()
    seed_rows = [valid_seed_row(), dict(valid_seed_row(), _line_number=2)]

    monkeypatch.setattr(enrich_species_benefits, "load_seed_rows", lambda _path: seed_rows)
    monkeypatch.setattr(
        enrich_species_benefits,
        "load_species_directory",
        lambda _cursor: species_directory(),
    )
    monkeypatch.setattr(
        enrich_species_benefits,
        "fetch_existing_benefit",
        lambda _cursor, _benefit: None,
    )

    results = enrich_species_benefits.enrich_species_benefits(cursor, dry_run=True)

    assert results["inserted"] == 1
    assert results["rejected"] == 1
