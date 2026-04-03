#!/usr/bin/env python3
"""Batch process all NDA files in a folder."""

import os
import sys
import glob
import shutil
from nda_pipeline import process

INPUT_DIR = "/home/cliff/redact/TestInput"
COMPLETED_DIR = "/home/cliff/redact/Completed"


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else INPUT_DIR
    config_name = sys.argv[2] if len(sys.argv) > 2 else "default_receiver"
    os.makedirs(COMPLETED_DIR, exist_ok=True)

    files = sorted(
        f for f in
        glob.glob(os.path.join(folder, "*.doc*")) +
        glob.glob(os.path.join(folder, "*.pdf")) +
        glob.glob(os.path.join(folder, "*.txt")) +
        glob.glob(os.path.join(folder, "*.mhtml"))
        if ':Zone.Identifier' not in f
    )

    if not files:
        print(f"No files found in {folder}")
        sys.exit(1)

    print(f"Found {len(files)} files to process\n")
    results = []

    for i, f in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] {os.path.basename(f)}")
        try:
            process(f, config_name)
            shutil.move(f, os.path.join(COMPLETED_DIR, os.path.basename(f)))
            results.append((os.path.basename(f), "✅"))
        except Exception as e:
            print(f"❌ Failed: {e}")
            results.append((os.path.basename(f), f"❌ {e}"))

    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE: {len(files)} files")
    print(f"{'='*60}")
    for name, status in results:
        print(f"  {status} {name}")


if __name__ == "__main__":
    main()
