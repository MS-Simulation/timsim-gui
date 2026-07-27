import type { ModRow, SampleDesignerRequest } from "./types";

// The four modification presets from flow/mods.toml — a chemist picks from these and tunes occupancy.
export const MOD_PRESETS: ModRow[] = [
  { name: "Carbamidomethyl", unimod_id: 4, targets: "C", site: "residue", occupancy: 0.98,
    mass_delta: 57.021464, composition: "C2H3NO", blocks_cleavage: false, stage: "protein" },
  { name: "Oxidation", unimod_id: 35, targets: "M", site: "residue", occupancy: 0.05,
    mass_delta: 15.994915, composition: "O", blocks_cleavage: false, stage: "peptide" },
  // Protein N-terminal acetylation — co-translational, on the protein N-terminus (a terminus mod,
  // so no residue target). Common on human proteins; occupancy is highly protein-dependent.
  { name: "Acetyl (N-term)", unimod_id: 1, targets: "", site: "n_term", occupancy: 0.5,
    mass_delta: 42.010565, composition: "C2H2O", blocks_cleavage: false, stage: "protein" },
  { name: "Phospho", unimod_id: 21, targets: "STY", site: "residue", occupancy: 0.30,
    mass_delta: 79.966331, composition: "HO3P", blocks_cleavage: false, stage: "protein" },
  { name: "GG", unimod_id: 121, targets: "K", site: "residue", occupancy: 0.001,
    mass_delta: 114.042927, composition: "C4H6N2O2", blocks_cleavage: true, stage: "protein" },
];

// The simplest experiment: QC of one sample. A single condition (one proteome at 100%), a few
// biological + technical replicates, and the variance set over those replicate sets. Prep is set to
// the CLI defaults so the first screen is already runnable.
export function qcDefault(sampleName: string, organism: string): SampleDesignerRequest {
  return {
    proteome_sources: [],
    mods: { modifications: [MOD_PRESETS[0], MOD_PRESETS[1]] }, // carbamidomethyl + oxidation
    design: {
      design: { reference: sampleName, load_ng: 200, n_proteins: null, seed: 42 },
      abundance: { [organism]: { source: "hockeystick" } },
      conditions: [
        { name: sampleName, mix: { [organism]: 1.0 }, replicates: 3, technical_replicates: 2 },
      ],
      variance: { biological: 0.15, biological_heterogeneity: 0.5, technical: 0.05 },
    },
    enzyme: "trypsin",
    max_missed_cleavages: 2,
    min_length: 7,
    max_length: 30,
    modify_floor: 1e-3,
    digestion_efficiency: 0.9,
  };
}
