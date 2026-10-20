import {
  useEffect,
  useId,
  useRef,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { Icon } from "../../ui/Icon";
import { clampScratchPanelHeight, maxScratchPanelHeight, SCRATCH_PANEL_DEFAULT_HEIGHT, SCRATCH_PANEL_MIN_HEIGHT } from "./useScratchPanel";

const KEYBOARD_RESIZE_STEP = 40;

interface ScratchOutputPanelProps {
  eyebrow: string;
  title: string;
  ariaLabel: string;
  status: { label: string; tone: "success" | "warning" | "error" } | null;
  open: boolean;
  height: number;
  dragging: boolean;
  onToggle: () => void;
  onResize: (height: number) => void;
  onDragChange: (dragging: boolean) => void;
  panelRef?: RefObject<HTMLElement | null>;
  footer: ReactNode;
  children: ReactNode;
}

export function ScratchOutputPanel(props: ScratchOutputPanelProps) {
  const { eyebrow, title, ariaLabel, status, open, height, dragging, onToggle, onResize, onDragChange, panelRef, footer, children } = props;
  const bodyId = useId();
  const dragOrigin = useRef<{ pointerY: number; height: number } | null>(null);

  useEffect(() => () => document.body.classList.remove("scratch-panel-dragging"), []);

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragOrigin.current = { pointerY: event.clientY, height };
    onDragChange(true);
    document.body.classList.add("scratch-panel-dragging");
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (!dragOrigin.current) return;
    onResize(dragOrigin.current.height + (dragOrigin.current.pointerY - event.clientY));
  }

  function handlePointerEnd(event: ReactPointerEvent<HTMLDivElement>) {
    if (!dragOrigin.current) return;
    dragOrigin.current = null;
    onDragChange(false);
    document.body.classList.remove("scratch-panel-dragging");
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function handleResizeKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === "ArrowUp") {
      event.preventDefault();
      onResize(clampScratchPanelHeight(height + KEYBOARD_RESIZE_STEP));
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      onResize(clampScratchPanelHeight(height - KEYBOARD_RESIZE_STEP));
    } else if (event.key === "Home") {
      event.preventDefault();
      onResize(SCRATCH_PANEL_DEFAULT_HEIGHT);
    }
  }

  return (
    <section
      ref={panelRef}
      className={`scratch-panel scratch-output ${open ? "expanded" : "collapsed"}${dragging ? " resizing" : ""}`}
      aria-label={ariaLabel}
    >
      {open && (
        <div
          className="scratch-panel-resizer"
          role="separator"
          aria-orientation="horizontal"
          aria-label="Resize the output panel"
          aria-valuemin={SCRATCH_PANEL_MIN_HEIGHT}
          aria-valuemax={maxScratchPanelHeight()}
          aria-valuenow={height}
          tabIndex={0}
          title="Drag to resize, double-click to reset the height"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onPointerCancel={handlePointerEnd}
          onDoubleClick={() => onResize(SCRATCH_PANEL_DEFAULT_HEIGHT)}
          onKeyDown={handleResizeKeyDown}
        />
      )}

      <div className="scratch-output-heading">
        <button type="button" className="scratch-panel-toggle" aria-expanded={open} aria-controls={bodyId} onClick={onToggle}>
          <span className="scratch-panel-chevron" aria-hidden="true"><Icon name="chevron-down" /></span>
          <span className="scratch-panel-titles">
            <span className="scratch-panel-eyebrow">{eyebrow}</span>
            <span className="scratch-panel-title">{title}</span>
          </span>
        </button>
        {status && <span className={`scratch-status-pill ${status.tone}`}>{status.label}</span>}
      </div>

      {open && (
        <>
          <div
            className="scratch-output-body"
            id={bodyId}
            aria-live="polite"
            style={{ "--scratch-panel-height": `${height}px` } as CSSProperties}
          >
            {children}
          </div>
          <div className="scratch-output-footer">{footer}</div>
        </>
      )}
    </section>
  );
}
