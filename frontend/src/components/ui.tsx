import { useState, type ReactNode } from "react";

export function NumberField(props: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
  hint?: string;
}) {
  return (
    <label className="field">
      <span className="field-label">{props.label}</span>
      <input
        type="number"
        value={Number.isFinite(props.value) ? props.value : ""}
        step={props.step ?? 1}
        min={props.min}
        max={props.max}
        onChange={(e) => props.onChange(e.target.value === "" ? NaN : Number(e.target.value))}
      />
      {props.hint && <span className="field-hint">{props.hint}</span>}
    </label>
  );
}

export function TextField(props: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
}) {
  return (
    <label className="field">
      <span className="field-label">{props.label}</span>
      <input type="text" value={props.value} onChange={(e) => props.onChange(e.target.value)} />
      {props.hint && <span className="field-hint">{props.hint}</span>}
    </label>
  );
}

export function Collapsible(props: { summary: string; children: ReactNode; open?: boolean }) {
  const [open, setOpen] = useState(props.open ?? false);
  return (
    <div className={`collapsible ${open ? "open" : ""}`}>
      <button className="collapsible-summary" onClick={() => setOpen(!open)}>
        <span className="chevron">{open ? "▾" : "▸"}</span> {props.summary}
      </button>
      {open && <div className="collapsible-body">{props.children}</div>}
    </div>
  );
}

export function Card(props: { title?: string; children: ReactNode; note?: string }) {
  return (
    <section className="card">
      {props.title && <h3 className="card-title">{props.title}</h3>}
      {props.note && <p className="card-note">{props.note}</p>}
      {props.children}
    </section>
  );
}
