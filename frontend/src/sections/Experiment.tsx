import type { Abundance, Condition, SampleDesignerRequest } from "../types";
import { Card, Collapsible, NumberField, TextField } from "../components/ui";
import { MixtureEditor } from "../components/MixtureEditor";
import { ExperimentSheet } from "../components/ExperimentSheet";
import { newCondition } from "../model";

// Section ③. The experiment: one or more conditions, each with biological × technical replicates and
// variance over the sets. One condition = a QC sample; several = a differential (A/B/C) experiment.
export function Experiment(props: {
  req: SampleDesignerRequest;
  organisms: string[];
  onChange: (r: SampleDesignerRequest) => void;
}) {
  const { req, organisms, onChange } = props;
  const d = req.design;
  const conds = d.conditions;
  const multiOrg = organisms.length > 1;
  const multiCond = conds.length > 1;

  const setHeader = (patch: Partial<SampleDesignerRequest["design"]["design"]>) =>
    onChange({ ...req, design: { ...d, design: { ...d.design, ...patch } } });
  const setConditions = (conditions: Condition[]) =>
    onChange({ ...req, design: { ...d, conditions } });
  const patchCondition = (i: number, patch: Partial<Condition>) =>
    setConditions(conds.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const setVariance = (patch: Partial<SampleDesignerRequest["design"]["variance"]>) =>
    onChange({ ...req, design: { ...d, variance: { ...d.variance, ...patch } } });
  const setAbundance = (org: string, ab: Abundance) =>
    onChange({ ...req, design: { ...d, abundance: { ...d.abundance, [org]: ab } } });

  const addCondition = () => setConditions([...conds, newCondition(req)]);
  const removeCondition = (i: number) => setConditions(conds.filter((_, j) => j !== i));

  return (
    <>
      <Card title="Loading">
        <div className="row">
          <NumberField
            label="load (ng on column)" value={d.design.load_ng} min={0} step={10}
            onChange={(v) => setHeader({ load_ng: v })}
          />
          <NumberField label="seed" value={d.design.seed} onChange={(v) => setHeader({ seed: v })} />
          {multiCond && (
            <label className="field">
              <span className="field-label">reference condition</span>
              <select
                value={d.design.reference}
                onChange={(e) => setHeader({ reference: e.target.value })}
              >
                {conds.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
              </select>
            </label>
          )}
        </div>
      </Card>

      {conds.map((c, i) => {
        const isRef = c.name === d.design.reference;
        const reg = c.regulate && "fraction" in c.regulate ? c.regulate : null;
        return (
          <Card key={i} title={multiCond ? `Condition ${c.name}${isRef ? " · reference" : ""}` : "Sample"}>
            <div className="row">
              <TextField label="name" value={c.name} onChange={(v) => patchCondition(i, { name: v })} />
              <NumberField
                label="biological replicates" value={c.replicates} min={1}
                onChange={(v) => patchCondition(i, { replicates: v })}
                hint="different material — amounts differ"
              />
              <NumberField
                label="technical replicates" value={c.technical_replicates} min={1}
                onChange={(v) => patchCondition(i, { technical_replicates: v })}
                hint="same tube — measurement-only"
              />
              {multiCond && (
                <button className="remove-btn" onClick={() => removeCondition(i)} title="Remove condition">
                  ✕ remove
                </button>
              )}
            </div>

            {multiOrg && (
              <>
                <p className="field-label" style={{ marginTop: "0.6rem" }}>composition</p>
                <MixtureEditor
                  organisms={organisms}
                  mix={c.mix}
                  loadNg={d.design.load_ng}
                  onChange={(mix) => patchCondition(i, { mix })}
                />
              </>
            )}

            <Collapsible summary={`Regulate a subset of proteins${reg ? " (on)" : ""}`}>
              <p className="field-hint">
                Move a random fraction of proteins by a fold change — a differential signal within one
                proteome (e.g. treated vs control). The reference condition is usually left unregulated.
              </p>
              <label className="field checkbox">
                <input
                  type="checkbox" checked={!!reg}
                  onChange={(e) =>
                    patchCondition(i, {
                      regulate: e.target.checked ? { fraction: 0.1, log2fc_sd: 1.0 } : null,
                    })
                  }
                />
                <span>regulate a random subset</span>
              </label>
              {reg && (
                <div className="row">
                  <NumberField
                    label="fraction of proteins" value={reg.fraction} min={0} max={1} step={0.05}
                    onChange={(v) => patchCondition(i, { regulate: { ...reg, fraction: v } })}
                  />
                  <NumberField
                    label="log2FC spread (sd)" value={reg.log2fc_sd} min={0} step={0.1}
                    onChange={(v) => patchCondition(i, { regulate: { ...reg, log2fc_sd: v } })}
                  />
                </div>
              )}
            </Collapsible>
          </Card>
        );
      })}

      <div className="add-condition-row">
        <button className="add-btn" onClick={addCondition}>＋ Add a condition to compare (A/B/C)</button>
      </div>

      <Card title="Variance over the replicate sets"
        note="How much the amounts vary between replicates — the knob a QC/quant benchmark turns.">
        <div className="row">
          <NumberField
            label="biological CV" value={d.variance.biological} step={0.01} min={0}
            onChange={(v) => setVariance({ biological: v })}
            hint="spread between biological replicates"
          />
          <NumberField
            label="technical CV" value={d.variance.technical} step={0.01} min={0}
            onChange={(v) => setVariance({ technical: v })}
            hint="between injections (applied at render)"
          />
        </div>
        <Collapsible summary="Advanced — heterogeneity & abundance">
          <div className="row">
            <NumberField
              label="biological heterogeneity" value={d.variance.biological_heterogeneity} step={0.1} min={0}
              onChange={(v) => setVariance({ biological_heterogeneity: v })}
              hint="spread of per-protein CVs (0 = shared)"
            />
            {organisms.map((org) => (
              <label className="field" key={org}>
                <span className="field-label">abundance ({org})</span>
                <select
                  value={d.abundance[org]?.source ?? "hockeystick"}
                  onChange={(e) => setAbundance(org, { source: e.target.value as Abundance["source"] })}
                >
                  <option value="hockeystick">hockeystick</option>
                  <option value="lognormal">lognormal</option>
                </select>
              </label>
            ))}
          </div>
        </Collapsible>
      </Card>

      <Card title="What you're building">
        <ExperimentSheet
          conditions={conds.map((c) => ({
            name: c.name, bio: c.replicates, tech: c.technical_replicates,
          }))}
        />
      </Card>
    </>
  );
}
