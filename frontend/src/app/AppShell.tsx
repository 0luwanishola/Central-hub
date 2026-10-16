import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getTools } from "../services/apiClient";
import type { Tool } from "../types";
import { Icon, type IconName } from "../ui/Icon";

export type AppContext = {
  tools: Tool[];
  toolsLoading: boolean;
  toolsError: Error | null;
  theme: "light" | "dark";
  setTheme: (theme: "light" | "dark") => void;
};

const categoryIcons: Record<string, IconName> = {
  crypto: "crypto",
  data: "data",
  design: "design",
  encoding: "encoding",
  generators: "generators",
  pdf: "pdf",
  sports: "sports",
  text: "text",
  time: "time",
};

// Fallback tool catalog matching backend/main.py TOOLS definition.
// Used when the API is unavailable so the UI remains functional.
const FALLBACK_TOOLS: Tool[] = [
  { id: "json-formatter", name: "JSON Formatter", description: "Format, validate, and minify JSON", icon: "json", category: "data", ready: true, execution: "client" },
  { id: "base64-encoder", name: "Base64 Encoder/Decoder", description: "Encode/decode Base64 strings", icon: "base64", category: "encoding", ready: true, execution: "client" },
  { id: "hash-generator", name: "Hash Generator", description: "Generate MD5, SHA1, SHA256 hashes", icon: "hash", category: "crypto", ready: true, execution: "client" },
  { id: "uuid-generator", name: "UUID Generator", description: "Generate v1, v4, v7 UUIDs", icon: "uuid", category: "generators", ready: true, execution: "client" },
  { id: "timestamp-converter", name: "Timestamp Converter", description: "Convert between Unix time and human dates", icon: "timestamp", category: "time", ready: true, execution: "client" },
  { id: "regex-tester", name: "Regex Tester", description: "Test and debug regular expressions", icon: "regex", category: "text", ready: true, execution: "client" },
  { id: "color-picker", name: "Color Picker", description: "Pick and convert colors (HEX, RGB, HSL)", icon: "color", category: "design", ready: true, execution: "client" },
  { id: "qr-generator", name: "QR Code Generator", description: "Generate QR codes from text/URLs", icon: "qr", category: "generators", ready: true, execution: "client" },
  { id: "live-score", name: "LiveScore", description: "Live football scores with scorers, assists and lineups", icon: "sports", category: "sports", ready: true, execution: "api" },

  // PDF tools (subset that have frontend pages)
  { id: "pdf-merge", name: "Merge PDFs", description: "Combine several PDFs into one, in order", icon: "pdf", category: "pdf", ready: true, execution: "api" },
  { id: "pdf-split", name: "Split PDF", description: "Pull pages out into separate PDFs, zipped", icon: "pdf", category: "pdf", ready: true, execution: "api" },
  { id: "pdf-page-organiser", name: "Organise Pages", description: "Reorder, rotate and delete pages", icon: "pdf", category: "pdf", ready: true, execution: "api" },
  { id: "pdf-add-text", name: "Add Text", description: "Stamp text onto a page", icon: "pdf", category: "pdf", ready: true, execution: "api" },
  { id: "pdf-add-image", name: "Add Image or Logo", description: "Place an image on a page", icon: "pdf", category: "pdf", ready: true, execution: "api" },
  { id: "pdf-watermark", name: "Add Watermark", description: "Overlay diagonal text across pages", icon: "pdf", category: "pdf", ready: true, execution: "api" },
  { id: "pdf-metadata", name: "Edit PDF Metadata", description: "View or change title, author and subject", icon: "pdf", category: "pdf", ready: true, execution: "api" },
  { id: "pdf-sign", name: "Sign PDF", description: "Draw, type or upload a signature", icon: "pdf", category: "pdf", ready: true, execution: "api" },

  // PDF tools requiring external dependencies (not ready)
  { id: "pdf-page-numbers", name: "Add Page Numbers", description: "Stamp page numbers in a chosen position", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "pdf-to-images", name: "PDF to Images", description: "Render pages to PNG or JPEG", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "images-to-pdf", name: "Images to PDF", description: "Turn PNG or JPEG files into a PDF", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "pdf-to-text", name: "Extract PDF Text", description: "Pull the text out to a plain file", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "pdf-to-word", name: "PDF to Word", description: "Convert to an editable .docx", icon: "pdf", category: "pdf", ready: false, requires: "LibreOffice", execution: "unavailable" },
  { id: "pdf-to-excel", name: "PDF to Excel", description: "Convert tables to .xlsx", icon: "pdf", category: "pdf", ready: false, requires: "LibreOffice", execution: "unavailable" },
  { id: "word-to-pdf", name: "Word to PDF", description: "Convert .docx and .odt to PDF", icon: "pdf", category: "pdf", ready: false, requires: "LibreOffice", execution: "unavailable" },
  { id: "pdf-ocr", name: "OCR Scanned PDF", description: "Make a scanned PDF searchable", icon: "pdf", category: "pdf", ready: false, requires: "Tesseract", execution: "unavailable" },
  { id: "pdf-annotate", name: "Highlight and Annotate", description: "Mark up text and add notes", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "pdf-redact", name: "Redact Text", description: "Black out text permanently", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "pdf-fill-forms", name: "Fill PDF Forms", description: "Complete AcroForm fields", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "pdf-request-signatures", name: "Request Signatures", description: "Prepare a document for others to sign", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "pdf-certificate-sign", name: "Digital Signature", description: "Cryptographically sign with a certificate", icon: "pdf", category: "pdf", ready: false, requires: "a certificate or signing service", execution: "unavailable" },
  { id: "pdf-verify-signature", name: "Verify Signatures", description: "Check whether a signature is intact", icon: "pdf", category: "pdf", ready: false, requires: "a certificate or signing service", execution: "unavailable" },
  { id: "pdf-compress", name: "Compress PDF", description: "Shrink file size without ghostscript", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "pdf-compress-small", name: "Compress PDF (Small)", description: "Aggressive compression via Ghostscript", icon: "pdf", category: "pdf", ready: false, requires: "Ghostscript", execution: "unavailable" },
  { id: "pdf-repair", name: "Repair PDF", description: "Rebuild a damaged or unreadable file", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "pdf-protect", name: "Encrypt PDF", description: "Add a password and set permissions", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "pdf-unlock", name: "Remove PDF Password", description: "Strip an open password you know", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
  { id: "pdf-compare", name: "Compare PDFs", description: "Show what changed between two versions", icon: "pdf", category: "pdf", ready: false, execution: "unavailable" },
];

export function AppShell() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tools"],
    queryFn: getTools,
    staleTime: 60_000,
    retry: 1,
  });
  // Use API data when available, otherwise fall back to static catalog
  const tools = data?.length ? data : FALLBACK_TOOLS;
  const categories = [...new Set(tools.map((tool) => tool.category))].sort();
  const [theme, setThemeState] = useState<"light" | "dark">(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light",
  );
  const [menuOpen, setMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.matchMedia("(max-width: 740px)").matches);
  const location = useLocation();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const previousPath = useRef(location.pathname);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 740px)");
    const updateViewport = () => {
      setIsMobile(media.matches);
      if (!media.matches) setMenuOpen(false);
    };
    media.addEventListener("change", updateViewport);
    return () => media.removeEventListener("change", updateViewport);
  }, []);

  useEffect(() => {
    if (!menuOpen || !isMobile) return;
    const firstLink = sidebarRef.current?.querySelector<HTMLElement>("a[href]");
    firstLink?.focus();
  }, [menuOpen, isMobile]);

  useEffect(() => {
    if (previousPath.current === location.pathname) return;
    previousPath.current = location.pathname;
    const focusHeading = () => {
      const heading = mainRef.current?.querySelector<HTMLElement>("h1");
      if (!heading) return false;
      heading.tabIndex = -1;
      heading.focus();
      return true;
    };
    if (focusHeading()) return;
    const observer = new MutationObserver(() => {
      if (focusHeading()) observer.disconnect();
    });
    if (mainRef.current) observer.observe(mainRef.current, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [location.pathname]);

  function closeMenu(restoreFocus: boolean) {
    const focusWasInSidebar = isMobile && Boolean(sidebarRef.current?.contains(document.activeElement));
    setMenuOpen(false);
    if (restoreFocus || focusWasInSidebar) {
      requestAnimationFrame(() => {
        if (restoreFocus || previousPath.current === location.pathname) menuButtonRef.current?.focus();
      });
    }
  }

  function handleSidebarKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeMenu(true);
      return;
    }
    if (event.key !== "Tab" || !menuOpen || !isMobile) return;
    const items = [...(sidebarRef.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled])') ?? [])];
    const first = items[0];
    const last = items.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }

  function setTheme(nextTheme: "light" | "dark") {
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
    localStorage.setItem("theme", nextTheme);
    setThemeState(nextTheme);
  }

  const pageTitle = location.pathname.startsWith("/settings")
    ? "Settings"
    : location.pathname.startsWith("/activities")
      ? "Activities"
      : location.pathname.startsWith("/learn")
        ? "Code Quest"
        : location.pathname.startsWith("/notes")
          ? "Quick notes"
          : location.pathname.startsWith("/tools")
            ? "Digital tools"
            : location.pathname.startsWith("/tool/live-score")
              ? "LiveScore"
              : location.pathname.startsWith("/match/")
                ? "Match details"
                : location.pathname.startsWith("/tool/")
                  ? tools.find((tool) => location.pathname.endsWith(tool.id))?.name ?? "Tool"
                  : location.pathname.startsWith("/category/")
                    ? displayCategory(location.pathname.split("/").pop() ?? "")
                    : "Home";

  return (
    <div className="app-frame">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      {menuOpen && <button className="mobile-scrim" aria-label="Close navigation menu" onClick={() => closeMenu(true)} />}
      <aside id="primary-navigation" ref={sidebarRef} className={`sidebar ${menuOpen ? "sidebar-open" : ""}`} aria-label="Primary navigation" aria-hidden={isMobile && !menuOpen} inert={isMobile && !menuOpen} onKeyDown={handleSidebarKeyDown}>
        <NavLink to="/" end className="brand" onClick={() => closeMenu(false)}>
          <span className="brand-mark">C<span>H</span></span>
          <span className="brand-name">Central<span>Hub</span></span>
        </NavLink>

        <nav className="side-nav" aria-label="Main navigation">
          <p className="nav-label">Your hub</p>
          <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? "nav-active" : ""}`} onClick={() => closeMenu(false)}>
            <Icon name="home" className="nav-icon" /><span>Home</span>
          </NavLink>
          <NavLink to="/activities" className={({ isActive }) => `nav-item ${isActive ? "nav-active" : ""}`} onClick={() => closeMenu(false)}>
            <Icon name="activities" className="nav-icon" /><span>Activities</span><span className="nav-count">3</span>
          </NavLink>
          <NavLink to="/learn" className={({ isActive }) => `nav-item ${isActive ? "nav-active" : ""}`} onClick={() => closeMenu(false)}>
            <Icon name="code" className="nav-icon" /><span>Code Quest</span>
          </NavLink>
          <NavLink to="/notes" className={({ isActive }) => `nav-item ${isActive ? "nav-active" : ""}`} onClick={() => closeMenu(false)}>
            <Icon name="notes" className="nav-icon" /><span>Quick notes</span>
          </NavLink>
          <NavLink to="/tools" className={({ isActive }) => `nav-item ${isActive ? "nav-active" : ""}`} onClick={() => closeMenu(false)}>
            <Icon name="tools" className="nav-icon" /><span>Digital tools</span><span className="nav-count">{tools.length}</span>
          </NavLink>

          <p className="nav-label nav-label-spaced">Tool collections</p>
          {categories.map((category) => {
            const count = tools.filter((tool) => tool.category === category).length;
            return (
              <NavLink
                key={category}
                to={`/category/${encodeURIComponent(category)}`}
                className={({ isActive }) => `nav-item ${isActive ? "nav-active" : ""}`}
                onClick={() => closeMenu(false)}
              >
                <Icon name={categoryIcons[category] ?? "tools"} className="nav-icon" />
                <span>{displayCategory(category)}</span>
                <span className="nav-count">{count}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <NavLink to="/settings" className={({ isActive }) => `nav-item ${isActive ? "nav-active" : ""}`} onClick={() => closeMenu(false)}>
            <Icon name="settings" className="nav-icon" /><span>Settings</span>
          </NavLink>
          <div className="sidebar-footnote"><span className="status-dot" /> Your workspace, ready</div>
        </div>
      </aside>

      <main id="main-content" ref={mainRef} className="main-area" tabIndex={-1}>
        <header className="topbar">
          <button ref={menuButtonRef} className="icon-button menu-button" aria-label={menuOpen ? "Close menu" : "Open menu"} aria-controls="primary-navigation" aria-expanded={menuOpen} onClick={() => menuOpen ? closeMenu(true) : setMenuOpen(true)}><Icon name="menu" /></button>
          <div className="breadcrumb"><span>Central Hub</span><span className="breadcrumb-divider">/</span><strong>{pageTitle}</strong></div>
          <div className="topbar-actions">
            <button
              className="theme-toggle"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              <Icon name={theme === "dark" ? "sun" : "moon"} />
              <span className="theme-label">{theme === "dark" ? "Light" : "Dark"}</span>
            </button>
          </div>
        </header>

        {error && !location.pathname.startsWith("/activities") && !location.pathname.startsWith("/notes") && !location.pathname.startsWith("/learn") && <div className="api-banner" role="status">Can’t connect to the tool catalog. Start the FastAPI backend at <code>127.0.0.1:8000</code> and refresh.</div>}
        <Outlet context={{ tools, toolsLoading: isLoading, toolsError: error ?? null, theme, setTheme } satisfies AppContext} />
      </main>
    </div>
  );
}

export function displayCategory(category: string): string {
  return category === "pdf" ? "PDF" : category.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
