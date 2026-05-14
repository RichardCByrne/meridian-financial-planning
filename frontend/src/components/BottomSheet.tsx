import { useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";

import { useFocusTrap } from "../lib/focusTrap";

export interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  snapPoints?: Array<"50%" | "90%" | "full">;
  initialSnap?: number;
  dismissOnOverlay?: boolean;
  dismissOnSwipeDown?: boolean;
  children: ReactNode;
}

const DISMISS_DRAG_PX = 80;
const DISMISS_VELOCITY = 0.6;

function snapToHeight(snap: "50%" | "90%" | "full"): string {
  if (snap === "full") return "100vh";
  return `calc(${snap === "50%" ? "50vh" : "90vh"})`;
}

export function BottomSheet({
  open,
  onClose,
  title,
  snapPoints = ["90%"],
  initialSnap = 0,
  dismissOnOverlay = true,
  dismissOnSwipeDown = true,
  children,
}: BottomSheetProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const dragStart = useRef<{ y: number; t: number } | null>(null);
  const [dragOffset, setDragOffset] = useState(0);

  useFocusTrap({ open, panelRef, onClose });

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!dismissOnSwipeDown) return;
    dragStart.current = { y: e.clientY, t: Date.now() };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragStart.current) return;
    const dy = e.clientY - dragStart.current.y;
    setDragOffset(Math.max(0, dy));
  };
  const onPointerUp = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragStart.current) return;
    const dy = e.clientY - dragStart.current.y;
    const dt = Math.max(1, Date.now() - dragStart.current.t);
    const v = dy / dt;
    dragStart.current = null;
    setDragOffset(0);
    if (dy > DISMISS_DRAG_PX || v > DISMISS_VELOCITY) onClose();
  };

  if (!open) return null;

  const snap = snapPoints[initialSnap] ?? snapPoints[0] ?? "90%";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onMouseDown={(e) => {
        if (dismissOnOverlay && e.target === e.currentTarget) onClose();
      }}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15, 23, 42, 0.45)",
        zIndex: 1100,
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
      }}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        style={{
          background: "white",
          width: "100%",
          maxWidth: 640,
          height: snapToHeight(snap),
          transform: `translateY(${dragOffset}px)`,
          transition: dragStart.current ? "none" : "transform 160ms ease-out",
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          boxShadow: "0 -10px 30px rgba(0,0,0,0.18)",
          display: "flex",
          flexDirection: "column",
          paddingBottom: "env(safe-area-inset-bottom)",
        }}
      >
        <div
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          style={{
            padding: "10px 0",
            display: "flex",
            justifyContent: "center",
            cursor: "grab",
            touchAction: "none",
          }}
          aria-hidden="true"
        >
          <div style={{ width: 40, height: 4, borderRadius: 2, background: "#cbd5e1" }} />
        </div>
        {title && (
          <div
            className="row"
            style={{
              justifyContent: "space-between",
              alignItems: "center",
              padding: "0 16px 8px",
            }}
          >
            <h3 style={{ margin: 0, fontSize: 16 }}>{title}</h3>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              style={{
                background: "transparent",
                border: 0,
                fontSize: 22,
                lineHeight: 1,
                padding: "4px 8px",
                cursor: "pointer",
                color: "#64748b",
                minWidth: 44,
                minHeight: 44,
              }}
            >
              ×
            </button>
          </div>
        )}
        <div style={{ flex: 1, overflowY: "auto", padding: "0 16px 16px" }}>{children}</div>
      </div>
    </div>
  );
}
