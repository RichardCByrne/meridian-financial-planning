import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Collaborators are mocked so we test the request/response contract in
// isolation: auth-header injection, 401 redirect + one-shot toast, error
// propagation, and 204/JSON handling.
const getCurrentUserForApi = vi.fn();
const emitToast = vi.fn();

vi.mock("../auth/useAuth", () => ({
  getCurrentUserForApi: () => getCurrentUserForApi(),
}));
vi.mock("../components/Toast", () => ({
  emitToast: (t: unknown) => emitToast(t),
}));

const assign = vi.fn();

function res(init: {
  status: number;
  ok?: boolean;
  json?: unknown;
  text?: string;
}) {
  return {
    status: init.status,
    ok: init.ok ?? (init.status >= 200 && init.status < 300),
    json: async () => init.json,
    text: async () => init.text ?? "",
  } as Response;
}

// Re-import the module fresh each test so the module-level `toastedUnauthorized`
// latch resets between cases.
async function freshApi() {
  vi.resetModules();
  return (await import("./client")).api;
}

beforeEach(() => {
  getCurrentUserForApi.mockReset();
  emitToast.mockReset();
  assign.mockReset();
  getCurrentUserForApi.mockReturnValue(null);
  vi.stubGlobal("fetch", vi.fn());
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { pathname: "/plans", search: "?tab=assets", assign },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api request success paths", () => {
  it("GET returns parsed JSON from BASE + path", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(res({ status: 200, json: { id: 1 } }));
    const api = await freshApi();
    const out = await api.get<{ id: number }>("/plans/1");
    expect(out).toEqual({ id: 1 });
    expect(fetch).toHaveBeenCalledWith("/api/plans/1", expect.objectContaining({ method: "GET" }));
  });

  it("204 resolves to undefined without parsing a body", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(res({ status: 204 }));
    const api = await freshApi();
    await expect(api.del("/plans/1")).resolves.toBeUndefined();
  });

  it("POST sends JSON body and Content-Type", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(res({ status: 201, json: { ok: true } }));
    const api = await freshApi();
    await api.post("/plans", { name: "X" });
    const [, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(opts.method).toBe("POST");
    expect(opts.body).toBe(JSON.stringify({ name: "X" }));
    expect(opts.headers["Content-Type"]).toBe("application/json");
  });

  it("attaches a bearer token when a user is signed in", async () => {
    getCurrentUserForApi.mockReturnValue({ getIdToken: async () => "tok-123" });
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(res({ status: 200, json: {} }));
    const api = await freshApi();
    await api.get("/me");
    const [, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(opts.headers.Authorization).toBe("Bearer tok-123");
  });
});

describe("api error paths", () => {
  it("throws with method, path and status on a non-ok response", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      res({ status: 500, ok: false, text: "boom" }),
    );
    const api = await freshApi();
    await expect(api.get("/plans/1")).rejects.toThrow(/GET \/plans\/1 failed: 500 boom/);
  });

  it("401 emits one toast, redirects to /login with next, and throws", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(res({ status: 401, ok: false }));
    const api = await freshApi();
    await expect(api.get("/plans/1")).rejects.toThrow("Not authenticated");
    expect(emitToast).toHaveBeenCalledTimes(1);
    expect(emitToast).toHaveBeenCalledWith(expect.objectContaining({ kind: "error" }));
    expect(assign).toHaveBeenCalledWith("/login?next=" + encodeURIComponent("/plans?tab=assets"));
  });

  it("401 only toasts once per page load, but still redirects each time", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(res({ status: 401, ok: false }));
    const api = await freshApi();
    await expect(api.get("/a")).rejects.toThrow("Not authenticated");
    await expect(api.get("/b")).rejects.toThrow("Not authenticated");
    expect(emitToast).toHaveBeenCalledTimes(1);
    expect(assign).toHaveBeenCalledTimes(2);
  });

  it("does not redirect when already on the login page", async () => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { pathname: "/login", search: "", assign },
    });
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(res({ status: 401, ok: false }));
    const api = await freshApi();
    await expect(api.get("/plans/1")).rejects.toThrow("Not authenticated");
    expect(assign).not.toHaveBeenCalled();
    expect(emitToast).not.toHaveBeenCalled();
  });
});
