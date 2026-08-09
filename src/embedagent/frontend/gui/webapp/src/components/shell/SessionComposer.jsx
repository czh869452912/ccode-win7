import React from "react";

import Composer from "../Composer.jsx";

const COMPOSER_CHROME = Object.freeze({
  placeholder: "Message agent",
  commandPaletteLabel: "Commands",
  sendLabel: "Send",
  stopLabel: "Stop",
  hints: [],
});

const INTERACTION_CHROME = Object.freeze({
  alwaysAllowSessionLabel: "Always allow this session",
  approveOnceLabel: "Approve once",
  cancelTurnLabel: "Cancel turn",
  commandApprovalSummary: "Approve command",
  customAnswerPlaceholder: "Type an answer",
  declineLabel: "Decline",
  expiredBody: "The request is no longer active.",
  expiredTitle: "Request expired",
  fileChangeApprovalSummary: "Approve file changes",
  fileReadApprovalSummary: "Approve file access",
  inputRequiredKicker: "Input required",
  inputSummary: "Agent needs your input",
  pendingApprovalKicker: "Approval required",
  submitLabel: "Submit",
});

export default function SessionComposer({ actions, composer, interaction, modes }) {
  return (
    <section className="agent-composer-region" data-session-composer>
      <Composer
        chrome={{ ...COMPOSER_CHROME, ...(composer.chrome || {}) }}
        interactionChrome={{ ...INTERACTION_CHROME, ...(composer.interactionChrome || {}) }}
        value={composer.draft}
        onChange={actions.setComposerDraft}
        onSend={actions.sendMessage}
        onStop={actions.cancelSession}
        isRunning={composer.isRunning}
        currentMode={modes.current}
        modeCatalog={modes.catalog}
        onModeChange={actions.setMode}
        commandGroupLabels={composer.commandGroupLabels}
        commands={composer.commands}
        fileTree={composer.fileTree}
        onOpenCommandPalette={actions.openCommandPalette}
        interaction={interaction}
        interactionNotice={composer.interactionNotice}
        interactionBusy={composer.interactionBusy}
        onRespondInteraction={actions.respondToInteraction}
      />
    </section>
  );
}
