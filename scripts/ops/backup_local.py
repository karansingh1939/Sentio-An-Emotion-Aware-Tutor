"""Snapshot/verify/restore local data without starting the tutor or models."""

import argparse
from pathlib import Path

from sentio.maintenance.backup import create_backup, restore_backup, verify_backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "verify", "restore"])
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, nargs="?")
    args = parser.parse_args()
    if args.action == "verify":
        print(f"Verified {verify_backup(args.source)} private files")
        return
    if args.destination is None:
        parser.error("create and restore require a destination")
    if args.action == "create":
        create_backup(args.source, args.destination)
    else:
        restore_backup(args.source, args.destination)
    print("Completed. Backup and restored data are private; do not publish them.")


if __name__ == "__main__":
    main()
