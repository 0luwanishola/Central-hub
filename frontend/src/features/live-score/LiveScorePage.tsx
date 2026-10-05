import { useQuery } from "@tanstack/react-query";
import { Link, useOutletContext, useParams, useSearchParams } from "react-router-dom";
import { getLive, getMatch } from "../../services/apiClient";
import type { AppContext } from "../../app/AppShell";
import type { Fixture, Lineup, MatchEvent } from "../../types";
import { Icon } from "../../ui/Icon";

const LIVE_STATUSES = new Set(["1H", "2H", "HT", "LIVE", "ET", "BT", "VAR", "P"]);
const FINAL_STATUSES = new Set(["FT", "AET", "PEN"]);

export function LiveScorePage() {
  const { tools } = useOutletContext<AppContext>();
  const [params, setParams] = useSearchParams();
  const day = params.get("day") || new Date().toISOString().slice(0, 10);
  const scope = params.get("scope") || "all";
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["live", day, scope],
    queryFn: () => getLive(day, scope),
    refetchInterval: 60_000,
  });
  const matches = data?.matches ?? [];
  const liveCount = matches.filter((match) => LIVE_STATUSES.has(match.status_short ?? "")).length;
  const grouped = matches.reduce<Record<string, Fixture[]>>((result, match) => {
    const label = match.group === "international" ? "International" : "Domestic leagues";
    (result[label] ??= []).push(match);
    return result;
  }, {});

  function changeQuery(next: Partial<{ day: string; scope: string }>) {
    setParams({ day: next.day ?? day, scope: next.scope ?? scope });
  }

  return (
    <section className="page-wrap live-page">
      <header className="feature-heading live-heading">
        <div className="feature-icon football-icon"><Icon name="sports" /></div>
        <div><span className="eyebrow">Scores & fixtures</span><h1>LiveScore</h1><p className="muted">Football from domestic leagues and international competitions.</p></div>
        <div className="live-heading-actions">
          {liveCount > 0 && <span className="live-pill"><i />{liveCount} live</span>}
          <button className="button button-secondary" onClick={() => void refetch()} disabled={isFetching}>{isFetching ? "Updating…" : <><Icon name="refresh" /> Refresh</>}</button>
        </div>
      </header>

      <div className="scoreboard-controls">
        <div className="date-control">
          <button className="icon-button" aria-label="Previous day" onClick={() => changeQuery({ day: shiftDate(day, -1) })}><Icon name="chevron-left" /></button>
          <input type="date" value={day} onChange={(event) => changeQuery({ day: event.target.value })} aria-label="Fixture date" />
          <button className="icon-button" aria-label="Next day" onClick={() => changeQuery({ day: shiftDate(day, 1) })}><Icon name="chevron-right" /></button>
          {day !== new Date().toISOString().slice(0, 10) && <button className="text-button" onClick={() => changeQuery({ day: new Date().toISOString().slice(0, 10) })}>Today</button>}
        </div>
        <div className="scope-tabs" role="group" aria-label="Competition coverage">
          {(["all", "domestic", "international"] as const).map((value) => <button key={value} type="button" aria-pressed={scope === value} className={scope === value ? "scope-active" : ""} onClick={() => changeQuery({ scope: value })}>{value[0].toUpperCase() + value.slice(1)}</button>)}
        </div>
        <span className="utc-note">Times shown in UTC</span>
      </div>

      {error && <div className="notice notice-error" role="alert">{(error as Error).message}</div>}
      {data?.error && <div className="notice notice-error" role="alert">LiveScore is temporarily unavailable: {data.error}</div>}
      {isLoading && <div className="loading-line">Loading fixtures…</div>}
      {!isLoading && !error && matches.length === 0 && <div className="empty-state compact"><span className="empty-symbol"><Icon name="sports" /></span><h2>No matches scheduled</h2><p>No {scope === "all" ? "matches" : scope} fixtures for {day}. Try another date.</p></div>}

      <div className="match-groups">
        {Object.entries(grouped).map(([label, fixtures]) => (
          <section className="match-group" key={label}>
            {scope === "all" && <div className="group-title"><h2>{label}</h2><span>{fixtures.length} {fixtures.length === 1 ? "match" : "matches"}</span></div>}
            <div className="league-list">
              {groupByLeague(fixtures).map(([league, leagueMatches]) => (
                <div className="league-block" key={league}>
                  <div className="league-title"><span className="league-mark" />{league}<span>{leagueMatches.length}</span></div>
                  <div className="fixture-list">{leagueMatches.map((fixture) => <FixtureCard key={fixture.id} fixture={fixture} />)}</div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
      <p className="data-note">Data provided by {data?.provider || "the configured score provider"}.</p>
      {tools.length === 0 && <span className="sr-only">Tool catalog is still loading.</span>}
    </section>
  );
}

export function MatchDetailPage() {
  const { fixtureId = "" } = useParams();
  const { data, isLoading, error } = useQuery({ queryKey: ["match", fixtureId], queryFn: () => getMatch(fixtureId), enabled: Boolean(fixtureId) });
  const live = LIVE_STATUSES.has(data?.status_short ?? "");
  const finished = FINAL_STATUSES.has(data?.status_short ?? "");

  if (isLoading) return <section className="page-wrap"><div className="loading-line">Loading match details…</div></section>;
  if (error || data?.error || !data) return <section className="page-wrap"><Link to="/tool/live-score" className="back-link">← Back to LiveScore</Link><div className="notice notice-error">{(error as Error | undefined)?.message ?? data?.error ?? "Match details are unavailable."}</div></section>;

  return (
    <section className="page-wrap match-detail-page">
      <Link to="/tool/live-score" className="back-link">← Back to LiveScore</Link>
      <article className="score-detail-card">
        <div className="score-detail-meta"><span>{data.league}</span><span>{data.round || data.venue || "Match details"}</span></div>
        <div className="score-detail-teams">
          <TeamScore side={data.home} align="right" />
          <div className="score-detail-center"><strong>{hasScore(data) ? `${data.home.score ?? "–"}  –  ${data.away.score ?? "–"}` : "vs"}</strong><span className={live ? "live-text" : ""}>{live ? `${data.elapsed ? `${data.elapsed}′` : "LIVE"}` : finished ? "Full time" : data.status_long || data.status_short}</span></div>
          <TeamScore side={data.away} align="left" />
        </div>
        <div className="score-detail-footer">{formatKickoff(data.kickoff)}{data.venue ? ` · ${data.venue}` : ""} · UTC</div>
      </article>

      <section className="detail-section"><div className="section-heading small-heading"><div><span className="eyebrow">Match events</span><h2>Timeline</h2></div></div>
        {data.events?.length ? <div className="timeline">{data.events.map((event, index) => <TimelineEvent key={`${event.minute}-${index}`} event={event} />)}</div> : <div className="empty-state compact"><p>{live || finished ? "No goals, cards or substitutions recorded yet." : "Events appear once the match kicks off."}</p></div>}
      </section>
      <section className="detail-section"><div className="section-heading small-heading"><div><span className="eyebrow">Squads</span><h2>Lineups</h2></div></div>
        {data.lineups?.length ? <div className="lineup-grid">{data.lineups.map((lineup) => <LineupCard lineup={lineup} key={lineup.team} />)}</div> : <div className="empty-state compact"><p>Lineups are published shortly before kickoff.</p></div>}
      </section>
    </section>
  );
}

function FixtureCard({ fixture }: { fixture: Fixture }) {
  const live = LIVE_STATUSES.has(fixture.status_short ?? "");
  return (
    <Link to={`/match/${encodeURIComponent(fixture.id)}`} className="fixture-card">
      <div className="fixture-status">{live ? <><i className="live-dot" />{fixture.elapsed ? `${fixture.elapsed}′` : "LIVE"}</> : FINAL_STATUSES.has(fixture.status_short ?? "") ? "FT" : formatKickoff(fixture.kickoff)}</div>
      <div className="fixture-teams"><TeamLine side={fixture.home} /><TeamLine side={fixture.away} /></div>
      <div className="fixture-score"><span>{hasScore(fixture) ? fixture.home.score ?? "–" : ""}</span><span>{hasScore(fixture) ? fixture.away.score ?? "–" : ""}</span></div>
      <span className="fixture-arrow">↗</span>
    </Link>
  );
}

function TeamLine({ side }: { side: Fixture["home"] }) {
  return <span className="team-line">{side.logo && <img src={side.logo} alt="" loading="lazy" />}<span>{side.name}</span></span>;
}

function TeamScore({ side, align }: { side: Fixture["home"]; align: "left" | "right" }) {
  return <div className={`team-score team-score-${align}`}>{side.logo && <img src={side.logo} alt="" />}<strong>{side.name}</strong></div>;
}

function TimelineEvent({ event }: { event: MatchEvent }) {
  const symbol = event.kind === "goal" ? "⚽" : event.kind === "card" ? (event.card === "red" ? "🟥" : "🟨") : "↔";
  return <div className="timeline-row"><span className="timeline-minute">{event.minute ?? "–"}′</span><span className="timeline-symbol">{symbol}</span><div><strong>{event.player || event.player_in || event.player_out || "Match event"}</strong>{event.assist && <p>Assist: {event.assist}</p>}{event.note && <p>{event.note}</p>}{event.kind === "card" && <p>{event.card} card</p>}</div><span className="timeline-side">{event.side ?? ""}</span></div>;
}

function LineupCard({ lineup }: { lineup: Lineup }) {
  return <article className="lineup-card"><header>{lineup.logo && <img src={lineup.logo} alt="" />}<strong>{lineup.team}</strong>{lineup.formation && <span>{lineup.formation}</span>}</header><p className="lineup-label">Starting XI</p><ol>{(lineup.starters ?? []).map((player, index) => <li key={`${player.number}-${index}`}><span>{player.number ?? ""}</span>{player.name}</li>)}</ol>{Boolean(lineup.bench?.length) && <><p className="lineup-label">Bench</p><ol>{lineup.bench?.map((player, index) => <li key={`${player.number}-${index}`}><span>{player.number ?? ""}</span>{player.name}</li>)}</ol></>}</article>;
}

function groupByLeague(matches: Fixture[]): [string, Fixture[]][] {
  const groups = new Map<string, Fixture[]>();
  for (const match of matches) groups.set(match.league, [...(groups.get(match.league) ?? []), match]);
  return [...groups.entries()];
}

function hasScore(match: Fixture): boolean {
  return LIVE_STATUSES.has(match.status_short ?? "") || FINAL_STATUSES.has(match.status_short ?? "");
}

function formatKickoff(value?: string | null): string {
  if (!value) return "Kickoff TBD";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
}

function shiftDate(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
