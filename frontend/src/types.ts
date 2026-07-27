// Mirrors the backend `SampleDesignerRequest` (backend/timsim_api/app.py) and the Pydantic specs.

export type MixShare = number | "rest";

export interface ProteomeSourceReq {
  dataset_id: string;
  organism?: string | null;
  is_contaminant?: boolean;
}

export type Site = "residue" | "n_term" | "c_term";
export type Stage = "protein" | "peptide";

export interface ModRow {
  name: string;
  unimod_id: number;
  targets: string;
  site: Site;
  occupancy: number;
  mass_delta: number;
  composition: string;
  blocks_cleavage: boolean;
  stage: Stage;
}

export interface Abundance {
  source: "lognormal" | "hockeystick" | "table";
  sigma?: number;
  decay?: number | null;
  tail?: number | null;
  path?: string;
}

export type RegulateGenerative = { fraction: number; log2fc_sd: number };
export type RegulateExplicit = { proteins: string[]; log2fc: number };
export type Regulate = RegulateGenerative | RegulateExplicit;

export interface Condition {
  name: string;
  mix: Record<string, MixShare>;
  replicates: number;
  technical_replicates: number;
  regulate?: Regulate | null;
}

export interface Variance {
  biological: number;
  biological_heterogeneity: number;
  technical: number;
}

export interface DesignReq {
  design: { reference: string; load_ng: number; n_proteins: number | null; seed: number };
  abundance: Record<string, Abundance>;
  conditions: Condition[];
  variance: Variance;
}

export interface SampleDesignerRequest {
  proteome_sources: ProteomeSourceReq[];
  mods: { modifications: ModRow[] };
  design: DesignReq;
  enzyme: string;
  max_missed_cleavages: number;
  min_length: number;
  max_length: number;
  modify_floor: number;
  digestion_efficiency: number;
}

export interface DatasetInfo { id: string; label: string; organism: string }

export interface PlanNode {
  label: string;
  artifact: string;
  state: string;
  cached: boolean;
  command: string;
}

export interface PlanResult {
  nodes: PlanNode[];
  total: number;
  to_run: number;
  cached: number;
}

export interface ValidateResult {
  ok: boolean;
  conditions: {
    name: string;
    resolved_mix: Record<string, number>;
    remainder_organism: string | null;
    remainder: number | null;
  }[];
}

export interface RunSnapshot {
  run_id: string;
  state: "queued" | "running" | "succeeded" | "failed" | "cancelled" | "lost";
  error: string | null;
  last_seq: number;
}

export interface RunEvent {
  seq: number;
  ts: number;
  kind: string;
  node?: string;
  phase?: string;
  line?: string;
  state?: string;
  error?: string | null;
}

export interface Results {
  design: {
    samples: number;
    runs: number;
    reference_condition: string;
    conditions: { name: string; biological_replicates: number; technical_replicates: number }[];
    set_biological_cv: number | null;
    set_technical_cv: number | null;
    realized_biological_cv: number | null;
    technical_note: string;
    fold_change_answer_key: { organism: string; median_true_log2fc: number; n_proteins: number }[];
  };
  structure: {
    proteins: number;
    unique_peptides: number;
    peptide_sample_rows: number;
    modforms: number;
    peptides_with_modforms: number;
    dynamic_range: { min_amol?: number; max_amol?: number; orders_of_magnitude?: number | null };
  };
  yield: {
    digestion_efficiency: number;
    truncation_loss: number;
    filter_loss: number;
    missed_cleavages: Record<string, number>;
  };
}
