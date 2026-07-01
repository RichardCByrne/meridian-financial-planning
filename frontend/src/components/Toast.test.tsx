import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider, useToast, emitToast } from "./Toast";

// A tiny consumer that fires a toast on mount so we can assert it renders.
function Emitter({ message, kind = "info" }: { message: string; kind?: "info" | "error" }) {
  const { push } = useToast();
  return (
    <button type="button" onClick={() => push({ kind, message })}>
      emit
    </button>
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe("ToastProvider", () => {
  it("renders a pushed toast message", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Emitter message="Saved changes" />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "emit" }));
    expect(screen.getByText("Saved changes")).toBeInTheDocument();
  });

  it("dismisses a toast when the dismiss button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Emitter message="Dismiss me" />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "emit" }));
    expect(screen.getByText("Dismiss me")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("Dismiss me")).not.toBeInTheDocument();
  });

  it("auto-dismisses after the kind-based timeout", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Emitter message="Auto gone" kind="info" />
      </ToastProvider>,
    );
    act(() => {
      screen.getByRole("button", { name: "emit" }).click();
    });
    expect(screen.getByText("Auto gone")).toBeInTheDocument();
    // info toasts default to 4000ms.
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByText("Auto gone")).not.toBeInTheDocument();
  });

  it("emitToast bridges from non-component callers into the rendered provider", () => {
    render(
      <ToastProvider>
        <div />
      </ToastProvider>,
    );
    act(() => {
      emitToast({ kind: "error", message: "From the bridge" });
    });
    expect(screen.getByText("From the bridge")).toBeInTheDocument();
  });
});
