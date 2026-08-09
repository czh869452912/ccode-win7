import React, { forwardRef } from "react";

import Timeline from "../Timeline.jsx";

const DEFAULT_TIMELINE_CHROME = Object.freeze({
  ariaLabel: "Session timeline",
  cancelled: "Turn cancelled",
  emptyState: "Start a session",
  guardStopped: "Turn stopped by the progress guard",
  historyPartialFallback: "History is incomplete",
  historyPartialLabel: "Partial history",
  historyUnavailable: "Session history is unavailable",
  explicitLoopLimitReached: "Turn limit reached",
  maxTurnLimitTemplate: "Turn limit reached ({turnsUsed}/{maxTurns})",
  reasoningLabel: "Reasoning",
  thinkingLabel: "Thinking",
  workingLabel: "Working",
});

const SessionTimeline = forwardRef(function SessionTimeline({ actions, status, timeline }, ref) {
  return (
    <section className="agent-timeline-region" data-session-timeline>
      <Timeline
        ref={ref}
        rows={timeline.items}
        historyIntegrity={timeline.historyIntegrity}
        terminationReason={timeline.terminationReason}
        terminationDisplayReason={timeline.terminationReason}
        terminationMessage={timeline.terminationMessage}
        turnsUsed={status.turnsUsed}
        maxTurns={status.maxTurns}
        onScroll={actions.onTimelineScroll}
        onOpenDiff={actions.openDiff}
        onOpenFile={actions.openFile}
        chrome={{ ...DEFAULT_TIMELINE_CHROME, ...(timeline.chrome || {}) }}
      />
    </section>
  );
});

export default SessionTimeline;
