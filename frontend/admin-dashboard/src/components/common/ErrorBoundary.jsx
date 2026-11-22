import { Component } from "react";

/**
 * Catches any render-time exception and shows it instead of a blank screen.
 *
 * Without this, a single thrown error in any provider, layout or page unmounts
 * the whole React tree and leaves the user staring at an empty white page with
 * no hint of what happened — the failure is only visible in the browser console,
 * which nobody has open. React requires a class component for this; there is no
 * hook equivalent.
 *
 * Deliberately dependency-free and inline-styled so it still works when the
 * failure is caused by CSS or by a third-party module that never loaded.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Keep the details for the report panel; also surface them in the console
    // with the component stack, which is what support needs to fix the bug.
    this.setState({ info });
    // eslint-disable-next-line no-console
    console.error("UMS Mart crashed while rendering:", error, info?.componentStack);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    try {
      window.localStorage.clear();
      window.sessionStorage.clear();
    } catch {
      /* storage unavailable — reload anyway */
    }
    window.location.href = "/";
  };

  render() {
    const { error, info } = this.state;
    if (!error) return this.props.children;

    const message = error?.message || String(error);
    const stack = (info?.componentStack || "").trim().split("\n").slice(0, 8).join("\n");

    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <div style={styles.badge}>Something went wrong</div>
          <h1 style={styles.h1}>This page could not be displayed</h1>
          <p style={styles.p}>
            A part of the app threw an error while rendering, so the whole page was
            replaced by this message. Your data is unaffected.
          </p>

          <div style={styles.codeBlock}>
            <strong style={styles.codeLabel}>Error</strong>
            <pre style={styles.pre}>{message}</pre>
            {stack ? (
              <>
                <strong style={styles.codeLabel}>Where</strong>
                <pre style={styles.pre}>{stack}</pre>
              </>
            ) : null}
          </div>

          <div style={styles.actions}>
            <button type="button" onClick={this.handleReload} style={styles.primary}>
              Reload the page
            </button>
            <button type="button" onClick={this.handleReset} style={styles.secondary}>
              Clear saved data and restart
            </button>
          </div>

          <p style={styles.hint}>
            If this keeps happening, check that the API is running at{" "}
            <code style={styles.inline}>http://127.0.0.1:8000/health/</code> and that
            you opened the app at <code style={styles.inline}>http://localhost:5173</code>{" "}
            — not by double-clicking a built file.
          </p>
        </div>
      </div>
    );
  }
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#f8fafc",
    padding: "24px",
    fontFamily:
      'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  },
  card: {
    maxWidth: "640px",
    width: "100%",
    background: "#fff",
    border: "1px solid #e2e8f0",
    borderRadius: "16px",
    padding: "28px",
    boxShadow: "0 1px 3px rgba(15,23,42,.06)",
  },
  badge: {
    display: "inline-block",
    background: "#fef2f2",
    color: "#b91c1c",
    border: "1px solid #fecaca",
    borderRadius: "999px",
    padding: "4px 12px",
    fontSize: "12px",
    fontWeight: 700,
    letterSpacing: ".02em",
  },
  h1: { fontSize: "22px", margin: "14px 0 6px", color: "#0f172a" },
  p: { margin: "0 0 16px", color: "#475569", fontSize: "14px", lineHeight: 1.6 },
  codeBlock: {
    background: "#0f172a",
    borderRadius: "10px",
    padding: "14px 16px",
    marginBottom: "18px",
  },
  codeLabel: {
    display: "block",
    color: "#94a3b8",
    fontSize: "11px",
    textTransform: "uppercase",
    letterSpacing: ".06em",
    marginBottom: "4px",
    marginTop: "8px",
  },
  pre: {
    margin: 0,
    color: "#f1f5f9",
    fontSize: "12.5px",
    lineHeight: 1.55,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  },
  actions: { display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "16px" },
  primary: {
    background: "#4f46e5",
    color: "#fff",
    border: 0,
    borderRadius: "8px",
    padding: "10px 18px",
    fontSize: "14px",
    fontWeight: 600,
    cursor: "pointer",
  },
  secondary: {
    background: "#fff",
    color: "#334155",
    border: "1px solid #cbd5e1",
    borderRadius: "8px",
    padding: "10px 18px",
    fontSize: "14px",
    fontWeight: 600,
    cursor: "pointer",
  },
  hint: { margin: 0, fontSize: "12.5px", color: "#64748b", lineHeight: 1.6 },
  inline: {
    background: "#f1f5f9",
    padding: "1px 5px",
    borderRadius: "4px",
    fontSize: "12px",
  },
};
