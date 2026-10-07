import { useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useOutletContext, useParams, useSearchParams } from "react-router-dom";
import { displayCategory } from "../../app/AppShell";
import type { AppContext } from "../../app/AppShell";
import type { Tool } from "../../types";
import { Icon, iconForTool } from "../../ui/Icon";
import { LEARNING_SESSION_QUERY_KEY, startLearningSession } from "../../services/apiClient";

const RECENT_TOOLS_KEY = "central-hub:recent-tools:v1";

const descriptions: Record<string, string> = {
  crypto: "Create hashes and work with secure formats.",
  data: "Format, inspect and shape everyday data.",
  design: "Quick helpers for colour and visual details.",
  encoding: "Move text safely between common encodings.",
  generators: "Make useful IDs, codes and fresh starting points.",
  pdf: "Work with PDF files using focused document tools.",
  sports: "Follow live football scores, fixtures and match details.",
  text: "Small, focused helpers for writing and patterns.",
  time: "Convert timestamps and make dates easier to read.",
};

const destinations = [
  { label: "Offline activities", detail: "Play a quick game", to: "/activities", terms: "game games play activity activities tic tac toe memory match number guess" },
  { label: "Code Quest", detail: "Learn Python and SQL", to: "/learn", terms: "learn code python sql coding quest" },
  { label: "Quick notes", detail: "Write a reminder or idea", to: "/notes", terms: "note notes write reminder idea" },
  { label: "Digital tools", detail: "Browse every tool", to: "/tools", terms: "tools utility utilities catalog" },
];

function readRecentToolIds(): string[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(RECENT_TOOLS_KEY) ?? "[]");
    return Array.isArray(stored) ? stored.filter((item): item is string => typeof item === "string").slice(0, 8) : [];
  } catch {
    return [];
  }
}

function rememberTool(toolId: string) {
  try {
    localStorage.setItem(RECENT_TOOLS_KEY, JSON.stringify([toolId, ...readRecentToolIds().filter((id) => id !== toolId)].slice(0, 8)));
  } catch {
    // Recent tools improve discovery but are optional when browser storage is unavailable.
  }
}

export function CatalogPage({ showAll = false }: { showAll?: boolean }) {
  const { tools, toolsLoading, toolsError } = useOutletContext<AppContext>();
  const { categoryId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: learningSession } = useQuery({ queryKey: LEARNING_SESSION_QUERY_KEY, queryFn: startLearningSession, staleTime: 30_000, enabled: !showAll && !categoryId });
  const search = searchParams.get("search") ?? "";
  const categories = [...new Set(tools.map((tool) => tool.category))].sort();
  const filteredTools = useMemo(() => tools.filter((tool) =>
    (!categoryId || tool.category === categoryId) &&
    `${tool.name} ${tool.description} ${tool.category}`.toLowerCase().includes(search.trim().toLowerCase()),
  ), [tools, categoryId, search]);

  function updateSearch(value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set("search", value);
    else next.delete("search");
    setSearchParams(next, { replace: true });
  }

  if ((showAll || categoryId) && toolsLoading && tools.length === 0) return <section className="page-wrap"><div className="loading-line">Loading your workspace...</div></section>;
  if ((showAll || categoryId) && toolsError && tools.length === 0) return <section className="page-wrap"><div className="empty-state"><span className="eyebrow">Catalog unavailable</span><h1>Tools will appear here.</h1><p>Start the FastAPI backend, then reload this page.</p></div></section>;

  if (showAll || categoryId) {
    const heading = categoryId ? displayCategory(categoryId) : "Digital tools";
    const description = categoryId ? descriptions[categoryId] ?? "A focused set of tools for everyday tasks." : "Browse quick browser utilities, document tools, and connected services.";
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    const availableTools = filteredTools.filter((tool) => tool.ready);
    const unavailableTools = filteredTools.filter((tool) => !tool.ready);
    return (
      <section className="page-wrap">
        <div className="page-heading-row">
          <div><span className="eyebrow">{categoryId ? "Tool collection" : "Browse and search"}</span><h1>{heading}</h1><p className="muted">{description}</p></div>
          {categoryId && <div className="heading-stat"><strong>{tools.filter((tool) => tool.category === categoryId && tool.ready).length}</strong><span>ready to use</span></div>}
        </div>
        <div className="catalog-controls">
          <nav className="category-pills" aria-label="Filter tools by category">
            <Link aria-current={!categoryId ? "page" : undefined} className={`filter-pill ${!categoryId ? "filter-pill-active" : ""}`} to={`/tools${query}`}>All tools</Link>
            {categories.map((category) => <Link key={category} aria-current={category === categoryId ? "page" : undefined} className={`filter-pill ${category === categoryId ? "filter-pill-active" : ""}`} to={`/category/${encodeURIComponent(category)}${query}`}>{displayCategory(category)}</Link>)}
          </nav>
          <SearchInput value={search} onChange={updateSearch} />
        </div>
        <p className="catalog-result-count" role="status" aria-live="polite">{filteredTools.length} {filteredTools.length === 1 ? "tool" : "tools"}{search ? ` matching “${search}”` : ""}</p>
        {filteredTools.length ? <>
          {availableTools.length > 0 && <section className="catalog-group" aria-labelledby="available-tools-heading">
            <div className="section-heading catalog-group-heading"><div><span className="eyebrow">Ready to use</span><h2 id="available-tools-heading">Available now</h2></div><span>{availableTools.length}</span></div>
            <ToolGrid tools={availableTools} />
          </section>}
          {unavailableTools.length > 0 && <section className="catalog-group" aria-labelledby="upcoming-tools-heading">
            <div className="section-heading catalog-group-heading"><div><span className="eyebrow">Not ready yet</span><h2 id="upcoming-tools-heading">Needs setup or development</h2><p>Some tools need an optional program; others are still being built.</p></div><span>{unavailableTools.length}</span></div>
            <ToolGrid tools={unavailableTools} />
          </section>}
        </> : <div className="empty-state compact"><h2>No matching tools</h2><p>Try another search, or choose a different collection.</p>{search && <button className="text-button" type="button" onClick={() => updateSearch("")}>Clear search</button>}</div>}
      </section>
    );
  }

  const readyTools = tools.filter((tool) => tool.ready);
  const recentIds = readRecentToolIds();
  const recentTools = recentIds.map((id) => readyTools.find((tool) => tool.id === id)).filter((tool): tool is Tool => Boolean(tool));
  const quickTools = [...recentTools, ...readyTools.filter((tool) => !recentIds.includes(tool.id))].slice(0, 4);
  const clearedChallenges = (learningSession?.progress.python.length ?? 0) + (learningSession?.progress.sql.length ?? 0);
  const totalChallenges = learningSession?.tracks.reduce((total, track) => total + track.challenges.length, 0) ?? 0;
  return (
    <section className="page-wrap dashboard-page">
      <header className="dashboard-heading">
        <span className="eyebrow">Central Hub</span>
        <h1>What do you need today?</h1>
        <p>Everyday tools, quick activities, and a place to keep a thought.</p>
        <HomeSearch tools={readyTools} />
      </header>

      <div className="hub-feature-grid">
        <Link to="/activities" className="hub-feature-card">
          <span className="hub-feature-icon"><Icon name="activities" /></span>
          <span className="hub-feature-label">Play offline</span>
          <h2>Quick activities</h2>
          <p>Take a short break with three simple games that work on this device.</p>
          <span className="hub-feature-meta">3 games <Icon name="arrow" /></span>
        </Link>
        <Link to="/learn" className="hub-feature-card">
          <span className="hub-feature-icon"><Icon name="code" /></span>
          <span className="hub-feature-label">Learn by playing</span>
          <h2>Code Quest</h2>
          <p>Write Python and SQL with starter code, hints, and instant feedback.</p>
          <span className="hub-feature-meta">2 learning tracks <Icon name="arrow" /></span>
        </Link>
        <Link to="/tools" className="hub-feature-card">
          <span className="hub-feature-icon"><Icon name="tools" /></span>
          <span className="hub-feature-label">Get things done</span>
          <h2>Digital tools</h2>
          <p>Format data, work with PDFs, generate codes, and more.</p>
          <span className="hub-feature-meta">{tools.length ? `${tools.length} tools` : "Open catalog"} <Icon name="arrow" /></span>
        </Link>
        <Link to="/notes" className="hub-feature-card">
          <span className="hub-feature-icon"><Icon name="notes" /></span>
          <span className="hub-feature-label">Saved on this device</span>
          <h2>Quick notes</h2>
          <p>Jot down a reminder or idea. Your note stays in this browser.</p>
          <span className="hub-feature-meta">Private scratchpad <Icon name="arrow" /></span>
        </Link>
      </div>

      {clearedChallenges > 0 && <Link to="/learn" className="continue-quest-card"><span className="continue-quest-icon"><Icon name="code" /></span><span><strong>Continue Code Quest</strong><small>{clearedChallenges} of {totalChallenges} challenges cleared · {learningSession?.xp ?? 0} XP</small></span><Icon name="arrow" /></Link>}

      {quickTools.length > 0 && <>
        <div className="section-heading section-heading-tools">
          <div><span className="eyebrow">{recentTools.length > 0 ? "Pick up where you left off" : "Ready to use"}</span><h2>{recentTools.length > 0 ? "Recent tools" : "Quick tools"}</h2></div>
          <Link to="/tools" className="text-link">Browse all tools <Icon name="chevron-right" /></Link>
        </div>
        <ToolGrid tools={quickTools} />
      </>}
    </section>
  );
}

function SearchInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <div className="search-field"><Icon name="search" /><input type="search" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Search tools" aria-label="Search tools" />{value && <button className="search-clear" type="button" aria-label="Clear tool search" onClick={() => onChange("")}><Icon name="close" /></button>}</div>;
}

function HomeSearch({ tools }: { tools: Tool[] }) {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const normalized = query.trim().toLowerCase();
  const matchingDestinations = normalized ? destinations.filter((item) => `${item.label} ${item.detail} ${item.terms}`.toLowerCase().includes(normalized)) : [];
  const matchingTools = normalized ? tools.filter((tool) => `${tool.name} ${tool.description} ${tool.category}`.toLowerCase().includes(normalized)).slice(0, 5) : [];
  const hasQuery = Boolean(normalized);
  const resultCount = matchingDestinations.length + matchingTools.length;

  function focusResult(index: number) {
    resultsRef.current?.querySelectorAll<HTMLAnchorElement>("a[href]")[index]?.focus();
  }

  function moveResultFocus(event: ReactKeyboardEvent<HTMLAnchorElement>, index: number) {
    if (event.key === "ArrowDown" && index < resultCount - 1) {
      event.preventDefault();
      focusResult(index + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (index === 0) inputRef.current?.focus();
      else focusResult(index - 1);
    } else if (event.key === "Escape") {
      event.preventDefault();
      inputRef.current?.focus();
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (matchingDestinations[0]) navigate(matchingDestinations[0].to);
    else if (matchingTools[0]) {
      rememberTool(matchingTools[0].id);
      navigate(`/tool/${matchingTools[0].id}`);
    }
  }
  return <form className="home-search-wrap" role="search" onSubmit={submitSearch}>
    <div className="home-search-control">
      <label className="search-field home-search"><Icon name="search" /><input ref={inputRef} type="search" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "ArrowDown" && resultCount > 0) { event.preventDefault(); focusResult(0); } }} placeholder="Search tools, games, Python, notes..." aria-label="Search Central Hub" aria-describedby="home-search-help" /></label>
      {query && <button className="search-clear home-search-clear" type="button" aria-label="Clear Central Hub search" onClick={() => setQuery("")}><Icon name="close" /></button>}
      <button className="button button-primary home-search-submit" type="submit" disabled={!resultCount}>{hasQuery ? "Open first match" : "Search"}</button>
    </div>
    <span id="home-search-help" className="sr-only">Search tools and hub sections by name or task. Use the arrow keys to move through suggestions; Enter opens the focused result.</span>
    {hasQuery && <span className="sr-only" role="status" aria-live="polite">Showing {matchingDestinations.length + matchingTools.length} results.</span>}
    {hasQuery && <div ref={resultsRef} className="home-search-results" role="region" aria-label="Search results">
      {!matchingDestinations.length && !matchingTools.length ? <p>No results for “{query}”. Try a tool or section name.</p> : <>
        <p className="home-search-guidance">Use ↑ and ↓ to move through suggestions. Press Enter to open one.</p>
        {matchingDestinations.map((item, index) => <Link key={item.to} to={item.to} className="home-search-result" onKeyDown={(event) => moveResultFocus(event, index)}><span><strong>{item.label}</strong><small>{item.detail}</small></span><Icon name="arrow" /></Link>)}
        {matchingTools.map((tool, index) => <Link key={tool.id} to={`/tool/${tool.id}`} className="home-search-result" onClick={() => rememberTool(tool.id)} onKeyDown={(event) => moveResultFocus(event, matchingDestinations.length + index)}><span><strong>{tool.name}</strong><small>{displayCategory(tool.category)} · {tool.description}</small></span><Icon name="arrow" /></Link>)}
      </>}
    </div>}
  </form>;
}

function ToolGrid({ tools }: { tools: Tool[] }) {
  return <div className="tool-grid">{tools.map((tool) => <ToolCard key={tool.id} tool={tool} />)}</div>;
}

function ToolCard({ tool }: { tool: Tool }) {
  const availability = tool.ready ? "Ready" : tool.requires ? "Needs setup" : "Planned";
  return (
    <Link to={`/tool/${tool.id}`} className="tool-card" onClick={() => rememberTool(tool.id)}>
      <span className="tool-card-icon"><Icon name={iconForTool(tool.id, tool.category)} /></span>
      <div className="tool-card-content">
        <div className="tool-card-title"><h3>{tool.name}</h3><span className={`tool-status ${tool.ready ? "status-ready" : "status-soon"}`}>{availability}</span></div>
        <p>{tool.description}</p>
        {tool.requires && <small>Requires {tool.requires}</small>}
      </div>
      <span className="tool-card-arrow" aria-hidden="true"><Icon name="arrow" /></span>
    </Link>
  );
}
