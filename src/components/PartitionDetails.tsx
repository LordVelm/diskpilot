import type { DiskInfo } from "../types/disk";
import { formatBytes } from "../lib/format";

interface PartitionDetailsProps {
  disk: DiskInfo;
  selectedPartitionIndex: number | null;
  onSelectPartition: (index: number) => void;
}

export function PartitionDetails({
  disk,
  selectedPartitionIndex,
  onSelectPartition,
}: PartitionDetailsProps) {
  if (disk.partitions.length === 0) {
    return (
      <div
        className="rounded-lg p-4 text-sm"
        style={{ background: "var(--bg-card)", color: "var(--text-muted)" }}
      >
        No partitions — disk may be uninitialized
      </div>
    );
  }

  return (
    <div className="rounded-lg overflow-hidden" style={{ background: "var(--bg-card)" }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ borderBottom: "1px solid var(--separator)" }}>
            <Th>#</Th>
            <Th>Letter</Th>
            <Th>Label</Th>
            <Th>Filesystem</Th>
            <Th>Size</Th>
            <Th>Type</Th>
            <Th>Status</Th>
          </tr>
        </thead>
        <tbody>
          {disk.partitions.map((part) => {
            const isSelected = part.index === selectedPartitionIndex;
            return (
              <tr
                key={part.index}
                className="cursor-pointer transition-colors"
                style={{
                  background: isSelected ? "var(--bg-table-sel)" : "var(--bg-table-row)",
                }}
                onClick={() => onSelectPartition(part.index)}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.background = "var(--bg-card-hover)";
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) e.currentTarget.style.background = isSelected ? "var(--bg-table-sel)" : "var(--bg-table-row)";
                }}
              >
                <Td>{part.index}</Td>
                <Td>{part.drive_letter ? `${part.drive_letter}:` : "—"}</Td>
                <Td>{part.label || "—"}</Td>
                <Td>{part.filesystem || "—"}</Td>
                <Td>{formatBytes(part.size_bytes)}</Td>
                <Td>{part.partition_type}</Td>
                <Td>
                  {part.is_system && (
                    <StatusBadge text="System" color="var(--accent-blue)" />
                  )}
                  {part.is_boot && (
                    <StatusBadge text="Boot" color="var(--accent-cyan)" />
                  )}
                  {!part.is_system && !part.is_boot && "—"}
                </Td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th
      className="text-left px-3 py-2 text-xs font-medium uppercase tracking-wide"
      style={{ color: "var(--text-muted)" }}
    >
      {children}
    </th>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return (
    <td className="px-3 py-2" style={{ borderBottom: "1px solid var(--separator)" }}>
      {children}
    </td>
  );
}

function StatusBadge({ text, color }: { text: string; color: string }) {
  return (
    <span
      className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded mr-1"
      style={{ color, background: `${color}20` }}
    >
      {text}
    </span>
  );
}
