"""Core disk operations: WMI queries for reading, diskpart subprocess for mutations."""

import ctypes
import os
import subprocess
import tempfile
from dataclasses import dataclass, field

import wmi


@dataclass
class PartitionInfo:
    index: int
    size_bytes: int
    filesystem: str  # NTFS, FAT32, exFAT, RAW, ""
    label: str
    drive_letter: str  # "C", "D", etc. or ""
    partition_type: str  # "Basic", "EFI", "Recovery", "MSR", etc.
    is_system: bool  # boot/system/active partition
    is_boot: bool
    offset_bytes: int  # byte offset on disk for proportional bar positioning


@dataclass
class DiskInfo:
    index: int
    model: str
    size_bytes: int
    media_type: str  # "Fixed hard disk media", "Removable media", etc.
    partition_style: str  # "GPT", "MBR", or "RAW"
    is_removable: bool
    is_system_disk: bool  # contains Windows boot partition
    partitions: list[PartitionInfo] = field(default_factory=list)


def is_admin() -> bool:
    """Check if the current process has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def elevate_self():
    """Re-launch this script with admin privileges via UAC prompt."""
    import sys
    if is_admin():
        return
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    sys.exit(0)


def _bytes_to_display(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    if size_bytes < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def get_all_disks() -> list[DiskInfo]:
    """Query WMI for all physical disks, their partitions, and drive letters."""
    c = wmi.WMI()

    # Build a map: partition DeviceID -> list of drive letters
    partition_to_letters: dict[str, list[str]] = {}
    for logical in c.Win32_LogicalDisk():
        for assoc in logical.associators(
            wmi_result_class="Win32_DiskPartition"
        ):
            partition_to_letters.setdefault(assoc.DeviceID, []).append(
                logical.DeviceID.rstrip(":")  # "C:" -> "C"
            )

    # Build a map: partition DeviceID -> logical disk info (filesystem, label)
    partition_to_logical: dict[str, dict] = {}
    for logical in c.Win32_LogicalDisk():
        for assoc in logical.associators(
            wmi_result_class="Win32_DiskPartition"
        ):
            partition_to_logical[assoc.DeviceID] = {
                "filesystem": logical.FileSystem or "",
                "label": logical.VolumeName or "",
            }

    # Find which disk index contains the system/boot partition
    system_drive = os.environ.get("SystemDrive", "C:")[:1]  # "C"
    system_disk_indices: set[int] = set()
    for part in c.Win32_DiskPartition():
        if part.BootPartition:
            system_disk_indices.add(part.DiskIndex)
        # Also check if this partition holds the system drive letter
        letters = partition_to_letters.get(part.DeviceID, [])
        if system_drive in letters:
            system_disk_indices.add(part.DiskIndex)

    disks: list[DiskInfo] = []
    for dd in c.Win32_DiskDrive():
        disk_index = dd.Index

        # Determine partition style
        partition_style = "RAW"
        try:
            for dp in c.query(
                f"SELECT * FROM Win32_DiskPartition WHERE DiskIndex={disk_index}"
            ):
                ptype = (dp.Type or "").upper()
                if "GPT" in ptype:
                    partition_style = "GPT"
                    break
                elif "MBR" in ptype or "INSTALLABLE" in ptype or "PRIMARY" in ptype:
                    partition_style = "MBR"
        except Exception:
            pass

        disk = DiskInfo(
            index=disk_index,
            model=(dd.Model or "Unknown").strip(),
            size_bytes=int(dd.Size or 0),
            media_type=(dd.MediaType or "").strip(),
            partition_style=partition_style,
            is_removable="removable" in (dd.MediaType or "").lower(),
            is_system_disk=disk_index in system_disk_indices,
        )

        # Enumerate partitions
        for part in c.query(
            f"SELECT * FROM Win32_DiskPartition WHERE DiskIndex={disk_index}"
        ):
            part_id = part.DeviceID
            logical_info = partition_to_logical.get(part_id, {})
            letters = partition_to_letters.get(part_id, [])

            # Determine partition type label
            ptype_raw = (part.Type or "").upper()
            if "EFI" in ptype_raw or "SYSTEM" in ptype_raw:
                ptype_label = "EFI System"
            elif "RECOVERY" in ptype_raw:
                ptype_label = "Recovery"
            elif "MSR" in ptype_raw or "RESERVED" in ptype_raw:
                ptype_label = "MSR"
            else:
                ptype_label = "Basic"

            # Detect system partition: hosts the system drive or is EFI
            part_is_system = (
                ptype_label == "EFI System"
                or system_drive in letters
            )

            pinfo = PartitionInfo(
                index=part.Index,
                size_bytes=int(part.Size or 0),
                filesystem=logical_info.get("filesystem", ""),
                label=logical_info.get("label", ""),
                drive_letter=letters[0] if letters else "",
                partition_type=ptype_label,
                is_system=part_is_system,
                is_boot=bool(part.BootPartition),
                offset_bytes=int(part.StartingOffset or 0),
            )
            disk.partitions.append(pinfo)

        # Sort partitions by offset
        disk.partitions.sort(key=lambda p: p.offset_bytes)
        disks.append(disk)

    # Sort disks by index
    disks.sort(key=lambda d: d.index)
    return disks


def is_system_disk(disk: DiskInfo) -> bool:
    """Defense-in-depth check: is this disk the system disk?"""
    if disk.is_system_disk:
        return True
    for p in disk.partitions:
        if p.is_system or p.is_boot:
            return True
        if p.drive_letter and os.environ.get("SystemDrive", "C:").startswith(p.drive_letter):
            return True
    return False


def _is_protected_partition(part: PartitionInfo, on_system_disk: bool = False) -> bool:
    """Check if a partition is protected. Only enforced on the system disk."""
    if not on_system_disk:
        return False
    system_drive = os.environ.get("SystemDrive", "C:")[:1]  # "C"
    return (
        part.is_system
        or part.is_boot
        or part.partition_type in ("EFI System", "Recovery", "MSR")
        or part.drive_letter == system_drive
    )


# ── Safety gate ──

def _get_system_disk_index() -> int | None:
    """Query WMI to find the system disk index. Cached after first call."""
    if not hasattr(_get_system_disk_index, "_cached"):
        try:
            disks = get_all_disks()
            for d in disks:
                if is_system_disk(d):
                    _get_system_disk_index._cached = d.index
                    break
            else:
                _get_system_disk_index._cached = None
        except Exception:
            _get_system_disk_index._cached = None
    return _get_system_disk_index._cached


def _assert_not_system_disk(disk_index: int) -> tuple[bool, str] | None:
    """Return an error tuple if disk_index is the system disk, else None."""
    sys_idx = _get_system_disk_index()
    if sys_idx is not None and disk_index == sys_idx:
        return False, "BLOCKED: Operation refused — this is the system disk (contains Windows)."
    return None


def _assert_not_system_partition(disk_index: int, partition_index: int) -> tuple[bool, str] | None:
    """Return an error tuple if the target partition is on the system disk and is protected."""
    sys_idx = _get_system_disk_index()
    if sys_idx is not None and disk_index == sys_idx:
        try:
            disks = get_all_disks()
            for d in disks:
                if d.index == disk_index:
                    for p in d.partitions:
                        if p.index == partition_index and _is_protected_partition(p, on_system_disk=True):
                            return False, (
                                f"BLOCKED: Operation refused — partition {partition_index} "
                                f"({p.drive_letter + ':' if p.drive_letter else p.partition_type}) "
                                f"is protected on the system disk."
                            )
        except Exception:
            return False, "BLOCKED: Could not verify partition safety — operation refused."
    return None


# ── Diskpart subprocess infrastructure ──

def _run_diskpart_script(commands: list[str]) -> tuple[bool, str]:
    """Write a diskpart script to a temp file, execute it, return (success, output)."""
    script_content = "\n".join(commands) + "\n"
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="dpgui_"
        )
        tmp.write(script_content)
        tmp.close()

        result = subprocess.run(
            ["diskpart", "/s", tmp.name],
            capture_output=True, text=True, timeout=60
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0 and "error" not in output.lower()
        return success, output
    except subprocess.TimeoutExpired:
        return False, "diskpart timed out after 60 seconds."
    except Exception as e:
        return False, str(e)
    finally:
        if tmp and os.path.exists(tmp.name):
            os.unlink(tmp.name)


def format_partition(
    disk_index: int, partition_index: int,
    filesystem: str = "NTFS", label: str = "", quick: bool = True
) -> tuple[bool, str]:
    """Format a partition. Returns (success, output)."""
    blocked = _assert_not_system_partition(disk_index, partition_index)
    if blocked:
        return blocked

    fs = filesystem.upper()
    if fs not in ("NTFS", "FAT32", "EXFAT"):
        return False, f"Unsupported filesystem: {fs}"

    fmt_cmd = f"format fs={fs}"
    if label:
        fmt_cmd += f' label="{label}"'
    if quick:
        fmt_cmd += " quick"

    commands = [
        f"select disk {disk_index}",
        f"select partition {partition_index + 1}",  # diskpart is 1-indexed
        fmt_cmd,
    ]
    return _run_diskpart_script(commands)


def clean_disk(disk_index: int) -> tuple[bool, str]:
    """Clean (wipe partition table) a disk. Returns (success, output)."""
    blocked = _assert_not_system_disk(disk_index)
    if blocked:
        return blocked

    commands = [
        f"select disk {disk_index}",
        "clean",
    ]
    return _run_diskpart_script(commands)


def create_partition(
    disk_index: int, size_mb: int | None = None, primary: bool = True
) -> tuple[bool, str]:
    """Create a new partition. size_mb=None uses all available space."""
    cmd = "create partition primary" if primary else "create partition extended"
    if size_mb is not None:
        cmd += f" size={size_mb}"

    commands = [
        f"select disk {disk_index}",
        cmd,
    ]
    return _run_diskpart_script(commands)


def delete_partition(disk_index: int, partition_index: int) -> tuple[bool, str]:
    """Delete a partition. Returns (success, output)."""
    blocked = _assert_not_system_partition(disk_index, partition_index)
    if blocked:
        return blocked

    commands = [
        f"select disk {disk_index}",
        f"select partition {partition_index + 1}",
        "delete partition override",
    ]
    return _run_diskpart_script(commands)


def assign_letter(
    disk_index: int, partition_index: int, letter: str
) -> tuple[bool, str]:
    """Assign or change a drive letter. Returns (success, output)."""
    letter = letter.upper().strip(":")
    if len(letter) != 1 or not letter.isalpha():
        return False, f"Invalid drive letter: {letter}"

    commands = [
        f"select disk {disk_index}",
        f"select partition {partition_index + 1}",
        f"assign letter={letter}",
    ]
    return _run_diskpart_script(commands)


def remove_letter(disk_index: int, partition_index: int, letter: str) -> tuple[bool, str]:
    """Remove a drive letter from a partition."""
    system_drive = os.environ.get("SystemDrive", "C:")[:1]
    letter = letter.upper().strip(":")
    if letter == system_drive:
        return False, f"BLOCKED: Cannot remove the system drive letter ({letter}:)."

    commands = [
        f"select disk {disk_index}",
        f"select partition {partition_index + 1}",
        f"remove letter={letter}",
    ]
    return _run_diskpart_script(commands)
