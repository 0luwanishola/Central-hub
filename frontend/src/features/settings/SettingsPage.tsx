import { useOutletContext } from "react-router-dom";
import type { AppContext } from "../../app/AppShell";
import { Icon } from "../../ui/Icon";

export function SettingsPage() {
  const { theme, setTheme } = useOutletContext<AppContext>();
  return (
    <section className="page-wrap settings-page">
      <header className="page-heading"><span className="eyebrow">Preferences</span><h1>Settings</h1><p className="muted">Choose how Central Hub looks on this device.</p></header>
      <section className="settings-card" aria-labelledby="appearance-heading">
        <div className="settings-card-copy"><span className="settings-symbol"><Icon name="sun" /></span><div><h2 id="appearance-heading">Appearance</h2><p>Choose a light or dark colour theme.</p></div></div>
        <div className="segmented-control" role="group" aria-label="Choose appearance">
          {(["light", "dark"] as const).map((choice) => <button type="button" key={choice} aria-pressed={theme === choice} className={theme === choice ? "segment-selected" : ""} onClick={() => setTheme(choice)}><Icon name={choice === "light" ? "sun" : "moon"} /> {choice[0].toUpperCase() + choice.slice(1)}</button>)}
        </div>
        <p className="settings-note">Your choice is saved in this browser and applies across the app.</p>
      </section>
    </section>
  );
}
