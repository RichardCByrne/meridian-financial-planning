/**
 * NumericInput — a text field that behaves like a number input but without the
 * browser's type="number" quirks (no spinners, no rejection of intermediate
 * states like "2." or "-").
 *
 * - While focused: raw text editing; any character sequence is allowed.
 * - On focus: selects all existing text so the user can overwrite immediately.
 * - On blur / Enter: parses the string and calls onChange.
 *   If the field is empty or unparseable, onChange is called with NaN — the
 *   parent decides whether that means "keep old value" or "treat as null".
 * - When not focused: displays the formatted value (no trailing precision noise).
 */

import { useState } from "react";

interface NumericInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> {
  value: number;
  /** Called with the parsed float, or NaN if empty / invalid. */
  onChange: (value: number) => void;
  /** Round to integer on commit (e.g. years, months). */
  integer?: boolean;
  /** Override the display format when not focused. Defaults to compact float representation. */
  format?: (v: number) => string;
}

function defaultFmt(v: number, integer: boolean): string {
  if (!Number.isFinite(v)) return "";
  if (integer) return String(Math.round(v));
  // Strip floating-point noise up to 10 significant figures, then remove trailing zeros.
  return String(parseFloat(v.toPrecision(10)));
}

export function NumericInput({
  value,
  onChange,
  integer = false,
  format,
  onFocus,
  onBlur,
  onKeyDown,
  ...rest
}: NumericInputProps) {
  const [raw, setRaw] = useState<string | null>(null);
  const fmt = format ?? ((v: number) => defaultFmt(v, integer));

  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    const display = fmt(value);
    setRaw(display);
    // Select all after a frame so the browser doesn't reset cursor position.
    requestAnimationFrame(() => e.target.select());
    onFocus?.(e);
  };

  const commit = (s: string) => {
    const trimmed = s.trim();
    if (trimmed === "") {
      onChange(NaN);
    } else {
      const parsed = parseFloat(trimmed);
      onChange(integer && Number.isFinite(parsed) ? Math.round(parsed) : parsed);
    }
    setRaw(null);
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    if (raw !== null) commit(raw);
    onBlur?.(e);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") (e.target as HTMLInputElement).blur();
    onKeyDown?.(e);
  };

  return (
    <input
      {...rest}
      type="text"
      inputMode={integer ? "numeric" : "decimal"}
      value={raw !== null ? raw : fmt(value)}
      onChange={(e) => setRaw(e.target.value)}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
    />
  );
}
