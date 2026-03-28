//! Safety gates — mirrors Python _assert_not_system_disk / _assert_not_system_partition.
//!
//! Defense-in-depth: backend REFUSES dangerous operations even if UI buttons are enabled.

use crate::wmi_disk::{enumerate_disks, DiskInfo};

fn system_drive_letter() -> String {
    std::env::var("SystemDrive")
        .unwrap_or_else(|_| "C:".to_string())
        .trim_end_matches(':')
        .to_string()
}

/// Determine system disk index. Re-queries WMI every call so hot-swap
/// and late-boot scenarios stay safe. Returns Err if WMI fails (fail closed).
pub fn get_system_disk_index() -> Result<Option<u32>, String> {
    let disks = enumerate_disks()
        .map_err(|e| format!("BLOCKED: Could not enumerate disks for safety check: {e}"))?;
    for d in &disks {
        if is_system_disk(d) {
            return Ok(Some(d.index));
        }
    }
    Ok(None)
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
/// Fails closed: if we can't determine the system disk, the operation is refused.
pub fn assert_not_system_disk(disk_index: u32) -> Result<(), String> {
    match get_system_disk_index() {
        Ok(Some(sys_idx)) if disk_index == sys_idx => {
            Err("BLOCKED: Operation refused — this is the system disk (contains Windows).".to_string())
        }
        Ok(_) => Ok(()),
        Err(e) => Err(e),
    }
}

/// Returns Err(message) if the target partition is protected on the system disk.
/// Fails closed: if we can't determine the system disk, the operation is refused.
pub fn assert_not_system_partition(disk_index: u32, partition_index: u32) -> Result<(), String> {
    let sys_idx = match get_system_disk_index() {
        Ok(Some(idx)) => idx,
        Ok(None) => return Ok(()), // No system disk found in any enumerated disk — allow
        Err(e) => return Err(e),   // WMI failed — refuse
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
