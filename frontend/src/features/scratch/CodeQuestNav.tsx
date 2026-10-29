import { Link, NavLink, useLocation } from "react-router-dom";
import { Icon, type IconName } from "../../ui/Icon";
import { CODE_QUEST_MODULES, getCodeQuestModule, type CodeQuestModuleId } from "../learning/codeQuestModules";

const moduleIcons: Record<CodeQuestModuleId, IconName> = {
  python: "code",
  sql: "database",
  case_files: "flag",
};

export function CodeQuestNav({ module }: { module: CodeQuestModuleId }) {
  const moduleInfo = getCodeQuestModule(module);
  const location = useLocation();
  const scratchMode = Boolean(moduleInfo.scratch && location.pathname === moduleInfo.scratch);

  return (
    <nav className="quest-module-nav" aria-label={`${moduleInfo.label} navigation`}>
      <div className="quest-nav-topline">
        <Link to="/learn" className="quest-back-link">
          <Icon name="chevron-left" /> Code Quest
        </Link>
        <div className="quest-language-switcher" role="group" aria-label="Choose a language module">
          {CODE_QUEST_MODULES.map((item) => {
            const target = scratchMode && item.scratch ? item.scratch : item.path;
            const active = item.id === module;
            return (
              <Link
                key={item.id}
                to={target}
                className={`quest-language-link ${active ? "quest-language-link-active" : ""}`}
                aria-current={active ? "location" : undefined}
              >
                <Icon name={moduleIcons[item.id]} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>
      </div>

      <section className="quest-module quest-module-active">
        <div className="quest-module-heading">
          <span className="quest-mode-icon"><Icon name={moduleIcons[module]} /></span>
          <span>
            <strong>{moduleInfo.label}</strong>
            <small>{moduleInfo.detail}</small>
          </span>
        </div>
        {moduleInfo.scratch && <div className="quest-module-modes" aria-label={`${moduleInfo.label} workspace`}>
          <NavLink
            to={moduleInfo.path}
            end
            className={({ isActive }) => `quest-mode-tab ${isActive ? "quest-mode-tab-active" : ""}`}
          >
            {moduleInfo.scratch ? "Path" : "Project"}
          </NavLink>
          {moduleInfo.scratch && (
            <NavLink
              to={moduleInfo.scratch}
              end
              className={({ isActive }) => `quest-mode-tab ${isActive ? "quest-mode-tab-active" : ""}`}
            >
              Scratch
            </NavLink>
          )}
        </div>}
      </section>
    </nav>
  );
}
