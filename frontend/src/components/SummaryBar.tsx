import type { SampleDesignerRequest } from "../types";
import { orgsOf } from "../model";

// The persistent "specified truth" anchor: the whole experiment, always visible while editing a part.
export function SummaryBar({ req }: { req: SampleDesignerRequest }) {
  const conds = req.design.conditions;
  const organisms = orgsOf(req);
  const samples = conds.reduce((s, c) => s + c.replicates, 0);
  const runs = conds.reduce((s, c) => s + c.replicates * c.technical_replicates, 0);
  const nmods = req.mods.modifications.length;

  const experiment =
    conds.length > 1
      ? `${conds.length} conditions · ${samples} samples · ${runs} runs`
      : `${conds[0].replicates} bio × ${conds[0].technical_replicates} tech = ${runs} run${runs === 1 ? "" : "s"}`;

  const items: [string, string][] = [
    ["sample", conds.length > 1 ? conds.map((c) => c.name).join(" / ") : conds[0].name],
    ["proteome", organisms.join(" + ")],
    ["experiment", experiment],
    ["load", `${req.design.design.load_ng} ng`],
    ["digest", `${req.enzyme}, ≤${req.max_missed_cleavages} missed, ${req.min_length}–${req.max_length} aa`],
    ["mods", nmods === 0 ? "none" : `${nmods}`],
  ];

  return (
    <div className="summary-bar">
      <span className="sum-lead">You are building</span>
      {items.map(([k, v]) => (
        <span className="sum-chip" key={k}>
          <span className="sum-k">{k}</span>
          <span className="sum-v">{v}</span>
        </span>
      ))}
    </div>
  );
}
