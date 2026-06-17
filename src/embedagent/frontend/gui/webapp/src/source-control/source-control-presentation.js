const STATUS_LABELS = {
  added: "A",
  copied: "C",
  deleted: "D",
  modified: "M",
  renamed: "R",
  typechange: "T",
  untracked: "U",
  conflicted: "C",
};

const GROUP_LABELS = {
  staged: "Staged",
  unstaged: "Changes",
  untracked: "Untracked",
  conflicted: "Conflicts",
};

const PROVIDER_LABELS = {
  azure: "Azure Repos",
  bitbucket: "Bitbucket",
  gitea: "Gitea",
  github: "GitHub",
  gitlab: "GitLab",
  local: "Local Git",
};

export function fileStatusLabel(file = {}) {
  const status = String(file.status || "").toLowerCase();
  if (STATUS_LABELS[status]) return STATUS_LABELS[status];
  return status ? status.slice(0, 1).toUpperCase() : "?";
}

export function groupLabel(group) {
  return GROUP_LABELS[String(group || "").toLowerCase()] || "Changes";
}

export function providerLabel(provider = {}) {
  if (provider.name) return String(provider.name);
  return PROVIDER_LABELS[String(provider.kind || "").toLowerCase()] || "Local Git";
}

export function changeSummary(file = {}) {
  const insertions = Number(file.insertions || 0);
  const deletions = Number(file.deletions || 0);
  if (!insertions && !deletions) return "";
  return `+${insertions} -${deletions}`;
}
