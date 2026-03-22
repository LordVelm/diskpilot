import { useEffect, useState, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { DiskInfo } from "./types/disk";
import { DiskList } from "./components/DiskList";
import { PartitionBar } from "./components/PartitionBar";
import { PartitionDetails } from "./components/PartitionDetails";
import { ActionBar } from "./components/ActionBar";
import { StatusBar } from "./components/StatusBar";
import { TitleBar } from "./components/TitleBar";
import { ConfirmDialog } from "./components/ConfirmDialog";

export default function App() {
  const [disks, setDisks] = useState<DiskInfo[]>([]);
  const [selectedDiskIndex, setSelectedDiskIndex] = useState<number | null>(null);
  const [selectedPartitionIndex, setSelectedPartitionIndex] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("Loading disks...");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [confirmDialog, setConfirmDialog] = useState<{
    title: string;
    message: string;
    confirmText: string;
    onConfirm: () => void;
  } | null>(null);

  const refreshDisks = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await invoke<DiskInfo[]>("get_disks");
      setDisks(result);
      setStatus(`${result.length} disk(s) found`);

      // If selected disk no longer exists, clear selection
      if (selectedDiskIndex !== null && !result.find((d) => d.index === selectedDiskIndex)) {
        setSelectedDiskIndex(null);
        setSelectedPartitionIndex(null);
      }
    } catch (e) {
      const msg = typeof e === "string" ? e : (e as Error).message ?? "Unknown error";
      setError(msg);
      setStatus("Error loading disks");
    } finally {
      setLoading(false);
    }
  }, [selectedDiskIndex]);

  useEffect(() => {
    refreshDisks();
  }, [refreshDisks]);

  const selectedDisk = disks.find((d) => d.index === selectedDiskIndex) ?? null;
  const selectedPartition =
    selectedDisk?.partitions.find((p) => p.index === selectedPartitionIndex) ?? null;

  const toggleTheme = () => {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  };

  return (
    <div className={theme === "light" ? "light" : ""} style={{ height: "100vh" }}>
      <div
        className="flex flex-col h-full"
        style={{ background: "var(--bg-main)", color: "var(--text-primary)" }}
      >
        {/* Custom title bar (no native decorations) */}
        <TitleBar
          theme={theme}
          loading={loading}
          onRefresh={refreshDisks}
          onToggleTheme={toggleTheme}
        />

        {/* Error banner */}
        {error && (
          <div
            className="px-5 py-2 text-sm"
            style={{ background: "var(--accent-red)", color: "#fff" }}
          >
            {error}
          </div>
        )}

        {/* Main content */}
        <div className="flex flex-1 min-h-0">
          {/* Sidebar: disk list */}
          <aside
            className="w-72 border-r overflow-y-auto flex-shrink-0"
            style={{ borderColor: "var(--separator)", background: "var(--bg-sidebar)" }}
          >
            <DiskList
              disks={disks}
              selectedDiskIndex={selectedDiskIndex}
              onSelectDisk={(idx) => {
                setSelectedDiskIndex(idx);
                setSelectedPartitionIndex(null);
              }}
            />
          </aside>

          {/* Main area */}
          <main className="flex-1 flex flex-col overflow-y-auto p-5 gap-4">
            {selectedDisk ? (
              <>
                <PartitionBar
                  disk={selectedDisk}
                  selectedPartitionIndex={selectedPartitionIndex}
                  onSelectPartition={setSelectedPartitionIndex}
                />
                <PartitionDetails
                  disk={selectedDisk}
                  selectedPartitionIndex={selectedPartitionIndex}
                  onSelectPartition={setSelectedPartitionIndex}
                />
                <ActionBar
                  disk={selectedDisk}
                  partition={selectedPartition}
                  onAction={refreshDisks}
                  setStatus={setStatus}
                  setConfirmDialog={setConfirmDialog}
                />
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center" style={{ color: "var(--text-muted)" }}>
                <p className="text-lg">
                  {loading ? "Scanning disks..." : "Select a disk to get started"}
                </p>
              </div>
            )}
          </main>
        </div>

        {/* Status bar */}
        <StatusBar status={status} />

        {/* Confirm dialog overlay */}
        {confirmDialog && (
          <ConfirmDialog
            {...confirmDialog}
            onCancel={() => setConfirmDialog(null)}
            onConfirmed={() => {
              confirmDialog.onConfirm();
              setConfirmDialog(null);
            }}
          />
        )}
      </div>
    </div>
  );
}
