import type { SampleDesignerRequest } from "./types";

/** The organisms currently in the sample, derived from the selected proteome sources. */
export function orgsOf(req: SampleDesignerRequest): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const s of req.proteome_sources) {
    const org = s.organism ?? "";
    if (org && !seen.has(org)) {
      seen.add(org);
      out.push(org);
    }
  }
  return out;
}

/** Keep the design consistent with the selected organisms and conditions:
 *  - every organism has an abundance profile;
 *  - every condition's mix covers exactly the selected organisms (one organism ⇒ 100%);
 *  - the reference points at a real condition. */
export function normalize(req: SampleDesignerRequest): SampleDesignerRequest {
  const organisms = orgsOf(req);
  const orgSet = new Set(organisms);

  const abundance = { ...req.design.abundance };
  for (const o of organisms) if (!abundance[o]) abundance[o] = { source: "hockeystick" };
  for (const o of Object.keys(abundance)) if (!orgSet.has(o)) delete abundance[o];

  const conditions = req.design.conditions.map((c) => {
    let mix = { ...c.mix };
    if (organisms.length === 1) {
      mix = { [organisms[0]]: 1.0 };
    } else {
      for (const o of organisms) if (!(o in mix)) mix[o] = 0;
      for (const o of Object.keys(mix)) if (!orgSet.has(o)) delete mix[o];
    }
    return { ...c, mix };
  });

  const names = conditions.map((c) => c.name);
  const reference = names.includes(req.design.design.reference)
    ? req.design.design.reference
    : names[0];

  return {
    ...req,
    design: { ...req.design, abundance, conditions, design: { ...req.design.design, reference } },
  };
}

/** A fresh condition, copying an existing one's composition so it is valid immediately. */
export function newCondition(req: SampleDesignerRequest) {
  const base = req.design.conditions[0];
  const used = new Set(req.design.conditions.map((c) => c.name));
  let n = req.design.conditions.length + 1;
  while (used.has(`S${n}`)) n += 1;
  return {
    name: `S${n}`,
    mix: { ...base.mix },
    replicates: base.replicates,
    technical_replicates: base.technical_replicates,
    regulate: null,
  };
}
