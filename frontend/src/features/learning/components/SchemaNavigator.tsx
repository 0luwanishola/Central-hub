import { useState } from "react";
import type { LearningSchema } from "../../../types";
import { Icon } from "../../../ui/Icon";

interface SchemaNavigatorProps {
  schema: LearningSchema;
}

export function SchemaNavigator({ schema }: SchemaNavigatorProps) {
  const [filter, setFilter] = useState("");
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set(schema.tables.slice(0, 3).map((t) => t.name)));

  const normalized = filter.trim().toLowerCase();
  const tables = schema.tables.filter((table) =>
    !normalized || `${table.name} ${table.description} ${table.columns.join(" ")}`.toLowerCase().includes(normalized)
  );
  const visibleNames = new Set(tables.map((table) => table.name));
  const relationships = schema.relationships.filter(
    (relationship) => visibleNames.has(relationship.from_table) && visibleNames.has(relationship.to_table)
  );

  function toggleTable(name: string) {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  return (
    <aside className="schema-navigator" aria-label="Database schema">
      <div className="schema-navigator-header">
        <h4>Schemas</h4>
        <span className="schema-count">{schema.tables.length} tables</span>
      </div>

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
        {tables.map((table) => {
          const isExpanded = expandedTables.has(table.name);
          return (
            <details key={table.name} className="schema-table-card" open={isExpanded} onToggle={() => toggleTable(table.name)}>
              <summary>
                <strong>{table.name}</strong>
                <span className="table-grain">{table.grain}</span>
                <Icon name={isExpanded ? "chevron-down" : "chevron-right"} className="expand-icon" />
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
          );
        })}
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
