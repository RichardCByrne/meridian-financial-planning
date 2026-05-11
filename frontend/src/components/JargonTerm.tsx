import type { ReactNode } from "react";

import { GLOSSARY, type GlossaryKey } from "../copy/glossary";

// Inline glossary term: underlines the word and shows a tooltip on hover/focus.
// Reuses the .helptip-bubble styling so jargon hints match HelpTip visually.
//
// Usage:
//   <JargonTerm term="PRSI" />              → renders "PRSI" with hover def
//   <JargonTerm term="PRSI">PRSI rate</JargonTerm> → custom label, same def
export function JargonTerm({
  term,
  children,
}: {
  term: GlossaryKey;
  children?: ReactNode;
}) {
  const entry = GLOSSARY[term];
  const label = children ?? entry.short;
  return (
    <span
      className="jargon-term"
      tabIndex={0}
      role="button"
      aria-label={`${entry.short}: ${entry.body}`}
    >
      {label}
      <span className="helptip-bubble">
        <strong style={{ display: "block", marginBottom: 2 }}>{entry.short}</strong>
        {entry.body}
      </span>
    </span>
  );
}
