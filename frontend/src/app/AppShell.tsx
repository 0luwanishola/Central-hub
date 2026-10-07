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

export function AppShell() {
  const { data, isLoading, error } = useQuery({ queryKey: ["tools"], queryFn: getTools });
  const tools = data ?? [];
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
