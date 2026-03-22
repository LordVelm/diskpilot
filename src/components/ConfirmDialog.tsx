import { useState } from "react";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmText: string;
  onCancel: () => void;
  onConfirmed: () => void;
}

export function ConfirmDialog({
  title,
  message,
  confirmText,
  onCancel,
  onConfirmed,
}: ConfirmDialogProps) {
  const [input, setInput] = useState("");
  const matches = input.trim().toUpperCase() === confirmText.toUpperCase();

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: "rgba(0,0,0,0.6)" }}
      onClick={onCancel}
    >
      <div
        className="rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl"
        style={{ background: "var(--bg-card)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold mb-2" style={{ color: "var(--accent-red)" }}>
          {title}
        </h2>
        <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>
          {message}
        </p>
        <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>
          Type <strong style={{ color: "var(--text-primary)" }}>{confirmText}</strong> to confirm:
        </p>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="w-full px-3 py-2 rounded-md text-sm mb-4 outline-none border"
          style={{
            background: "var(--bg-input)",
            color: "var(--text-primary)",
            borderColor: matches ? "var(--accent-green)" : "var(--separator)",
          }}
          autoFocus
          onKeyDown={(e) => {
            if (e.key === "Enter" && matches) onConfirmed();
            if (e.key === "Escape") onCancel();
          }}
        />
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm rounded-md"
            style={{ background: "var(--accent-gray)", color: "#fff" }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirmed}
            disabled={!matches}
            className="px-4 py-2 text-sm rounded-md font-medium"
            style={{
              background: matches ? "var(--accent-red)" : "var(--accent-gray)",
              color: "#fff",
              opacity: matches ? 1 : 0.4,
              cursor: matches ? "pointer" : "not-allowed",
            }}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
