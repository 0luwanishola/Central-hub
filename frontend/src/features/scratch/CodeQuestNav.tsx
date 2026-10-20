import { NavLink } from "react-router-dom";
import { Icon, type IconName } from "../../ui/Icon";

const modes: Array<{ to: string; label: string; detail: string; icon: IconName; end?: boolean }> = [
  { to: "/learn", label: "Challenges", detail: "Guided practice and grading", icon: "flag", end: true },
  { to: "/learn/scratch/python", label: "Python Scratch", detail: "Run your own scripts", icon: "terminal" },
  { to: "/learn/scratch/sql", label: "SQL Scratch", detail: "A temporary SQLite workspace", icon: "database" },
];

export function CodeQuestNav() {
  return (
    <nav className="quest-mode-nav" aria-label="Code Quest: Challenges and Scratch">
      {modes.map((mode) => (
        <NavLink
          key={mode.to}
          to={mode.to}
          end={mode.end}
          className={({ isActive }) => `quest-mode-link ${isActive ? "quest-mode-link-active" : ""}`}
        >
          <span className="quest-mode-icon"><Icon name={mode.icon} /></span>
          <span>
            <strong>{mode.label}</strong>
            <small>{mode.detail}</small>
          </span>
        </NavLink>
      ))}
    </nav>
  );
}
