import { getCurrentWindow } from "@tauri-apps/api/window";

interface TitleBarProps {
  theme: "dark" | "light";
  loading: boolean;
  onRefresh: () => void;
  onToggleTheme: () => void;
}

export function TitleBar({ theme, loading, onRefresh, onToggleTheme }: TitleBarProps) {
  const appWindow = getCurrentWindow();

  return (
    <header
      data-tauri-drag-region
      className="flex items-center justify-between pl-4 pr-0 border-b select-none flex-shrink-0"
      style={{
        borderColor: "var(--separator)",
        background: "var(--bg-sidebar)",
        height: 40,
        minHeight: 40,
      }}
    >
      {/* Left: app title */}
      <h1
        data-tauri-drag-region
        className="text-sm font-semibold tracking-tight pointer-events-none"
        style={{ color: "var(--text-primary)" }}
      >
        DiskPilot
      </h1>

      {/* Drag region fills the middle */}
      <div data-tauri-drag-region className="flex-1" />

      {/* Right: actions + window controls */}
      <div className="flex items-center h-full gap-2 pr-1">
        <button
          onClick={onRefresh}
          disabled={loading}
          className="px-2.5 py-1 text-xs rounded transition-colors"
          style={{ background: "var(--accent-blue)", color: "#fff" }}
        >
          {loading ? "Scanning..." : "Refresh"}
        </button>
        <button
          onClick={onToggleTheme}
          className="px-2.5 py-1 text-xs rounded transition-colors"
          style={{ background: "var(--accent-gray)", color: "#fff" }}
        >
          {theme === "dark" ? "Light" : "Dark"}
        </button>
      </div>

      {/* Window controls */}
      <div className="flex h-full">
        <WindowButton label={"\uE921"} onClick={() => appWindow.minimize()} />
        <WindowButton label={"\uE922"} onClick={() => appWindow.toggleMaximize()} />
        <WindowButton
          label={"\uE8BB"}
          onClick={() => appWindow.close()}
          isClose
        />
      </div>
    </header>
  );
}

function WindowButton({
  label,
  onClick,
  isClose = false,
}: {
  label: string;
  onClick: () => void;
  isClose?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className="w-11 h-full flex items-center justify-center transition-colors"
      style={{
        fontFamily: "'Segoe MDL2 Assets'",
        fontSize: 10,
        color: "var(--text-secondary)",
        background: "transparent",
        border: "none",
        outline: "none",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = isClose ? "#c42b1c" : "var(--bg-card-hover)";
        if (isClose) e.currentTarget.style.color = "#fff";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.color = "var(--text-secondary)";
      }}
    >
      {label}
    </button>
  );
}
