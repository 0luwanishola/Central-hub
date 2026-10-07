import { Link, useOutletContext, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import type { AppContext } from "../../app/AppShell";
import { displayCategory } from "../../app/AppShell";
import { ClientUtility } from "./ClientUtility";
import { PdfTool } from "./PdfTool";
import { Icon, iconForTool } from "../../ui/Icon";

export function ToolPage() {
  const { toolId } = useParams();
  const { tools, toolsLoading, toolsError } = useOutletContext<AppContext>();
  const queryClient = useQueryClient();
  const tool = tools.find((item) => item.id === toolId);

  if (toolsLoading && !tool) return <section className="page-wrap"><div className="loading-line">Loading tool…</div></section>;
  if (toolsError && !tool) return <section className="page-wrap"><div className="empty-state"><span className="eyebrow">Catalog unavailable</span><h1>We couldn’t load this tool.</h1><p role="alert">{toolsError.message}</p><button className="button button-primary" type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ["tools"] })}>Try again</button></div></section>;
  if (!tool) return <section className="page-wrap"><div className="empty-state"><span className="eyebrow">Tool not found</span><h1>We couldn’t find that tool.</h1><Link className="button button-primary" to="/">Back to dashboard</Link></div></section>;

  return (
    <section className="page-wrap tool-page">
      <Link to={`/category/${tool.category}`} className="back-link"><Icon name="chevron-left" /> Back to {displayCategory(tool.category)}</Link>
      <header className="feature-heading tool-heading">
        <span className="feature-icon"><Icon name={iconForTool(tool.id, tool.category)} /></span>
        <div><span className="eyebrow">{displayCategory(tool.category)} · {tool.execution === "client" ? "Runs in your browser" : "Connected tool"}</span><h1>{tool.name}</h1><p className="muted">{tool.description}</p></div>
      </header>
      <section className="tool-panel">
        {tool.execution === "client" && <ClientUtility toolId={tool.id} />}
        {tool.execution === "api" && tool.category === "pdf" && <PdfTool key={tool.id} tool={tool} />}
        {!tool.ready && <div className="coming-soon"><Icon name="generators" /><h2>This tool is on its way.</h2><p>{tool.requires ? `It needs ${tool.requires} before it can run.` : "It will be available here as soon as it is ready."}</p></div>}
        {tool.ready && tool.execution === "api" && tool.category !== "pdf" && <div className="notice">This tool is connected to the API, but does not have a frontend page yet.</div>}
      </section>
    </section>
  );
}
