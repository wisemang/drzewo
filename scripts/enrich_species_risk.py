#!/usr/bin/env python3

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tree_loader

APPROVED_RISK_TYPES = {
    "native_status",
    "introduced_status",
    "pest_host",
    "management_concern",
}
STATUS_BY_RISK_TYPE = {
    "native_status": {"native"},
    "introduced_status": {"introduced"},
    "pest_host": {"present", "reported"},
    "management_concern": {"present", "reported"},
}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
PLACEHOLDER_TEXT = {"unknown", "n/a", "no data available"}
FORBIDDEN_SAFETY_PATTERNS = (
    re.compile(r"\bsafe\b", re.IGNORECASE),
    re.compile(r"\bno risk\b", re.IGNORECASE),
    re.compile(r"\bnot risky\b", re.IGNORECASE),
    re.compile(r"\brisk[- ]free\b", re.IGNORECASE),
)
FORBIDDEN_BROAD_CLAIM_PATTERNS = (
    re.compile(r"\binvasive\b", re.IGNORECASE),
    re.compile(r"\brestricted\b", re.IGNORECASE),
    re.compile(r"\bprohibited\b", re.IGNORECASE),
)
DEFAULT_SEED_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "enrichment" / "risk_seed.jsonl"
)


class ValidationError(ValueError):
    """Raised when a reviewed seed row fails TE-018 validation."""


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


def validate_required_text(seed_row, field_name):
    value = normalize_text(seed_row.get(field_name))
    if value is None:
        raise ValidationError(f"{field_name} is required")
    if value.lower() in PLACEHOLDER_TEXT:
        raise ValidationError(f"{field_name} uses placeholder text")
    return value


def validate_risk_type(value):
    risk_type = normalize_text(value)
    if risk_type is None:
        raise ValidationError("risk_type is required")
    if risk_type not in APPROVED_RISK_TYPES:
        raise ValidationError(f"unsupported risk_type: {risk_type}")
    return risk_type


def validate_status(value, risk_type):
    status = normalize_text(value)
    if status is None:
        raise ValidationError("status is required")
    if status.lower() in PLACEHOLDER_TEXT:
        raise ValidationError("status uses placeholder text")
    if status not in STATUS_BY_RISK_TYPE[risk_type]:
        raise ValidationError(f"unsupported status for {risk_type}: {status}")
    return status


def validate_note(value):
    note = normalize_text(value)
    if note is None:
        raise ValidationError("note is required")
    if note.lower() in PLACEHOLDER_TEXT:
        raise ValidationError("note uses placeholder text")
    for pattern in FORBIDDEN_SAFETY_PATTERNS:
        if pattern.search(note):
            raise ValidationError("note uses missing-data-as-safety wording")
    for pattern in FORBIDDEN_BROAD_CLAIM_PATTERNS:
        if pattern.search(note):
            raise ValidationError("note makes an unsupported broad invasive or statutory claim")
    return note


def validate_confidence(value):
    confidence = normalize_text(value)
    if confidence is None:
        raise ValidationError("confidence is required")
    if confidence not in ALLOWED_CONFIDENCE:
        raise ValidationError(f"unsupported confidence: {confidence}")
    return confidence


def build_species_risk(seed_row, species_directory):
    species_row = resolve_species_row(seed_row, species_directory)
    risk_type = validate_risk_type(seed_row.get("risk_type"))
    status = validate_status(seed_row.get("status"), risk_type)
    note = validate_note(seed_row.get("note"))
    region = validate_required_text(seed_row, "region")
    region_type = validate_required_text(seed_row, "region_type")
    source_system = validate_required_text(seed_row, "source_system")
    validate_required_text(seed_row, "source_title")
    source_url = validate_required_text(seed_row, "source_url")
    license_name = validate_required_text(seed_row, "license_name")
    license_url = validate_required_text(seed_row, "license_url")
    attribution = validate_required_text(seed_row, "attribution")
    method_version = validate_required_text(seed_row, "method_version")
    confidence = validate_confidence(seed_row.get("confidence"))
    retrieved_at = parse_timestamp(seed_row.get("retrieved_at"), "retrieved_at")
    observed_at = normalize_optional_timestamp(seed_row.get("observed_at"), "observed_at")

    return {
        "species_id": species_row["id"],
        "species_key": species_row["species_key"],
        "risk_type": risk_type,
        "status": status,
        "region": region,
        "region_type": region_type,
        "source_system": source_system,
        "source_url": source_url,
        "license_name": license_name,
        "license_url": license_url,
        "attribution": attribution,
        "method_version": method_version,
        "confidence": confidence,
        "retrieved_at": retrieved_at,
        "observed_at": observed_at,
        "notes": note,
        "signal_key": normalize_text(seed_row.get("signal_key")),
    }


def risk_identity_key(risk):
    return (
        risk["species_id"],
        risk["risk_type"],
        risk["region"],
        risk["region_type"],
        risk["source_system"],
        risk["source_url"],
        risk["method_version"],
    )


def fetch_existing_risk(cursor, risk):
    cursor.execute(
        """
        SELECT
            id,
            status,
            confidence,
            retrieved_at,
            observed_at,
            license_name,
            license_url,
            attribution,
            notes
        FROM species_risk
        WHERE species_id = %s
          AND risk_type = %s
          AND region = %s
          AND region_type = %s
          AND source_system = %s
          AND source_url = %s
          AND method_version = %s
        ORDER BY id
        LIMIT 1;
        """,
        (
            risk["species_id"],
            risk["risk_type"],
            risk["region"],
            risk["region_type"],
            risk["source_system"],
            risk["source_url"],
            risk["method_version"],
        ),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "status": row[1],
        "confidence": row[2],
        "retrieved_at": row[3],
        "observed_at": row[4],
        "license_name": row[5],
        "license_url": row[6],
        "attribution": row[7],
        "notes": row[8],
    }


def risk_has_changed(existing_risk, risk):
    return any(
        (
            existing_risk.get("status") != risk["status"],
            existing_risk.get("confidence") != risk["confidence"],
            existing_risk.get("retrieved_at") != risk["retrieved_at"],
            existing_risk.get("observed_at") != risk["observed_at"],
            existing_risk.get("license_name") != risk["license_name"],
            existing_risk.get("license_url") != risk["license_url"],
            existing_risk.get("attribution") != risk["attribution"],
            existing_risk.get("notes") != risk["notes"],
        )
    )


def insert_species_risk(cursor, risk):
    cursor.execute(
        """
        INSERT INTO species_risk (
            species_id,
            risk_type,
            status,
            region,
            region_type,
            source_system,
            source_url,
            retrieved_at,
            observed_at,
            method_version,
            confidence,
            license_name,
            license_url,
            attribution,
            notes,
            updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now()
        );
        """,
        (
            risk["species_id"],
            risk["risk_type"],
            risk["status"],
            risk["region"],
            risk["region_type"],
            risk["source_system"],
            risk["source_url"],
            risk["retrieved_at"],
            risk["observed_at"],
            risk["method_version"],
            risk["confidence"],
            risk["license_name"],
            risk["license_url"],
            risk["attribution"],
            risk["notes"],
        ),
    )


def update_species_risk(cursor, risk_id, risk):
    cursor.execute(
        """
        UPDATE species_risk
        SET status = %s,
            confidence = %s,
            retrieved_at = %s,
            observed_at = %s,
            license_name = %s,
            license_url = %s,
            attribution = %s,
            notes = %s,
            updated_at = now()
        WHERE id = %s;
        """,
        (
            risk["status"],
            risk["confidence"],
            risk["retrieved_at"],
            risk["observed_at"],
            risk["license_name"],
            risk["license_url"],
            risk["attribution"],
            risk["notes"],
            risk_id,
        ),
    )


def enrich_species_risk(cursor, *, seed_path=DEFAULT_SEED_PATH, dry_run=False):
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
            risk = build_species_risk(seed_row, species_directory)
            dedupe_key = risk_identity_key(risk)
            if dedupe_key in seen_keys:
                raise ValidationError("duplicate seed row for the same species/risk/source key")
            seen_keys.add(dedupe_key)

            existing_risk = fetch_existing_risk(cursor, risk)
            touched_species.add(risk["species_id"])
            if existing_risk is None:
                results["inserted"] += 1
                if not dry_run:
                    insert_species_risk(cursor, risk)
            elif risk_has_changed(existing_risk, risk):
                results["updated"] += 1
                if not dry_run:
                    update_species_risk(cursor, existing_risk["id"], risk)
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
            "Species risk enrichment complete.",
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
        description="Populate reviewed regional species risk records from a local seed file."
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
        results = enrich_species_risk(
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
