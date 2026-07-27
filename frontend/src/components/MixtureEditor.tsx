import type { MixShare } from "../types";

// The composition of one condition. Masses (ng) and percentages side by side; total and remainder
// shown explicitly; "rest" chosen deliberately, never silent.
export function MixtureEditor(props: {
  organisms: string[];
  mix: Record<string, MixShare>;
  loadNg: number;
  onChange: (mix: Record<string, MixShare>) => void;
}) {
  const { organisms, mix, loadNg, onChange } = props;
  const restOrg = organisms.find((o) => mix[o] === "rest") ?? null;
  const explicitTotal = organisms
    .filter((o) => mix[o] !== "rest")
    .reduce((s, o) => s + (typeof mix[o] === "number" ? (mix[o] as number) : 0), 0);
  const remainder = restOrg ? Math.max(0, 1 - explicitTotal) : null;

  const setFraction = (org: string, pct: number) => onChange({ ...mix, [org]: clamp01(pct / 100) });
  const setRest = (org: string) => {
    const next: Record<string, MixShare> = { ...mix };
    for (const o of organisms) if (next[o] === "rest") next[o] = 0;
    next[org] = "rest";
    onChange(next);
  };

  const sumsToOne = restOrg !== null || Math.abs(explicitTotal - 1) < 1e-6;

  return (
    <div className="mixture">
      <table className="mixture-table">
        <thead>
          <tr><th>Organism</th><th>Percent</th><th>Mass (ng)</th><th className="center">Rest</th></tr>
        </thead>
        <tbody>
          {organisms.map((org) => {
            const isRest = mix[org] === "rest";
            const frac = isRest ? remainder ?? 0 : (mix[org] as number) ?? 0;
            return (
              <tr key={org}>
                <td className="org">{org}</td>
                <td>
                  {isRest ? (
                    <span className="derived">{(frac * 100).toFixed(1)}%</span>
                  ) : (
                    <input
                      type="number" className="pct" min={0} max={100} step={0.5}
                      value={round(frac * 100, 3)}
                      onChange={(e) => setFraction(org, Number(e.target.value))}
                    />
                  )}
                </td>
                <td className="derived">{round(frac * loadNg, 1)}</td>
                <td className="center">
                  <input
                    type="radio" name={`rest-${organisms.join()}-${Object.keys(mix).length}`}
                    checked={isRest} onChange={() => setRest(org)}
                    title="Assign the remainder to this organism"
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className={`mixture-total ${sumsToOne ? "ok" : "warn"}`}>
        {restOrg ? (
          <>Explicit {round(explicitTotal * 100, 2)}% + <b>{restOrg}</b> remainder {round((remainder ?? 0) * 100, 2)}% = 100%</>
        ) : (
          <>Total {round(explicitTotal * 100, 2)}% {sumsToOne ? "✓" : "— must be 100% or pick a remainder organism"}</>
        )}
      </div>
    </div>
  );
}

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const round = (x: number, n: number) => {
  const f = 10 ** n;
  return Math.round(x * f) / f;
};
