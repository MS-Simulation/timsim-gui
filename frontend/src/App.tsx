import { useEffect, useState } from "react";
import { api } from "./api";
import { qcDefault } from "./presets";
import { normalize, orgsOf } from "./model";
import type { DatasetInfo, SampleDesignerRequest } from "./types";
import { SampleSources } from "./sections/SampleSources";
import { SamplePrep } from "./sections/SamplePrep";
import { Experiment } from "./sections/Experiment";
import { ReviewGenerate } from "./sections/ReviewGenerate";
import { SummaryBar } from "./components/SummaryBar";

const SECTIONS = ["Sample", "Sample preparation", "Experiment", "Review & generate"];

export function App() {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [req, setReqRaw] = useState<SampleDesignerRequest | null>(null);
  const [section, setSection] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const e = await api.enums();
        setDatasets(e.datasets);
        const p = await api.createProject();
        setProjectId(p.project_id);
        // Default: a single HeLa sample (the simplest QC experiment).
        const hela = e.datasets.find((d) => d.id === "demo-hela") ?? e.datasets[0];
        const base = qcDefault("HeLa", hela.organism);
        base.proteome_sources = [{ dataset_id: hela.id, organism: hela.organism }];
        setReqRaw(normalize(base));
      } catch (ex) {
        setErr(String(ex));
      }
    })();
  }, []);

  const setReq = (r: SampleDesignerRequest) => setReqRaw(normalize(r));

  if (err) return <div className="fatal">Backend error: {err}</div>;
  if (!req || !projectId) return <div className="loading">Setting up a project…</div>;

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">timsim · Sample&nbsp;Designer</span>
        <span className="project">project {projectId}</span>
      </header>
      <SummaryBar req={req} />
      <div className="body">
        <nav className="spine">
          {SECTIONS.map((label, i) => (
            <button
              key={label}
              className={`spine-item ${i === section ? "active" : ""}`}
              onClick={() => setSection(i)}
            >
              <span className="num">{i + 1}</span>
              <span>{label}</span>
            </button>
          ))}
          <p className="spine-hint">Steps are hints, not gates — jump around freely.</p>
        </nav>

        <main className="content">
          {section === 0 && (
            <SampleSources datasets={datasets} req={req} onChange={setReq} />
          )}
          {section === 1 && <SamplePrep req={req} onChange={setReq} />}
          {section === 2 && <Experiment req={req} organisms={orgsOf(req)} onChange={setReq} />}
          {section === 3 && <ReviewGenerate projectId={projectId} req={req} />}

          <div className="section-nav">
            <button disabled={section === 0} onClick={() => setSection(section - 1)}>
              ← Back
            </button>
            <button
              className="primary"
              disabled={section === SECTIONS.length - 1}
              onClick={() => setSection(section + 1)}
            >
              Next →
            </button>
          </div>
        </main>
      </div>
    </div>
  );
}
