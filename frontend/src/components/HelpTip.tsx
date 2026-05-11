import type { ReactNode } from "react";

export function HelpTip({ children }: { children: ReactNode }) {
  return (
    <span className="helptip" tabIndex={0} role="img" aria-label="Help">
      ?
      <span className="helptip-bubble">{children}</span>
    </span>
  );
}
