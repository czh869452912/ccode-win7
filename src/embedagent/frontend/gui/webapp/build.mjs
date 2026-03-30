import { build } from "esbuild";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const staticDir = path.resolve(__dirname, "../static");
const assetsDir = path.join(staticDir, "assets");
const jsOutfile = path.join(assetsDir, "app.js");

fs.rmSync(staticDir, { recursive: true, force: true });
fs.mkdirSync(assetsDir, { recursive: true });

await build({
  entryPoints: [path.resolve(__dirname, "src/main.jsx")],
  bundle: true,
  format: "esm",
  minify: true,
  sourcemap: false,
  target: ["chrome109"],
  outfile: jsOutfile,
  loader: {
    ".js": "jsx",
    ".jsx": "jsx",
  },
  jsx: "automatic",
});

const cssFilename = "app.css";
const cssPath = path.join(assetsDir, cssFilename);
const hasCss = fs.existsSync(cssPath);

const indexHtml = `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta http-equiv="X-UA-Compatible" content="IE=edge" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>EmbedAgent</title>
    ${hasCss ? '<link rel="stylesheet" href="/static/assets/app.css" />' : ""}
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/static/assets/app.js"></script>
  </body>
</html>
`;

fs.writeFileSync(path.join(staticDir, "index.html"), indexHtml, "utf-8");
