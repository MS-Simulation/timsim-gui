import type { DatasetInfo, SampleDesignerRequest } from "../types";
import { Card } from "../components/ui";

// Section ①. Pick the proteome(s) the sample is made of — curated server-side datasets, never paths.
// One proteome = a QC sample; several organisms = a mixed sample whose composition can differ across
// conditions (e.g. HYE).
export function SampleSources(props: {
  datasets: DatasetInfo[];
  req: SampleDesignerRequest;
  onChange: (r: SampleDesignerRequest) => void;
}) {
  const { datasets, req, onChange } = props;
  const selected = new Set(req.proteome_sources.map((s) => s.dataset_id));

  const toggle = (d: DatasetInfo) => {
    const sources = selected.has(d.id)
      ? req.proteome_sources.filter((s) => s.dataset_id !== d.id)
      : [...req.proteome_sources, { dataset_id: d.id, organism: d.organism, is_contaminant: false }];
    if (sources.length === 0) return; // keep at least one
    onChange({ ...req, proteome_sources: sources });
  };

  return (
    <Card
      title="Sample"
      note="Choose the proteome(s) in your sample. One proteome is a QC sample; adding organisms lets conditions differ by composition (e.g. a HYE spike-in). Organism is a declared property of each dataset."
    >
      <div className="dataset-list">
        {datasets.map((d) => {
          const on = selected.has(d.id);
          return (
            <button key={d.id} className={`dataset ${on ? "on" : ""}`} onClick={() => toggle(d)}>
              <span className="checkmark">{on ? "✓" : ""}</span>
              <span className="dataset-label">{d.label}</span>
              <span className="dataset-org">{d.organism}</span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
