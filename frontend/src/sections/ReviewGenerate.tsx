import { useRef, useState } from "react";
import { api, ApiError, streamEvents } from "../api";
import type { PlanResult, Results, SampleDesignerRequest, ValidateResult } from "../types";
import { Card, Collapsible } from "../components/ui";

// Section ④. Review the design, preview what will run, generate, and read the results in one place.
export function ReviewGenerate(props: { projectId: string; req: SampleDesignerRequest }) {
  const { projectId, req } = props;
  const [val, setVal] = useState<ValidateResult | null>(null);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [runId, setRunId] = useState<string | null>(null);
  const [runState, setRunState] = useState<string | null>(null);
  const [nodePhase, setNodePhase] = useState<Record<string, string>>({});
  const [logLines, setLogLines] = useState<string[]>([]);
  const [results, setResults] = useState<Results | null>(null);
  const unsub = useRef<(() => void) | null>(null);

  const guard = async (name: string, fn: () => Promise<void>) => {
    setErr(null);
    setBusy(name);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof ApiError ? String(e.detail) : String(e));
    } finally {
      setBusy(null);
    }
  };

  const doValidate = () => guard("validate", async () => setVal(await api.validate(projectId, req)));
  const doPlan = () => guard("plan", async () => setPlan(await api.plan(projectId, req)));

  const doRun = () =>
    guard("run", async () => {
      setResults(null);
      setNodePhase({});
      setLogLines([]);
      setRunState("queued");
      const { run_id } = await api.startRun(projectId, req);
      setRunId(run_id);
      unsub.current?.();
      unsub.current = streamEvents(
        run_id,
        0,
        (ev) => {
          if (ev.kind === "node" && ev.node)
            setNodePhase((p) => ({ ...p, [ev.node!]: ev.phase ?? "" }));
          else if (ev.kind === "log" && ev.line)
            setLogLines((l) => [...l.slice(-200), ev.line!]);
          else if (ev.kind === "state" && ev.state) setRunState(ev.state);
        },
        async () => {
          const snap = await api.runSnapshot(run_id);
          setRunState(snap.state);
          if (snap.state === "succeeded") setResults(await api.results(run_id));
          else if (snap.error) setErr(snap.error);
        }
      );
    });

  const doCancel = () =>
    guard("cancel", async () => {
      if (runId) await api.cancelRun(runId);
    });

  const running = runState === "queued" || runState === "running";

  return (
    <>
      <Card title="Review & generate">
        <div className="button-row">
          <button onClick={doValidate} disabled={!!busy}>Check design</button>
          <button onClick={doPlan} disabled={!!busy}>Preview run</button>
          <button className="primary" onClick={doRun} disabled={!!busy || running}>
            Generate sample
          </button>
          {running && <button className="danger" onClick={doCancel}>Cancel</button>}
        </div>
        {err && <p className="warn-text">{err}</p>}

        {val && (
          <div className="validate-out">
            <h4>Resolved mixtures</h4>
            {val.conditions.map((c) => (
              <div key={c.name} className="cond-line">
                <b>{c.name}</b>:{" "}
                {Object.entries(c.resolved_mix)
                  .map(([o, f]) => `${o} ${(f * 100).toFixed(1)}%`)
                  .join(" · ")}
                {c.remainder_organism && (
                  <span className="muted"> (remainder → {c.remainder_organism})</span>
                )}
              </div>
            ))}
          </div>
        )}

        {plan && (
          <div className="plan-out">
            <p className="plan-summary">
              <b>{plan.to_run}</b> stage{plan.to_run === 1 ? "" : "s"} will run,{" "}
              <b>{plan.cached}</b> reused from cache.
            </p>
            <Collapsible summary="Technical details — per-stage cache state">
              <table className="node-table">
                <tbody>
                  {plan.nodes.map((n) => (
                    <tr key={n.label + n.artifact}>
                      <td>
                        <span className={`dot ${n.cached ? "cached" : "run"}`} />
                      </td>
                      <td>{n.label ?? n.artifact}</td>
                      <td className="muted">{n.cached ? "reuse" : n.state.toLowerCase()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Collapsible>
          </div>
        )}
      </Card>

      {(running || Object.keys(nodePhase).length > 0) && (
        <Card title={`Run ${runState ?? ""}`}>
          <div className="progress-list">
            {Object.entries(nodePhase).map(([node, phase]) => (
              <div key={node} className={`progress-row ${phase}`}>
                <span className="phase-icon">
                  {phase === "done" ? "✓" : phase === "failed" ? "✕" : phase === "cancelled" ? "⊘" : "▶"}
                </span>
                {node}
              </div>
            ))}
          </div>
          {logLines.length > 0 && (
            <Collapsible summary="Log">
              <pre className="log">{logLines.join("\n")}</pre>
            </Collapsible>
          )}
        </Card>
      )}

      {results && <ResultsPanel r={results} />}
    </>
  );
}

function ResultsPanel({ r }: { r: Results }) {
  const mc = Object.entries(r.yield.missed_cleavages).sort();
  const dyn = r.structure.dynamic_range;
  const cond = r.design.conditions[0];
  const setCv = r.design.set_biological_cv;
  const realCv = r.design.realized_biological_cv;
  return (
    <Card title="Results">
      <div className="results-grid">
        <div className="stat">
          <div className="stat-num">{r.design.samples}</div>
          <div className="stat-label">biological replicates</div>
        </div>
        <div className="stat">
          <div className="stat-num">{r.design.runs}</div>
          <div className="stat-label">runs</div>
        </div>
        <div className="stat">
          <div className="stat-num">{r.structure.unique_peptides.toLocaleString()}</div>
          <div className="stat-label">unique peptides</div>
        </div>
        <div className="stat">
          <div className="stat-num">{r.structure.modforms.toLocaleString()}</div>
          <div className="stat-label">modforms</div>
        </div>
        <div className="stat">
          <div className="stat-num">{dyn.orders_of_magnitude ?? "—"}</div>
          <div className="stat-label">orders of dynamic range</div>
        </div>
      </div>

      <h4>Replicate quant ground truth</h4>
      <table className="answer-key">
        <tbody>
          <tr>
            <td>design</td>
            <td className="num">
              {cond?.biological_replicates ?? "—"} biological × {cond?.technical_replicates ?? "—"} technical
            </td>
          </tr>
          <tr>
            <td>set biological CV</td>
            <td className="num">{setCv != null ? `${(setCv * 100).toFixed(1)}%` : "—"}</td>
          </tr>
          <tr>
            <td>realized biological CV</td>
            <td className="num">{realCv != null ? `${(realCv * 100).toFixed(1)}%` : "n/a (need ≥2 replicates)"}</td>
          </tr>
        </tbody>
      </table>
      <p className="muted">{r.design.technical_note}</p>

      {r.design.fold_change_answer_key.length > 0 && (
        <>
          <h4>Fold-change answer key (vs {r.design.reference_condition})</h4>
          <table className="answer-key">
            <thead>
              <tr><th>Organism</th><th>median true log2FC</th><th>proteins</th></tr>
            </thead>
            <tbody>
              {r.design.fold_change_answer_key.map((row) => (
                <tr key={row.organism}>
                  <td>{row.organism}</td>
                  <td className="num">{row.median_true_log2fc.toFixed(3)}</td>
                  <td className="num">{row.n_proteins}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h4>Digestion yield</h4>
      <div className="mc-bars">
        {mc.map(([k, v]) => (
          <div className="mc-bar" key={k}>
            <span className="mc-k">{k} missed</span>
            <span className="mc-track"><span className="mc-fill" style={{ width: `${v * 100}%` }} /></span>
            <span className="mc-v">{(v * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
      <p className="muted">
        truncation loss {(r.yield.truncation_loss * 100).toFixed(3)}% · filter loss{" "}
        {(r.yield.filter_loss * 100).toFixed(2)}%
      </p>
    </Card>
  );
}
