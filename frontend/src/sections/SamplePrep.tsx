import type { SampleDesignerRequest } from "../types";
import { Card, Collapsible, NumberField } from "../components/ui";
import { OccupancyGrid } from "../components/OccupancyGrid";

// Section ②. Digestion + modifications. Prep has sensible defaults; the deep knobs are collapsed.
export function SamplePrep(props: {
  req: SampleDesignerRequest;
  onChange: (r: SampleDesignerRequest) => void;
}) {
  const { req, onChange } = props;

  return (
    <>
      <Card title="Digestion" note="How the proteins are cut into peptides.">
        <div className="row">
          <label className="field">
            <span className="field-label">enzyme</span>
            <select value={req.enzyme} onChange={(e) => onChange({ ...req, enzyme: e.target.value })}>
              <option value="trypsin">trypsin</option>
            </select>
          </label>
          <NumberField
            label="max missed cleavages"
            value={req.max_missed_cleavages}
            min={0}
            onChange={(v) => onChange({ ...req, max_missed_cleavages: v })}
          />
        </div>
        <Collapsible summary="Advanced — peptide length filter">
          <div className="row">
            <NumberField
              label="min length"
              value={req.min_length}
              min={1}
              onChange={(v) => onChange({ ...req, min_length: v })}
            />
            <NumberField
              label="max length"
              value={req.max_length}
              min={1}
              onChange={(v) => onChange({ ...req, max_length: v })}
            />
            <NumberField
              label="digestion efficiency"
              value={req.digestion_efficiency}
              step={0.01}
              min={0}
              max={1}
              onChange={(v) => onChange({ ...req, digestion_efficiency: v })}
            />
          </div>
        </Collapsible>
      </Card>

      <Card
        title="Modifications"
        note="Set the fraction of each site that carries the mod (its occupancy) — not a variable-mod budget."
      >
        <OccupancyGrid
          mods={req.mods.modifications}
          onChange={(mods) => onChange({ ...req, mods: { modifications: mods } })}
        />
        <Collapsible summary="Advanced — modform abundance floor">
          <NumberField
            label="floor (discard modforms below this fraction)"
            value={req.modify_floor}
            step={0.0001}
            min={0}
            max={1}
            onChange={(v) => onChange({ ...req, modify_floor: v })}
          />
        </Collapsible>
      </Card>
    </>
  );
}
