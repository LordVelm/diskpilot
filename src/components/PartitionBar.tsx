import type { DiskInfo, PartitionInfo } from "../types/disk";
import { formatBytes } from "../lib/format";

interface PartitionBarProps {
  disk: DiskInfo;
  selectedPartitionIndex: number | null;
  onSelectPartition: (index: number) => void;
}

/** Get the bar color for a partition — same rules as Python _partition_color(). */
function partitionColor(part: PartitionInfo, onSystemDisk: boolean): string {
  if (isProtected(part, onSystemDisk)) return "var(--bar-protected)";
  const fs = part.filesystem.toUpperCase();
  if (fs === "NTFS") {
    return part.is_boot || part.is_system
      ? "var(--bar-ntfs-system)"
      : "var(--bar-ntfs-data)";
  }
  if (["FAT32", "EXFAT", "FAT"].includes(fs)) return "var(--bar-fat)";
  return "var(--bar-unallocated)";
}

function isProtected(part: PartitionInfo, onSystemDisk: boolean): boolean {
  if (!onSystemDisk) return false;
  // Backend enforces via %SystemDrive%; frontend uses system disk flags as primary signal.
  // Drive letter check is a fallback — most system partitions have is_system or is_boot set.
  return (
    part.is_system ||
    part.is_boot ||
    ["EFI System", "Recovery", "MSR"].includes(part.partition_type) ||
    part.drive_letter === "C"
  );
}

export function PartitionBar({ disk, selectedPartitionIndex, onSelectPartition }: PartitionBarProps) {
  const total = disk.size_bytes || 1;
  const onSystemDisk = disk.is_system_disk;

  // Build segments: free gaps + partitions (same logic as Python DiskBarWidget)
  type Segment = { kind: "free" | "part"; size: number; part: PartitionInfo | null };
  const segments: Segment[] = [];
  let currentOffset = 0;

  for (const part of disk.partitions) {
    const gap = part.offset_bytes - currentOffset;
    if (gap > total * 0.01) {
      segments.push({ kind: "free", size: gap, part: null });
    }
    segments.push({ kind: "part", size: part.size_bytes, part });
    currentOffset = part.offset_bytes + part.size_bytes;
  }
  const trailing = total - currentOffset;
  if (trailing > total * 0.01) {
    segments.push({ kind: "free", size: trailing, part: null });
  }

  if (segments.length === 0) {
    segments.push({ kind: "free", size: total, part: null });
  }

  return (
    <div
      className="flex rounded-xl overflow-hidden h-16 gap-0.5"
      style={{ background: "var(--bg-card)" }}
    >
      {segments.map((seg, i) => {
        const fraction = Math.max(seg.size / total, 0.025);
        const isPartition = seg.kind === "part" && seg.part;
        const isSelected = isPartition && seg.part!.index === selectedPartitionIndex;
        const color = isPartition
          ? partitionColor(seg.part!, onSystemDisk)
          : "var(--bar-unallocated)";

        const textColor =
          color === "var(--bar-protected)"
            ? "var(--bar-text-protected)"
            : isPartition
              ? "var(--bar-text)"
              : "var(--bar-text-free)";

        let label = "";
        if (isPartition && seg.part) {
          const p = seg.part;
          const letterStr = p.drive_letter ? `${p.drive_letter}:` : "";
          const sizeStr = formatBytes(p.size_bytes);
          label = letterStr ? `${letterStr}  ${sizeStr}` : sizeStr;
          if (p.filesystem) label += `\n${p.filesystem}`;
        } else {
          label = "Free";
        }

        return (
          <div
            key={i}
            className="flex items-center justify-center cursor-pointer transition-all relative overflow-hidden"
            style={{
              flex: `${fraction} 0 0`,
              background: color,
              borderRadius: i === 0 ? "10px 4px 4px 10px" : i === segments.length - 1 ? "4px 10px 10px 4px" : "4px",
              outline: isSelected ? "2px solid var(--bar-selected-border)" : "none",
              outlineOffset: "-1px",
            }}
            onClick={() => {
              if (isPartition && seg.part) onSelectPartition(seg.part.index);
            }}
          >
            <span
              className="text-[10px] font-semibold text-center whitespace-pre-line leading-tight px-1"
              style={{ color: textColor }}
            >
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
