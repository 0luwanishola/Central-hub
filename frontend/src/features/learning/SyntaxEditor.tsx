import { useRef, type KeyboardEvent, type ReactNode, type UIEvent } from "react";

type CodeLanguage = "python" | "sql";

type SyntaxEditorProps = {
  id: string;
  language: CodeLanguage;
  value: string;
  readOnly: boolean;
  onChange: (value: string) => void;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
};

const pythonKeywords = new Set([
  "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del", "elif", "else",
  "except", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
  "or", "pass", "raise", "return", "try", "while", "with", "yield",
]);
const pythonBuiltins = new Set([
  "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len", "list", "max", "min", "print",
  "range", "round", "set", "sorted", "str", "sum", "tuple", "zip",
]);
const sqlKeywords = new Set([
  "all", "and", "as", "asc", "between", "by", "case", "cast", "check", "collate", "column", "create",
  "cross", "current", "database", "default", "delete", "desc", "distinct", "else", "end", "escape", "except",
  "exists", "false", "fetch", "filter", "first", "following", "for", "from", "full", "group", "having", "in",
  "index", "inner", "insert", "intersect", "into", "is", "join", "last", "left", "like", "limit", "not", "null",
  "offset", "on", "or", "order", "outer", "over", "partition", "preceding", "range", "recursive", "references",
  "right", "row", "rows", "select", "set", "table", "then", "true", "union", "unique", "update", "using", "values",
  "when", "where", "with",
]);
const sqlFunctions = new Set([
  "abs", "avg", "coalesce", "count", "dense_rank", "ifnull", "length", "lower", "max", "min", "nullif", "rank",
  "round", "row_number", "sum", "upper",
]);

const pythonTokenPattern = /(?:#[^\n]*|"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|0[xX][\da-fA-F]+|\b\d+(?:\.\d+)?\b|[A-Za-z_]\w*)/gy;
const sqlTokenPattern = /(?:--[^\n]*|\/\*[\s\S]*?\*\/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`[^`]*`|[@:$][A-Za-z_]\w*|\b\d+(?:\.\d+)?\b|[A-Za-z_]\w*)/gy;

function syntaxClass(token: string, language: CodeLanguage, source: string, end: number, nextDefinitionName: boolean): string | undefined {
  if (language === "python") {
    if (token.startsWith("#")) return "quest-token-comment";
    if (token.startsWith("\"") || token.startsWith("'")) return "quest-token-string";
    if (/^(?:0[xX][\da-fA-F]+|\d)/.test(token)) return "quest-token-number";
    if (pythonKeywords.has(token)) return "quest-token-command";
    if (["False", "None", "True"].includes(token)) return "quest-token-literal";
    if (nextDefinitionName || pythonBuiltins.has(token)) return "quest-token-function";
    if (/^\s*\(/.test(source.slice(end))) return "quest-token-function";
    return "quest-token-variable";
  }

  if (token.startsWith("--") || token.startsWith("/*")) return "quest-token-comment";
  if (token.startsWith("\"") || token.startsWith("'") || token.startsWith("`")) return "quest-token-string";
  if (/^[@:$]/.test(token)) return "quest-token-variable";
  if (/^\d/.test(token)) return "quest-token-number";
  const normalized = token.toLowerCase();
  if (sqlKeywords.has(normalized)) return "quest-token-command";
  if (sqlFunctions.has(normalized) || /^\s*\(/.test(source.slice(end))) return "quest-token-function";
  return "quest-token-variable";
}

function paintSource(source: string, language: CodeLanguage): ReactNode[] {
  const pattern = language === "python" ? pythonTokenPattern : sqlTokenPattern;
  const painted: ReactNode[] = [];
  let cursor = 0;
  let expectsDefinitionName = false;

  while (cursor < source.length) {
    pattern.lastIndex = cursor;
    const match = pattern.exec(source);
    if (!match) {
      painted.push(source[cursor]);
      cursor += 1;
      continue;
    }

    const token = match[0];
    const end = cursor + token.length;
    const className = syntaxClass(token, language, source, end, expectsDefinitionName);
    painted.push(className ? <span key={cursor} className={className}>{token}</span> : token);
    expectsDefinitionName = language === "python" && (token === "def" || token === "class");
    cursor = end;
  }

  return painted;
}

export function SyntaxEditor({ id, language, value, readOnly, onChange, onKeyDown }: SyntaxEditorProps) {
  const highlightLayer = useRef<HTMLPreElement>(null);

  function syncScroll(event: UIEvent<HTMLTextAreaElement>) {
    if (!highlightLayer.current) return;
    highlightLayer.current.scrollTop = event.currentTarget.scrollTop;
    highlightLayer.current.scrollLeft = event.currentTarget.scrollLeft;
  }

  return (
    <div className="syntax-editor">
      <div className={`syntax-editor-input syntax-editor-input-${language}`}>
        <pre ref={highlightLayer} className="syntax-highlight-layer" aria-hidden="true">{value ? paintSource(value, language) : " "}</pre>
        <textarea
          id={id}
          className={`quest-code-editor quest-code-editor-${language}`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          onScroll={syncScroll}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          autoComplete="off"
          readOnly={readOnly}
        />
      </div>
      <div className="syntax-legend" aria-label="Syntax color guide">
        <span><i className="quest-token-command" />Commands</span>
        <span><i className="quest-token-variable" />Variables / names</span>
        <span><i className="quest-token-string" />Text</span>
        <span><i className="quest-token-comment" />Comments</span>
      </div>
    </div>
  );
}
