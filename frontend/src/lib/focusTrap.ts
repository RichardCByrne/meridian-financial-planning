import { useEffect, useRef, type RefObject } from "react";

export const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface FocusTrapOptions {
  open: boolean;
  panelRef: RefObject<HTMLElement | null>;
  onClose: () => void;
  lockBodyScroll?: boolean;
}

export function useFocusTrap({
  open,
  panelRef,
  onClose,
  lockBodyScroll = true,
}: FocusTrapOptions) {
  // Hold onClose in a ref so an unstable inline `onClose={() => …}` from the
  // caller doesn't re-run this effect on every render — which would otherwise
  // re-fire the focus-on-open timeout and steal focus from inputs on each
  // keystroke. The effect should only set up/tear down when `open` flips.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    if (lockBodyScroll) document.body.style.overflow = "hidden";

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusables = Array.from(
        panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((el) => el.offsetParent !== null || el === document.activeElement);
      if (focusables.length === 0) {
        e.preventDefault();
        panel.focus();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && (active === first || !panel.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);

    const t = setTimeout(() => {
      const first = panelRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      (first ?? panelRef.current)?.focus();
    }, 0);

    return () => {
      window.removeEventListener("keydown", onKey);
      if (lockBodyScroll) document.body.style.overflow = prevOverflow;
      clearTimeout(t);
      if (previouslyFocused && document.contains(previouslyFocused) && typeof previouslyFocused.focus === "function") {
        previouslyFocused.focus();
      } else {
        document.body.focus?.();
      }
    };
  }, [open, panelRef, lockBodyScroll]);
}
