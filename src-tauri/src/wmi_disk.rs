//! WMI-based disk enumeration — mirrors Python disk_ops.get_all_disks() exactly.
//!
//! Key rules:
//! - WMI partition Index is 0-based (diskpart uses 1-based — handled in diskpart.rs)
//! - Partitions sorted by StartingOffset (same as Python)
//! - Disks sorted by Index

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use wmi::{COMLibrary, WMIConnection};

// ── Public types (serialized to frontend) ──

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PartitionInfo {
    pub index: u32,
    pub size_bytes: u64,
    pub filesystem: String,
    pub label: String,
    pub drive_letter: String,
    pub partition_type: String,
    pub is_system: bool,
    pub is_boot: bool,
    pub offset_bytes: u64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DiskInfo {
    pub index: u32,
    pub model: String,
    pub size_bytes: u64,
    pub media_type: String,
    pub partition_style: String,
    pub is_removable: bool,
    pub is_system_disk: bool,
    pub partitions: Vec<PartitionInfo>,
}

// ── WMI query structs (serde field names must match WMI property names) ──

#[derive(Deserialize, Debug)]
#[serde(rename_all = "PascalCase")]
struct Win32DiskDrive {
    index: u32,
    model: Option<String>,
    size: Option<u64>,
    media_type: Option<String>,
}

#[derive(Deserialize, Debug)]
#[serde(rename_all = "PascalCase")]
struct Win32DiskPartition {
    device_i_d: Option<String>,
    disk_index: u32,
    index: u32,
    size: Option<u64>,
    #[serde(rename = "Type")]
    r#type: Option<String>,
    boot_partition: Option<bool>,
    starting_offset: Option<u64>,
}

#[derive(Deserialize, Debug)]
#[serde(rename_all = "PascalCase")]
struct Win32LogicalDisk {
    device_i_d: Option<String>,
    file_system: Option<String>,
    volume_name: Option<String>,
}

#[derive(Deserialize, Debug)]
#[serde(rename_all = "PascalCase")]
struct DiskPartitionAssoc {
    antecedent: Option<String>,
    dependent: Option<String>,
}

/// Extract the WMI object key from a reference string like:
/// `\\\\MACHINE\\root\\cimv2:Win32_DiskPartition.DeviceID="Disk #0, Partition #0"`
/// Returns the DeviceID value.
fn extract_device_id(reference: &str) -> Option<String> {
    // Look for DeviceID="..." pattern
    if let Some(start) = reference.find("DeviceID=\"") {
        let rest = &reference[start + 10..]; // skip past DeviceID="
        if let Some(end) = rest.find('"') {
            return Some(rest[..end].to_string());
        }
    }
    None
}

pub fn enumerate_disks() -> Result<Vec<DiskInfo>, String> {
    let com = COMLibrary::new().map_err(|e| format!("COM init failed: {e}"))?;
    let wmi = WMIConnection::new(com).map_err(|e| format!("WMI connect failed: {e}"))?;

    // Step 1: Query all logical disks
    let logical_disks: Vec<Win32LogicalDisk> = wmi
        .raw_query("SELECT DeviceID, FileSystem, VolumeName FROM Win32_LogicalDisk")
        .map_err(|e| format!("LogicalDisk query failed: {e}"))?;

    // Step 2: Query Win32_LogicalDiskToPartition associations
    let assocs: Vec<DiskPartitionAssoc> = wmi
        .raw_query("SELECT Antecedent, Dependent FROM Win32_LogicalDiskToPartition")
        .map_err(|e| format!("Association query failed: {e}"))?;

    // Build maps: partition DeviceID -> drive letter(s) and logical disk info
    let mut logical_map: HashMap<String, &Win32LogicalDisk> = HashMap::new();
    for ld in &logical_disks {
        if let Some(ref did) = ld.device_i_d {
            logical_map.insert(did.clone(), ld);
        }
    }

    // partition_device_id -> Vec<drive_letter>
    let mut partition_to_letters: HashMap<String, Vec<String>> = HashMap::new();
    // partition_device_id -> (filesystem, label)
    let mut partition_to_logical: HashMap<String, (String, String)> = HashMap::new();

    for assoc in &assocs {
        let part_id = assoc.antecedent.as_deref().and_then(extract_device_id);
        let logical_id = assoc.dependent.as_deref().and_then(extract_device_id);

        if let (Some(part_id), Some(logical_id)) = (part_id, logical_id) {
            // Drive letter: strip trailing ':'
            let letter = logical_id.trim_end_matches(':').to_string();
            partition_to_letters
                .entry(part_id.clone())
                .or_default()
                .push(letter);

            if let Some(ld) = logical_map.get(&logical_id) {
                partition_to_logical.insert(
                    part_id,
                    (
                        ld.file_system.clone().unwrap_or_default(),
                        ld.volume_name.clone().unwrap_or_default(),
                    ),
                );
            }
        }
    }

    // Step 3: Query all partitions
    let partitions: Vec<Win32DiskPartition> = wmi
        .raw_query("SELECT DeviceID, DiskIndex, Index, Size, Type, BootPartition, StartingOffset FROM Win32_DiskPartition")
        .map_err(|e| format!("DiskPartition query failed: {e}"))?;

    // Find system disk indices (same logic as Python)
    let system_drive = std::env::var("SystemDrive")
        .unwrap_or_else(|_| "C:".to_string());
    let system_drive_letter = system_drive.trim_end_matches(':').to_string();

    let mut system_disk_indices: std::collections::HashSet<u32> = std::collections::HashSet::new();
    for part in &partitions {
        if part.boot_partition.unwrap_or(false) {
            system_disk_indices.insert(part.disk_index);
        }
        if let Some(ref did) = part.device_i_d {
            if let Some(letters) = partition_to_letters.get(did) {
                if letters.contains(&system_drive_letter) {
                    system_disk_indices.insert(part.disk_index);
                }
            }
        }
    }

    // Step 4: Query all disk drives
    let drives: Vec<Win32DiskDrive> = wmi
        .raw_query("SELECT Index, Model, Size, MediaType FROM Win32_DiskDrive")
        .map_err(|e| format!("DiskDrive query failed: {e}"))?;

    // Step 5: Build DiskInfo list
    let mut disks: Vec<DiskInfo> = Vec::new();

    for dd in &drives {
        let disk_index = dd.index;

        // Determine partition style from partition types
        let mut partition_style = "RAW".to_string();
        for part in &partitions {
            if part.disk_index != disk_index {
                continue;
            }
            let ptype = part.r#type.as_deref().unwrap_or("").to_uppercase();
            if ptype.contains("GPT") {
                partition_style = "GPT".to_string();
                break;
            } else if ptype.contains("MBR")
                || ptype.contains("INSTALLABLE")
                || ptype.contains("PRIMARY")
            {
                partition_style = "MBR".to_string();
            }
        }

        let media_type = dd.media_type.clone().unwrap_or_default();
        let disk = DiskInfo {
            index: disk_index,
            model: dd
                .model
                .as_deref()
                .unwrap_or("Unknown")
                .trim()
                .to_string(),
            size_bytes: dd.size.unwrap_or(0),
            media_type: media_type.trim().to_string(),
            partition_style,
            is_removable: media_type.to_lowercase().contains("removable"),
            is_system_disk: system_disk_indices.contains(&disk_index),
            partitions: Vec::new(),
        };

        disks.push(disk);
    }

    // Step 6: Attach partitions to their disks
    for part in &partitions {
        let Some(disk) = disks.iter_mut().find(|d| d.index == part.disk_index) else {
            continue;
        };

        let device_id = part.device_i_d.clone().unwrap_or_default();
        let (filesystem, label) = partition_to_logical
            .get(&device_id)
            .cloned()
            .unwrap_or_default();
        let letters = partition_to_letters
            .get(&device_id)
            .cloned()
            .unwrap_or_default();

        // Determine partition type label (same logic as Python)
        let ptype_raw = part.r#type.as_deref().unwrap_or("").to_uppercase();
        let ptype_label = if ptype_raw.contains("EFI") || ptype_raw.contains("SYSTEM") {
            "EFI System"
        } else if ptype_raw.contains("RECOVERY") {
            "Recovery"
        } else if ptype_raw.contains("MSR") || ptype_raw.contains("RESERVED") {
            "MSR"
        } else {
            "Basic"
        };

        let drive_letter = letters.first().cloned().unwrap_or_default();
        let is_system = ptype_label == "EFI System" || letters.contains(&system_drive_letter);
        let is_boot = part.boot_partition.unwrap_or(false);

        let pinfo = PartitionInfo {
            index: part.index,
            size_bytes: part.size.unwrap_or(0),
            filesystem,
            label,
            drive_letter,
            partition_type: ptype_label.to_string(),
            is_system,
            is_boot,
            offset_bytes: part.starting_offset.unwrap_or(0),
        };

        disk.partitions.push(pinfo);
    }

    // Sort partitions by offset, disks by index (same as Python)
    for disk in &mut disks {
        disk.partitions.sort_by_key(|p| p.offset_bytes);
    }
    disks.sort_by_key(|d| d.index);

    Ok(disks)
}
