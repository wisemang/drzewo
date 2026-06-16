#!/usr/bin/env python3

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tree_loader

APPROVED_METRIC_TYPES = {
    "wildlife_food",
    "wildlife_habitat",
    "pollinator_support",
    "shade_or_amenity",
    "site_rehabilitation",
    "cultural_or_human_use",
}
METRIC_LABELS = {
    "wildlife_food": "Wildlife food",
    "wildlife_habitat": "Wildlife habitat",
    "pollinator_support": "Pollinator support",
    "shade_or_amenity": "Shade and amenity",
    "site_rehabilitation": "Site rehabilitation",
    "cultural_or_human_use": "Cultural or human use",
}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
PLACEHOLDER_TEXT = {"unknown", "n/a", "no data available"}
ESTIMATE_FIELDS = (
    "value",
    "unit",
    "min_value",
    "max_value",
    "currency",
    "tree_source",
    "tree_objectid",
    "calculated_at",
)
DEFAULT_SEED_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "enrichment" / "benefits_seed.jsonl"
)


class ValidationError(ValueError):
    """Raised when a reviewed seed row fails TE-017 validation."""


def normalize_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def has_present_value(value):
    return value is not None and not (isinstance(value, str) and not value.strip())


def parse_timestamp(value, field_name):
    text = normalize_text(value)
    if text is None:
        raise ValidationError(f"{field_name} is required")
    try:
        timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be an ISO-8601 date or datetime") from exc
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp


def normalize_optional_timestamp(value, field_name):
    if not has_present_value(value):
        return None
    return parse_timestamp(value, field_name)


def load_seed_rows(seed_path):
    rows = []
    with Path(seed_path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(payload, dict):
                raise ValidationError(f"line {line_number}: seed row must be a JSON object")
            payload["_line_number"] = line_number
            rows.append(payload)
    return rows


def load_species_directory(cursor):
    cursor.execute(
        """
        SELECT id, species_key, canonical_botanical_name, display_common_name
        FROM species
        ORDER BY species_key;
        """
    )
    species_rows = [
        {
            "id": row[0],
            "species_key": row[1],
            "canonical_botanical_name": row[2],
            "display_common_name": row[3],
        }
        for row in cursor.fetchall()
    ]
    return {
        "by_key": {row["species_key"]: row for row in species_rows},
        "by_scientific_name": {
            row["canonical_botanical_name"].strip().lower(): row for row in species_rows
        },
    }


def resolve_species_row(seed_row, species_directory):
    species_key = normalize_text(seed_row.get("species_key"))
    scientific_name = normalize_text(seed_row.get("scientific_name"))

    if species_key is None and scientific_name is None:
        raise ValidationError("species_key or scientific_name is required")

    by_key = species_directory["by_key"]
    by_scientific_name = species_directory["by_scientific_name"]
    resolved_from_key = by_key.get(species_key) if species_key is not None else None
    resolved_from_name = (
        by_scientific_name.get(scientific_name.lower()) if scientific_name is not None else None
    )

    if species_key is not None and resolved_from_key is None:
        raise ValidationError(f"species_key does not resolve: {species_key}")
    if scientific_name is not None and resolved_from_name is None:
        raise ValidationError(f"scientific_name does not resolve: {scientific_name}")
    if (
        resolved_from_key is not None
        and resolved_from_name is not None
        and resolved_from_key["id"] != resolved_from_name["id"]
    ):
        raise ValidationError(
            "species_key and scientific_name resolve to different species records"
        )

    return resolved_from_key or resolved_from_name


def validate_note(text):
    normalized = normalize_text(text)
    if normalized is None:
        raise ValidationError("note is required")
    if normalized.lower() in PLACEHOLDER_TEXT:
        raise ValidationError("note uses placeholder text")
    return normalized


def validate_metric_type(value):
    metric_type = normalize_text(value)
    if metric_type is None:
        raise ValidationError("metric_type is required")
    if metric_type not in APPROVED_METRIC_TYPES:
        raise ValidationError(f"unsupported metric_type: {metric_type}")
    return metric_type


def validate_confidence(value):
    confidence = normalize_text(value)
    if confidence is None:
        raise ValidationError("confidence is required")
    if confidence not in ALLOWED_CONFIDENCE:
        raise ValidationError(f"unsupported confidence: {confidence}")
    return confidence


def validate_required_text(seed_row, field_name):
    value = normalize_text(seed_row.get(field_name))
    if value is None:
        raise ValidationError(f"{field_name} is required")
    if field_name == "source_title" and value.lower() in PLACEHOLDER_TEXT:
        raise ValidationError("source_title uses placeholder text")
    return value


def reject_estimate_fields(seed_row):
    for field_name in ESTIMATE_FIELDS:
        if has_present_value(seed_row.get(field_name)):
            raise ValidationError(f"{field_name} is not allowed for qualitative species benefits")


def build_species_benefit(seed_row, species_directory):
    reject_estimate_fields(seed_row)

    if has_present_value(seed_row.get("observed_at")):
        raise ValidationError("observed_at is not supported for qualitative species benefits")

    scope = normalize_text(seed_row.get("scope"))
    if scope != "species":
        raise ValidationError("scope must be species")

    species_row = resolve_species_row(seed_row, species_directory)
    metric_type = validate_metric_type(seed_row.get("metric_type"))
    note = validate_note(seed_row.get("note"))
    source_system = validate_required_text(seed_row, "source_system")
    source_url = validate_required_text(seed_row, "source_url")
    validate_required_text(seed_row, "source_title")
    attribution = validate_required_text(seed_row, "attribution")
    license_name = validate_required_text(seed_row, "license_name")
    license_url = validate_required_text(seed_row, "license_url")
    method_version = validate_required_text(seed_row, "method_version")
    confidence = validate_confidence(seed_row.get("confidence"))
    retrieved_at = parse_timestamp(seed_row.get("retrieved_at"), "retrieved_at")
    region = normalize_text(seed_row.get("region"))

    return {
        "species_id": species_row["id"],
        "species_key": species_row["species_key"],
        "metric_type": metric_type,
        "scope": scope,
        "label": METRIC_LABELS[metric_type],
        "text": note,
        "region": region,
        "method_version": method_version,
        "confidence": confidence,
        "source_system": source_system,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "license_name": license_name,
        "license_url": license_url,
        "attribution": attribution,
        "claim_key": normalize_text(seed_row.get("claim_key")),
    }


def benefit_identity_key(benefit):
    return (
        benefit["species_id"],
        benefit["metric_type"],
        benefit["scope"],
        benefit["region"],
        benefit["source_system"],
        benefit["source_url"],
        benefit["method_version"],
    )


def fetch_existing_benefit(cursor, benefit):
    cursor.execute(
        """
        SELECT
            id,
            label,
            text,
            confidence,
            source_system,
            source_url,
            retrieved_at,
            license_name,
            license_url,
            attribution
        FROM species_benefit
        WHERE species_id = %s
          AND metric_type = %s
          AND scope = %s
          AND region IS NOT DISTINCT FROM %s
          AND source_system = %s
          AND source_url = %s
          AND method_version = %s
        ORDER BY id
        LIMIT 1;
        """,
        (
            benefit["species_id"],
            benefit["metric_type"],
            benefit["scope"],
            benefit["region"],
            benefit["source_system"],
            benefit["source_url"],
            benefit["method_version"],
        ),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "label": row[1],
        "text": row[2],
        "confidence": row[3],
        "source_system": row[4],
        "source_url": row[5],
        "retrieved_at": row[6],
        "license_name": row[7],
        "license_url": row[8],
        "attribution": row[9],
    }


def benefit_has_changed(existing_benefit, benefit):
    return any(
        (
            existing_benefit.get("label") != benefit["label"],
            existing_benefit.get("text") != benefit["text"],
            existing_benefit.get("confidence") != benefit["confidence"],
            existing_benefit.get("source_system") != benefit["source_system"],
            existing_benefit.get("source_url") != benefit["source_url"],
            existing_benefit.get("license_name") != benefit["license_name"],
            existing_benefit.get("license_url") != benefit["license_url"],
            existing_benefit.get("attribution") != benefit["attribution"],
            existing_benefit.get("retrieved_at") != benefit["retrieved_at"],
        )
    )


def insert_species_benefit(cursor, benefit):
    cursor.execute(
        """
        INSERT INTO species_benefit (
            species_id,
            metric_type,
            scope,
            label,
            text,
            region,
            method_version,
            confidence,
            source_system,
            source_url,
            retrieved_at,
            license_name,
            license_url,
            attribution,
            updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now()
        );
        """,
        (
            benefit["species_id"],
            benefit["metric_type"],
            benefit["scope"],
            benefit["label"],
            benefit["text"],
            benefit["region"],
            benefit["method_version"],
            benefit["confidence"],
            benefit["source_system"],
            benefit["source_url"],
            benefit["retrieved_at"],
            benefit["license_name"],
            benefit["license_url"],
            benefit["attribution"],
        ),
    )


def update_species_benefit(cursor, benefit_id, benefit):
    cursor.execute(
        """
        UPDATE species_benefit
        SET label = %s,
            text = %s,
            confidence = %s,
            retrieved_at = %s,
            license_name = %s,
            license_url = %s,
            attribution = %s,
            updated_at = now()
        WHERE id = %s;
        """,
        (
            benefit["label"],
            benefit["text"],
            benefit["confidence"],
            benefit["retrieved_at"],
            benefit["license_name"],
            benefit["license_url"],
            benefit["attribution"],
            benefit_id,
        ),
    )


def enrich_species_benefits(cursor, *, seed_path=DEFAULT_SEED_PATH, dry_run=False):
    seed_rows = load_seed_rows(seed_path)
    species_directory = load_species_directory(cursor)
    seen_keys = set()
    touched_species = set()
    results = {
        "rows_read": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "rejected": 0,
        "species_touched": 0,
    }

    for seed_row in seed_rows:
        results["rows_read"] += 1
        line_number = seed_row.get("_line_number", "?")
        try:
            benefit = build_species_benefit(seed_row, species_directory)
            dedupe_key = benefit_identity_key(benefit)
            if dedupe_key in seen_keys:
                raise ValidationError("duplicate seed row for the same species/metric/source key")
            seen_keys.add(dedupe_key)

            existing_benefit = fetch_existing_benefit(cursor, benefit)
            touched_species.add(benefit["species_id"])
            if existing_benefit is None:
                results["inserted"] += 1
                if not dry_run:
                    insert_species_benefit(cursor, benefit)
            elif benefit_has_changed(existing_benefit, benefit):
                results["updated"] += 1
                if not dry_run:
                    update_species_benefit(cursor, existing_benefit["id"], benefit)
            else:
                results["skipped"] += 1
        except ValidationError as exc:
            results["rejected"] += 1
            print(f"Rejected row {line_number}: {exc}")

    results["species_touched"] = len(touched_species)
    return results


def format_enrichment_summary(results, *, dry_run=False):
    if dry_run:
        return "\n".join(
            [
                "DRY RUN: no database changes written.",
                f"Rows read: {results['rows_read']}",
                f"Would insert: {results['inserted']}",
                f"Would update: {results['updated']}",
                f"Would skip unchanged: {results['skipped']}",
                f"Would reject: {results['rejected']}",
                f"Species touched: {results['species_touched']}",
            ]
        )

    return "\n".join(
        [
            "Species benefit enrichment complete.",
            f"Rows read: {results['rows_read']}",
            f"Inserted: {results['inserted']}",
            f"Updated: {results['updated']}",
            f"Skipped unchanged: {results['skipped']}",
            f"Rejected: {results['rejected']}",
            f"Species touched: {results['species_touched']}",
        ]
    )


def main():
    parser = argparse.ArgumentParser(
        description="Populate reviewed qualitative species benefits from a local seed file."
    )
    parser.add_argument(
        "--seed",
        default=str(DEFAULT_SEED_PATH),
        help="Path to the reviewed JSONL seed file",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate but do not write rows")
    args = parser.parse_args()

    conn = tree_loader.connect_db()
    try:
        cursor = conn.cursor()
        tree_loader.ensure_species_tables(cursor)
        tree_loader.ensure_species_enrichment_tables(cursor)
        results = enrich_species_benefits(
            cursor,
            seed_path=args.seed,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
        print(format_enrichment_summary(results, dry_run=args.dry_run))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
