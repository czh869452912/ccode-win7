import React from "react";
import { X } from "lucide-react";

import { contributionRenderer } from "./renderer-registry.js";

export default function ContributionOutlet({ actions, contribution }) {
  if (!contribution?.active) return null;
  const Renderer = contributionRenderer(contribution.active.rendererKey);
  return (
    <div className="contribution-backdrop" role="presentation">
      <section className="contribution-outlet" role="dialog" aria-label={contribution.active.label} data-testid="contribution-outlet">
        <header className="contribution-header">
          <div className="contribution-tabs" role="tablist">
            {contribution.items.map((surface) => (
              <button type="button" role="tab" aria-selected={surface.id === contribution.activeId} onClick={() => actions.selectContribution(surface)} key={surface.id}>{surface.label}</button>
            ))}
          </div>
          <button type="button" className="icon-button" onClick={() => actions.closeContribution(contribution.active)} aria-label="Close contribution" title="Close">
            <X size={17} />
          </button>
        </header>
        <div className="contribution-body">
          <Renderer actions={actions} contribution={contribution} />
        </div>
      </section>
    </div>
  );
}
