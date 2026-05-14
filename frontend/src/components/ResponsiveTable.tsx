import { Fragment, type Key, type ReactNode } from "react";

import { useIsMobile } from "../hooks/useIsMobile";

export type Column<T> = {
  header: string;
  cell: (row: T) => ReactNode;
  align?: "left" | "right";
  hideOnMobile?: boolean;
  thExtra?: ReactNode;
};

export function ResponsiveTable<T>({
  rows,
  columns,
  getKey,
  renderActions,
  emptyMessage,
  cardTitle,
}: {
  rows: T[];
  columns: Column<T>[];
  getKey: (row: T) => Key;
  renderActions?: (row: T) => ReactNode;
  emptyMessage?: ReactNode;
  cardTitle?: (row: T) => ReactNode;
}) {
  const isMobile = useIsMobile();

  if (rows.length === 0) return emptyMessage ? <>{emptyMessage}</> : null;

  if (isMobile) {
    return (
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {rows.map((r) => (
          <li
            key={getKey(r)}
            style={{
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              padding: 12,
              marginBottom: 10,
            }}
          >
            {cardTitle && (
              <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>
                {cardTitle(r)}
              </div>
            )}
            <dl
              style={{
                display: "grid",
                gridTemplateColumns: "max-content 1fr",
                columnGap: 12,
                rowGap: 6,
                margin: 0,
              }}
            >
              {columns
                .filter((c) => !c.hideOnMobile)
                .map((c) => (
                  <Fragment key={c.header}>
                    <dt
                      style={{
                        color: "#64748b",
                        fontSize: 11,
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.04em",
                        alignSelf: "center",
                      }}
                    >
                      {c.header}
                    </dt>
                    <dd style={{ margin: 0, fontSize: 14, wordBreak: "break-word" }}>
                      {c.cell(r)}
                    </dd>
                  </Fragment>
                ))}
            </dl>
            {renderActions && (
              <div
                style={{
                  marginTop: 12,
                  display: "flex",
                  gap: 8,
                  flexWrap: "nowrap",
                }}
              >
                {renderActions(r)}
              </div>
            )}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div style={{ overflowX: "auto", width: "100%" }}>
      <table>
          <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.header} style={c.align ? { textAlign: c.align } : undefined}>
                {c.header}
                {c.thExtra}
              </th>
            ))}
            {renderActions && <th />}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={getKey(r)}>
              {columns.map((c) => (
                <td key={c.header} style={c.align ? { textAlign: c.align } : undefined}>
                  {c.cell(r)}
                </td>
              ))}
              {renderActions && (
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {renderActions(r)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
