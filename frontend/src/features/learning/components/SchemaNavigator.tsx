import { useEffect, useState } from "react";
import type { LearningDatasetMetadata } from "../../../types";
import { Icon } from "../../../ui/Icon";

interface SchemaNavigatorProps {
  datasets: LearningDatasetMetadata[];
  activeDatasetId?: string;
}

export function SchemaNavigator({ datasets, activeDatasetId }: SchemaNavigatorProps) {
  const [filter, setFilter] = useState("");
  const [selectedId, setSelectedId] = useState(activeDatasetId ?? datasets[0]?.id ?? "");
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());

  const selected = datasets.find((dataset) => dataset.id === selectedId) ?? datasets[0];

  // Follow the challenge's dataset when it changes.
  useEffect(() => {
    if (activeDatasetId && datasets.some((dataset) => dataset.id === activeDatasetId)) {
      setSelectedId(activeDatasetId);
    }
  }, [activeDatasetId, datasets]);

  // Start each dataset with its first three tables open.
  useEffect(() => {
    setExpandedTables(new Set((selected?.tables ?? []).slice(0, 3).map((table) => table.name)));
  }, [selected?.id]);

  if (!selected) return null;

  const normalized = filter.trim().toLowerCase();
  const tables = selected.tables.filter((table) =>
    !normalized || `${table.name} ${table.description} ${table.columns.join(" ")}`.toLowerCase().includes(normalized)
  );
  const visibleNames = new Set(tables.map((table) => table.name));
  const relationships = selected.relationships.filter(
    (relationship) => visibleNames.has(relationship.from_table) && visibleNames.has(relationship.to_table)
  );

  // The browser also fires `toggle` for programmatic open/close changes, so sync
  // from the DOM's actual state and bail when nothing changed — flipping the
  // state blindly would ping-pong with the `open` prop and flicker forever.
  function syncTableOpen(name: string, isOpen: boolean) {
    setExpandedTables((prev) => {
      if (prev.has(name) === isOpen) return prev;
      const next = new Set(prev);
      if (isOpen) next.add(name);
      else next.delete(name);
      return next;
    });
  }

  return (
    <aside className="schema-navigator" aria-label="Dataset explorer">
      <div className="schema-navigator-header">
        <h4>Datasets</h4>
        <span className="schema-count">{selected.tables.length} tables</span>
      </div>

      <div className="dataset-switcher">
        <label htmlFor="dataset-select">Dataset</label>
        <select
          id="dataset-select"
          value={selected.id}
          onChange={(event) => setSelectedId(event.target.value)}
        >
          {datasets.map((dataset) => (
            <option key={dataset.id} value={dataset.id}>{dataset.name}</option>
          ))}
        </select>
      </div>
      <p className="dataset-summary">{selected.summary}</p>

      <div className="schema-search-wrap">
        <label htmlFor="schema-nav-search" className="sr-only">Search tables and columns</label>
        <input
          id="schema-nav-search"
          type="search"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filter tables, columns..."
        />
      </div>

      <div className="schema-table-list">
        {tables.map((table) => (
          <details
            key={table.name}
            className="schema-table-card"
            open={expandedTables.has(table.name)}
            onToggle={(event) => syncTableOpen(table.name, event.currentTarget.open)}
          >
            <summary>
              <strong>{table.name}</strong>
              <span className="table-grain">{table.grain}</span>
              <Icon name="chevron-right" className="expand-icon" />
            </summary>
            <p className="table-description">{table.description}</p>
            <ul className="table-columns">
              {table.columns.map((column) => (
                <li key={column}>
                  <code>{column}</code>
                  <span>
                    {table.types[column] ?? "value"}
                    {table.keys.primary.includes(column) && " · PK"}
                    {table.keys.foreign.includes(column) && " · FK"}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        ))}
        {tables.length === 0 && <p className="schema-empty">No table or column matches that search.</p>}
      </div>

      {relationships.length > 0 && (
        <div className="schema-relationships">
          <strong>Relationships</strong>
          {relationships.map((relationship) => (
            <p key={`${relationship.from_table}-${relationship.from_column}`}>
              <code>{relationship.from_table}.{relationship.from_column}</code>
              <span aria-hidden="true"> → </span>
              <code>{relationship.to_table}.{relationship.to_column}</code>
              <small>{relationship.cardinality}</small>
            </p>
          ))}
        </div>
      )}
    </aside>
  );
}
