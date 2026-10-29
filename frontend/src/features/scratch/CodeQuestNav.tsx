import { NavLink, useLocation } from "react-router-dom";
import { Icon, type IconName } from "../../ui/Icon";
import { CASE_FILES_PROJECT, CODE_QUEST_MODULES, type CodeQuestModuleId } from "../learning/codeQuestModules";

const moduleIcons: Record<string, IconName> = {
  python: "code",
  sql: "database",
};

function activeModule(pathname: string): CodeQuestModuleId {
  if (pathname.startsWith("/learn/case-files")) return "case_files";
  if (pathname.startsWith("/learn/sql")) return "sql";
  return "python";
}

export function CodeQuestNav() {
  const { pathname } = useLocation();
  const current = activeModule(pathname);

  return (
    <nav className="quest-module-nav" aria-label="Code Quest language modules">
      <div className="quest-module-list">
        {CODE_QUEST_MODULES.map((module) => (
          <section key={module.id} className={`quest-module ${current === module.id ? "quest-module-active" : ""}`}>
            <div className="quest-module-heading">
              <span className="quest-mode-icon"><Icon name={moduleIcons[module.id]} /></span>
              <span>
                <strong>{module.label}</strong>
                <small>{module.detail}</small>
              </span>
            </div>
            <div className="quest-module-modes">
              <NavLink
                to={module.path}
                end
                className={({ isActive }) => `quest-mode-tab ${isActive ? "quest-mode-tab-active" : ""}`}
              >
                Path
              </NavLink>
              {module.scratch && (
                <NavLink
                  to={module.scratch}
                  end
                  className={({ isActive }) => `quest-mode-tab ${isActive ? "quest-mode-tab-active" : ""}`}
                >
                  Scratch
                </NavLink>
              )}
            </div>
          </section>
        ))}
      </div>

      <NavLink
        to={CASE_FILES_PROJECT.path}
        end
        className={({ isActive }) => `quest-project-link ${isActive ? "quest-project-link-active" : ""}`}
      >
        <span className="quest-mode-icon"><Icon name="flag" /></span>
        <span>
          <strong>{CASE_FILES_PROJECT.label}</strong>
          <small>{CASE_FILES_PROJECT.detail}</small>
        </span>
      </NavLink>
    </nav>
  );
}
