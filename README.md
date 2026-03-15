# DiskPart GUI

A free, lightweight, open-source GUI wrapper for Windows `diskpart`. Manage disks and partitions without bloated tools like MiniTool or EaseUS.

## Features

- **Visual partition bar** — Proportionally-sized, color-coded segments for each partition (click to select)
- **Full disk overview** — Model name, size, GPT/MBR, removable/system badges
- **Partition details** — Drive letter, label, filesystem, size, type, and status
- **Destructive operations** — Format, delete partition, create partition, clean disk, change drive letter
- **Safety-first design** — System disk protection, type-to-confirm dialogs, EFI/Recovery/MSR partitions blocked
- **Admin auto-elevation** — Prompts for UAC on launch

### Color Coding

| Color | Meaning |
|-------|---------|
| Blue | NTFS (system/boot) |
| Green | NTFS (data) |
| Purple | FAT32 / exFAT |
| Dark gray | Unallocated |
| Yellow | EFI / Recovery / MSR (protected) |

## Requirements

- Windows 10/11
- Python 3.12+
- Administrator privileges (required for disk operations)

## Setup

```powershell
cd diskpart-gui
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1

pip install customtkinter wmi pywin32
```

## Usage

### GUI

```powershell
python gui.py
```

Or download the standalone `.exe` from [Releases](https://github.com/LordVelm/diskpart-gui/releases).

The app will prompt for administrator privileges on launch.

## Safety Design

1. **System disk protection** — Cannot clean/format system or boot partitions; buttons are grayed out AND the backend refuses the operation
2. **Type-to-confirm** — Destructive operations (clean, format, delete) require typing the exact confirmation text (e.g., `CLEAN DISK 1`)
3. **Visual identification** — Disk model and size shown prominently so you pick the right disk
4. **Protected partitions** — EFI, Recovery, and MSR partitions are visible but cannot be modified

## Building a Standalone Executable

```powershell
pip install pyinstaller
python build.py          # outputs to dist/DiskPartGUI.exe
```

The exe includes a UAC admin manifest — Windows will show the shield icon and prompt for elevation.

## How It Works

- **Reading** — Uses WMI (`Win32_DiskDrive`, `Win32_DiskPartition`, `Win32_LogicalDisk`) for structured, locale-independent disk enumeration
- **Writing** — Uses `diskpart /s` subprocess with temp script files for all destructive operations (format, clean, create, delete, assign letter)

## Feedback & Support

- **Bug reports & feature requests** — [Open an issue](https://github.com/LordVelm/diskpart-gui/issues)
- **Support the project** — [Buy Me a Coffee](https://buymeacoffee.com/lordvelm)
