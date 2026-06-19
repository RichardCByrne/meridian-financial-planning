import { fmtMoney } from "../lib/format";

/** Right-aligned total shown in a pane's card header (e.g. "Total value €X").
 * Mirrors the summary the Expenses tab shows. */
export function PaneTotal({
  label,
  amount,
  suffix,
}: {
  label: string;
  amount: number;
  suffix?: string;
}) {
  return (
    <div className="muted" style={{ fontSize: 13, textAlign: "right" }}>
      {label}: <strong style={{ color: "#0f172a" }}>{fmtMoney(amount)}</strong>
      {suffix ? ` ${suffix}` : ""}
    </div>
  );
}
