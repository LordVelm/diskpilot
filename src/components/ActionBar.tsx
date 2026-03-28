import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { DiskInfo, PartitionInfo, DiskOpResult } from "../types/disk";

interface ActionBarProps {
  disk: DiskInfo;
  partition: PartitionInfo | null;
  onAction: () => void;
  setStatus: (s: string) => void;
  setConfirmDialog: (dialog: {
    title: string;
    message: string;
    confirmText: string;
    onConfirm: () => void;
  } | null) => void;
}

/** The system drive letter (usually "C" but not always). */
const SYS_LETTER = (typeof navigator !== "undefined" ? "C" : "C"); // Backend enforces via %SystemDrive%

/** Check if a partition is protected on the system disk. */
function isProtected(part: PartitionInfo, disk: DiskInfo): boolean {
  if (!disk.is_system_disk) return false;
  return (
    part.is_system ||
    part.is_boot ||
    ["EFI System", "Recovery", "MSR"].includes(part.partition_type) ||
    part.drive_letter === SYS_LETTER
  );
}

export function ActionBar({
  disk,
  partition,
  onAction,
  setStatus,
  setConfirmDialog,
}: ActionBarProps) {
  const isSystemDisk = disk.is_system_disk;
  const partProtected = partition ? isProtected(partition, disk) : false;
  const [formatFs, setFormatFs] = useState<"NTFS" | "FAT32" | "exFAT">("NTFS");
  const [formatQuick, setFormatQuick] = useState(true);

  const runOp = async (
    label: string,
    fn: () => Promise<DiskOpResult>,
  ) => {
    setStatus(`${label}...`);
    try {
      const result = await fn();
      if (result.success) {
        setStatus(`${label} completed`);
      } else {
        // Extract the first meaningful line from diskpart output
        const lines = result.message.split("\n").filter((l) => l.trim());
        const detail = lines.find((l) => /error|blocked|denied|protected|failed/i.test(l)) ?? lines[lines.length - 1] ?? "Unknown error";
        setStatus(`${label} failed: ${detail.trim()}`);
      }
      onAction(); // refresh
    } catch (e) {
      const msg = typeof e === "string" ? e : (e as Error).message ?? "Unknown error";
      setStatus(`Error: ${msg}`);
    }
  };

  const handleFormat = () => {
    if (!partition) return;
    setConfirmDialog({
      title: "Format Partition",
      message: `This will erase all data on partition ${partition.index}${partition.drive_letter ? ` (${partition.drive_letter}:)` : ""} and format as ${formatFs}${formatQuick ? " (quick)" : " (full)"}. This cannot be undone.`,
      confirmText: `FORMAT PARTITION ${partition.index}`,
      onConfirm: () => {
        runOp("Format", () =>
          invoke<DiskOpResult>("format_partition", {
            diskIndex: disk.index,
            partitionIndex: partition.index,
            filesystem: formatFs,
            label: "",
            quick: formatQuick,
          }),
        );
      },
    });
  };

  const handleDelete = () => {
    if (!partition) return;
    setConfirmDialog({
      title: "Delete Partition",
      message: `This will permanently delete partition ${partition.index}${partition.drive_letter ? ` (${partition.drive_letter}:)` : ""} and all its data.`,
      confirmText: `DELETE PARTITION ${partition.index}`,
      onConfirm: () => {
        runOp("Delete partition", () =>
          invoke<DiskOpResult>("delete_partition", {
            diskIndex: disk.index,
            partitionIndex: partition.index,
          }),
        );
      },
    });
  };

  const handleClean = () => {
    setConfirmDialog({
      title: "Clean Disk",
      message: `This will WIPE the entire partition table on Disk ${disk.index} (${disk.model}). ALL partitions and data will be lost.`,
      confirmText: `CLEAN DISK ${disk.index}`,
      onConfirm: () => {
        runOp("Clean disk", () =>
          invoke<DiskOpResult>("clean_disk", { diskIndex: disk.index }),
        );
      },
    });
  };

  const handleCreate = () => {
    setConfirmDialog({
      title: "Create Partition",
      message: `This will create a new primary partition using all available free space on Disk ${disk.index} (${disk.model}).`,
      confirmText: `CREATE PARTITION`,
      onConfirm: () => {
        runOp("Create partition", () =>
          invoke<DiskOpResult>("create_partition", {
            diskIndex: disk.index,
            sizeMb: null,
            primary: true,
          }),
        );
      },
    });
  };

  const handleAssignLetter = async () => {
    if (!partition) return;
    // Check letters across ALL disks, not just the current one
    try {
      const allDisks = await invoke<DiskInfo[]>("get_disks");
      const usedLetters = new Set(
        allDisks.flatMap((d) => d.partitions.map((p) => p.drive_letter)).filter(Boolean),
      );
      let available = "";
      for (let code = 68; code <= 90; code++) {
        // D-Z
        const l = String.fromCharCode(code);
        if (!usedLetters.has(l)) {
          available = l;
          break;
        }
      }
      if (!available) {
        setStatus("No available drive letters");
        return;
      }
      runOp(`Assign letter ${available}:`, () =>
        invoke<DiskOpResult>("assign_letter", {
          diskIndex: disk.index,
          partitionIndex: partition.index,
          letter: available,
        }),
      );
    } catch {
      setStatus("Failed to check available drive letters");
    }
  };

  const handleRemoveLetter = () => {
    if (!partition || !partition.drive_letter) return;
    runOp(`Remove letter ${partition.drive_letter}:`, () =>
      invoke<DiskOpResult>("remove_letter", {
        diskIndex: disk.index,
        partitionIndex: partition.index,
        letter: partition.drive_letter,
      }),
    );
  };

  return (
    <div
      className="flex flex-wrap gap-2 items-center rounded-lg p-3"
      style={{ background: "var(--bg-card)" }}
    >
      {/* Format options */}
      <select
        value={formatFs}
        onChange={(e) => setFormatFs(e.target.value as "NTFS" | "FAT32" | "exFAT")}
        className="px-2 py-1.5 text-xs rounded-md border"
        style={{ background: "var(--bg-input)", color: "var(--text-primary)", borderColor: "var(--separator)" }}
      >
        <option value="NTFS">NTFS</option>
        <option value="FAT32">FAT32</option>
        <option value="exFAT">exFAT</option>
      </select>
      <label className="flex items-center gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
        <input type="checkbox" checked={formatQuick} onChange={(e) => setFormatQuick(e.target.checked)} />
        Quick
      </label>
      <ActionButton
        label="Format"
        color="var(--accent-purple)"
        hover="var(--hover-purple)"
        disabled={!partition || partProtected}
        onClick={handleFormat}
      />
      <ActionButton
        label="Delete"
        color="var(--accent-red)"
        hover="var(--hover-red)"
        disabled={!partition || partProtected}
        onClick={handleDelete}
      />
      <ActionButton
        label="Assign Letter"
        color="var(--accent-cyan)"
        hover="var(--hover-cyan)"
        disabled={!partition}
        onClick={handleAssignLetter}
      />
      <ActionButton
        label="Remove Letter"
        color="var(--accent-gray)"
        hover="var(--hover-gray)"
        disabled={!partition || !partition.drive_letter || partition.drive_letter === "C"}
        onClick={handleRemoveLetter}
      />

      <div className="w-px mx-1" style={{ background: "var(--separator)" }} />

      {/* Disk-level actions */}
      <ActionButton
        label="Create Partition"
        color="var(--accent-green)"
        hover="var(--hover-green)"
        disabled={isSystemDisk}
        onClick={handleCreate}
      />
      <ActionButton
        label="Clean Disk"
        color="var(--accent-red)"
        hover="var(--hover-red)"
        disabled={isSystemDisk}
        onClick={handleClean}
      />
    </div>
  );
}

function ActionButton({
  label,
  color,
  hover,
  disabled,
  onClick,
}: {
  label: string;
  color: string;
  hover: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="px-3 py-1.5 text-xs font-medium rounded-md transition-colors"
      style={{
        background: disabled ? "var(--accent-gray)" : color,
        color: "#fff",
        opacity: disabled ? 0.4 : 1,
        cursor: disabled ? "not-allowed" : "pointer",
      }}
      onMouseEnter={(e) => {
        if (!disabled) e.currentTarget.style.background = hover;
      }}
      onMouseLeave={(e) => {
        if (!disabled) e.currentTarget.style.background = color;
      }}
    >
      {label}
    </button>
  );
}
