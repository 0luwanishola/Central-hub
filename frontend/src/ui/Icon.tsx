import type { ReactNode } from "react";

export type IconName =
  | "home" | "activities" | "code" | "notes" | "tools" | "settings" | "menu"
  | "sun" | "moon" | "arrow" | "refresh" | "download" | "chevron-left" | "chevron-right" | "crypto" | "data" | "design" | "encoding"
  | "generators" | "pdf" | "sports" | "text" | "time" | "tic-tac-toe"
  | "memory" | "guess" | "search" | "close" | "check" | "lock" | "trophy" | "json" | "base64" | "hash" | "uuid" | "timestamp"
  | "regex" | "color" | "qr";

const drawings: Record<IconName, ReactNode> = {
  home: <><path d="m3 10 9-7 9 7" /><path d="M5 9v12h14V9M9 21v-7h6v7" /></>,
  activities: <><rect x="3" y="3" width="8" height="8" rx="2" /><rect x="13" y="3" width="8" height="8" rx="2" /><rect x="3" y="13" width="8" height="8" rx="2" /><rect x="13" y="13" width="8" height="8" rx="2" /></>,
  code: <><path d="m8 8-4 4 4 4M16 8l4 4-4 4M14 5l-4 14" /></>,
  notes: <><path d="M5 3h11l3 3v15H5z" /><path d="M15 3v4h4M8 12h8M8 16h6" /></>,
  tools: <><path d="M14.5 6.5a5 5 0 0 0-6.4 6.4L3 18a2.1 2.1 0 0 0 3 3l5.1-5.1a5 5 0 0 0 6.4-6.4l-3 3-3-3z" /><path d="m15 4 5 5" /></>,
  settings: <><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3" /><path d="M2 14h4M10 8h4M18 16h4" /></>,
  menu: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" /></>,
  moon: <><path d="M20.8 13A8.5 8.5 0 0 1 11 3.2 8.5 8.5 0 1 0 20.8 13Z" /></>,
  arrow: <><path d="M7 17 17 7M8 7h9v9" /></>,
  refresh: <><path d="M20 11a8 8 0 0 0-14.8-4L4 9M4 5v4h4M4 13a8 8 0 0 0 14.8 4L20 15m0 4v-4h-4" /></>,
  download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" /></>,
  "chevron-left": <><path d="m15 18-6-6 6-6" /></>,
  "chevron-right": <><path d="m9 18 6-6-6-6" /></>,
  crypto: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></>,
  data: <><path d="m8 5-5 7 5 7M16 5l5 7-5 7M14 4l-4 16" /></>,
  design: <><path d="M12 3a9 9 0 1 0 0 18h1.2a2 2 0 0 0 1.5-3.3 1.8 1.8 0 0 1 1.4-3h1.4A3.5 3.5 0 0 0 21 11.2C21 6.7 17 3 12 3Z" /><path d="M7.5 10h.01M10 7.5h.01M15 8h.01" /></>,
  encoding: <><path d="M4 8h15l-3-3M20 16H5l3 3" /></>,
  generators: <><path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z" /><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z" /></>,
  pdf: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h5M8 16h8M8 12h4" /></>,
  sports: <><circle cx="12" cy="12" r="9" /><path d="m12 7 3 2-1 4h-4L9 9l3-2ZM5 6l4 3M19 6l-4 3M5 18l5-5M19 18l-5-5" /></>,
  text: <><path d="M4 6V4h16v2M12 4v16M8 20h8" /></>,
  time: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  "tic-tac-toe": <><path d="M9 3v18M15 3v18M3 9h18M3 15h18" /></>,
  memory: <><rect x="3" y="3" width="8" height="8" rx="1.5" /><rect x="13" y="3" width="8" height="8" rx="1.5" /><rect x="3" y="13" width="8" height="8" rx="1.5" /><rect x="13" y="13" width="8" height="8" rx="1.5" /></>,
  guess: <><path d="M9.5 9a2.7 2.7 0 1 1 4.5 2c-1.3 1.1-2 1.5-2 3" /><path d="M12 18h.01" /><circle cx="12" cy="12" r="9" /></>,
  search: <><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4.5 4.5" /></>,
  close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16.5 9" /></>,
  lock: <><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" /></>,
  trophy: <><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4ZM7 6H4v2a4 4 0 0 0 4 4M17 6h3v2a4 4 0 0 1-4 4" /></>,
  json: <><path d="m8 5-4 7 4 7M16 5l4 7-4 7M14 4l-4 16" /></>,
  base64: <><path d="M4 7h16M4 12h10M4 17h7" /><circle cx="18" cy="16" r="2" /></>,
  hash: <><path d="M5 9h14M4 15h14M10 4 8 20M16 4l-2 16" /></>,
  uuid: <><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4" /><circle cx="12" cy="12" r="8" /></>,
  timestamp: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2M7 2 4 5M17 2l3 3" /></>,
  regex: <><path d="m4 6 6 6-6 6M13 18h7M14 6h6" /></>,
  color: <><path d="M12 3a9 9 0 1 0 0 18h1.2a2 2 0 0 0 1.5-3.3 1.8 1.8 0 0 1 1.4-3h1.4A3.5 3.5 0 0 0 21 11.2C21 6.7 17 3 12 3Z" /><path d="M7.5 10h.01M10 7.5h.01M15 8h.01" /></>,
  qr: <><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5" /><path d="M8 8h3v3H8zM14 8h2v2h-2zM14 14h3v3h-3zM8 14h2v2H8z" /></>,
};

export function Icon({ name, className }: { name: IconName; className?: string }) {
  return <svg aria-hidden="true" className={className} width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" focusable="false">{drawings[name]}</svg>;
}

const toolIcons: Record<string, IconName> = {
  "json-formatter": "json",
  "base64-encoder": "base64",
  "hash-generator": "hash",
  "uuid-generator": "uuid",
  "timestamp-converter": "timestamp",
  "regex-tester": "regex",
  "color-picker": "color",
  "qr-generator": "qr",
  "live-score": "sports",
};

const categoryIcons: Record<string, IconName> = {
  crypto: "crypto", data: "data", design: "design", encoding: "encoding",
  generators: "generators", pdf: "pdf", sports: "sports", text: "text", time: "time",
};

export function iconForTool(id: string, category: string): IconName {
  if (id.startsWith("pdf-")) return "pdf";
  return toolIcons[id] ?? categoryIcons[category] ?? "tools";
}
