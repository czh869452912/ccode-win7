import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App.jsx";
import { createHttpTransport } from "./client-runtime/http-transport.js";
import { createAgentAppProtocolAdapter } from "./client-runtime/protocol-adapter.js";
import { createSocketTransport } from "./client-runtime/socket-transport.js";
import "./styles.css";
// KaTeX CSS is injected by build.mjs as a separate <link> stylesheet

const protocol = createAgentAppProtocolAdapter({
  http: createHttpTransport(),
  socket: createSocketTransport(),
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App protocol={protocol} />
  </React.StrictMode>,
);
