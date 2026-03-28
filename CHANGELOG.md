# Changelog

All notable changes to DiskPilot will be documented in this file.

## [2.0.1] - 2026-03-28

### Fixed
- Shell injection vulnerability: volume labels are now sanitized before reaching diskpart
- Safety model fails closed: if the system disk can't be identified, all destructive operations are refused
- System disk index re-queried on every operation (was cached forever, broke on hot-swap)
- Create Partition now blocked on system disk (was the only unprotected mutation)
- Concurrent operation guard prevents two diskpart commands from running simultaneously

### Changed
- Diskpart execution has a 60-second timeout (was blocking indefinitely)
- Failure detection expanded beyond "error" to include "access denied", "write protected", etc.
- Drive letter assignment checks all disks, not just the currently selected one
- Format now offers filesystem choice (NTFS, FAT32, exFAT) and quick/full toggle
- Create Partition requires type-to-confirm dialog
- Status bar shows actual diskpart error details on failure
- Disk list no longer re-scans WMI on every selection change

## [2.0.0] - 2026-03-22

### Changed
- Complete rewrite from Python + CustomTkinter to Tauri v2 + React + TypeScript + Rust
- Single binary, no Python runtime needed
- WMI disk enumeration in Rust (was Python wmi package)
- Diskpart mutations in Rust (was Python subprocess)
- Safety gates ported to Rust with defense-in-depth
- Dark and light theme support
- Custom title bar with drag region

## [1.0.0] - 2026-03-15

### Added
- Initial release: Python + CustomTkinter GUI
- Visual partition bar with color-coded segments
- Full disk management: format, delete, create, clean, assign/remove letter
- System disk protection with type-to-confirm dialogs
- WMI-based disk enumeration
- Standalone .exe via PyInstaller with UAC elevation
