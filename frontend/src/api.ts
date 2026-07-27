import type {
  DatasetInfo,
  PlanResult,
  Results,
  RunEvent,
  RunSnapshot,
  SampleDesignerRequest,
  ValidateResult,
} from "./types";

async function j0(res: Response) {
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
  }
}

export const api = {
  enums: (): Promise<{ datasets: DatasetInfo[]; enzymes: string[] }> =>
    fetch("/api/enums").then(j0),

  createProject: (): Promise<{ project_id: string }> =>
    fetch("/api/projects", { method: "POST" }).then(j0),

  validate: (pid: string, req: SampleDesignerRequest): Promise<ValidateResult> =>
    fetch(`/api/projects/${pid}/validate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(req),
    }).then(j0),

  plan: (pid: string, req: SampleDesignerRequest): Promise<PlanResult> =>
    fetch(`/api/projects/${pid}/plan`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(req),
    }).then(j0),

  startRun: (pid: string, req: SampleDesignerRequest): Promise<{ run_id: string; state: string }> =>
    fetch(`/api/projects/${pid}/runs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(req),
    }).then(j0),

  runSnapshot: (runId: string): Promise<RunSnapshot> =>
    fetch(`/api/runs/${runId}`).then(j0),

  cancelRun: (runId: string): Promise<unknown> =>
    fetch(`/api/runs/${runId}/cancel`, { method: "POST" }).then(j0),

  results: (runId: string): Promise<Results> =>
    fetch(`/api/runs/${runId}/results`).then(j0),
};

/** Subscribe to a run's SSE event stream. Returns an unsubscribe fn. */
export function streamEvents(
  runId: string,
  since: number,
  onEvent: (ev: RunEvent) => void,
  onEnd: () => void
): () => void {
  const es = new EventSource(`/api/runs/${runId}/events?since=${since}`);
  es.onmessage = (m) => {
    const ev = JSON.parse(m.data) as RunEvent;
    if (ev.kind === "eof") {
      es.close();
      onEnd();
      return;
    }
    onEvent(ev);
  };
  es.onerror = () => {
    // The stream closes cleanly on eof; an error here means the connection dropped.
    es.close();
    onEnd();
  };
  return () => es.close();
}
