/** Shared disk/partition types — mirrors Rust backend structs exactly. */

export interface PartitionInfo {
  index: number;
  size_bytes: number;
  filesystem: string; // "NTFS", "FAT32", "exFAT", "RAW", ""
  label: string;
  drive_letter: string; // "C", "D", etc. or ""
  partition_type: string; // "Basic", "EFI System", "Recovery", "MSR"
  is_system: boolean;
  is_boot: boolean;
  offset_bytes: number;
}

export interface DiskInfo {
  index: number;
  model: string;
  size_bytes: number;
  media_type: string;
  partition_style: string; // "GPT", "MBR", "RAW"
  is_removable: boolean;
  is_system_disk: boolean;
  partitions: PartitionInfo[];
}

/** Format options passed to the format command. */
export interface FormatOptions {
  disk_index: number;
  partition_index: number;
  filesystem: "NTFS" | "FAT32" | "EXFAT";
  label: string;
  quick: boolean;
}

/** Result from any diskpart mutation. */
export interface DiskOpResult {
  success: boolean;
  message: string;
}
