from datetime import datetime, timezone

from scripts import enrich_species_risk


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
            },
            "fraxinus_americana": {
                "id": 99,
                "species_key": "fraxinus_americana",
                "canonical_botanical_name": "Fraxinus americana",
                "display_common_name": "White Ash",
            },
        },
        "by_scientific_name": {
            "acer rubrum": {
                "id": 12,
                "species_key": "acer_rubrum",
                "canonical_botanical_name": "Acer rubrum",
                "display_common_name": "Red Maple",
            },
            "fraxinus americana": {
                "id": 99,
                "species_key": "fraxinus_americana",
                "canonical_botanical_name": "Fraxinus americana",
                "display_common_name": "White Ash",
            },
        },
    }


def valid_vascan_seed_row():
    return {
        "species_key": "acer_rubrum",
        "scientific_name": "Acer rubrum",
        "common_name": "Red Maple",
        "risk_type": "native_status",
        "status": "native",
        "note": "VASCAN lists this species as native in Ontario.",
        "region": "CA-ON",
        "region_type": "province",
        "source_system": "vascan",
        "source_title": "VASCAN: Database of Vascular Plants of Canada",
        "source_url": "https://data.canadensys.net/vascan/taxon/9212?lang=en",
        "license_name": "Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0)",
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "attribution": "VASCAN / Canadensys",
        "retrieved_at": "2026-06-15",
        "observed_at": None,
        "method_version": "risk_seed_vascan_cfia_v1",
        "confidence": "high",
        "signal_key": "acer_rubrum_native_status_ca_on_vascan",
        "_line_number": 1,
    }


def valid_cfia_seed_row():
    return {
        "species_key": "fraxinus_americana",
        "scientific_name": "Fraxinus americana",
        "common_name": "White Ash",
        "risk_type": "pest_host",
        "status": "reported",
        "note": (
            "Ash species are associated with CFIA emerald ash borer host and "
            "regulatory concern. This does not mean this individual tree is infested."
        ),
        "region": "CA",
        "region_type": "country",
        "source_system": "cfia_eab",
        "source_title": "CFIA: Emerald ash borer",
        "source_url": "https://inspection.canada.ca/en/plant-health/invasive-pests-and-plants/insects/emerald-ash-borer",
        "license_name": "Open Government Licence - Canada",
        "license_url": "https://open.canada.ca/en/open-government-licence-canada",
        "attribution": "Canadian Food Inspection Agency / Government of Canada",
        "retrieved_at": "2026-06-15",
        "observed_at": None,
        "method_version": "risk_seed_vascan_cfia_v1",
        "confidence": "high",
        "signal_key": "fraxinus_americana_pest_host_ca_cfia",
        "_line_number": 1,
    }


def test_load_seed_rows_reads_jsonl(tmp_path):
    seed_path = tmp_path / "risk_seed.jsonl"
    seed_path.write_text(
        "\n".join(
            [
                '{"species_key":"acer_rubrum","risk_type":"native_status","status":"native"}',
                "",
                '{"species_key":"acer_rubrum","risk_type":"introduced_status","status":"introduced"}',
            ]
        ),
        encoding="utf-8",
    )

    rows = enrich_species_risk.load_seed_rows(seed_path)

    assert len(rows) == 2
    assert rows[0]["_line_number"] == 1
    assert rows[1]["_line_number"] == 3


def test_build_species_risk_accepts_native_vascan_row():
    risk = enrich_species_risk.build_species_risk(valid_vascan_seed_row(), species_directory())

    assert risk["species_id"] == 12
    assert risk["risk_type"] == "native_status"
    assert risk["status"] == "native"
    assert risk["region"] == "CA-ON"
    assert risk["region_type"] == "province"
    assert risk["retrieved_at"] == datetime(2026, 6, 15, tzinfo=timezone.utc)


def test_build_species_risk_accepts_introduced_vascan_row():
    seed_row = valid_vascan_seed_row()
    seed_row["risk_type"] = "introduced_status"
    seed_row["status"] = "introduced"
    seed_row["note"] = "VASCAN lists this species as introduced in Ontario."

    risk = enrich_species_risk.build_species_risk(seed_row, species_directory())

    assert risk["risk_type"] == "introduced_status"
    assert risk["status"] == "introduced"


def test_build_species_risk_accepts_cfia_pest_host_row():
    risk = enrich_species_risk.build_species_risk(valid_cfia_seed_row(), species_directory())

    assert risk["species_id"] == 99
    assert risk["risk_type"] == "pest_host"
    assert risk["status"] == "reported"
    assert risk["region"] == "CA"
    assert risk["region_type"] == "country"


def test_build_species_risk_rejects_missing_provenance():
    seed_row = valid_vascan_seed_row()
    seed_row["source_url"] = " "

    try:
        enrich_species_risk.build_species_risk(seed_row, species_directory())
    except enrich_species_risk.ValidationError as exc:
        assert str(exc) == "source_url is required"
    else:
        raise AssertionError("expected ValidationError")


def test_build_species_risk_rejects_missing_region():
    seed_row = valid_vascan_seed_row()
    seed_row["region"] = ""

    try:
        enrich_species_risk.build_species_risk(seed_row, species_directory())
    except enrich_species_risk.ValidationError as exc:
        assert str(exc) == "region is required"
    else:
        raise AssertionError("expected ValidationError")


def test_build_species_risk_rejects_missing_region_type():
    seed_row = valid_vascan_seed_row()
    seed_row["region_type"] = ""

    try:
        enrich_species_risk.build_species_risk(seed_row, species_directory())
    except enrich_species_risk.ValidationError as exc:
        assert str(exc) == "region_type is required"
    else:
        raise AssertionError("expected ValidationError")


def test_build_species_risk_rejects_unresolved_species():
    seed_row = valid_vascan_seed_row()
    seed_row["species_key"] = "unknown_species"

    try:
        enrich_species_risk.build_species_risk(seed_row, species_directory())
    except enrich_species_risk.ValidationError as exc:
        assert str(exc) == "species_key does not resolve: unknown_species"
    else:
        raise AssertionError("expected ValidationError")


def test_build_species_risk_rejects_unsupported_risk_type():
    seed_row = valid_vascan_seed_row()
    seed_row["risk_type"] = "invasive_status"

    try:
        enrich_species_risk.build_species_risk(seed_row, species_directory())
    except enrich_species_risk.ValidationError as exc:
        assert str(exc) == "unsupported risk_type: invasive_status"
    else:
        raise AssertionError("expected ValidationError")


def test_build_species_risk_rejects_safe_wording():
    seed_row = valid_vascan_seed_row()
    seed_row["note"] = "This species is safe in Ontario."

    try:
        enrich_species_risk.build_species_risk(seed_row, species_directory())
    except enrich_species_risk.ValidationError as exc:
        assert str(exc) == "note uses missing-data-as-safety wording"
    else:
        raise AssertionError("expected ValidationError")


def test_build_species_risk_rejects_broad_invasive_claim():
    seed_row = valid_vascan_seed_row()
    seed_row["note"] = "This species is invasive in Ontario."

    try:
        enrich_species_risk.build_species_risk(seed_row, species_directory())
    except enrich_species_risk.ValidationError as exc:
        assert str(exc) == "note makes an unsupported broad invasive or statutory claim"
    else:
        raise AssertionError("expected ValidationError")


def test_enrich_species_risk_inserts_valid_rows(monkeypatch):
    cursor = FakeCursor()
    inserted_risks = []
    updated_risks = []
    seed_rows = [valid_vascan_seed_row(), dict(valid_cfia_seed_row(), _line_number=2)]

    monkeypatch.setattr(enrich_species_risk, "load_seed_rows", lambda _path: seed_rows)
    monkeypatch.setattr(
        enrich_species_risk,
        "load_species_directory",
        lambda _cursor: species_directory(),
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "fetch_existing_risk",
        lambda _cursor, _risk: None,
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "insert_species_risk",
        lambda _cursor, risk: inserted_risks.append(risk),
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "update_species_risk",
        lambda _cursor, _risk_id, risk: updated_risks.append(risk),
    )

    results = enrich_species_risk.enrich_species_risk(cursor)

    assert results == {
        "rows_read": 2,
        "inserted": 2,
        "updated": 0,
        "skipped": 0,
        "rejected": 0,
        "species_touched": 2,
    }
    assert len(inserted_risks) == 2
    assert updated_risks == []


def test_enrich_species_risk_updates_changed_row(monkeypatch):
    cursor = FakeCursor()
    inserted_risks = []
    updated_risks = []
    existing_risk = {
        "id": 91,
        "status": "native",
        "confidence": "medium",
        "retrieved_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "observed_at": None,
        "license_name": "Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0)",
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "attribution": "VASCAN / Canadensys",
        "notes": "Old note.",
    }

    monkeypatch.setattr(
        enrich_species_risk, "load_seed_rows", lambda _path: [valid_vascan_seed_row()]
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "load_species_directory",
        lambda _cursor: species_directory(),
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "fetch_existing_risk",
        lambda _cursor, _risk: existing_risk,
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "insert_species_risk",
        lambda _cursor, risk: inserted_risks.append(risk),
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "update_species_risk",
        lambda _cursor, risk_id, risk: updated_risks.append((risk_id, risk)),
    )

    results = enrich_species_risk.enrich_species_risk(cursor)

    assert results["updated"] == 1
    assert inserted_risks == []
    assert updated_risks[0][0] == 91


def test_enrich_species_risk_skips_unchanged_row(monkeypatch):
    cursor = FakeCursor()
    inserted_risks = []
    updated_risks = []
    risk = enrich_species_risk.build_species_risk(valid_vascan_seed_row(), species_directory())
    existing_risk = {
        "id": 91,
        "status": risk["status"],
        "confidence": risk["confidence"],
        "retrieved_at": risk["retrieved_at"],
        "observed_at": risk["observed_at"],
        "license_name": risk["license_name"],
        "license_url": risk["license_url"],
        "attribution": risk["attribution"],
        "notes": risk["notes"],
    }

    monkeypatch.setattr(
        enrich_species_risk, "load_seed_rows", lambda _path: [valid_vascan_seed_row()]
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "load_species_directory",
        lambda _cursor: species_directory(),
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "fetch_existing_risk",
        lambda _cursor, _risk: existing_risk,
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "insert_species_risk",
        lambda _cursor, risk: inserted_risks.append(risk),
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "update_species_risk",
        lambda _cursor, risk_id, risk: updated_risks.append((risk_id, risk)),
    )

    results = enrich_species_risk.enrich_species_risk(cursor)

    assert results["skipped"] == 1
    assert inserted_risks == []
    assert updated_risks == []


def test_enrich_species_risk_dry_run_counts_without_writing(monkeypatch):
    cursor = FakeCursor()
    inserted_risks = []

    monkeypatch.setattr(
        enrich_species_risk, "load_seed_rows", lambda _path: [valid_vascan_seed_row()]
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "load_species_directory",
        lambda _cursor: species_directory(),
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "fetch_existing_risk",
        lambda _cursor, _risk: None,
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "insert_species_risk",
        lambda _cursor, risk: inserted_risks.append(risk),
    )

    results = enrich_species_risk.enrich_species_risk(cursor, dry_run=True)

    assert results["inserted"] == 1
    assert inserted_risks == []


def test_enrich_species_risk_rejects_duplicate_seed_identity(monkeypatch):
    cursor = FakeCursor()
    seed_rows = [valid_vascan_seed_row(), dict(valid_vascan_seed_row(), _line_number=2)]

    monkeypatch.setattr(enrich_species_risk, "load_seed_rows", lambda _path: seed_rows)
    monkeypatch.setattr(
        enrich_species_risk,
        "load_species_directory",
        lambda _cursor: species_directory(),
    )
    monkeypatch.setattr(
        enrich_species_risk,
        "fetch_existing_risk",
        lambda _cursor, _risk: None,
    )

    results = enrich_species_risk.enrich_species_risk(cursor, dry_run=True)

    assert results["inserted"] == 1
    assert results["rejected"] == 1
