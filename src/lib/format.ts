/** Convert bytes to human-readable string — matches Python _bytes_to_display(). */
export function formatBytes(bytes: number): string {
  if (bytes < 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  for (const unit of units) {
    if (Math.abs(value) < 1024) {
      return unit === "B" ? `${value} B` : `${value.toFixed(1)} ${unit}`;
    }
    value /= 1024;
  }
  return `${value.toFixed(1)} PB`;
}
