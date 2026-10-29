import { Link, NavLink, useLocation } from "react-router-dom";
import { Icon, type IconName } from "../../ui/Icon";
import { getCodeQuestModule, type CodeQuestModuleId } from "../learning/codeQuestModules";

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
    <nav className="quest-module-nav" aria-label={`${moduleInfo.label} workspace navigation`}>
      <div className="quest-nav-topline">
        <Link to="/learn" className="quest-back-link">
          <Icon name="chevron-left" /> Code Quest
        </Link>
      </div>

      <section className="quest-module quest-module-active">
        <div className="quest-module-heading">
          <span className="quest-mode-icon"><Icon name={moduleIcons[module]} /></span>
          <span>
            <strong>{moduleInfo.label}</strong>
            <small>{moduleInfo.detail}</small>
          </span>
        </div>
        {moduleInfo.scratch && <div className="quest-module-modes" role="group" aria-label={`${moduleInfo.label} workspace`}>
          <NavLink
            to={moduleInfo.path}
            end
            className={({ isActive }) => `quest-mode-tab ${isActive ? "quest-mode-tab-active" : ""}`}
            aria-label={`${moduleInfo.label} guided Path`}
          >
            Path
          </NavLink>
          <NavLink
            to={moduleInfo.scratch}
            end
            className={({ isActive }) => `quest-mode-tab ${isActive ? "quest-mode-tab-active" : ""}`}
            aria-label={`${moduleInfo.label} Scratch workspace`}
          >
            Scratch
          </NavLink>
        </div>}
      </section>
    </nav>
  );
}
