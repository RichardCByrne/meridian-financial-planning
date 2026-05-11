import { Component, type ErrorInfo, type ReactNode } from "react";

type State = { error: Error | null };

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface in console for now. Phase 9 wires structured logging to Cloud Run.
    console.error("Meridian render error:", error, info);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div style={{ padding: 32, maxWidth: 720 }}>
        <h2 style={{ color: "#dc2626" }}>Something went wrong</h2>
        <p>
          The page hit an unexpected error and couldn't render. Your data is safe — try reloading.
          If it keeps happening, the error message below may help debug it.
        </p>
        <pre
          style={{
            background: "#0f172a",
            color: "#fecaca",
            padding: 12,
            borderRadius: 6,
            fontSize: 12,
            overflow: "auto",
            whiteSpace: "pre-wrap",
          }}
        >
          {this.state.error.message}
          {"\n\n"}
          {this.state.error.stack}
        </pre>
        <div style={{ marginTop: 16 }}>
          <button
            className="btn"
            onClick={() => {
              this.reset();
              window.location.reload();
            }}
          >
            Reload
          </button>
          <button className="btn btn-secondary" style={{ marginLeft: 8 }} onClick={this.reset}>
            Dismiss
          </button>
        </div>
      </div>
    );
  }
}
