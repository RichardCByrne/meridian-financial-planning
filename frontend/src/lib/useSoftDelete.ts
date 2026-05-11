import { useToast } from "../components/Toast";

// Generic soft-delete with 8s Undo toast. Backend does a hard delete; Undo
// re-creates the entity from the cached payload. New row gets a new id, so
// any cascades (linked scenarios, members, etc.) are not restored — callers
// that care about cascades should warn in the toast message.
export function useSoftDelete<T, P>(opts: {
  describe: (entity: T) => string;
  toPayload: (entity: T) => P;
  remove: (id: number) => void;
  recreate: (payload: P) => void;
  warnCascade?: boolean;
}) {
  const toast = useToast();
  return (entity: T, id: number) => {
    const payload = opts.toPayload(entity);
    opts.remove(id);
    const cascadeNote = opts.warnCascade ? " (Undo creates a fresh copy; linked items not restored.)" : "";
    toast.push({
      kind: "info",
      message: `Deleted ${opts.describe(entity)}.${cascadeNote}`,
      autoDismissMs: 8000,
      action: {
        label: "Undo",
        onClick: () => opts.recreate(payload),
      },
    });
  };
}
