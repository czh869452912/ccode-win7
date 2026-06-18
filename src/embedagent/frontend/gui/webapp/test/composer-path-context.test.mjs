import assert from "node:assert/strict";

import {
  buildPathContextInsertion,
  flattenComposerPathCandidates,
  groupComposerPathCandidates,
  searchComposerPathCandidates,
} from "../src/composer/composer-path-context.js";

const FILE_TREE = [
  {
    id: "src",
    path: "src",
    name: "src",
    kind: "dir",
    childrenLoaded: true,
    children: [
      { id: "src/main.c", path: "src/main.c", name: "main.c", kind: "file" },
      { id: "src/parser.c", path: "src/parser.c", name: "parser.c", kind: "file" },
      {
        id: "src/include",
        path: "src/include",
        name: "include",
        kind: "dir",
        childrenLoaded: true,
        children: [
          { id: "src/include/parser.h", path: "src/include/parser.h", name: "parser.h", kind: "file" },
        ],
      },
    ],
  },
  { id: "README.md", path: "README.md", name: "README.md", kind: "file" },
  { id: "broken", name: "broken", kind: "file" },
];

export function runComposerPathContextTests() {
  const candidates = flattenComposerPathCandidates(FILE_TREE);
  assert.deepEqual(
    candidates.map((candidate) => candidate.path),
    ["README.md", "src/include/parser.h", "src/main.c", "src/parser.c"],
  );
  assert.equal(candidates.every((candidate) => candidate.type === "path-context"), true);
  assert.equal(candidates.every((candidate) => candidate.id.startsWith("path:")), true);

  assert.deepEqual(
    searchComposerPathCandidates(candidates, "par").map((candidate) => candidate.path),
    ["src/parser.c", "src/include/parser.h"],
  );

  assert.equal(searchComposerPathCandidates(candidates, "read")[0].path, "README.md");
  assert.equal(searchComposerPathCandidates(candidates, "include")[0].path, "src/include/parser.h");
  assert.equal(searchComposerPathCandidates(candidates, "missing").length, 0);

  assert.equal(buildPathContextInsertion(candidates.find((candidate) => candidate.path === "src/parser.c")), "@src/parser.c ");

  const grouped = groupComposerPathCandidates(searchComposerPathCandidates(candidates, "parser"));
  assert.equal(grouped.length, 1);
  assert.equal(grouped[0].label, "Files");
  assert.deepEqual(
    grouped[0].items.map((candidate) => candidate.path),
    ["src/parser.c", "src/include/parser.h"],
  );
}
