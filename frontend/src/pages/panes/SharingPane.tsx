import { useState } from "react";

import {
  useCreateInvite,
  useInvites,
  useMembers,
  useRemoveMember,
  useRevokeInvite,
  useUpdateMemberRole,
} from "../../api/hooks";
import type { PlanInvite, PlanMember, PlanRole } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import { HelpTip } from "../../components/HelpTip";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { TableSkeleton } from "../../components/Skeleton";
import { useToast } from "../../components/Toast";
import { useSoftDelete } from "../../lib/useSoftDelete";

const ROLES: { value: PlanRole; label: string; help: string }[] = [
  { value: "viewer", label: "Viewer", help: "Read-only access to the plan and its projection." },
  { value: "editor", label: "Editor", help: "Can change income, expenses, assets, scenarios, and goals — but not delete the plan or change member roles." },
  { value: "owner", label: "Owner", help: "Full control: edit, delete, manage members, generate invites." },
];

const ROLE_COLORS: Record<PlanRole, { bg: string; fg: string }> = {
  owner: { bg: "#fef3c7", fg: "#92400e" },
  editor: { bg: "#dbeafe", fg: "#1e40af" },
  viewer: { bg: "#e2e8f0", fg: "#475569" },
};

export function SharingPane({ planId }: { planId: number }) {
  const auth = useAuth();
  const { data: members, isLoading } = useMembers(planId);
  const { data: invites } = useInvites(planId);
  const createInvite = useCreateInvite(planId);
  const revokeInvite = useRevokeInvite(planId);
  const updateRole = useUpdateMemberRole(planId);
  const removeMember = useRemoveMember(planId);

  const myUid = auth.status === "signed-in" ? auth.user.uid : null;
  // Derive my role from the members list (matched on Firebase email since the
  // PlanMember row is keyed by internal user_id, which the frontend doesn't track).
  const myEmail = auth.status === "signed-in" ? auth.user.email : null;
  const me = members?.find((m) => m.email && myEmail && m.email.toLowerCase() === myEmail.toLowerCase());
  const isOwner = me?.role === "owner";

  const [newRole, setNewRole] = useState<PlanRole>("viewer");
  const [emailBound, setEmailBound] = useState("");
  const [generatedLink, setGeneratedLink] = useState<string | null>(null);
  const toast = useToast();

  const softDeleteInvite = useSoftDelete<PlanInvite, { role: PlanRole; email: string | null }>({
    describe: (inv) => `invite (${inv.role}${inv.email ? `, ${inv.email}` : ""})`,
    toPayload: (inv) => ({ role: inv.role, email: inv.email }),
    remove: (id) => revokeInvite.mutate(id),
    recreate: (payload) => createInvite.mutate(payload),
    warnCascade: true,
  });

  const onGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    const inv = await createInvite.mutateAsync({
      role: newRole,
      email: emailBound.trim() || null,
    });
    const link = `${window.location.origin}/invites/${inv.token}`;
    setGeneratedLink(link);
    setEmailBound("");
  };

  const onCopy = async (link: string) => {
    try {
      await navigator.clipboard.writeText(link);
      toast.push({ kind: "success", message: "Invite link copied to clipboard." });
    } catch {
      toast.push({
        kind: "error",
        message: "Copy failed — select the link and copy manually.",
      });
    }
  };

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Members</h3>
        <p className="muted">
          Plans can be shared with other Meridian users at three permission levels —
          {ROLES.map((r) => (
            <span key={r.value}>
              {" "}
              <strong>{r.label}</strong>
              <HelpTip>{r.help}</HelpTip>
            </span>
          )).reduce<React.ReactNode[]>((acc, el, i) => (i ? [...acc, ", ", el] : [el]), [])}
          .
        </p>
        {isLoading && <TableSkeleton rows={2} />}
        {members && members.length > 0 && (
          <ResponsiveTable<PlanMember>
            rows={members}
            getKey={(m) => m.user_id}
            cardTitle={(m) => {
              const isMe = !!myEmail && m.email?.toLowerCase() === myEmail.toLowerCase();
              return (
                <>
                  {m.display_name || "—"}
                  {isMe && <span className="muted" style={{ marginLeft: 6 }}>(you)</span>}
                </>
              );
            }}
            columns={[
              {
                header: "Name",
                hideOnMobile: true,
                cell: (m) => {
                  const isMe = !!myEmail && m.email?.toLowerCase() === myEmail.toLowerCase();
                  return (
                    <>
                      {m.display_name || "—"}
                      {isMe && <span className="muted" style={{ marginLeft: 6 }}>(you)</span>}
                    </>
                  );
                },
              },
              {
                header: "Email",
                cell: (m) => <span className="muted">{m.email || "—"}</span>,
              },
              {
                header: "Role",
                cell: (m) => {
                  const isMe = !!myEmail && m.email?.toLowerCase() === myEmail.toLowerCase();
                  return isOwner && !isMe ? (
                    <select
                      value={m.role}
                      onChange={(e) =>
                        updateRole.mutate({
                          userId: m.user_id,
                          role: e.target.value as PlanRole,
                        })
                      }
                    >
                      {ROLES.map((r) => (
                        <option key={r.value} value={r.value}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <RoleBadge role={m.role} />
                  );
                },
              },
              {
                header: "Joined",
                cell: (m) => (
                  <span className="muted">
                    {new Date(m.created_at).toLocaleDateString()}
                  </span>
                ),
              },
            ]}
            renderActions={(m) => {
              const isMe = !!myEmail && m.email?.toLowerCase() === myEmail.toLowerCase();
              if (!(isOwner || isMe)) return null;
              return (
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    const label = isMe
                      ? "leave this plan"
                      : `remove ${m.display_name || m.email}`;
                    if (confirm(`Are you sure you want to ${label}?`)) {
                      removeMember.mutate(m.user_id);
                    }
                  }}
                >
                  {isMe ? "Leave plan" : "Remove"}
                </button>
              );
            }}
          />
        )}
      </div>

      {isOwner && (
        <>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>
              Invite by share link
              <HelpTip>
                Share-link invites: anyone with the link who's signed in to Meridian can accept and
                join with the role you pick. Lock it down to a specific email if you want only that
                person to be able to accept. Email delivery is on the roadmap — for now copy the
                link and send it via your channel of choice.
              </HelpTip>
            </h3>
            <form onSubmit={onGenerate} className="row" style={{ flexWrap: "wrap" }}>
              <div className="field">
                <label>Role</label>
                <select value={newRole} onChange={(e) => setNewRole(e.target.value as PlanRole)}>
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field" style={{ flex: "1 1 200px" }}>
                <label>Lock to email (optional)</label>
                <input
                  type="email"
                  placeholder="leave blank for anyone-with-link"
                  value={emailBound}
                  onChange={(e) => setEmailBound(e.target.value)}
                />
              </div>
              <button className="btn" type="submit" disabled={createInvite.isPending} style={{ alignSelf: "flex-end" }}>
                Generate link
              </button>
            </form>
            {generatedLink && (
              <div
                style={{
                  marginTop: 12,
                  padding: 12,
                  background: "#0f172a",
                  color: "#f8fafc",
                  borderRadius: 6,
                  fontSize: 13,
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                }}
              >
                <code style={{ flex: 1, wordBreak: "break-all" }}>{generatedLink}</code>
                <button className="btn" onClick={() => onCopy(generatedLink)}>
                  Copy
                </button>
              </div>
            )}
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Pending invites</h3>
            {invites && invites.length === 0 && (
              <p className="muted">No outstanding invites.</p>
            )}
            {invites && invites.length > 0 && (
              <ResponsiveTable<PlanInvite>
                rows={invites}
                getKey={(inv) => inv.id}
                cardTitle={(inv) => <RoleBadge role={inv.role} />}
                columns={[
                  {
                    header: "Role",
                    cell: (inv) => <RoleBadge role={inv.role} />,
                    hideOnMobile: true,
                  },
                  {
                    header: "Email lock",
                    cell: (inv) => (
                      <span className="muted">{inv.email || "anyone-with-link"}</span>
                    ),
                  },
                  {
                    header: "Expires",
                    cell: (inv) => (
                      <span className="muted">
                        {inv.expires_at
                          ? new Date(inv.expires_at).toLocaleDateString()
                          : "never"}
                      </span>
                    ),
                  },
                ]}
                renderActions={(inv) => {
                  const link = `${window.location.origin}/invites/${inv.token}`;
                  return (
                    <>
                      <button
                        className="btn btn-secondary"
                        style={{ marginRight: 6 }}
                        onClick={() => onCopy(link)}
                      >
                        Copy link
                      </button>
                      <button
                        className="btn btn-secondary"
                        onClick={() => softDeleteInvite(inv, inv.id)}
                      >
                        Revoke
                      </button>
                    </>
                  );
                }}
              />
            )}
          </div>
        </>
      )}

      {!isOwner && me && (
        <div className="card">
          <p className="muted">
            You are a <strong>{me.role}</strong> on this plan. Only owners can invite new members or change roles.
          </p>
        </div>
      )}

      {auth.status === "signed-in" && !me && myUid !== "dev-local" && (
        <div className="card">
          <p className="muted">
            Heads-up: your account isn't listed as a member of this plan. If you reached this page
            through a shared link, accept the invite first.
          </p>
        </div>
      )}
    </div>
  );
}

function RoleBadge({ role }: { role: PlanRole }) {
  const c = ROLE_COLORS[role];
  return (
    <span
      style={{
        background: c.bg,
        color: c.fg,
        padding: "2px 8px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        textTransform: "capitalize",
      }}
    >
      {role}
    </span>
  );
}
