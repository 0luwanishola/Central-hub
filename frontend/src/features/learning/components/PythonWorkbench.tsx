import { SqlWorkbench } from "./SqlWorkbench";
import type { LearningWorkspaceProps } from "./LearningWorkspace";

export function PythonWorkbench(props: LearningWorkspaceProps) {
  return <SqlWorkbench {...props} isMySQLTrack={false} isPythonTrack />;
}
