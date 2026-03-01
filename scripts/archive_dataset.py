#!/usr/bin/env python3

import argparse
import shutil
from pathlib import Path

from data_management import archive_destination


def main():
    parser = argparse.ArgumentParser(
        description="Archive a local dataset into data/raw/<city>/<date>/"
    )
    parser.add_argument("city", help="City slug, e.g. oakville")
    parser.add_argument("file", help="Path to the downloaded dataset file")
    parser.add_argument(
        "--date",
        help=(
            "Override the archive date (YYYY-MM-DD). "
            "Defaults to filesystem creation/modification date."
        ),
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy instead of move the file",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform the move/copy. Without this flag the script is a dry run.",
    )

    args = parser.parse_args()
    source_path = Path(args.file)
    if not source_path.exists():
        raise SystemExit(f"File not found: {source_path}")

    destination = archive_destination(source_path, args.city, date_str=args.date)
    print(f"Source:      {source_path}")
    print(f"Destination: {destination}")

    if not args.apply:
        print("Dry run only. Re-run with --apply to perform the archive.")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise SystemExit(f"Destination already exists: {destination}")

    if args.copy:
        shutil.copy2(source_path, destination)
        print("Copied dataset.")
    else:
        source_path.rename(destination)
        print("Moved dataset.")


if __name__ == "__main__":
    main()
