"""DiskPilot — CustomTkinter frontend for disk management."""

import os
import threading
import webbrowser
import customtkinter as ctk

from disk_ops import (
    DiskInfo, PartitionInfo, get_all_disks, is_admin, elevate_self,
    is_system_disk, _is_protected_partition, _bytes_to_display,
    format_partition, clean_disk, create_partition, delete_partition,
    assign_letter, remove_letter,
)

# ── Theme system ──

THEMES = {
    "dark": {
        # Partition bar
        "bar_ntfs_system": "#5B8DEF",
        "bar_ntfs_data": "#4ADE80",
        "bar_fat": "#C084FC",
        "bar_unallocated": "#2A2D35",
        "bar_protected": "#FACC15",
        "bar_selected_border": "#F97316",
        "bar_text": "white",
        "bar_text_protected": "#000000",
        "bar_text_free": "#555D73",
        # UI chrome
        "bg_main": "#0F1117",
        "bg_sidebar": "#161921",
        "bg_card": "#1C1F2B",
        "bg_card_hover": "#242838",
        "bg_surface": "#1A1D27",
        "bg_table_row": "#1E2130",
        "bg_table_alt": "transparent",
        "bg_table_sel": "#2A3A5C",
        "bg_status": "#12141B",
        "bg_input": "#0F1117",
        "separator": "#252835",
        # Text
        "text_primary": "#E2E8F0",
        "text_secondary": "#8892A8",
        "text_muted": "#555D73",
        # Accents
        "accent_blue": "#5B8DEF",
        "accent_red": "#EF4444",
        "accent_green": "#34D399",
        "accent_purple": "#A78BFA",
        "accent_cyan": "#22D3EE",
        "accent_gray": "#4B5563",
        # Accent hovers
        "hover_blue": "#4A7AD8",
        "hover_red": "#DC2626",
        "hover_green": "#22B07A",
        "hover_purple": "#8B5CF6",
        "hover_cyan": "#06B6D4",
        "hover_gray": "#6B7280",
        # Badges
        "badge_os_fg": "#EF4444", "badge_os_bg": "#2A1215",
        "badge_usb_fg": "#F59E0B", "badge_usb_bg": "#2A2010",
        "badge_style_fg": "#5B8DEF", "badge_style_bg": "#152240",
        # Buttons on green/cyan need dark text
        "btn_dark_text": "#000000",
        # CTk appearance
        "appearance": "dark",
    },
    "light": {
        # Partition bar
        "bar_ntfs_system": "#3B82F6",
        "bar_ntfs_data": "#16A34A",
        "bar_fat": "#9333EA",
        "bar_unallocated": "#D1D5DB",
        "bar_protected": "#EAB308",
        "bar_selected_border": "#EA580C",
        "bar_text": "white",
        "bar_text_protected": "#000000",
        "bar_text_free": "#6B7280",
        # UI chrome
        "bg_main": "#F3F4F6",
        "bg_sidebar": "#FFFFFF",
        "bg_card": "#F9FAFB",
        "bg_card_hover": "#EEF2FF",
        "bg_surface": "#FFFFFF",
        "bg_table_row": "#F9FAFB",
        "bg_table_alt": "transparent",
        "bg_table_sel": "#DBEAFE",
        "bg_status": "#E5E7EB",
        "bg_input": "#F9FAFB",
        "separator": "#E5E7EB",
        # Text
        "text_primary": "#111827",
        "text_secondary": "#4B5563",
        "text_muted": "#9CA3AF",
        # Accents
        "accent_blue": "#3B82F6",
        "accent_red": "#EF4444",
        "accent_green": "#10B981",
        "accent_purple": "#8B5CF6",
        "accent_cyan": "#06B6D4",
        "accent_gray": "#9CA3AF",
        # Accent hovers
        "hover_blue": "#2563EB",
        "hover_red": "#DC2626",
        "hover_green": "#059669",
        "hover_purple": "#7C3AED",
        "hover_cyan": "#0891B2",
        "hover_gray": "#6B7280",
        # Badges
        "badge_os_fg": "#FFFFFF", "badge_os_bg": "#EF4444",
        "badge_usb_fg": "#FFFFFF", "badge_usb_bg": "#F59E0B",
        "badge_style_fg": "#FFFFFF", "badge_style_bg": "#3B82F6",
        # Buttons on green/cyan need dark text
        "btn_dark_text": "#FFFFFF",
        # CTk appearance
        "appearance": "light",
    },
}

# Active theme — mutable reference
T = dict(THEMES["dark"])


def _partition_color(part: PartitionInfo, on_system_disk: bool = False) -> str:
    if _is_protected_partition(part, on_system_disk=on_system_disk):
        return T["bar_protected"]
    fs = part.filesystem.upper()
    if fs == "NTFS":
        if part.is_boot or part.is_system:
            return T["bar_ntfs_system"]
        return T["bar_ntfs_data"]
    if fs in ("FAT32", "EXFAT", "FAT"):
        return T["bar_fat"]
    return T["bar_unallocated"]


class DiskBarWidget(ctk.CTkFrame):
    """Visual proportional partition bar."""

    def __init__(self, master, disk: DiskInfo, on_partition_click=None, **kwargs):
        super().__init__(master, height=64, corner_radius=10, **kwargs)
        self.disk = disk
        self.on_partition_click = on_partition_click
        self.selected_index: int | None = None
        self.segment_frames: list[ctk.CTkFrame] = []
        self._build()

    def _build(self):
        for w in self.winfo_children():
            w.destroy()
        self.segment_frames.clear()
        self.pack_propagate(False)
        total = self.disk.size_bytes if self.disk.size_bytes > 0 else 1

        if not self.disk.partitions:
            seg = ctk.CTkFrame(self, fg_color=T["bar_unallocated"], corner_radius=6)
            seg.pack(side="left", fill="both", expand=True, padx=1, pady=3)
            ctk.CTkLabel(seg, text="Unallocated", font=("Segoe UI", 11),
                         text_color=T["bar_text_free"]).pack(expand=True)
            return

        segments: list[tuple[str, int, PartitionInfo | None]] = []
        current_offset = 0
        for part in self.disk.partitions:
            gap = part.offset_bytes - current_offset
            if gap > total * 0.01:
                segments.append(("free", gap, None))
            segments.append(("part", part.size_bytes, part))
            current_offset = part.offset_bytes + part.size_bytes
        trailing = total - current_offset
        if trailing > total * 0.01:
            segments.append(("free", trailing, None))

        for _, seg_size, part in segments:
            fraction = max(seg_size / total, 0.025)

            if part is not None:
                color = _partition_color(part, on_system_disk=is_system_disk(self.disk))
                seg = ctk.CTkFrame(self, fg_color=color, corner_radius=6)
                idx = part.index

                letter_str = f"{part.drive_letter}:" if part.drive_letter else ""
                size_str = _bytes_to_display(part.size_bytes)
                line1 = f"{letter_str}  {size_str}".strip() if letter_str else size_str
                line2 = part.filesystem if part.filesystem else ""
                text = f"{line1}\n{line2}" if line2 else line1

                text_color = T["bar_text_protected"] if color == T["bar_protected"] else T["bar_text"]
                lbl = ctk.CTkLabel(seg, text=text, font=("Segoe UI Semibold", 10),
                                   text_color=text_color)
                lbl.pack(expand=True, padx=4)

                def _click(e, i=idx):
                    self.select_partition(i)
                seg.bind("<Button-1>", _click)
                lbl.bind("<Button-1>", _click)
                self.segment_frames.append(seg)
            else:
                seg = ctk.CTkFrame(self, fg_color=T["bar_unallocated"], corner_radius=6)
                ctk.CTkLabel(seg, text=f"Free\n{_bytes_to_display(seg_size)}",
                             font=("Segoe UI", 9), text_color=T["bar_text_free"]).pack(expand=True, padx=4)
                self.segment_frames.append(seg)

            seg.pack(side="left", fill="both", padx=1, pady=3)
            seg.configure(width=max(int(fraction * 650), 45))

    def select_partition(self, part_index: int):
        self.selected_index = part_index
        for seg in self.segment_frames:
            seg.configure(border_width=0)
        for i, part in enumerate(self.disk.partitions):
            if part.index == part_index and i < len(self.segment_frames):
                self.segment_frames[i].configure(border_width=2, border_color=T["bar_selected_border"])
                break
        if self.on_partition_click:
            self.on_partition_click(part_index)


class ConfirmDialog(ctk.CTkToplevel):
    """Type-to-confirm dialog for destructive operations."""

    def __init__(self, master, title: str, message: str, confirm_text: str,
                 on_confirm=None, simple: bool = False):
        super().__init__(master)
        self.title(title)
        self.geometry("460x240")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=T["bg_surface"])
        self.on_confirm = on_confirm
        self.confirm_text = confirm_text
        self.result = False

        ctk.CTkLabel(self, text=message, font=("Segoe UI", 13), wraplength=410,
                     justify="left", text_color=T["text_primary"]).pack(padx=24, pady=(24, 12))

        if simple:
            btn_frame = ctk.CTkFrame(self, fg_color="transparent")
            btn_frame.pack(pady=20)
            ctk.CTkButton(btn_frame, text="Cancel", width=110, height=34,
                          fg_color=T["accent_gray"], hover_color=T["hover_gray"],
                          font=("Segoe UI Semibold", 12),
                          command=self.destroy).pack(side="left", padx=8)
            ctk.CTkButton(btn_frame, text="Confirm", width=110, height=34,
                          fg_color=T["accent_red"], hover_color=T["hover_red"],
                          font=("Segoe UI Semibold", 12),
                          command=self._on_simple_confirm).pack(side="left", padx=8)
        else:
            ctk.CTkLabel(self, text=f'Type  {confirm_text}  to confirm:',
                         font=("Consolas", 12), text_color="#F87171").pack(padx=24, pady=(0, 6))
            self.entry = ctk.CTkEntry(self, width=320, height=36, font=("Consolas", 13),
                                      fg_color=T["bg_input"], border_color=T["text_muted"])
            self.entry.pack(padx=24)
            self.entry.focus_set()

            btn_frame = ctk.CTkFrame(self, fg_color="transparent")
            btn_frame.pack(pady=18)
            ctk.CTkButton(btn_frame, text="Cancel", width=110, height=34,
                          fg_color=T["accent_gray"], hover_color=T["hover_gray"],
                          font=("Segoe UI Semibold", 12),
                          command=self.destroy).pack(side="left", padx=8)
            ctk.CTkButton(btn_frame, text="Confirm", width=110, height=34,
                          fg_color=T["accent_red"], hover_color=T["hover_red"],
                          font=("Segoe UI Semibold", 12),
                          command=self._on_typed_confirm).pack(side="left", padx=8)
            self.entry.bind("<Return>", lambda e: self._on_typed_confirm())

    def _on_simple_confirm(self):
        self.result = True
        if self.on_confirm:
            self.on_confirm()
        self.destroy()

    def _on_typed_confirm(self):
        if self.entry.get().strip().upper() == self.confirm_text.upper():
            self.result = True
            if self.on_confirm:
                self.on_confirm()
            self.destroy()
        else:
            self.entry.configure(border_color=T["accent_red"])


class DiskPartApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("DiskPilot")
        self.geometry("1100x680")
        self.minsize(950, 580)

        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            self.after(200, lambda: self.iconbitmap(icon_path))
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.disks: list[DiskInfo] = []
        self.selected_disk: DiskInfo | None = None
        self.selected_partition: PartitionInfo | None = None
        self.disk_cards: dict[int, ctk.CTkFrame] = {}
        self.disk_bar: DiskBarWidget | None = None
        self._current_theme = "dark"

        self._build_layout()
        self._refresh_disks()

    # ── Theme toggle ──

    def _toggle_theme(self):
        self._current_theme = "light" if self._current_theme == "dark" else "dark"
        T.update(THEMES[self._current_theme])
        ctk.set_appearance_mode(T["appearance"])
        self._apply_theme()

    def _apply_theme(self):
        """Re-apply all custom colors after a theme switch."""
        self.configure(fg_color=T["bg_main"])

        # Sidebar
        self.left_panel.configure(fg_color=T["bg_sidebar"])
        self.sidebar_sep.configure(fg_color=T["separator"])
        self.hdr_label.configure(text_color=T["text_primary"])
        self.hdr_refresh_btn.configure(fg_color=T["bg_card"], hover_color=T["bg_card_hover"],
                                       text_color=T["text_secondary"])
        self.theme_btn.configure(
            text="Light" if self._current_theme == "dark" else "Dark",
            fg_color=T["bg_card"], hover_color=T["bg_card_hover"],
            text_color=T["text_secondary"],
        )

        # Scrollable frames — force background + scrollbar colors
        self.disk_list_frame.configure(fg_color=T["bg_sidebar"],
                                       scrollbar_button_color=T["bg_card"],
                                       scrollbar_button_hover_color=T["bg_card_hover"])

        # Center
        self.center.configure(fg_color=T["bg_main"])
        self.disk_header.configure(text_color=T["text_primary"])
        self.disk_subheader.configure(text_color=T["text_secondary"])
        self.bar_frame.configure(fg_color=T["bg_surface"])
        self.partitions_label.configure(text_color=T["text_primary"])
        self.table_frame.configure(fg_color=T["bg_surface"])
        self.action_container.configure(fg_color=T["bg_surface"])
        self.status_frame.configure(fg_color=T["bg_status"])
        self.status_bar.configure(text_color=T["text_muted"])

        # Rebuild dynamic content with new colors
        self._rebuild_disk_cards()
        self._build_action_buttons()
        if self.selected_disk:
            self._update_partition_bar()
            self._update_partition_table()

    def _rebuild_disk_cards(self):
        """Rebuild all disk cards in the sidebar."""
        for w in self.disk_list_frame.winfo_children():
            w.destroy()
        self.disk_cards.clear()
        for disk in self.disks:
            self._add_disk_card(disk)
        # Re-highlight selected
        if self.selected_disk:
            card = self.disk_cards.get(self.selected_disk.index)
            if card:
                card.configure(fg_color=T["bg_card_hover"], border_width=2,
                               border_color=T["accent_blue"])

    # ── Layout ──

    def _build_layout(self):
        self.configure(fg_color=T["bg_main"])

        # Sidebar
        self.left_panel = ctk.CTkFrame(self, width=270, fg_color=T["bg_sidebar"], corner_radius=0)
        self.left_panel.pack(side="left", fill="y")
        self.left_panel.pack_propagate(False)

        # Sidebar header
        hdr = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(14, 4))
        self.hdr_label = ctk.CTkLabel(hdr, text="Disks", font=("Segoe UI Semibold", 18),
                                      text_color=T["text_primary"])
        self.hdr_label.pack(side="left")

        self.hdr_refresh_btn = ctk.CTkButton(
            hdr, text="Refresh", width=70, height=28, corner_radius=6,
            font=("Segoe UI", 11), fg_color=T["bg_card"], hover_color=T["bg_card_hover"],
            text_color=T["text_secondary"], command=self._refresh_disks)
        self.hdr_refresh_btn.pack(side="right")

        self.support_btn = ctk.CTkButton(
            hdr, text="☕ Support", width=80, height=28, corner_radius=6,
            font=("Segoe UI", 11, "bold"), fg_color="#FFDD00", hover_color="#E5C700",
            text_color="#000000",
            command=lambda: webbrowser.open("https://buymeacoffee.com/lordvelm"))
        self.support_btn.pack(side="right", padx=(0, 6))

        self.theme_btn = ctk.CTkButton(
            hdr, text="Light", width=50, height=28, corner_radius=6,
            font=("Segoe UI", 11), fg_color=T["bg_card"], hover_color=T["bg_card_hover"],
            text_color=T["text_secondary"], command=self._toggle_theme)
        self.theme_btn.pack(side="right", padx=(0, 6))

        self.sidebar_sep = ctk.CTkFrame(self.left_panel, height=1, fg_color=T["separator"])
        self.sidebar_sep.pack(fill="x", padx=14, pady=(6, 6))

        self.disk_list_frame = ctk.CTkScrollableFrame(
            self.left_panel, fg_color=T["bg_sidebar"],
            scrollbar_button_color=T["bg_card"], scrollbar_button_hover_color=T["bg_card_hover"])
        self.disk_list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Center
        self.center = ctk.CTkFrame(self, fg_color=T["bg_main"], corner_radius=0)
        self.center.pack(side="left", fill="both", expand=True)

        # Disk info header
        self.disk_header = ctk.CTkLabel(self.center, text="Select a disk",
                                        font=("Segoe UI Semibold", 15), text_color=T["text_primary"],
                                        anchor="w")
        self.disk_header.pack(fill="x", padx=20, pady=(16, 4))

        self.disk_subheader = ctk.CTkLabel(self.center, text="",
                                           font=("Segoe UI", 11), text_color=T["text_secondary"],
                                           anchor="w")
        self.disk_subheader.pack(fill="x", padx=20, pady=(0, 8))

        # Partition bar
        self.bar_frame = ctk.CTkFrame(self.center, fg_color=T["bg_surface"], corner_radius=10, height=80)
        self.bar_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.bar_frame.pack_propagate(False)

        # Table header label
        self.partitions_label = ctk.CTkLabel(self.center, text="Partitions",
                                             font=("Segoe UI Semibold", 13),
                                             text_color=T["text_primary"], anchor="w")
        self.partitions_label.pack(fill="x", padx=20, pady=(4, 4))

        # Partition table
        self.table_frame = ctk.CTkScrollableFrame(
            self.center, fg_color=T["bg_surface"], corner_radius=10,
            scrollbar_button_color=T["bg_card"], scrollbar_button_hover_color=T["bg_card_hover"])
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        # Action bar
        self.action_container = ctk.CTkFrame(self.center, fg_color=T["bg_surface"],
                                             corner_radius=10, height=56)
        self.action_container.pack(fill="x", padx=20, pady=(0, 6))
        self.action_container.pack_propagate(False)

        self.action_frame = ctk.CTkFrame(self.action_container, fg_color="transparent")
        self.action_frame.pack(expand=True)

        self._build_action_buttons()

        # Status bar
        self.status_frame = ctk.CTkFrame(self.center, fg_color=T["bg_status"],
                                         corner_radius=8, height=30)
        self.status_frame.pack(fill="x", padx=20, pady=(0, 12))
        self.status_frame.pack_propagate(False)
        self.status_bar = ctk.CTkLabel(self.status_frame, text="Ready", font=("Segoe UI", 11),
                                       text_color=T["text_muted"], anchor="w")
        self.status_bar.pack(fill="x", padx=12, expand=True)

    def _build_action_buttons(self):
        for w in self.action_frame.winfo_children():
            w.destroy()

        btn_cfg = {"height": 34, "font": ("Segoe UI Semibold", 11), "corner_radius": 8, "width": 120}

        self.btn_format = ctk.CTkButton(
            self.action_frame, text="Format", fg_color=T["accent_blue"],
            hover_color=T["hover_blue"], command=self._on_format, **btn_cfg)
        self.btn_format.pack(side="left", padx=4)

        self.btn_delete = ctk.CTkButton(
            self.action_frame, text="Delete", fg_color=T["accent_red"],
            hover_color=T["hover_red"], command=self._on_delete_partition, **btn_cfg)
        self.btn_delete.pack(side="left", padx=4)

        self.btn_create = ctk.CTkButton(
            self.action_frame, text="Create", fg_color=T["accent_green"],
            hover_color=T["hover_green"], text_color=T["btn_dark_text"],
            command=self._on_create_partition, **btn_cfg)
        self.btn_create.pack(side="left", padx=4)

        self.btn_clean = ctk.CTkButton(
            self.action_frame, text="Clean Disk", fg_color=T["accent_purple"],
            hover_color=T["hover_purple"], command=self._on_clean_disk, **btn_cfg)
        self.btn_clean.pack(side="left", padx=4)

        self.btn_letter = ctk.CTkButton(
            self.action_frame, text="Drive Letter", fg_color=T["accent_cyan"],
            hover_color=T["hover_cyan"], text_color=T["btn_dark_text"],
            command=self._on_change_letter, **btn_cfg)
        self.btn_letter.pack(side="left", padx=4)

        self._update_button_states()

    def _update_button_states(self):
        disk = self.selected_disk
        part = self.selected_partition
        sys_disk = disk and is_system_disk(disk)
        protected = part and _is_protected_partition(part, on_system_disk=bool(sys_disk))

        can_format = part is not None and not protected
        self.btn_format.configure(state="normal" if can_format else "disabled")

        can_delete = part is not None and not protected
        self.btn_delete.configure(state="normal" if can_delete else "disabled")

        can_create = disk is not None
        self.btn_create.configure(state="normal" if can_create else "disabled")

        can_clean = disk is not None and not sys_disk
        self.btn_clean.configure(state="normal" if can_clean else "disabled")

        can_letter = part is not None and not protected
        self.btn_letter.configure(state="normal" if can_letter else "disabled")

    def _set_status(self, text: str):
        self.status_bar.configure(text=text)

    # ── Disk list ──

    def _refresh_disks(self):
        self._set_status("Scanning disks...")
        self.update_idletasks()

        try:
            self.disks = get_all_disks()
        except Exception as e:
            self._set_status(f"Error: {e}")
            return

        for w in self.disk_list_frame.winfo_children():
            w.destroy()
        self.disk_cards.clear()

        for disk in self.disks:
            self._add_disk_card(disk)

        if self.disks:
            self._select_disk(self.disks[0])

        self._set_status(f"Found {len(self.disks)} disk(s)")

    def _add_disk_card(self, disk: DiskInfo):
        card = ctk.CTkFrame(self.disk_list_frame, fg_color=T["bg_card"], corner_radius=10,
                            border_width=0, cursor="hand2")
        card.pack(fill="x", pady=3, padx=2)
        self.disk_cards[disk.index] = card

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(top, text=f"Disk {disk.index}", font=("Segoe UI Semibold", 13),
                     text_color=T["text_primary"], anchor="w").pack(side="left")

        badge_frame = ctk.CTkFrame(top, fg_color="transparent")
        badge_frame.pack(side="right")
        if disk.is_system_disk:
            _badge(badge_frame, "OS", T["badge_os_fg"], T["badge_os_bg"])
        if disk.is_removable:
            _badge(badge_frame, "USB", T["badge_usb_fg"], T["badge_usb_bg"])
        _badge(badge_frame, disk.partition_style, T["badge_style_fg"], T["badge_style_bg"])

        ctk.CTkLabel(card, text=disk.model[:35], font=("Segoe UI", 11),
                     text_color=T["text_secondary"], anchor="w").pack(fill="x", padx=12, pady=(1, 0))

        ctk.CTkLabel(card, text=_bytes_to_display(disk.size_bytes), font=("Segoe UI", 11),
                     text_color=T["text_muted"], anchor="w").pack(fill="x", padx=12, pady=(0, 10))

        def _click(e, d=disk):
            self._select_disk(d)
        card.bind("<Button-1>", _click)
        for child in _all_descendants(card):
            child.bind("<Button-1>", _click)

    def _select_disk(self, disk: DiskInfo):
        self.selected_disk = disk
        self.selected_partition = None

        for idx, card in self.disk_cards.items():
            if idx == disk.index:
                card.configure(fg_color=T["bg_card_hover"], border_width=2,
                               border_color=T["accent_blue"])
            else:
                card.configure(fg_color=T["bg_card"], border_width=0)

        sys_str = "  (System Disk)" if disk.is_system_disk else ""
        self.disk_header.configure(text=f"Disk {disk.index} — {disk.model}{sys_str}")
        parts_str = f"{len(disk.partitions)} partition(s)"
        self.disk_subheader.configure(
            text=f"{_bytes_to_display(disk.size_bytes)}  |  {disk.partition_style}  |  {parts_str}"
        )

        self._update_partition_bar()
        self._update_partition_table()
        self._update_button_states()

    # ── Partition bar ──

    def _update_partition_bar(self):
        for w in self.bar_frame.winfo_children():
            w.destroy()
        if not self.selected_disk:
            return
        self.disk_bar = DiskBarWidget(self.bar_frame, self.selected_disk,
                                      on_partition_click=self._on_bar_partition_click,
                                      fg_color=T["bg_surface"])
        self.disk_bar.pack(fill="both", expand=True, padx=6, pady=6)

    def _on_bar_partition_click(self, part_index: int):
        if not self.selected_disk:
            return
        for part in self.selected_disk.partitions:
            if part.index == part_index:
                self.selected_partition = part
                self._highlight_table_row(part_index)
                self._update_button_states()
                lbl = f" ({part.drive_letter}:)" if part.drive_letter else ""
                self._set_status(f"Selected Partition {part_index}{lbl}")
                break

    # ── Partition table ──

    def _update_partition_table(self):
        for w in self.table_frame.winfo_children():
            w.destroy()
        if not self.selected_disk:
            return

        headers = ["", "#", "Letter", "Label", "File System", "Size", "Type", "Status"]
        widths = [16, 30, 60, 120, 90, 90, 100, 70]

        hdr_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent", height=28)
        hdr_frame.pack(fill="x", padx=8, pady=(8, 0))
        for h, w in zip(headers, widths):
            ctk.CTkLabel(hdr_frame, text=h, width=w, font=("Segoe UI Semibold", 10),
                         text_color=T["text_muted"], anchor="w").pack(side="left", padx=3)

        ctk.CTkFrame(self.table_frame, height=1, fg_color=T["separator"]).pack(fill="x", padx=8, pady=4)

        if not self.selected_disk.partitions:
            ctk.CTkLabel(self.table_frame, text="No partitions — disk is empty or uninitialized",
                         font=("Segoe UI", 12), text_color=T["text_muted"]).pack(pady=30)
            return

        sys_disk = is_system_disk(self.selected_disk)
        self.table_rows: dict[int, ctk.CTkFrame] = {}

        for i, part in enumerate(self.selected_disk.partitions):
            row_bg = T["bg_table_row"] if i % 2 == 0 else T["bg_table_alt"]
            row = ctk.CTkFrame(self.table_frame, fg_color=row_bg, corner_radius=6,
                               height=32, cursor="hand2")
            row.pack(fill="x", padx=6, pady=1)
            row.pack_propagate(False)
            self.table_rows[part.index] = row

            dot_frame = ctk.CTkFrame(row, fg_color="transparent", width=16)
            dot_frame.pack(side="left", padx=(6, 0))
            dot_frame.pack_propagate(False)
            dot = ctk.CTkFrame(dot_frame, width=10, height=10, corner_radius=5,
                               fg_color=_partition_color(part, on_system_disk=sys_disk))
            dot.place(relx=0.5, rely=0.5, anchor="center")

            values = [
                str(part.index),
                f"{part.drive_letter}:" if part.drive_letter else "—",
                part.label or "—",
                part.filesystem or "—",
                _bytes_to_display(part.size_bytes),
                part.partition_type,
                "Boot" if part.is_boot else ("System" if part.is_system else ""),
            ]
            for val, w in zip(values, widths[1:]):
                ctk.CTkLabel(row, text=val, width=w, font=("Segoe UI", 11),
                             text_color=T["text_primary"], anchor="w").pack(side="left", padx=3)

            def _click(e, p=part):
                self.selected_partition = p
                self._highlight_table_row(p.index)
                self._update_button_states()
                if self.disk_bar:
                    self.disk_bar.select_partition(p.index)
            row.bind("<Button-1>", _click)
            for child in _all_descendants(row):
                child.bind("<Button-1>", _click)

    def _highlight_table_row(self, part_index: int):
        for i, (idx, row) in enumerate(self.table_rows.items()):
            if idx == part_index:
                row.configure(fg_color=T["bg_table_sel"], border_width=1,
                              border_color=T["accent_blue"])
            else:
                row.configure(fg_color=T["bg_table_row"] if i % 2 == 0 else T["bg_table_alt"],
                              border_width=0)

    # ── Action handlers ──

    def _run_in_thread(self, func, success_msg: str):
        def _worker():
            success, output = func()
            self.after(0, lambda: self._op_done(success, output, success_msg))
        self._set_status("Working...")
        self._disable_all_buttons()
        threading.Thread(target=_worker, daemon=True).start()

    def _op_done(self, success: bool, output: str, success_msg: str):
        if success:
            self._set_status(success_msg)
        else:
            self._set_status(f"Failed: {output[:120]}")
        self._refresh_disks()

    def _disable_all_buttons(self):
        for btn in (self.btn_format, self.btn_delete, self.btn_create,
                    self.btn_clean, self.btn_letter):
            btn.configure(state="disabled")

    def _on_format(self):
        part = self.selected_partition
        disk = self.selected_disk
        if not part or not disk:
            return
        if _is_protected_partition(part, on_system_disk=is_system_disk(disk)):
            self._set_status("Cannot format a protected partition on the system disk.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Format Partition")
        dialog.geometry("420x300")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=T["bg_surface"])

        letter_str = f" ({part.drive_letter}:)" if part.drive_letter else ""
        ctk.CTkLabel(dialog, text=f"Format Partition {part.index}{letter_str} on Disk {disk.index}",
                     font=("Segoe UI Semibold", 14), text_color=T["text_primary"]).pack(padx=24, pady=(20, 14))

        fs_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        fs_frame.pack(padx=24, fill="x")
        ctk.CTkLabel(fs_frame, text="File system", font=("Segoe UI", 12),
                     text_color=T["text_secondary"]).pack(side="left")
        fs_var = ctk.StringVar(value="NTFS")
        ctk.CTkOptionMenu(fs_frame, variable=fs_var, values=["NTFS", "FAT32", "exFAT"],
                          width=130, fg_color=T["bg_card"], button_color=T["bg_card_hover"],
                          button_hover_color=T["accent_blue"]).pack(side="right")

        lbl_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        lbl_frame.pack(padx=24, fill="x", pady=(10, 0))
        ctk.CTkLabel(lbl_frame, text="Volume label", font=("Segoe UI", 12),
                     text_color=T["text_secondary"]).pack(side="left")
        lbl_entry = ctk.CTkEntry(lbl_frame, width=160, fg_color=T["bg_input"],
                                 border_color=T["text_muted"])
        lbl_entry.pack(side="right")

        quick_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(dialog, text="Quick format", variable=quick_var,
                        font=("Segoe UI", 12), fg_color=T["accent_blue"],
                        hover_color=T["hover_blue"]).pack(padx=24, pady=(12, 0), anchor="w")

        confirm_text = f"FORMAT PARTITION {part.index}"

        def _do_format():
            dialog.destroy()
            ConfirmDialog(self, "Confirm Format",
                          f"This will ERASE ALL DATA on partition {part.index}{letter_str}.\n"
                          f"Disk: {disk.model}",
                          confirm_text,
                          on_confirm=lambda: self._run_in_thread(
                              lambda: format_partition(disk.index, part.index,
                                                      fs_var.get(), lbl_entry.get(), quick_var.get()),
                              "Format complete."))

        ctk.CTkButton(dialog, text="Next", fg_color=T["accent_blue"], hover_color=T["hover_blue"],
                      font=("Segoe UI Semibold", 12), height=36, width=140,
                      corner_radius=8, command=_do_format).pack(pady=20)

    def _on_delete_partition(self):
        part = self.selected_partition
        disk = self.selected_disk
        if not part or not disk:
            return
        if _is_protected_partition(part, on_system_disk=is_system_disk(disk)):
            self._set_status("Cannot delete a protected partition on the system disk.")
            return

        letter_str = f" ({part.drive_letter}:)" if part.drive_letter else ""
        ConfirmDialog(self, "Delete Partition",
                      f"Delete partition {part.index}{letter_str} on Disk {disk.index} ({disk.model})?\n"
                      f"All data will be lost.",
                      f"DELETE PARTITION {part.index}",
                      on_confirm=lambda: self._run_in_thread(
                          lambda: delete_partition(disk.index, part.index),
                          "Partition deleted."))

    def _on_create_partition(self):
        disk = self.selected_disk
        if not disk:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Create Partition")
        dialog.geometry("400x210")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=T["bg_surface"])

        ctk.CTkLabel(dialog, text=f"Create partition on Disk {disk.index}",
                     font=("Segoe UI Semibold", 14), text_color=T["text_primary"]).pack(padx=24, pady=(20, 14))

        size_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        size_frame.pack(padx=24, fill="x")
        ctk.CTkLabel(size_frame, text="Size (MB)", font=("Segoe UI", 12),
                     text_color=T["text_secondary"]).pack(side="left")
        size_entry = ctk.CTkEntry(size_frame, width=140, placeholder_text="All free space",
                                  fg_color=T["bg_input"], border_color=T["text_muted"])
        size_entry.pack(side="right")

        def _do_create():
            size_text = size_entry.get().strip()
            size_mb = int(size_text) if size_text.isdigit() else None
            dialog.destroy()
            ConfirmDialog(self, "Confirm Create Partition",
                          f"Create a new partition on Disk {disk.index} ({disk.model})?",
                          "", on_confirm=lambda: self._run_in_thread(
                              lambda: create_partition(disk.index, size_mb),
                              "Partition created."),
                          simple=True)

        ctk.CTkButton(dialog, text="Create", fg_color=T["accent_green"], hover_color=T["hover_green"],
                      text_color=T["btn_dark_text"], font=("Segoe UI Semibold", 12), height=36, width=140,
                      corner_radius=8, command=_do_create).pack(pady=20)

    def _on_clean_disk(self):
        disk = self.selected_disk
        if not disk:
            return
        if is_system_disk(disk):
            self._set_status("Cannot clean the system disk.")
            return

        ConfirmDialog(self, "Clean Disk",
                      f"CLEAN Disk {disk.index} ({disk.model}, {_bytes_to_display(disk.size_bytes)})?\n\n"
                      f"This will DESTROY ALL PARTITIONS and DATA on this disk.",
                      f"CLEAN DISK {disk.index}",
                      on_confirm=lambda: self._run_in_thread(
                          lambda: clean_disk(disk.index), "Disk cleaned."))

    def _on_change_letter(self):
        part = self.selected_partition
        disk = self.selected_disk
        if not part or not disk:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Change Drive Letter")
        dialog.geometry("370x200")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=T["bg_surface"])

        current = f"{part.drive_letter}:" if part.drive_letter else "None"
        ctk.CTkLabel(dialog, text=f"Current letter: {current}",
                     font=("Segoe UI", 13), text_color=T["text_primary"]).pack(padx=24, pady=(20, 14))

        entry_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        entry_frame.pack(padx=24, fill="x")
        ctk.CTkLabel(entry_frame, text="New letter", font=("Segoe UI", 12),
                     text_color=T["text_secondary"]).pack(side="left")
        letter_entry = ctk.CTkEntry(entry_frame, width=60, font=("Consolas", 14),
                                    fg_color=T["bg_input"], border_color=T["text_muted"])
        letter_entry.pack(side="right")

        def _do_change():
            new_letter = letter_entry.get().strip().upper().rstrip(":")
            if len(new_letter) != 1 or not new_letter.isalpha():
                self._set_status("Enter a single letter (A-Z).")
                dialog.destroy()
                return
            dialog.destroy()
            ConfirmDialog(self, "Confirm Letter Change",
                          f"Assign letter {new_letter}: to partition {part.index} on Disk {disk.index}?",
                          "", on_confirm=lambda: self._run_in_thread(
                              lambda: assign_letter(disk.index, part.index, new_letter),
                              f"Drive letter changed to {new_letter}:"),
                          simple=True)

        ctk.CTkButton(dialog, text="Assign", fg_color=T["accent_cyan"], hover_color=T["hover_cyan"],
                      text_color=T["btn_dark_text"], font=("Segoe UI Semibold", 12), height=36, width=140,
                      corner_radius=8, command=_do_change).pack(pady=20)


# ── Helpers ──

def _badge(parent, text: str, fg: str, bg: str):
    b = ctk.CTkLabel(parent, text=text, font=("Segoe UI Semibold", 9),
                     text_color=fg, fg_color=bg, corner_radius=4, width=36, height=18)
    b.pack(side="right", padx=(4, 0))


def _all_descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _all_descendants(child)


def main():
    if not is_admin():
        elevate_self()
    app = DiskPartApp()
    app.mainloop()


if __name__ == "__main__":
    main()
