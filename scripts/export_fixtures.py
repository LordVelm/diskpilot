"""Export golden disk fixtures from the current machine for parity testing.

Run from the diskpilot root (requires admin + venv with wmi/pywin32):
    python scripts/export_fixtures.py

Outputs: fixtures/golden_disks.json
"""

import json
import os
import sys
from dataclasses import asdict

# Add parent dir so we can import disk_ops
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disk_ops import get_all_disks


def main():
    disks = get_all_disks()
    data = [asdict(d) for d in disks]

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "golden_disks.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Exported {len(disks)} disk(s) to {out_path}")
    for d in disks:
        print(f"  Disk {d.index}: {d.model} — {len(d.partitions)} partition(s) — {'SYSTEM' if d.is_system_disk else 'data'}")


if __name__ == "__main__":
    main()
