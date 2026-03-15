# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DiskPart GUI — a Python GUI wrapper for Windows `diskpart` that provides visual disk and partition management. Uses WMI for reading disk info and diskpart subprocess for mutations. Designed as a free, lightweight alternative to MiniTool/EaseUS.

## Commands

```bash
# Setup & run
python -m venv venv
source venv/bin/activate        # or .\venv\Scripts\Activate.ps1 on Windows
pip install customtkinter wmi pywin32

# Run (requires admin — will auto-elevate via UAC)
python gui.py

# Build standalone exe
pip install pyinstaller
python build.py                 # outputs to dist/DiskPartGUI.exe (includes UAC admin manifest)
```

No test suite exists. Manual testing on USB flash drives for destructive operations.

## Architecture

### disk_ops.py — Core logic

- **Data classes** — `DiskInfo` and `PartitionInfo` hold all disk/partition metadata
- **`get_all_disks()`** — WMI query chain: `Win32_DiskDrive` → `Win32_DiskPartition` → `Win32_LogicalDisk` (via associators). Returns structured data, locale-independent, no text parsing.
- **`_run_diskpart_script()`** — Writes commands to a temp file, runs `diskpart /s`, returns (success, output). All destructive operations go through this.
- **Mutation functions** — `format_partition()`, `clean_disk()`, `create_partition()`, `delete_partition()`, `assign_letter()`, `remove_letter()`. All return `tuple[bool, str]` (success, output).
- **Safety checks** — 3-layer defense:
  1. `_is_protected_partition(part, on_system_disk)` — only protects EFI/Recovery/MSR/boot/C: partitions when `on_system_disk=True`. Non-system disks are fully unlocked.
  2. `_assert_not_system_disk()` / `_assert_not_system_partition()` — backend guards that independently query WMI and refuse operations on system disk.
  3. `_get_system_disk_index()` — cached WMI lookup for the system disk index, used by backend guards.

### gui.py — CustomTkinter frontend

- **Theme system** — `THEMES` dict holds full dark and light palettes. Active palette stored in global `T` dict. `_toggle_theme()` swaps `T`, calls `set_appearance_mode()`, then `_apply_theme()` which updates all widget colors and rebuilds dynamic content.
- **`DiskPartApp(ctk.CTk)`** — Main window. Left panel = disk list, center = partition bar + details table + action buttons + status bar. Theme toggle button in sidebar header.
- **`DiskBarWidget(ctk.CTkFrame)`** — Visual proportional partition bar with colored segments. Click-to-select syncs with the details table.
- **`ConfirmDialog(ctk.CTkToplevel)`** — Two modes: type-to-confirm (destructive ops) and simple yes/no (less risky ops).
- **Admin elevation** — `elevate_self()` re-launches with `ShellExecuteW("runas")` if not already admin.
- **Threading** — Destructive operations run in background threads to keep UI responsive, with `self.after()` for thread-safe UI updates.

### build.py — PyInstaller wrapper

- Builds one-file windowed exe with `--uac-admin` flag (embeds admin manifest for UAC shield icon).

## Key Design Decisions

- **WMI for reads, diskpart for writes** — WMI returns structured objects (no locale-dependent text parsing). diskpart is the canonical tool for disk mutations on Windows.
- **Protection scoped to system disk only** — EFI/Recovery/MSR/C: partitions are protected on the OS disk. Non-system disks (USB, secondary) have zero restrictions so users can freely manage them.
- **Layered safety** — UI disables buttons AND backend functions independently refuse unsafe operations (defense in depth).
- **Type-to-confirm** — Clean/format/delete require typing exact confirmation text. Prevents accidental clicks.
- **System disk detection** — Checks WMI boot partition flag + whether partition holds the SystemDrive letter + cached system disk index lookup.
- **Diskpart uses 1-indexed partitions** — `partition_index + 1` in all diskpart commands (WMI is 0-indexed).
- **No locale parsing** — Deliberately avoids parsing diskpart text output for reads; WMI handles all enumeration.
- **Theme toggle** — Uses a mutable global `T` dict pattern. On toggle: swap dict contents → set CTk appearance mode → re-configure all stored widget refs → rebuild dynamic content (cards, bar, table, buttons).

## Remaining Work (Phase 5)

- App icon (`icon.ico`) — needs creation + wiring into build.py
- GitHub repo creation + first release
- Edge case error handling polish

## Dependencies

- `customtkinter` — Modern themed Tkinter widgets
- `wmi` — Python WMI interface for disk enumeration
- `pywin32` — COM support required by the `wmi` package
