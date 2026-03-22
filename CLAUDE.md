# CLAUDE.md — DiskPilot

Guidance for Claude Code and collaborators working in this repository. **Read this before large changes.**

---

## Project overview

**DiskPilot** — Free, lightweight **Windows** disk & partition manager: visual disk list, proportional **partition bar**, partition details, and **destructive operations** (format, delete, create, clean, assign/remove drive letter) with **safety-first** design.

**Current implementation:** Python **CustomTkinter** GUI + **`disk_ops.py`** (WMI reads, `diskpart` writes).

**User intent:** Rebuild the app in **Tauri v2 + React + TypeScript + Vite + Tailwind**, aligned with **`debt-planner-local`** / **`steam-backlog-organizer`** (modern shell, performance, maintainability). **Windows-only** for v1 (same as today).

---

## Commands (Tauri v2 — primary)

```bash
cd diskpilot
npm install

# Dev mode (launches Tauri window + Vite HMR)
npx tauri dev

# Build installer (NSIS on Windows)
npx tauri build

# Type checks
npx tsc --noEmit          # TypeScript
cd src-tauri && cargo check   # Rust
```

## Commands (legacy Python app — reference only)

```powershell
cd diskpilot
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install customtkinter wmi pywin32
python gui.py

# Build standalone exe
pip install pyinstaller
python build.py   # dist/DiskPilot.exe (--uac-admin)
```

**Tests:** `scripts/export_fixtures.py` generates golden JSON for parity testing.

---

## Architecture (current — preserve behavior)

### `disk_ops.py` — Core logic

| Area | Behavior |
|------|----------|
| **Reads** | **WMI:** `Win32_DiskDrive` → `Win32_DiskPartition` → `Win32_LogicalDisk` (associators). Structured, **no locale-dependent parsing** of diskpart text for enumeration. |
| **Data** | `DiskInfo` / `PartitionInfo` — index, sizes, filesystem, label, letter, partition type (EFI/Recovery/MSR/Basic), `is_system` / `is_boot`, `offset_bytes` (for bar ordering). |
| **Writes** | **`diskpart /s`** with a **temp script file** — `_run_diskpart_script()`. All mutations go through this. Timeout **60s**. Success = return code 0 **and** `"error"` not in combined stdout/stderr (case-insensitive). |
| **Mutations** | `format_partition`, `clean_disk`, `create_partition`, `delete_partition`, `assign_letter`, `remove_letter`. |
| **Indexing** | **Diskpart uses 1-based partition numbers** — Python uses `partition_index + 1` in scripts; WMI `Index` is 0-based. **Must match exactly in Rust.** |
| **Admin** | `ctypes` + `IsUserAnAdmin` / `ShellExecuteW("runas")` for elevation. |

### Safety model (defense in depth — do not weaken)

1. **System disk** — Detected via boot partition, system drive letter, WMI flags. **Backend** refuses `clean` on system disk and refuses mutations on **protected** partitions on that disk.
2. **Protected partitions (on system disk only)** — EFI, Recovery, MSR, system/boot/C: — **not** modifiable. On **non-system** disks (e.g. USB), restrictions are relaxed per current Python behavior.
3. **UI + backend** — Buttons disabled where appropriate **and** backend `_assert_not_system_disk` / `_assert_not_system_partition` refuse unsafe ops.
4. **Type-to-confirm** — Destructive ops require typing exact confirmation text (see `gui.py` / `ConfirmDialog`).
5. **Remove letter** — Cannot remove **system drive** letter.

### `gui.py` — CustomTkinter

- Disk list, `DiskBarWidget` (proportional segments), details table, action buttons, theme toggle (dark/light), threading for long ops, status bar.

### `build.py` — PyInstaller

- `--onefile --windowed --uac-admin`, entry `gui.py`.

---

## Rebuild: Tauri + React + TypeScript

**Decision:** **Full port** to **Tauri v2 + React + TypeScript + Vite + Tailwind**. **No Python sidecar** in release builds — single installer, **Rust** in the Tauri backend for WMI + `diskpart` (same split as today: WMI read, diskpart write).

**Reference stack:** `C:\Users\Kareem\projects\debt-planner-local` (monorepo layout, design tokens, patterns).

| Layer | Responsibility |
|--------|----------------|
| **Tauri (Rust)** | WMI enumeration, diskpart scripting, safety checks, process spawning, structured errors to UI |
| **React + TS** | Layout, partition bar (SVG or canvas), tables, dialogs, theme, progress state |
| **Shared types** | `packages/core-types` or `src/types` — mirror `DiskInfo` / `PartitionInfo` JSON shape |

### Why Rust for backend (not Node)

- Native **Windows APIs** / WMI from Rust is well-trodden; keeps one binary and avoids embedding Python.
- **`std::process::Command`** for `diskpart` matches current design.

### Rust implementation notes (for implementers)

- **WMI:** Use a maintained crate (e.g. **`wmi`** on crates.io with `serde` structs, or **`windows`** crate + COM). Mirror the **same query chain** as Python so indices and partition ordering match.
- **diskpart:** Build identical command lists; temp file + `diskpart /s path`; preserve **60s timeout** and success heuristic unless improved with tests.
- **Elevation:** Tauri **Windows manifest** `requireAdministrator` (equivalent to PyInstaller `--uac-admin`). Document that the app **must** run elevated for mutations (reads may still work limited without admin — align with current behavior).
- **Async:** Run diskpart and heavy WMI work on **blocking thread pool** (`spawn_blocking` / `tokio::task::spawn_blocking`) — never block the UI thread.

---

## Parity testing strategy

**Goal:** Rust `enumerate_disks()` produces **equivalent** `DiskInfo[]` to Python `get_all_disks()` on the same machine, and mutation helpers refuse the same operations.

#### Step 1 — Golden fixtures (before trusting Rust)

1. Add **`scripts/export_fixtures.py`** (or extend `disk_ops.py`) to dump JSON:
   - `fixtures/golden_disks.json` — serialized output of `get_all_disks()` (all fields needed for UI).
2. Run on a **dev machine** with multiple disks if possible; **optional:** scrub serials if any PII in model strings (usually fine).

#### Step 2 — Rust tests

- Load `golden_disks.json` in Rust tests; compare disk count, partition count per disk, sizes, letters, types, offsets (tolerance: **exact** for integers).
- If WMI ordering differs, **sort** both sides by `offset_bytes` before compare (Python already sorts partitions).

#### Step 3 — Safety parity

- Table-driven tests: `(disk_index, partition_index, op)` → expect **blocked** or **allowed** matching Python guards (`_assert_not_system_disk`, `_assert_not_system_partition`, `remove_letter` on `C:`, etc.).

#### Step 4 — diskpart scripts (optional integration)

- On a **dedicated test USB** or VM snapshot: run minimal script sequences and compare exit behavior — **not** required for CI if too risky; document manual QA checklist.

---

## Build phases

### Phase 0 — Fixtures + types ✓

- [x] JSON schema / TypeScript types for `DiskInfo` + `PartitionInfo` (`src/types/disk.ts`).
- [x] `scripts/export_fixtures.py` + `fixtures/golden_disks.json` (gitignored).
- [x] Partition index rules documented in `wmi_disk.rs` and `diskpart.rs` headers.

### Phase 1 — Tauri scaffold + read-only path ✓

- [x] **Tauri v2 + React + Vite + Tailwind** project scaffolded.
- [x] Rust `wmi_disk` module: full WMI enumeration; `tauri::command` `get_disks` → JSON.
- [x] React shell layout: sidebar disk list, main area with partition bar + details.

### Phase 2 — diskpart mutation layer ✓

- [x] Rust `diskpart` module: temp script + `diskpart /s` + success heuristic (same as Python).
- [x] All mutations ported: format, clean, create, delete, assign, remove — identical guard order.
- [x] `safety.rs`: `assert_not_system_disk` / `assert_not_system_partition` with defense-in-depth.

### Phase 3 — Frontend: visualization + details ✓

- [x] Disk list with model, size, GPT/MBR, removable/system badges.
- [x] Partition bar with proportional segments + same color rules as Python `THEMES`.
- [x] Details table: letter, label, filesystem, size, type, status.
- [x] Selection sync: click bar segment ↔ row highlight.
- [x] Dark + light theme via CSS variables (ported all tokens from `gui.py`).

### Phase 4 — Actions + safety UX ✓

- [x] Buttons wired: format, clean, create, delete, assign/remove letter.
- [x] Type-to-confirm modals for destructive ops (same strings/UX intent as Python).
- [x] Controls disabled for illegal ops (system disk / protected partitions).
- [x] Status bar + error banner.

### Phase 5 — Packaging + docs ✓

- [x] Windows `requireAdministrator` manifest embedded via `build.rs`.
- [x] NSIS installer configured in `tauri.conf.json`.
- [x] Icon wired (`icon.ico` + placeholder PNGs in `src-tauri/icons/`).
- [ ] README rewrite for v2 (optional — current README still valid for Python).
- [ ] Manual QA checklist: USB disk, secondary disk.

---

## Rebuild checklist (cross-cutting)

- [x] **Windows only** for v1 — document; macOS/Linux **out of scope** (different disk APIs).
- [ ] **Parity** on disk enumeration and safety refusals before shipping destructive features broadly.
- [ ] **Partition index** — document clearly for any UI that shows “Partition N” vs internal index.
- [ ] **Accessibility** — keyboard focus, focus trap in modals, high-contrast friendly palette (optional stretch).
- [ ] **Error messages** — user-readable; log full diskpart output to a **local debug log** (optional) for support.

---

## Open questions

1. **Elevation:** Require admin on **every** launch (like today) vs. **restart elevated** only when user clicks a destructive action? (Product decision; security UX tradeoff.)
2. **CI:** No full WMI/diskpart in GitHub Actions — rely on **fixtures** + **mocked diskpart** for unit tests; manual QA on hardware.
3. **Icon:** Wire `icon.ico` into Tauri bundle (see existing `create_icon.py` / repo assets).

---

## Related projects (stack reference)

- **`C:\Users\Kareem\projects\debt-planner-local`** — Tauri + React + TS monorepo patterns.
- **`C:\Users\Kareem\projects\steam-backlog-organizer`** — Example of phased rebuild + `CLAUDE.md` build plan style.

---

## Files to read first

| File | Purpose |
|------|---------|
| `src-tauri/src/wmi_disk.rs` | WMI disk enumeration (Rust) |
| `src-tauri/src/diskpart.rs` | Diskpart mutations + temp script runner (Rust) |
| `src-tauri/src/safety.rs` | System disk / partition safety gates (Rust) |
| `src-tauri/src/lib.rs` | Tauri commands — all IPC entry points |
| `src/App.tsx` | Main React app — layout, state, routing |
| `src/components/PartitionBar.tsx` | SVG-like proportional bar (same color rules as Python) |
| `src/components/ActionBar.tsx` | Action buttons + confirm dialog triggers |
| `src/types/disk.ts` | Shared TS types mirroring Rust structs |
| `src/index.css` | Dark/light theme CSS variables (ported from Python THEMES) |

### Legacy reference (Python — still in repo)

| File | Purpose |
|------|---------|
| `disk_ops.py` | Original WMI + diskpart + safety gates |
| `gui.py` | Original CustomTkinter UI + themes |

---

*Update this file when rebuild phases complete or architecture decisions change.*
