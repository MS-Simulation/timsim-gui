// The experiment sheet: how the design expands into runs. Generalized to N conditions —
// condition → biological replicates (vials, different amounts) → technical runs (same amounts,
// measured again). The condition layer and the biological layer both act on amounts (realized now);
// the technical layer acts on the measurement (realized only at render).

const MAX_VIALS = 5;
const MAX_RUNS = 3;

export interface SheetCondition {
  name: string;
  bio: number;
  tech: number;
}

function Vial() {
  return (
    <svg width="20" height="30" viewBox="0 0 22 34" aria-hidden="true" className="vial">
      <rect x="6" y="2" width="10" height="2.4" rx="1.2" />
      <path d="M7.5 4.4 V25 a3.5 3.5 0 0 0 7 0 V4.4" fill="none" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M7.5 16 V25 a3.5 3.5 0 0 0 7 0 V16 Z" className="vial-liquid" />
    </svg>
  );
}

export function ExperimentSheet({ conditions }: { conditions: SheetCondition[] }) {
  const samples = conditions.reduce((s, c) => s + c.bio, 0);
  const runs = conditions.reduce((s, c) => s + c.bio * c.tech, 0);
  const multi = conditions.length > 1;

  return (
    <div className="expsheet">
      <div className="expsheet-head">
        {multi && (
          <span>
            Conditions <b>{conditions.length}</b>
            <span className="es-sub">what you compare</span>
          </span>
        )}
        {multi && <span className="es-arrow">→</span>}
        <span>
          {multi ? "Biological samples" : "Biological samples"} <b>{samples}</b>
          <span className="es-sub">different material</span>
        </span>
        <span className="es-arrow">→</span>
        <span>
          Technical runs <b>{runs}</b>
          <span className="es-sub">measurements</span>
        </span>
      </div>

      <div className="es-conditions">
        {conditions.map((c) => {
          const shownVials = Math.min(c.bio, MAX_VIALS);
          const extraVials = c.bio - shownVials;
          const shownRuns = Math.min(c.tech, MAX_RUNS);
          return (
            <div className="es-cond" key={c.name}>
              {multi && <div className="es-cond-label">{c.name}</div>}
              <div className="es-vials">
                {Array.from({ length: shownVials }).map((_, i) => (
                  <div className="es-vial" key={i}>
                    <Vial />
                    <div className="es-vial-name">{c.name}_R{i + 1}</div>
                    <div className="es-runs">
                      {Array.from({ length: shownRuns }).map((_, j) => (
                        <span className="es-run" key={j}>T{j + 1}</span>
                      ))}
                      {c.tech > MAX_RUNS && <span className="es-run more">×{c.tech}</span>}
                    </div>
                  </div>
                ))}
                {extraVials > 0 && (
                  <div className="es-vial es-more">
                    <span className="es-more-plus">+{extraVials}</span>
                    <span className="es-sub">more</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="es-caption">
        {multi && <>Each <b>condition</b> is a different intended biology (the signal you want a tool to
          recover). </>}
        Each <b>vial</b> is different material (a biological replicate — amounts genuinely differ). Each
        <b> run</b> measures that same material again (a technical replicate — variation is in the
        measurement, added at render). <b>{samples} samples · {runs} runs.</b>
      </p>
    </div>
  );
}
