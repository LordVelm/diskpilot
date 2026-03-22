interface StatusBarProps {
  status: string;
}

export function StatusBar({ status }: StatusBarProps) {
  return (
    <footer
      className="px-4 py-1.5 text-xs border-t"
      style={{
        background: "var(--bg-status)",
        color: "var(--text-muted)",
        borderColor: "var(--separator)",
      }}
    >
      {status}
    </footer>
  );
}
