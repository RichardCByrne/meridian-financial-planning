import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  exportPlan,
  useClonePlan,
  useCreatePlan,
  useDeletePlan,
  useImportPlan,
  usePlans,
} from "../api/hooks";
import { TableSkeleton } from "../components/Skeleton";
import { buildSampleHouseholdPayload } from "../lib/sampleHousehold";

export function PlansListPage() {
  const { data, isLoading, error } = usePlans();
  const createPlan = useCreatePlan();
  const deletePlan = useDeletePlan();
  const clonePlan = useClonePlan();
  const importPlan = useImportPlan();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [sampleBusy, setSampleBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const onCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    await createPlan.mutateAsync({ name: name.trim() });
    setName("");
  };

  const onExport = async (id: number, planName: string) => {
    setBusyId(id);
    try {
      const dump = await exportPlan(id);
      const blob = new Blob([JSON.stringify(dump, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${planName.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-${id}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setBusyId(null);
    }
  };

  const onSeedSample = async () => {
    setSampleBusy(true);
    try {
      const plan = await importPlan.mutateAsync(buildSampleHouseholdPayload());
      navigate(`/plans/${plan.id}`);
    } catch (e) {
      alert(`Couldn't create sample plan: ${e}`);
    } finally {
      setSampleBusy(false);
    }
  };

  const onImportFile = async (file: File) => {
    const text = await file.text();
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(text);
    } catch {
      alert("That file isn't valid JSON.");
      return;
    }
    try {
      await importPlan.mutateAsync(payload);
    } catch (e) {
      alert(`Import failed: ${e}`);
    }
  };

  const isEmpty = data && data.length === 0;

  return (
    <div>
      <h2>Plans</h2>

      {isEmpty && (
        <div className="card" style={{ background: "#eff6ff", borderLeft: "4px solid #2563eb" }}>
          <h3 style={{ marginTop: 0 }}>New here? Start with a sample household.</h3>
          <p style={{ marginTop: 0, color: "#334155" }}>
            We'll seed a two-earner Irish household with a mortgage, pensions, and a retirement
            goal — enough to see a full projection in seconds. You can edit or delete it after.
          </p>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn"
              onClick={onSeedSample}
              disabled={sampleBusy || importPlan.isPending}
            >
              {sampleBusy ? "Creating sample…" : "Try a sample plan"}
            </button>
            <Link
              to="#"
              onClick={(e) => {
                e.preventDefault();
                document.getElementById("plan-name-input")?.focus();
              }}
              style={{ alignSelf: "center" }}
            >
              or start from scratch ↓
            </Link>
          </div>
        </div>
      )}

      <div className="card">
        <form onSubmit={onCreate} className="row" style={{ flexWrap: "wrap" }}>
          <input
            id="plan-name-input"
            placeholder="New plan name (e.g. Smith household)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ flex: 1, minWidth: 220, padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: 6 }}
          />
          <button type="submit" className="btn" disabled={createPlan.isPending}>
            {createPlan.isPending ? "Creating…" : "Create plan"}
          </button>
          {!isEmpty && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onSeedSample}
              disabled={sampleBusy || importPlan.isPending}
              title="Seed a populated example household"
            >
              {sampleBusy ? "Creating sample…" : "Try a sample plan"}
            </button>
          )}
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => fileInputRef.current?.click()}
            disabled={importPlan.isPending}
          >
            {importPlan.isPending ? "Importing…" : "Import JSON"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onImportFile(f);
              e.target.value = "";
            }}
          />
        </form>
      </div>

      {isLoading && (
        <div className="card">
          <TableSkeleton rows={3} />
        </div>
      )}
      {error && <p style={{ color: "#dc2626" }}>Failed to load: {String(error)}</p>}

      {data && data.length > 0 && (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Base year</th>
                <th>Years</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id}>
                  <td>
                    <Link to={`/plans/${p.id}`}>{p.name}</Link>
                  </td>
                  <td>{p.base_year}</td>
                  <td>{p.projection_years}</td>
                  <td className="muted">{new Date(p.created_at).toLocaleDateString()}</td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      className="btn btn-secondary"
                      style={{ marginRight: 6 }}
                      onClick={() => clonePlan.mutate({ id: p.id })}
                      disabled={clonePlan.isPending}
                    >
                      Duplicate
                    </button>
                    <button
                      className="btn btn-secondary"
                      style={{ marginRight: 6 }}
                      onClick={() => onExport(p.id, p.name)}
                      disabled={busyId === p.id}
                    >
                      {busyId === p.id ? "…" : "Export"}
                    </button>
                    <button
                      className="btn btn-secondary"
                      onClick={() => {
                        if (confirm(`Delete plan "${p.name}"? This is permanent.`)) {
                          deletePlan.mutate(p.id);
                        }
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
