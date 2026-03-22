mod wmi_disk;
mod diskpart;
mod safety;

use serde::{Deserialize, Serialize};
use wmi_disk::DiskInfo;

// Re-export types for commands
pub use wmi_disk::{enumerate_disks};

/// Result from any diskpart mutation.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DiskOpResult {
    pub success: bool,
    pub message: String,
}

// ── Tauri commands ──

#[tauri::command]
async fn get_disks() -> Result<Vec<DiskInfo>, String> {
    tokio::task::spawn_blocking(|| enumerate_disks())
        .await
        .map_err(|e| format!("Task join error: {e}"))?
}

#[tauri::command]
async fn format_partition(
    disk_index: u32,
    partition_index: u32,
    filesystem: String,
    label: String,
    quick: bool,
) -> Result<DiskOpResult, String> {
    tokio::task::spawn_blocking(move || {
        diskpart::format_partition(disk_index, partition_index, &filesystem, &label, quick)
    })
    .await
    .map_err(|e| format!("Task join error: {e}"))
}

#[tauri::command]
async fn clean_disk(disk_index: u32) -> Result<DiskOpResult, String> {
    tokio::task::spawn_blocking(move || diskpart::clean_disk(disk_index))
        .await
        .map_err(|e| format!("Task join error: {e}"))
}

#[tauri::command]
async fn create_partition(
    disk_index: u32,
    size_mb: Option<u32>,
    primary: bool,
) -> Result<DiskOpResult, String> {
    tokio::task::spawn_blocking(move || diskpart::create_partition(disk_index, size_mb, primary))
        .await
        .map_err(|e| format!("Task join error: {e}"))
}

#[tauri::command]
async fn delete_partition(
    disk_index: u32,
    partition_index: u32,
) -> Result<DiskOpResult, String> {
    tokio::task::spawn_blocking(move || diskpart::delete_partition(disk_index, partition_index))
        .await
        .map_err(|e| format!("Task join error: {e}"))
}

#[tauri::command]
async fn assign_letter(
    disk_index: u32,
    partition_index: u32,
    letter: String,
) -> Result<DiskOpResult, String> {
    tokio::task::spawn_blocking(move || {
        diskpart::assign_letter(disk_index, partition_index, &letter)
    })
    .await
    .map_err(|e| format!("Task join error: {e}"))
}

#[tauri::command]
async fn remove_letter(
    disk_index: u32,
    partition_index: u32,
    letter: String,
) -> Result<DiskOpResult, String> {
    tokio::task::spawn_blocking(move || {
        diskpart::remove_letter(disk_index, partition_index, &letter)
    })
    .await
    .map_err(|e| format!("Task join error: {e}"))
}

pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_disks,
            format_partition,
            clean_disk,
            create_partition,
            delete_partition,
            assign_letter,
            remove_letter,
        ])
        .run(tauri::generate_context!())
        .expect("error while running DiskPilot");
}
