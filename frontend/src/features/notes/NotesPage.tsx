import { useEffect, useRef, useState } from "react";

const NOTE_KEY = "central-hub:quick-note:v1";
type SaveState = "saved" | "saving" | "unavailable";

function readNote(): string {
  try {
    return localStorage.getItem(NOTE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function NotesPage() {
  const [note, setNote] = useState(readNote);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [undoContent, setUndoContent] = useState<string | null>(null);
  const undoTimer = useRef<number | null>(null);

  useEffect(() => () => {
    if (undoTimer.current !== null) window.clearTimeout(undoTimer.current);
  }, []);

  function clearNote() {
    if (!note) return;
    setUndoContent(note);
    setNote("");
    if (undoTimer.current !== null) window.clearTimeout(undoTimer.current);
    undoTimer.current = window.setTimeout(() => {
      setUndoContent(null);
      undoTimer.current = null;
    }, 5000);
  }

  function undoClear() {
    if (undoContent === null) return;
    setNote(undoContent);
    setUndoContent(null);
    if (undoTimer.current !== null) window.clearTimeout(undoTimer.current);
    undoTimer.current = null;
  }

  function updateNote(value: string) {
    setNote(value);
    if (undoContent !== null) {
      setUndoContent(null);
      if (undoTimer.current !== null) window.clearTimeout(undoTimer.current);
      undoTimer.current = null;
    }
  }

  useEffect(() => {
    setSaveState("saving");
    const timeout = window.setTimeout(() => {
      try {
        if (note) localStorage.setItem(NOTE_KEY, note);
        else localStorage.removeItem(NOTE_KEY);
        setSaveState("saved");
      } catch {
        setSaveState("unavailable");
      }
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [note]);

  return (
    <section className="page-wrap notes-page">
      <header className="page-heading">
        <span className="eyebrow">A little space to think</span>
        <h1>Quick notes</h1>
        <p className="muted">A simple scratchpad saved in this browser on this device.</p>
      </header>
      <section className="notes-card" aria-labelledby="note-label">
        <div className="notes-card-top">
          <label id="note-label" htmlFor="quick-note">Your note</label>
          <span className={`save-state save-state-${saveState}`} aria-live="polite">{saveState === "saving" ? "Saving…" : saveState === "saved" ? "Saved on this device" : "Browser storage unavailable"}</span>
        </div>
        <textarea id="quick-note" className="form-textarea notes-textarea" value={note} onChange={(event) => updateNote(event.target.value)} maxLength={5000} placeholder="Write a reminder, an idea, or anything you want to come back to…" />
        <div className="notes-footer">
          <span>{note.length} / 5,000 characters</span>
          <div className="notes-actions">
            {undoContent !== null && <button type="button" className="text-button" onClick={undoClear}>Undo clear</button>}
            <button type="button" className="text-button" onClick={clearNote} disabled={!note}>Clear note</button>
          </div>
        </div>
        <span className="sr-only" role="status" aria-live="polite">{undoContent !== null ? "Note cleared. Undo is available for five seconds." : ""}</span>
      </section>
      <p className="notes-privacy">This note is stored in your browser. It is not sent to the Central Hub backend.</p>
    </section>
  );
}
