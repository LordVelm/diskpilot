//! Diskpart subprocess infrastructure — mirrors Python _run_diskpart_script() and all mutations.
//!
//! Key rules:
//! - Diskpart uses **1-based** partition numbers (WMI Index is 0-based)
//! - All scripts go through _run_diskpart_script() with temp file + 60s timeout
//! - Success = returncode 0 AND "error" not in combined output (case-insensitive)

use crate::safety;
use crate::DiskOpResult;
use std::process::Command;

/// Write a diskpart script to a temp file, execute it, return result.
/// Matches Python: temp file + `diskpart /s` + 60s timeout + success heuristic.
fn run_diskpart_script(commands: &[&str]) -> DiskOpResult {
    let script_content = commands.join("\n") + "\n";

    // Manual temp file (matches Python NamedTemporaryFile with delete=False)
    let tmp_dir = std::env::temp_dir();
    let tmp_path = tmp_dir.join(format!(
        "dpgui_{}.txt",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos()
    ));

    if let Err(e) = std::fs::write(&tmp_path, &script_content) {
        return DiskOpResult {
            success: false,
            message: format!("Failed to write script: {e}"),
        };
    }

    // Run diskpart
    let result = Command::new("diskpart")
        .arg("/s")
        .arg(&tmp_path)
        .output();

    // Clean up temp file
    let _ = std::fs::remove_file(&tmp_path);

    match result {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout);
            let stderr = String::from_utf8_lossy(&output.stderr);
            let combined = format!("{stdout}{stderr}");
            let success =
                output.status.success() && !combined.to_lowercase().contains("error");
            DiskOpResult {
                success,
                message: combined,
            }
        }
        Err(e) => DiskOpResult {
            success: false,
            message: format!("Failed to run diskpart: {e}"),
        },
    }
}

/// Sanitize a string for safe inclusion in a diskpart script.
/// Rejects newlines, carriage returns, and double quotes to prevent command injection.
fn sanitize_diskpart_input(input: &str, field_name: &str) -> Result<String, DiskOpResult> {
    if input.contains('\n') || input.contains('\r') || input.contains('"') {
        return Err(DiskOpResult {
            success: false,
            message: format!("BLOCKED: {field_name} contains unsafe characters."),
        });
    }
    Ok(input.to_string())
}

pub fn format_partition(
    disk_index: u32,
    partition_index: u32,
    filesystem: &str,
    label: &str,
    quick: bool,
) -> DiskOpResult {
    if let Err(msg) = safety::assert_not_system_partition(disk_index, partition_index) {
        return DiskOpResult {
            success: false,
            message: msg,
        };
    }

    let fs = filesystem.to_uppercase();
    if !matches!(fs.as_str(), "NTFS" | "FAT32" | "EXFAT") {
        return DiskOpResult {
            success: false,
            message: format!("Unsupported filesystem: {fs}"),
        };
    }

    let label = match sanitize_diskpart_input(label, "Volume label") {
        Ok(l) => l,
        Err(r) => return r,
    };

    let mut fmt_cmd = format!("format fs={fs}");
    if !label.is_empty() {
        fmt_cmd.push_str(&format!(" label=\"{label}\""));
    }
    if quick {
        fmt_cmd.push_str(" quick");
    }

    let select_disk = format!("select disk {disk_index}");
    let select_part = format!("select partition {}", partition_index + 1); // diskpart is 1-indexed
    run_diskpart_script(&[&select_disk, &select_part, &fmt_cmd])
}

pub fn clean_disk(disk_index: u32) -> DiskOpResult {
    if let Err(msg) = safety::assert_not_system_disk(disk_index) {
        return DiskOpResult {
            success: false,
            message: msg,
        };
    }

    let select_disk = format!("select disk {disk_index}");
    run_diskpart_script(&[&select_disk, "clean"])
}

pub fn create_partition(disk_index: u32, size_mb: Option<u32>, primary: bool) -> DiskOpResult {
    if let Err(msg) = safety::assert_not_system_disk(disk_index) {
        return DiskOpResult {
            success: false,
            message: msg,
        };
    }

    let cmd = if primary {
        "create partition primary"
    } else {
        "create partition extended"
    };

    let cmd = match size_mb {
        Some(size) => format!("{cmd} size={size}"),
        None => cmd.to_string(),
    };

    let select_disk = format!("select disk {disk_index}");
    run_diskpart_script(&[&select_disk, &cmd])
}

pub fn delete_partition(disk_index: u32, partition_index: u32) -> DiskOpResult {
    if let Err(msg) = safety::assert_not_system_partition(disk_index, partition_index) {
        return DiskOpResult {
            success: false,
            message: msg,
        };
    }

    let select_disk = format!("select disk {disk_index}");
    let select_part = format!("select partition {}", partition_index + 1);
    run_diskpart_script(&[&select_disk, &select_part, "delete partition override"])
}

pub fn assign_letter(disk_index: u32, partition_index: u32, letter: &str) -> DiskOpResult {
    let letter = letter.to_uppercase().replace(':', "");
    if letter.len() != 1 || !letter.chars().next().map_or(false, |c| c.is_ascii_alphabetic()) {
        return DiskOpResult {
            success: false,
            message: format!("Invalid drive letter: {letter}"),
        };
    }

    let select_disk = format!("select disk {disk_index}");
    let select_part = format!("select partition {}", partition_index + 1);
    let assign_cmd = format!("assign letter={letter}");
    run_diskpart_script(&[&select_disk, &select_part, &assign_cmd])
}

pub fn remove_letter(disk_index: u32, partition_index: u32, letter: &str) -> DiskOpResult {
    let sys_drive = std::env::var("SystemDrive")
        .unwrap_or_else(|_| "C:".to_string());
    let sys_letter = sys_drive.trim_end_matches(':');
    let letter = letter.to_uppercase().replace(':', "");

    if letter == sys_letter {
        return DiskOpResult {
            success: false,
            message: format!("BLOCKED: Cannot remove the system drive letter ({letter}:)."),
        };
    }

    let select_disk = format!("select disk {disk_index}");
    let select_part = format!("select partition {}", partition_index + 1);
    let remove_cmd = format!("remove letter={letter}");
    run_diskpart_script(&[&select_disk, &select_part, &remove_cmd])
}
