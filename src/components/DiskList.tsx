import type { DiskInfo } from "../types/disk";
import { formatBytes } from "../lib/format";

interface DiskListProps {
  disks: DiskInfo[];
  selectedDiskIndex: number | null;
  onSelectDisk: (index: number) => void;
}

export function DiskList({ disks, selectedDiskIndex, onSelectDisk }: DiskListProps) {
  if (disks.length === 0) {
    return (
      <div className="p-4" style={{ color: "var(--text-muted)" }}>
        No disks found
      </div>
    );
  }

  return (
    <div className="py-2">
      {disks.map((disk) => {
        const isSelected = disk.index === selectedDiskIndex;
        return (
          <button
            key={disk.index}
            onClick={() => onSelectDisk(disk.index)}
            className="w-full text-left px-4 py-3 transition-colors border-b"
            style={{
              background: isSelected ? "var(--bg-table-sel)" : "transparent",
              borderColor: "var(--separator)",
            }}
            onMouseEnter={(e) => {
              if (!isSelected) e.currentTarget.style.background = "var(--bg-card-hover)";
            }}
            onMouseLeave={(e) => {
              if (!isSelected) e.currentTarget.style.background = "transparent";
            }}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>
                Disk {disk.index}
              </span>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                {formatBytes(disk.size_bytes)}
              </span>
            </div>
            <div className="text-xs truncate mb-1.5" style={{ color: "var(--text-secondary)" }}>
              {disk.model}
            </div>
            <div className="flex gap-1.5 flex-wrap">
              {disk.partition_style !== "RAW" && (
                <Badge
                  text={disk.partition_style}
                  fg="var(--badge-style-fg)"
                  bg="var(--badge-style-bg)"
                />
              )}
              {disk.is_system_disk && (
                <Badge text="OS" fg="var(--badge-os-fg)" bg="var(--badge-os-bg)" />
              )}
              {disk.is_removable && (
                <Badge text="USB" fg="var(--badge-usb-fg)" bg="var(--badge-usb-bg)" />
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}

function Badge({ text, fg, bg }: { text: string; fg: string; bg: string }) {
  return (
    <span
      className="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide"
      style={{ color: fg, background: bg }}
    >
      {text}
    </span>
  );
}
