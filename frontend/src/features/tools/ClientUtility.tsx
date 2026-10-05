import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import * as CryptoJS from "crypto-js";
import QRCode from "qrcode";
import { v1, v4, v7 } from "uuid";

export function ClientUtility({ toolId }: { toolId: string }) {
  switch (toolId) {
    case "json-formatter": return <JsonFormatter />;
    case "base64-encoder": return <Base64Utility />;
    case "hash-generator": return <HashUtility />;
    case "uuid-generator": return <UuidUtility />;
    case "timestamp-converter": return <TimestampUtility />;
    case "regex-tester": return <RegexUtility />;
    case "color-picker": return <ColorUtility />;
    case "qr-generator": return <QrUtility />;
    default: return <div className="notice">This browser tool is not configured yet.</div>;
  }
}

function JsonFormatter() {
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");
  const [error, setError] = useState("");
  function transform(minify: boolean) {
    try {
      const parsed: unknown = JSON.parse(input);
      setOutput(JSON.stringify(parsed, null, minify ? undefined : 2));
      setError("");
    } catch (reason) {
      setOutput("");
      setError(reason instanceof Error ? reason.message : "Invalid JSON.");
    }
  }
  return <>
    <FieldLabel label="JSON input"><textarea className="form-textarea code-area" value={input} onChange={(event) => setInput(event.target.value)} placeholder={'Paste JSON here…\n\n{"name":"Central Hub"}'} spellCheck={false} /></FieldLabel>
    <div className="form-actions"><button className="button button-primary" onClick={() => transform(false)}>Format JSON</button><button className="button button-secondary" onClick={() => transform(true)}>Minify</button><button className="text-button" onClick={() => { setInput(""); setOutput(""); setError(""); }}>Clear</button></div>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
    {output && <OutputBox value={output} label="Result" />}
  </>;
}

function Base64Utility() {
  const [value, setValue] = useState("");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  function encode() {
    const bytes = new TextEncoder().encode(value);
    let binary = "";
    for (const byte of bytes) binary += String.fromCharCode(byte);
    setResult(btoa(binary)); setError("");
  }
  function decode() {
    try {
      const binary = atob(value.trim());
      const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
      setResult(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); setError("");
    } catch {
      setResult(""); setError("This is not valid UTF-8 Base64 text.");
    }
  }
  return <>
    <FieldLabel label="Text or Base64"><textarea className="form-textarea code-area" value={value} onChange={(event) => setValue(event.target.value)} placeholder="Enter text to encode, or Base64 to decode…" /></FieldLabel>
    <div className="form-actions"><button className="button button-primary" onClick={encode}>Encode</button><button className="button button-secondary" onClick={decode}>Decode</button></div>
    {error && <div className="notice notice-error" role="alert">{error}</div>}{result && <OutputBox value={result} label="Result" />}
  </>;
}

function HashUtility() {
  const [input, setInput] = useState("");
  const [algorithm, setAlgorithm] = useState("SHA256");
  const [result, setResult] = useState("");
  const algorithms: Record<string, (value: string) => CryptoJS.lib.WordArray> = {
    MD5: CryptoJS.MD5,
    SHA1: CryptoJS.SHA1,
    SHA256: CryptoJS.SHA256,
  };
  return <>
    <FieldLabel label="Text to hash"><textarea className="form-textarea code-area short-area" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Enter text…" /></FieldLabel>
    <div className="field-row"><FieldLabel label="Algorithm"><select className="form-select" value={algorithm} onChange={(event) => setAlgorithm(event.target.value)}><option>MD5</option><option>SHA1</option><option>SHA256</option></select></FieldLabel><button className="button button-primary align-bottom" onClick={() => setResult(algorithms[algorithm](input).toString())}>Generate hash</button></div>
    {result && <OutputBox value={result} label={`${algorithm} digest`} />}
    <p className="field-hint">The input stays in this browser. MD5 and SHA-1 are included for compatibility, not password storage.</p>
  </>;
}

function UuidUtility() {
  const [version, setVersion] = useState("v4");
  const [count, setCount] = useState("1");
  const [output, setOutput] = useState("");
  function generate() {
    const amount = Math.max(1, Math.min(50, Number(count) || 1));
    const generator = version === "v1" ? v1 : version === "v7" ? v7 : v4;
    setOutput(Array.from({ length: amount }, () => generator()).join("\n"));
  }
  return <>
    <div className="field-row"><FieldLabel label="UUID version"><select className="form-select" value={version} onChange={(event) => setVersion(event.target.value)}><option value="v1">Version 1 · time based</option><option value="v4">Version 4 · random</option><option value="v7">Version 7 · time ordered</option></select></FieldLabel><FieldLabel label="How many"><input className="form-input" type="number" min="1" max="50" value={count} onChange={(event) => setCount(event.target.value)} /></FieldLabel></div>
    <div className="form-actions"><button className="button button-primary" onClick={generate}>Generate UUIDs</button></div>
    {output && <OutputBox value={output} label="Generated IDs" />}
  </>;
}

function TimestampUtility() {
  const [timestamp, setTimestamp] = useState(() => String(Math.floor(Date.now() / 1000)));
  const [dateValue, setDateValue] = useState(() => toLocalInput(new Date()));
  const [error, setError] = useState("");
  function convertToDate() {
    const numeric = Number(timestamp);
    const milliseconds = Math.abs(numeric) < 100_000_000_000 ? numeric * 1000 : numeric;
    const date = new Date(milliseconds);
    if (!Number.isFinite(numeric) || Number.isNaN(date.getTime())) { setError("Enter a valid Unix timestamp."); return; }
    setDateValue(toLocalInput(date)); setError("");
  }
  function convertToTimestamp() {
    const date = new Date(dateValue);
    if (Number.isNaN(date.getTime())) { setError("Choose a valid date and time."); return; }
    setTimestamp(String(Math.floor(date.getTime() / 1000))); setError("");
  }
  return <>
    <div className="conversion-card"><FieldLabel label="Unix timestamp · seconds or milliseconds"><input className="form-input mono-text" value={timestamp} onChange={(event) => setTimestamp(event.target.value)} inputMode="numeric" /></FieldLabel><button className="button button-secondary" onClick={convertToDate}>Convert to date ↓</button></div>
    <div className="conversion-card"><FieldLabel label="Local date and time"><input className="form-input" type="datetime-local" value={dateValue} onChange={(event) => setDateValue(event.target.value)} /></FieldLabel><button className="button button-primary" onClick={convertToTimestamp}>Convert to timestamp ↑</button></div>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
  </>;
}

function RegexUtility() {
  const [pattern, setPattern] = useState("");
  const [flags, setFlags] = useState("g");
  const [sample, setSample] = useState("");
  const [matches, setMatches] = useState<string[]>([]);
  const [error, setError] = useState("");
  function run(event: FormEvent) {
    event.preventDefault();
    try {
      const expression = new RegExp(pattern, flags.includes("g") ? flags : `${flags}g`);
      const found = [...sample.matchAll(expression)].map((match) => `${match[0]}  ·  index ${match.index ?? 0}`);
      setMatches(found); setError("");
    } catch (reason) {
      setMatches([]); setError(reason instanceof Error ? reason.message : "Invalid regular expression.");
    }
  }
  return <form onSubmit={run}>
    <div className="field-row regex-fields"><FieldLabel label="Pattern"><input className="form-input mono-text" value={pattern} onChange={(event) => setPattern(event.target.value)} placeholder={"\\b\\w+@\\w+\\.\\w+\\b"} /></FieldLabel><FieldLabel label="Flags"><input className="form-input mono-text" value={flags} onChange={(event) => setFlags(event.target.value)} placeholder="gim" /></FieldLabel></div>
    <FieldLabel label="Test string"><textarea className="form-textarea code-area short-area" value={sample} onChange={(event) => setSample(event.target.value)} placeholder="Paste a sample to test…" /></FieldLabel>
    <div className="form-actions"><button className="button button-primary" type="submit">Find matches</button></div>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
    {matches.length > 0 && <div className="match-results"><strong>{matches.length} {matches.length === 1 ? "match" : "matches"}</strong>{matches.map((match, index) => <code key={`${match}-${index}`}>{match}</code>)}</div>}
    {!error && sample && matches.length === 0 && <p className="field-hint">No matches found.</p>}
  </form>;
}

function ColorUtility() {
  const [hex, setHex] = useState("#0ea5e9");
  const valid = /^#?(?:[0-9a-f]{3}|[0-9a-f]{6})$/i.test(hex);
  const normalized = hex.startsWith("#") ? hex : `#${hex}`;
  const rgb = valid ? hexToRgb(normalized) : null;
  const hsl = rgb ? rgbToHsl(...rgb) : null;
  return <>
    <div className="color-preview" style={{ backgroundColor: valid ? normalized : "transparent" }}><label className="color-picker-control" aria-label="Pick a colour"><input type="color" value={valid ? normalized : "#0ea5e9"} onChange={(event) => setHex(event.target.value)} /></label><span>{valid ? normalized.toUpperCase() : "Enter a valid HEX colour"}</span></div>
    <FieldLabel label="HEX"><input className={`form-input mono-text ${!valid ? "input-invalid" : ""}`} value={hex} onChange={(event) => setHex(event.target.value)} spellCheck={false} /></FieldLabel>
    {rgb && hsl && <div className="color-values"><div><span>RGB</span><strong>{rgb.join(", ")}</strong></div><div><span>HSL</span><strong>{hsl[0]}°, {hsl[1]}%, {hsl[2]}%</strong></div></div>}
  </>;
}

function QrUtility() {
  const [value, setValue] = useState("");
  const [image, setImage] = useState("");
  const [error, setError] = useState("");
  async function generate() {
    if (!value.trim()) { setError("Enter text or a URL first."); setImage(""); return; }
    try { setImage(await QRCode.toDataURL(value, { width: 320, margin: 2, color: { dark: "#111827", light: "#ffffff" } })); setError(""); }
    catch { setError("The QR code could not be generated."); }
  }
  return <>
    <FieldLabel label="Text or URL"><textarea className="form-textarea code-area short-area" value={value} onChange={(event) => setValue(event.target.value)} placeholder="https://example.com" /></FieldLabel>
    <div className="form-actions"><button className="button button-primary" onClick={() => void generate()}>Generate QR code</button></div>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
    {image && <div className="qr-result"><img src={image} alt="Generated QR code" /><a className="button button-secondary" href={image} download="central-hub-qr.png">Download PNG</a></div>}
  </>;
}

function FieldLabel({ label, children }: { label: string; children: ReactNode }) {
  return <label className="field-label"><span>{label}</span>{children}</label>;
}

function OutputBox({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const [copyMessage, setCopyMessage] = useState("");
  const outputId = useId();
  const copiedTimer = useRef<number | null>(null);

  useEffect(() => () => {
    if (copiedTimer.current !== null) window.clearTimeout(copiedTimer.current);
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setCopyMessage(`${label} copied to clipboard.`);
      if (copiedTimer.current !== null) window.clearTimeout(copiedTimer.current);
      copiedTimer.current = window.setTimeout(() => { setCopied(false); setCopyMessage(""); copiedTimer.current = null; }, 1800);
    } catch {
      setCopied(false);
      setCopyMessage("Could not copy. Select the result and copy it.");
      if (copiedTimer.current !== null) window.clearTimeout(copiedTimer.current);
      copiedTimer.current = window.setTimeout(() => { setCopyMessage(""); copiedTimer.current = null; }, 3500);
    }
  }
  return <div className="output-wrap"><div className="output-heading"><label htmlFor={outputId}>{label}</label><button type="button" className="text-button" aria-label={copied ? `${label} copied` : `Copy ${label.toLowerCase()}`} onClick={() => void copy()}>{copied ? "Copied" : "Copy"}</button></div><textarea id={outputId} className="form-textarea output-area mono-text" value={value} readOnly /><span className="sr-only" role="status" aria-live="polite">{copyMessage}</span></div>;
}

function hexToRgb(value: string): [number, number, number] {
  const raw = value.replace("#", "");
  const full = raw.length === 3 ? raw.split("").map((part) => part + part).join("") : raw;
  return [0, 2, 4].map((index) => Number.parseInt(full.slice(index, index + 2), 16)) as [number, number, number];
}

function rgbToHsl(red: number, green: number, blue: number): [number, number, number] {
  const r = red / 255; const g = green / 255; const b = blue / 255;
  const max = Math.max(r, g, b); const min = Math.min(r, g, b); const delta = max - min;
  let hue = 0; const lightness = (max + min) / 2;
  let saturation = 0;
  if (delta) {
    saturation = delta / (1 - Math.abs(2 * lightness - 1));
    if (max === r) hue = ((g - b) / delta) % 6;
    else if (max === g) hue = (b - r) / delta + 2;
    else hue = (r - g) / delta + 4;
    hue *= 60;
  }
  return [Math.round((hue + 360) % 360), Math.round(saturation * 100), Math.round(lightness * 100)];
}

function toLocalInput(date: Date): string {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}
