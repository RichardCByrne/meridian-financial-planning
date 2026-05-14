import { useState, useSyncExternalStore } from "react";

import { BottomSheet } from "./BottomSheet";

export interface SelectOption<T extends string | number> {
  value: T;
  label: string;
  description?: string;
  disabled?: boolean;
}

export interface ResponsiveSelectProps<T extends string | number> {
  value: T;
  onChange: (v: T) => void;
  options: SelectOption<T>[];
  label?: string;
  placeholder?: string;
  id?: string;
  disabled?: boolean;
}

const MQ = "(min-width: 768px)";

function subscribeMq(callback: () => void): () => void {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  const mq = window.matchMedia(MQ);
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getMqSnapshot(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return true;
  return window.matchMedia(MQ).matches;
}

function getServerSnapshot(): boolean {
  return true;
}

function useIsDesktop(): boolean {
  return useSyncExternalStore(subscribeMq, getMqSnapshot, getServerSnapshot);
}

export function ResponsiveSelect<T extends string | number>({
  value,
  onChange,
  options,
  label,
  placeholder,
  id,
  disabled,
}: ResponsiveSelectProps<T>) {
  const isDesktop = useIsDesktop();
  const [open, setOpen] = useState(false);

  const selected = options.find((o) => o.value === value);

  if (isDesktop) {
    return (
      <select
        id={id}
        value={String(value)}
        disabled={disabled}
        onChange={(e) => {
          const raw = e.target.value;
          const matched = options.find((o) => String(o.value) === raw);
          if (matched) onChange(matched.value);
        }}
        aria-label={label}
        style={{
          padding: "8px 10px",
          border: "1px solid #cbd5e1",
          borderRadius: 6,
          fontSize: 16,
          minHeight: 44,
          background: "white",
        }}
      >
        {placeholder && !selected && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((o) => (
          <option key={String(o.value)} value={String(o.value)} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
    );
  }

  return (
    <>
      <button
        type="button"
        id={id}
        disabled={disabled}
        onClick={() => setOpen(true)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={label}
        style={{
          padding: "10px 12px",
          border: "1px solid #cbd5e1",
          borderRadius: 6,
          fontSize: 16,
          minHeight: 44,
          background: "white",
          textAlign: "left",
          cursor: "pointer",
          color: selected ? "#0f172a" : "#94a3b8",
        }}
      >
        {selected?.label ?? placeholder ?? "Select…"}
      </button>
      <BottomSheet open={open} onClose={() => setOpen(false)} title={label}>
        <ul role="listbox" aria-label={label} style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {options.map((o) => {
            const isSelected = o.value === value;
            return (
              <li key={String(o.value)} role="option" aria-selected={isSelected}>
                <button
                  type="button"
                  disabled={o.disabled}
                  onClick={() => {
                    onChange(o.value);
                    setOpen(false);
                  }}
                  style={{
                    width: "100%",
                    minHeight: 44,
                    padding: "10px 8px",
                    background: isSelected ? "#eff6ff" : "transparent",
                    border: 0,
                    borderBottom: "1px solid #f1f5f9",
                    textAlign: "left",
                    cursor: o.disabled ? "not-allowed" : "pointer",
                    opacity: o.disabled ? 0.5 : 1,
                  }}
                >
                  <div style={{ fontSize: 16, color: "#0f172a" }}>{o.label}</div>
                  {o.description && (
                    <div style={{ fontSize: 13, color: "#64748b", marginTop: 2 }}>
                      {o.description}
                    </div>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </BottomSheet>
    </>
  );
}
