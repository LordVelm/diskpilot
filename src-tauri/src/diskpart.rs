//! Diskpart subprocess infrastructure — mirrors Python _run_diskpart_script() and all mutations.
//!
//! Key rules:
//! - Diskpart uses **1-based** partition numbers (WMI Index is 0-based)
//! - All scripts go through _run_diskpart_script() with temp file + 60s timeout
//! - Success = returncode 0 AND "error" not in combined output (case-insensitive)

use crate::safety;
use crate::DiskOpResult;
use std::process::Command;
use std::time::{Duration, Instant};

const DISKPART_TIMEOUT: Duration = Duration::from_secs(60);

/// Known diskpart failure phrases beyond just "error".
const FAILURE_PHRASES: &[&str] = &[
    "error",
    "access is denied",
    "the media is write protected",
    "the device is not ready",
    "the system cannot find",
    "virtual disk service error",
    "incorrect function",
    "the specified disk is not convertible",
];

/// Write a diskpart script to a temp file, execute it with a 60s timeout, return result.
fn run_diskpart_script(commands: &[&str]) -> DiskOpResult {
    let script_content = commands.join("\n") + "\n";

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

    // Spawn diskpart with timeout
    let mut child = match Command::new("diskpart")
        .arg("/s")
        .arg(&tmp_path)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            let _ = std::fs::remove_file(&tmp_path);
            return DiskOpResult {
                success: false,
                message: format!("Failed to start diskpart: {e}"),
            };
        }
    };

    let start = Instant::now();
    let result = loop {
        match child.try_wait() {
            Ok(Some(status)) => break Ok((status, child)),
            Ok(None) => {
                if start.elapsed() > DISKPART_TIMEOUT {
                    let _ = child.kill();
                    break Err("Diskpart timed out after 60 seconds.".to_string());
                }
                std::thread::sleep(Duration::from_millis(200));
            }
            Err(e) => break Err(format!("Failed to wait for diskpart: {e}")),
        }
    };

    // Clean up temp file
    let _ = std::fs::remove_file(&tmp_path);

    match result {
        Ok((status, mut child)) => {
            let stdout = {
                use std::io::Read;
                let mut s = String::new();
                if let Some(mut out) = child.stdout.take() { let _ = out.read_to_string(&mut s); }
                s
            };
            let stderr = {
                use std::io::Read;
                let mut s = String::new();
                if let Some(mut err) = child.stderr.take() { let _ = err.read_to_string(&mut s); }
                s
            };
            let combined = format!("{stdout}{stderr}");
            let lower = combined.to_lowercase();
            let has_failure = FAILURE_PHRASES.iter().any(|phrase| lower.contains(phrase));
            let success = status.success() && !has_failure;
            DiskOpResult {
                success,
                message: combined,
            }
        }
        Err(msg) => DiskOpResult {
            success: false,
            message: msg,
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
