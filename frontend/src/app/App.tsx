import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { CatalogPage } from "../features/catalog/CatalogPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { LiveScorePage, MatchDetailPage } from "../features/live-score/LiveScorePage";
import { ToolPage } from "../features/tools/ToolPage";
import { ActivitiesPage } from "../features/activities/ActivitiesPage";
import { NotesPage } from "../features/notes/NotesPage";
import { LearnPage } from "../features/learning/LearnPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<CatalogPage />} />
          <Route path="tools" element={<CatalogPage showAll />} />
          <Route path="category/:categoryId" element={<CatalogPage />} />
          <Route path="activities" element={<ActivitiesPage />} />
          <Route path="notes" element={<NotesPage />} />
          <Route path="learn" element={<LearnPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="tool/live-score" element={<LiveScorePage />} />
          <Route path="tool/:toolId" element={<ToolPage />} />
          <Route path="match/:fixtureId" element={<MatchDetailPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function NotFound() {
  return (
    <section className="page-wrap">
      <div className="empty-state">
        <span className="eyebrow">404 · Page not found</span>
        <h1>That page isn’t here.</h1>
        <p>Go back to the dashboard to find a tool.</p>
        <Link className="button button-primary" to="/">Back to dashboard</Link>
      </div>
    </section>
  );
}
