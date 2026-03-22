//! Safety gates — mirrors Python _assert_not_system_disk / _assert_not_system_partition.
//!
//! Defense-in-depth: backend REFUSES dangerous operations even if UI buttons are enabled.

use crate::wmi_disk::{enumerate_disks, DiskInfo};
use std::sync::OnceLock;

static SYSTEM_DISK_INDEX: OnceLock<Option<u32>> = OnceLock::new();

fn system_drive_letter() -> String {
    std::env::var("SystemDrive")
        .unwrap_or_else(|_| "C:".to_string())
        .trim_end_matches(':')
        .to_string()
}

/// Determine system disk index (cached after first call).
pub fn get_system_disk_index() -> Option<u32> {
    *SYSTEM_DISK_INDEX.get_or_init(|| {
        let disks = enumerate_disks().ok()?;
        for d in &disks {
            if is_system_disk(d) {
                return Some(d.index);
            }
        }
        None
    })
}

/// Defense-in-depth: is this disk the system disk?
pub fn is_system_disk(disk: &DiskInfo) -> bool {
    if disk.is_system_disk {
        return true;
    }
    let sys_letter = system_drive_letter();
    for p in &disk.partitions {
        if p.is_system || p.is_boot {
            return true;
        }
        if !p.drive_letter.is_empty() && p.drive_letter == sys_letter {
            return true;
        }
    }
    false
}

/// Check if a partition is protected. Only enforced on the system disk.
pub fn is_protected_partition(
    partition_type: &str,
    is_system: bool,
    is_boot: bool,
    drive_letter: &str,
    on_system_disk: bool,
) -> bool {
    if !on_system_disk {
        return false;
    }
    let sys_letter = system_drive_letter();
    is_system
        || is_boot
        || matches!(partition_type, "EFI System" | "Recovery" | "MSR")
        || drive_letter == sys_letter
}

/// Returns Err(message) if disk_index is the system disk.
pub fn assert_not_system_disk(disk_index: u32) -> Result<(), String> {
    if let Some(sys_idx) = get_system_disk_index() {
        if disk_index == sys_idx {
            return Err(
                "BLOCKED: Operation refused — this is the system disk (contains Windows)."
                    .to_string(),
            );
        }
    }
    Ok(())
}

/// Returns Err(message) if the target partition is protected on the system disk.
pub fn assert_not_system_partition(disk_index: u32, partition_index: u32) -> Result<(), String> {
    let Some(sys_idx) = get_system_disk_index() else {
        return Ok(());
    };
    if disk_index != sys_idx {
        return Ok(());
    }

    let disks = enumerate_disks().map_err(|_| {
        "BLOCKED: Could not verify partition safety — operation refused.".to_string()
    })?;

    for d in &disks {
        if d.index != disk_index {
            continue;
        }
        for p in &d.partitions {
            if p.index == partition_index
                && is_protected_partition(
                    &p.partition_type,
                    p.is_system,
                    p.is_boot,
                    &p.drive_letter,
                    true,
                )
            {
                let id = if p.drive_letter.is_empty() {
                    p.partition_type.clone()
                } else {
                    format!("{}:", p.drive_letter)
                };
                return Err(format!(
                    "BLOCKED: Operation refused — partition {partition_index} ({id}) is protected on the system disk."
                ));
            }
        }
    }
    Ok(())
}
