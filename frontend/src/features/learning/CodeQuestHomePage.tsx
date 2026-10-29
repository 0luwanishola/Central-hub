import { Link } from "react-router-dom";
import { Icon, type IconName } from "../../ui/Icon";
import { CASE_FILES_PROJECT, CODE_QUEST_MODULES } from "./codeQuestModules";

const moduleIcons: Record<string, IconName> = {
  python: "code",
  sql: "database",
};

export function CodeQuestHomePage() {
  return (
    <section className="page-wrap code-quest-home">
      <header className="dashboard-heading code-quest-home-heading">
        <span className="eyebrow">Code Quest / Python + SQL</span>
        <h1>Learn the Path. Try your own code.</h1>
        <p>Follow Python or SQL step by step, then use that language’s Scratch space to run an idea of your own.</p>
      </header>

      <div className="code-quest-module-grid">
        {CODE_QUEST_MODULES.map((module) => (
          <article key={module.id} className="code-quest-module-card">
            <span className="hub-feature-icon"><Icon name={moduleIcons[module.id]} /></span>
            <span className="code-quest-module-label">Path + Scratch</span>
            <h2>{module.label}</h2>
            <p>{module.description}</p>
            <div className="code-quest-module-actions">
              <Link to={module.path} className="button button-primary">
                Open {module.label} Path <Icon name="arrow" />
              </Link>
              {module.scratch && (
                <Link to={module.scratch} className="button button-secondary">
                  Open {module.label} Scratch
                </Link>
              )}
            </div>
          </article>
        ))}
      </div>

      <section className="code-quest-project-card" aria-labelledby="case-files-heading">
        <div className="code-quest-project-copy">
          <span className="hub-feature-icon"><Icon name="flag" /></span>
          <div>
            <span className="code-quest-module-label">Cross-language project</span>
            <h2 id="case-files-heading">{CASE_FILES_PROJECT.label}</h2>
            <p>{CASE_FILES_PROJECT.description}</p>
          </div>
        </div>
        <Link to={CASE_FILES_PROJECT.path} className="button button-secondary">
          Open Case Files <Icon name="arrow" />
        </Link>
      </section>
    </section>
  );
}
