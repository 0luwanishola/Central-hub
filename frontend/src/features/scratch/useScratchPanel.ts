import { useCallback, useEffect, useRef, useState } from "react";
import { readScratchPanel, writeScratchPanel } from "./storage";

export const SCRATCH_PANEL_MIN_HEIGHT = 160;
export const SCRATCH_PANEL_DEFAULT_HEIGHT = 320;

export function maxScratchPanelHeight(): number {
  return Math.max(SCRATCH_PANEL_MIN_HEIGHT + 80, Math.round(window.innerHeight * 0.72));
}

export function clampScratchPanelHeight(value: number): number {
  return Math.min(Math.max(Math.round(value), SCRATCH_PANEL_MIN_HEIGHT), maxScratchPanelHeight());
}

// Remembers whether the output panel is open and how tall it is. The state is
// persisted per page so the panel behaves like an editor panel that keeps its
// last layout, and Ctrl+` toggles it the way VS Code does.
export function useScratchPanelState(storageKey: string) {
  const [panel, setPanel] = useState(() => {
    const stored = readScratchPanel(storageKey);
    return { open: stored.open, height: clampScratchPanelHeight(stored.height) };
  });
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (dragging) return; // Persist once after the drag, not on every pointer move.
    writeScratchPanel(storageKey, { open: panel.open, height: panel.height });
  }, [storageKey, panel, dragging]);

  const toggle = useCallback(() => {
    setPanel((current) => ({ ...current, open: !current.open }));
  }, []);

  const expand = useCallback(() => {
    setPanel((current) => (current.open ? current : { ...current, open: true }));
  }, []);

  const setHeight = useCallback((value: number) => {
    setPanel((current) => (current.height === clampScratchPanelHeight(value) ? current : { ...current, height: clampScratchPanelHeight(value) }));
  }, []);

  const toggleRef = useRef(toggle);
  toggleRef.current = toggle;

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "`" || !event.ctrlKey || event.shiftKey || event.altKey || event.metaKey) return;
      if (event.defaultPrevented) return;
      event.preventDefault();
      toggleRef.current();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return { open: panel.open, height: panel.height, dragging, toggle, expand, setHeight, setDragging };
}
