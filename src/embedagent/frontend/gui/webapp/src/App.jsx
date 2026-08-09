import React from "react";

import { useAgentShellRuntime } from "./client-runtime/use-agent-shell-runtime.js";
import AgentShell from "./components/shell/AgentShell.jsx";

export default function App({ protocol }) {
  const { actions, timelineRef, view } = useAgentShellRuntime(protocol);
  return <AgentShell actions={actions} timelineRef={timelineRef} view={view} />;
}
