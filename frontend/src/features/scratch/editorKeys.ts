import type { KeyboardEvent } from "react";

type ScratchEditorKeyOptions = {
  value: string;
  language: "python" | "sql";
  onChange: (value: string) => void;
  onRun: () => void;
};

export function handleScratchEditorKeyDown(
  event: KeyboardEvent<HTMLTextAreaElement>,
  { value, language, onChange, onRun }: ScratchEditorKeyOptions,
) {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    onRun();
    return;
  }

  if (event.key === "Tab") {
    event.preventDefault();
    const editor = event.currentTarget;
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    const indent = "    ";
    onChange(`${value.slice(0, start)}${indent}${value.slice(end)}`);
    requestAnimationFrame(() => editor.setSelectionRange(start + indent.length, start + indent.length));
    return;
  }

  if (event.key !== "Enter") return;

  event.preventDefault();
  const editor = event.currentTarget;
  const start = editor.selectionStart;
  const end = editor.selectionEnd;
  const beforeCursor = value.slice(0, start);
  const currentLine = beforeCursor.slice(beforeCursor.lastIndexOf("\n") + 1);
  const indentation = currentLine.match(/^\s*/)?.[0] ?? "";
  const extraIndent = language === "python" && /:\s*(?:#.*)?$/.test(currentLine) ? "    " : "";
  const insertion = `\n${indentation}${extraIndent}`;
  onChange(`${beforeCursor}${insertion}${value.slice(end)}`);
  requestAnimationFrame(() => editor.setSelectionRange(start + insertion.length, start + insertion.length));
}

export function createScratchRunId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
