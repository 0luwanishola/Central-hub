import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { apiUrl, runPdfTool } from "../../services/apiClient";
import type { Tool } from "../../types";
import { Icon } from "../../ui/Icon";

type PdfField = {
  name: string;
  label: string;
  type?: "text" | "number" | "textarea" | "color" | "select";
  hint?: string;
  required?: boolean;
  defaultValue?: string;
  options?: string[];
  min?: number;
  max?: number;
};

const positions = ["top-left", "top-centre", "top-right", "middle-left", "centre", "middle-right", "bottom-left", "bottom-centre", "bottom-right"];
const fonts = ["Helvetica", "Helvetica-Bold", "Times", "Times-Bold", "Courier"];

const pdfFields: Record<string, PdfField[]> = {
  "pdf-split": [{ name: "pages", label: "Pages to split", required: true, hint: "Use a range such as 1-3, 5, 8-. Each selected page becomes a PDF in a ZIP." }],
  "pdf-page-organiser": [
    { name: "pages", label: "Pages to keep, in order", required: true, hint: "For example 1, 3, 2, 5-7. Omitted pages are removed." },
    { name: "rotate", label: "Rotations (optional)", hint: "For example 1=90, 3=-90. Use 90, 180 or 270 degrees." },
  ],
  "pdf-add-text": [
    { name: "text", label: "Text to stamp", type: "textarea", required: true },
    { name: "pages", label: "Pages (optional)", hint: "Leave blank to apply to every page. For example 1-3, 5." },
    { name: "font", label: "Font", type: "select", options: fonts, defaultValue: "Helvetica" },
    { name: "size", label: "Font size", type: "number", min: 4, max: 200, defaultValue: "24" },
    { name: "colour", label: "Text colour", type: "color", defaultValue: "#111827" },
    { name: "position", label: "Position", type: "select", options: positions, defaultValue: "bottom-right" },
    { name: "margin", label: "Margin (points)", type: "number", min: 0, max: 200, defaultValue: "36" },
    { name: "rotation", label: "Rotation in degrees", type: "number", min: -360, max: 360, defaultValue: "0" },
  ],
  "pdf-add-image": [
    { name: "pages", label: "Pages (optional)", hint: "Leave blank to apply to every page." },
    { name: "width", label: "Image width (% of page)", type: "number", min: 1, max: 100, defaultValue: "25" },
    { name: "position", label: "Position", type: "select", options: positions, defaultValue: "top-right" },
    { name: "margin", label: "Margin (points)", type: "number", min: 0, max: 200, defaultValue: "36" },
    { name: "opacity", label: "Opacity (0–1)", type: "number", min: 0, max: 1, defaultValue: "1" },
  ],
  "pdf-watermark": [
    { name: "text", label: "Watermark text", type: "textarea", required: true },
    { name: "pages", label: "Pages (optional)", hint: "Leave blank to apply to every page." },
    { name: "font", label: "Font", type: "select", options: fonts, defaultValue: "Helvetica-Bold" },
    { name: "size", label: "Font size", type: "number", min: 6, max: 300, defaultValue: "56" },
    { name: "colour", label: "Watermark colour", type: "color", defaultValue: "#808080" },
    { name: "opacity", label: "Opacity (0–1)", type: "number", min: 0, max: 1, defaultValue: "0.3" },
    { name: "rotation", label: "Rotation in degrees", type: "number", min: -360, max: 360, defaultValue: "45" },
  ],
  "pdf-metadata": [
    { name: "title", label: "Title" }, { name: "author", label: "Author" },
    { name: "subject", label: "Subject" }, { name: "keywords", label: "Keywords" },
    { name: "creator", label: "Creator" }, { name: "producer", label: "Producer" },
  ],
};

const acceptsMultiple = new Set(["pdf-merge", "pdf-add-image"]);
const acceptedTypes: Record<string, string> = {
  "pdf-add-image": ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg",
};

export function PdfTool({ tool }: { tool: Tool }) {
  const fields = pdfFields[tool.id] ?? [];
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(fields.map((field) => [field.name, field.defaultValue ?? ""])));
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ download_url: string; filename: string; expires_in_seconds: number } | null>(null);
  const multiple = acceptsMultiple.has(tool.id);

  function onFilesChanged(event: ChangeEvent<HTMLInputElement>) {
    setFiles(Array.from(event.target.files ?? []));
    setResult(null); setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setResult(null);
    if (!files.length) { setError("Choose a file to continue."); return; }
    if (tool.id === "pdf-merge" && files.length < 2) { setError("Choose at least two PDFs to merge."); return; }
    if (files.reduce((total, file) => total + file.size, 0) > 100 * 1024 * 1024) { setError("The combined upload must be 100 MB or smaller."); return; }

    const form = new FormData();
    for (const file of files) form.append("files", file);
    for (const [name, value] of Object.entries(values)) form.append(name, value);
    setBusy(true);
    try { setResult(await runPdfTool(tool.id, form)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "The PDF tool could not finish."); }
    finally { setBusy(false); }
  }

  return <>
    <form className="pdf-form" onSubmit={(event) => void submit(event)}>
      {tool.id === "pdf-merge" && <div className="pdf-tip">Add at least two PDFs. They will be combined in the order you select them.</div>}
      {tool.id === "pdf-add-image" && <div className="pdf-tip">Choose one PDF and one PNG or JPEG image.</div>}
      {fields.map((field) => <PdfField key={field.name} field={field} value={values[field.name] ?? ""} onChange={(value) => setValues((current) => ({ ...current, [field.name]: value }))} />)}
      <label className="field-label file-field"><span>{tool.id === "pdf-merge" ? "PDF files" : tool.id === "pdf-add-image" ? "PDF and image files" : "PDF file"}</span>
        <input type="file" accept={acceptedTypes[tool.id] ?? ".pdf,application/pdf"} multiple={multiple} required onChange={onFilesChanged} />
        <small>Maximum combined upload: 100 MB.</small>
      </label>
      {files.length > 0 && <div className="selected-files">{files.map((file) => <span key={`${file.name}-${file.lastModified}`}><Icon name="pdf" /> {file.name} <small>{formatBytes(file.size)}</small></span>)}</div>}
      <div className="form-actions"><button className="button button-primary" type="submit" disabled={busy}>{busy ? <><span className="spinner" /> Processing…</> : `Run ${tool.name}`}</button></div>
    </form>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
    {result && <div className="pdf-success" role="status"><div><span className="success-mark"><Icon name="check" /></span><div><strong>Your file is ready</strong><p>{result.filename} · download link expires after 10 minutes and works once.</p></div></div><a className="button button-primary" href={apiUrl(result.download_url)} download={result.filename}>Download file <Icon name="download" /></a></div>}
    <p className="privacy-note">Your file is sent to the configured Central Hub backend for processing. The backend temporarily stores it and removes the result after download or expiry.</p>
  </>;
}

function PdfField({ field, value, onChange }: { field: PdfField; value: string; onChange: (value: string) => void }) {
  const className = field.type === "textarea" ? "form-textarea" : field.type === "select" ? "form-select" : "form-input";
  return <label className="field-label"><span>{field.label}{field.required ? " *" : ""}</span>
    {field.type === "textarea" ? <textarea className={className} value={value} required={field.required} onChange={(event) => onChange(event.target.value)} />
      : field.type === "select" ? <select className={className} value={value} onChange={(event) => onChange(event.target.value)}>{field.options?.map((option) => <option key={option} value={option}>{option.replaceAll("-", " ")}</option>)}</select>
        : <input className={className} type={field.type ?? "text"} value={value} required={field.required} min={field.min} max={field.max} step={field.type === "number" ? "any" : undefined} onChange={(event) => onChange(event.target.value)} />}
    {field.hint && <small>{field.hint}</small>}
  </label>;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
