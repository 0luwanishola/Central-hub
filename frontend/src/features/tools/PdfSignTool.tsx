import { useRef, useState } from "react";
import type { ChangeEvent, FormEvent, MouseEvent, PointerEvent as ReactPointerEvent } from "react";
import { apiUrl, applyPdfSignature, getPdfSignPage, previewPdfSign } from "../../services/apiClient";
import type { PdfDownload, PdfSignPreview } from "../../types";
import { Icon } from "../../ui/Icon";

const MAX_UPLOAD = 100 * 1024 * 1024;

export function PdfSignTool() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PdfSignPreview | null>(null);
  const [spot, setSpot] = useState<{ across: number; down: number } | null>(null);
  const [signature, setSignature] = useState("");
  const [width, setWidth] = useState("25");
  const [typedName, setTypedName] = useState("");
  const [busy, setBusy] = useState<"preview" | "page" | "apply" | null>(null);
  const [error, setError] = useState("");
  const [result, setResult] = useState<PdfDownload | null>(null);
  const padRef = useRef<HTMLCanvasElement | null>(null);
  const drawingRef = useRef(false);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    setError("");
  }

  async function startPreview(event: FormEvent) {
    event.preventDefault();
    if (!file) { setError("Choose a PDF to sign."); return; }
    if (file.size > MAX_UPLOAD) { setError("The upload must be 100 MB or smaller."); return; }
    setBusy("preview"); setError(""); setResult(null);
    try {
      setPreview(await previewPdfSign(file, 1));
      setSpot(null); setSignature("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The PDF could not be opened.");
    } finally {
      setBusy(null);
    }
  }

  async function goToPage(page: number) {
    if (!preview || busy) return;
    setBusy("page"); setError("");
    try {
      setPreview(await getPdfSignPage(preview.token, page));
      setSpot(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "That page could not be rendered.");
    } finally {
      setBusy(null);
    }
  }

  function padContext(): CanvasRenderingContext2D | null {
    return padRef.current?.getContext("2d") ?? null;
  }

  function clearPad() {
    const canvas = padRef.current;
    const context = padContext();
    if (canvas && context) context.clearRect(0, 0, canvas.width, canvas.height);
    setSignature("");
  }

  function canvasPoint(event: ReactPointerEvent<HTMLCanvasElement>) {
    const canvas = event.currentTarget;
    const bounds = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - bounds.left) * (canvas.width / bounds.width),
      y: (event.clientY - bounds.top) * (canvas.height / bounds.height),
    };
  }

  function beginStroke(event: ReactPointerEvent<HTMLCanvasElement>) {
    const context = padContext();
    if (!context) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = canvasPoint(event);
    context.beginPath();
    context.moveTo(point.x, point.y);
    context.lineCap = "round";
    context.lineJoin = "round";
    context.lineWidth = 2.5;
    context.strokeStyle = "#111827";
    drawingRef.current = true;
  }

  function extendStroke(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (!drawingRef.current) return;
    const context = padContext();
    if (!context) return;
    const point = canvasPoint(event);
    context.lineTo(point.x, point.y);
    context.stroke();
  }

  function endStroke(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    setSignature(event.currentTarget.toDataURL("image/png"));
  }

  function applyTypedName() {
    const canvas = padRef.current;
    const context = padContext();
    const name = typedName.trim();
    if (!canvas || !context || !name) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#111827";
    context.font = "italic 64px 'Segoe Script', 'Brush Script MT', cursive";
    context.textBaseline = "middle";
    context.fillText(name, 20, canvas.height / 2, canvas.width - 40);
    setSignature(canvas.toDataURL("image/png"));
    setError("");
  }

  function uploadSignature(event: ChangeEvent<HTMLInputElement>) {
    const chosen = event.target.files?.[0];
    event.target.value = "";
    if (!chosen) return;
    const url = URL.createObjectURL(chosen);
    const image = new Image();
    image.onload = () => {
      const canvas = padRef.current;
      const context = padContext();
      URL.revokeObjectURL(url);
      if (!canvas || !context) return;
      context.clearRect(0, 0, canvas.width, canvas.height);
      const scale = Math.min(canvas.width / image.width, canvas.height / image.height, 1);
      const drawWidth = image.width * scale;
      const drawHeight = image.height * scale;
      context.drawImage(image, (canvas.width - drawWidth) / 2, (canvas.height - drawHeight) / 2, drawWidth, drawHeight);
      setSignature(canvas.toDataURL("image/png"));
      setError("");
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      setError("That image could not be read. Choose a PNG or JPEG.");
    };
    image.src = url;
  }

  function placeSpot(event: MouseEvent<HTMLImageElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    setSpot({
      across: Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
      down: Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
    });
  }

  async function apply() {
    if (!preview || !spot || !signature) return;
    setBusy("apply"); setError(""); setResult(null);
    try {
      setResult(await applyPdfSignature({
        token: preview.token,
        page: preview.page,
        across: spot.across,
        down: spot.down,
        width: Number(width) || 25,
        signature,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The signature could not be applied.");
    } finally {
      setBusy(null);
    }
  }

  function startOver() {
    setFile(null); setPreview(null); setSpot(null); setSignature("");
    setTypedName(""); setWidth("25"); setResult(null); setError("");
  }

  return <>
    {!preview && !result && (
      <form className="pdf-form" onSubmit={(event) => void startPreview(event)}>
        <div className="pdf-tip">Choose a PDF, then click the page where the signature belongs. You can draw, type or upload the signature itself.</div>
        <label className="field-label file-field"><span>PDF file</span>
          <input type="file" accept=".pdf,application/pdf" onChange={chooseFile} />
          <small>{file ? `${file.name} · maximum 100 MB.` : "Choose a PDF to sign. Maximum upload: 100 MB."}</small>
        </label>
        <div className="form-actions"><button className="button button-primary" type="submit" disabled={busy !== null || !file}>{busy === "preview" ? <><span className="spinner" /> Rendering…</> : "Preview the first page"}</button></div>
      </form>
    )}

    {preview && !result && (
      <div className="pdf-form sign-workspace">
        <div className="pdf-tip">Click the page where the signature's top-left corner should go, then apply it.</div>
        <div className="sign-stage">
          <img className="sign-page" src={preview.image} alt={`Page ${preview.page} of the uploaded PDF`} onClick={placeSpot} draggable={false} />
          {spot && <span className="sign-spot" style={{ left: `${spot.across * 100}%`, top: `${spot.down * 100}%` }} aria-hidden="true" />}
        </div>
        <div className="sign-toolbar">
          <button className="button button-secondary" type="button" disabled={busy !== null || preview.page <= 1} onClick={() => void goToPage(preview.page - 1)}>Previous page</button>
          <span>{busy === "page" ? "Rendering…" : `Page ${preview.page} of ${preview.pages}`}</span>
          <button className="button button-secondary" type="button" disabled={busy !== null || preview.page >= preview.pages} onClick={() => void goToPage(preview.page + 1)}>Next page</button>
        </div>
        <p className="sign-hint">{spot ? "The signature will be placed with its top-left corner at the marker. Click again to move it." : "No position chosen yet — click the page above."}</p>

        <label className="field-label"><span>Signature</span>
          <canvas ref={padRef} className="sign-pad" width={480} height={160} onPointerDown={beginStroke} onPointerMove={extendStroke} onPointerUp={endStroke} onPointerCancel={endStroke} aria-label="Draw your signature" />
          <small>Draw with the mouse or a finger. {signature ? "Signature captured." : "Nothing captured yet."}</small>
        </label>
        <div className="sign-pad-actions">
          <button className="text-button" type="button" onClick={clearPad} disabled={busy !== null}>Clear pad</button>
        </div>

        <label className="field-label file-field"><span>Or upload a signature image</span>
          <input type="file" accept="image/png,image/jpeg" onChange={uploadSignature} />
          <small>PNG or JPEG. A plain background is trimmed off automatically.</small>
        </label>

        <div className="sign-typed">
          <label className="field-label"><span>Or type your name</span>
            <input className="form-input" type="text" value={typedName} maxLength={60} onChange={(event) => setTypedName(event.target.value)} />
          </label>
          <button className="button button-secondary" type="button" disabled={!typedName.trim() || busy !== null} onClick={applyTypedName}>Use typed name</button>
        </div>

        <label className="field-label"><span>Signature width (% of page)</span>
          <input className="form-input" type="number" min={1} max={100} value={width} onChange={(event) => setWidth(event.target.value)} />
          <small>How wide the signature sits on the page, as a percentage. 25% suits most documents.</small>
        </label>

        <div className="form-actions">
          <button className="button button-primary" type="button" disabled={!spot || !signature || busy !== null} onClick={() => void apply()}>{busy === "apply" ? <><span className="spinner" /> Signing…</> : `Sign page ${preview.page}`}</button>
          <button className="button button-secondary" type="button" disabled={busy !== null} onClick={startOver}>Start over</button>
        </div>
      </div>
    )}

    {result && <div className="pdf-success" role="status"><div><span className="success-mark"><Icon name="check" /></span><div><strong>Your signed PDF is ready</strong><p>{result.filename} · download link expires after 10 minutes and works once.</p></div></div><a className="button button-primary" href={apiUrl(result.download_url)} download={result.filename}>Download file <Icon name="download" /></a></div>}
    {result && <div className="form-actions"><button className="button button-secondary" type="button" onClick={startOver}>Sign another PDF</button></div>}

    {error && <div className="notice notice-error" role="alert">{error}</div>}
    <p className="privacy-note">Your file is sent to the configured Central Hub backend for processing. The backend temporarily stores it and removes the result after download or expiry.</p>
  </>;
}
