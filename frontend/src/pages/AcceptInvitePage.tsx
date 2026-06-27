import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { useAcceptInvite, usePreviewInvite } from "../api/hooks";
import { useAuth } from "../auth/useAuth";

export function AcceptInvitePage() {
  const { token = "" } = useParams<{ token: string }>();
  const auth = useAuth();
  const navigate = useNavigate();
  const preview = usePreviewInvite(token);
  const accept = useAcceptInvite();
  const [error, setError] = useState<string | null>(null);

  if (auth.status === "loading") {
    return <p className="muted" style={{ padding: 32 }}>Checking sign-in…</p>;
  }
  if (auth.status === "signed-out") {
    // Bounce through login then come back here.
    return <Navigate to="/login" replace state={{ from: `/invites/${token}` }} />;
  }

  const onAccept = async () => {
    setError(null);
    try {
      const inv = await accept.mutateAsync(token);
      navigate(`/plans/${inv.plan_id}`, { replace: true });
    } catch {
      setError(
        "We couldn't accept this invite. It may have expired, been revoked, or already been used.",
      );
    }
  };

  return (
    <div style={{ maxWidth: 560 }}>
      <h2>Plan invite</h2>
      {preview.isLoading && <p className="muted">Loading invite…</p>}
      {preview.error && (
        <div className="card">
          <p style={{ color: "#dc2626" }}>
            This invite isn't valid. It may have expired, been revoked, or already been accepted.
          </p>
          <p>
            <Link to="/plans">← Back to your plans</Link>
          </p>
        </div>
      )}
      {preview.data && (
        <div className="card">
          <p>
            <strong>{preview.data.inviter_display_name || "Someone"}</strong> has invited you to
            join the plan <strong>{preview.data.plan_name}</strong> as a{" "}
            <strong>{preview.data.role}</strong>.
          </p>
          {preview.data.email_bound && (
            <p className="muted">
              This invite is locked to a specific email address. You'll only be able to accept it
              from the matching account.
            </p>
          )}
          {preview.data.expires_at && (() => {
            const d = new Date(preview.data.expires_at);
            if (Number.isNaN(d.getTime())) return null;
            return <p className="muted">Expires {d.toLocaleString()}</p>;
          })()}
          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn" onClick={onAccept} disabled={accept.isPending}>
              {accept.isPending ? "Accepting…" : "Accept invite"}
            </button>
            <Link to="/plans" className="btn btn-secondary" style={{ textDecoration: "none" }}>
              Decline
            </Link>
          </div>
          {error && <p style={{ color: "#dc2626", marginTop: 12 }}>{error}</p>}
        </div>
      )}
    </div>
  );
}
