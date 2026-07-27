import type { ModRow, Stage } from "../types";
import { MOD_PRESETS } from "../presets";
import { Collapsible } from "./ui";

// Modifications as occupancy — the fraction of a site carrying the mod — not "max N variable mods".
export function OccupancyGrid(props: {
  mods: ModRow[];
  onChange: (mods: ModRow[]) => void;
}) {
  const { mods, onChange } = props;
  const present = new Set(mods.map((m) => m.name));

  const toggle = (preset: ModRow) => {
    if (present.has(preset.name)) onChange(mods.filter((m) => m.name !== preset.name));
    else onChange([...mods, { ...preset }]);
  };
  const update = (name: string, patch: Partial<ModRow>) =>
    onChange(mods.map((m) => (m.name === name ? { ...m, ...patch } : m)));

  return (
    <div className="occupancy">
      <div className="preset-row">
        {MOD_PRESETS.map((p) => (
          <button
            key={p.name}
            className={`chip ${present.has(p.name) ? "on" : ""}`}
            onClick={() => toggle(p)}
          >
            {present.has(p.name) ? "✓ " : "+ "}
            {p.name}
          </button>
        ))}
      </div>

      {mods.length === 0 && <p className="field-hint">No modifications — every peptide stays unmodified.</p>}

      {mods.map((m) => (
        <div key={m.name} className="mod-row">
          <div className="mod-head">
            <b>{m.name}</b> <span className="muted">on {m.targets || "terminus"}</span>
            {m.blocks_cleavage && <span className="tag">blocks cleavage</span>}
          </div>
          <label className="occ-slider">
            <span>occupancy</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.001}
              value={m.occupancy}
              onChange={(e) => update(m.name, { occupancy: Number(e.target.value) })}
            />
            <input
              type="number"
              className="occ-num"
              min={0}
              max={1}
              step={0.001}
              value={m.occupancy}
              onChange={(e) => update(m.name, { occupancy: clamp01(Number(e.target.value)) })}
            />
          </label>
          <Collapsible summary="Advanced">
            <div className="row">
              <label className="field">
                <span className="field-label">targets</span>
                <input value={m.targets} onChange={(e) => update(m.name, { targets: e.target.value })} />
              </label>
              <label className="field">
                <span className="field-label">stage</span>
                <select
                  value={m.stage}
                  onChange={(e) => update(m.name, { stage: e.target.value as Stage })}
                >
                  <option value="protein">protein (before digest)</option>
                  <option value="peptide">peptide (after digest)</option>
                </select>
              </label>
              <label className="field checkbox">
                <input
                  type="checkbox"
                  checked={m.blocks_cleavage}
                  disabled={m.stage !== "protein"}
                  onChange={(e) => update(m.name, { blocks_cleavage: e.target.checked })}
                />
                <span>blocks cleavage (protein-stage only)</span>
              </label>
            </div>
          </Collapsible>
        </div>
      ))}
    </div>
  );
}

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
