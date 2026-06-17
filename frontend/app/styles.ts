import type React from "react";

export const card: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #e5e7eb",
  borderRadius: 18,
  boxShadow: "0 14px 40px rgba(15, 23, 42, 0.06)",
  padding: 22,
};

export const input: React.CSSProperties = {
  width: "100%",
  padding: "11px 12px",
  marginTop: 10,
  boxSizing: "border-box",
  border: "1px solid #d1d5db",
  borderRadius: 10,
  font: "inherit",
  outlineColor: "#2563eb",
};

export const muted: React.CSSProperties = { color: "#6b7280" };

export const secondaryButton: React.CSSProperties = {
  padding: "7px 10px",
  border: "1px solid #d1d5db",
  borderRadius: 999,
  background: "#fff",
  color: "#374151",
  cursor: "pointer",
  font: "inherit",
};

export const archiveButton: React.CSSProperties = {
  ...secondaryButton,
  borderColor: "#fed7aa",
  background: "#fff7ed",
  color: "#c2410c",
  padding: "6px 10px",
  fontSize: 12,
  fontWeight: 700,
};

export const restoreButton: React.CSSProperties = {
  ...secondaryButton,
  borderColor: "#bbf7d0",
  background: "#ecfdf5",
  color: "#047857",
  padding: "6px 10px",
  fontSize: 12,
  fontWeight: 700,
};

export function primaryButton(disabled: boolean): React.CSSProperties {
  return {
    padding: "10px 16px",
    border: 0,
    borderRadius: 10,
    background: "#111827",
    color: "white",
    cursor: disabled ? "not-allowed" : "pointer",
    fontWeight: 700,
    opacity: disabled ? 0.5 : 1,
  };
}
