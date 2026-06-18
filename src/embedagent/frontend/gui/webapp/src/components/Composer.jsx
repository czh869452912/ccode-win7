import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";
import {
  buildComposerCommandItems,
  groupComposerCommandItems,
  searchComposerCommandItems,
} from "../composer/composer-command-search.js";
import {
  buildPathContextInsertion,
  flattenComposerPathCandidates,
  groupComposerPathCandidates,
  searchComposerPathCandidates,
} from "../composer/composer-path-context.js";
import {
  composerTriggerKey,
  detectComposerTrigger,
  replaceComposerTrigger,
} from "../composer/composer-trigger.js";
import ComposerCommandMenu from "./composer/ComposerCommandMenu.jsx";
import ComposerInteractionPanel from "./composer/ComposerInteractionPanel.jsx";
import ComposerPrimaryActions from "./composer/ComposerPrimaryActions.jsx";
import BranchToolbar from "./workbench/BranchToolbar.jsx";

function flattenGroups(groups) {
  return (Array.isArray(groups) ? groups : []).reduce((items, group) => {
    return items.concat(Array.isArray(group.items) ? group.items : []);
  }, []);
}

function commandsFromHints(commandHints) {
  return (Array.isArray(commandHints) ? commandHints : [])
    .filter(Boolean)
    .map((slash) => ({
      id: `hint.${String(slash).replace(/[^a-z0-9]+/gi, ".")}`,
      group: "command",
      label: slash,
      slash,
      visibleWhen: "always",
    }));
}

export default function Composer({
  value,
  onChange,
  onSend,
  onStop,
  isRunning,
  currentMode,
  commandHints = [],
  commands = [],
  fileTree = [],
  onOpenCommandPalette,
  interaction = null,
  interactionNotice = null,
  answerValue = "",
  onAnswerChange,
  onRespondInteraction,
  branchToolbar = null,
  onRefreshSourceControl,
}) {
  const lang = useLang();
  const textareaRef = useRef(null);
  const [cursor, setCursor] = useState(String(value || "").length);
  const [activeIndex, setActiveIndex] = useState(0);
  const [dismissedTriggerKey, setDismissedTriggerKey] = useState("");

  const hasInteraction = Boolean(interaction || interactionNotice);
  const composerDisabled = Boolean(isRunning || hasInteraction);
  const textValue = String(value || "");
  const trigger = useMemo(() => detectComposerTrigger(textValue, cursor), [textValue, cursor]);
  const triggerKey = composerTriggerKey(trigger);

  const commandSource = commands.length > 0 ? commands : commandsFromHints(commandHints);
  const slashItems = useMemo(() => buildComposerCommandItems(commandSource), [commandSource]);
  const pathCandidates = useMemo(() => flattenComposerPathCandidates(fileTree), [fileTree]);
  const menuOpen = Boolean(!composerDisabled && trigger && triggerKey !== dismissedTriggerKey);

  const menuGroups = useMemo(() => {
    if (!menuOpen || !trigger) return [];
    if (trigger.kind === "slash") {
      return groupComposerCommandItems(searchComposerCommandItems(slashItems, trigger.query, 8));
    }
    if (trigger.kind === "path") {
      return groupComposerPathCandidates(searchComposerPathCandidates(pathCandidates, trigger.query, 8));
    }
    return [];
  }, [menuOpen, pathCandidates, slashItems, trigger]);

  const menuItems = useMemo(() => flattenGroups(menuGroups), [menuGroups]);
  const activeItem = menuItems[Math.min(activeIndex, Math.max(0, menuItems.length - 1))] || null;

  useEffect(() => {
    setActiveIndex(0);
  }, [triggerKey]);

  useEffect(() => {
    if (cursor > textValue.length) {
      setCursor(textValue.length);
    }
  }, [cursor, textValue.length]);

  useEffect(() => {
    if (composerDisabled) {
      setDismissedTriggerKey(triggerKey);
    }
  }, [composerDisabled, triggerKey]);

  function recordCursor(target) {
    if (!target) return;
    const nextCursor = typeof target.selectionStart === "number" ? target.selectionStart : String(target.value || "").length;
    setCursor(nextCursor);
  }

  function focusAt(nextCursor) {
    window.requestAnimationFrame(() => {
      const target = textareaRef.current;
      if (!target) return;
      target.focus();
      target.setSelectionRange(nextCursor, nextCursor);
      setCursor(nextCursor);
    });
  }

  function handleChange(event) {
    setDismissedTriggerKey("");
    recordCursor(event.target);
    onChange(event.target.value);
  }

  function selectMenuItem(item) {
    if (!trigger || !item) return;
    const insertion = item.type === "path-context"
      ? buildPathContextInsertion(item)
      : item.insertion || item.slash || "";
    if (!insertion) return;
    const next = replaceComposerTrigger(textValue, trigger, insertion);
    setDismissedTriggerKey("");
    onChange(next.text);
    focusAt(next.cursor);
  }

  function handleKeyDown(event) {
    if (menuOpen) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((index) => (menuItems.length === 0 ? 0 : (index + 1) % menuItems.length));
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((index) => (menuItems.length === 0 ? 0 : (index - 1 + menuItems.length) % menuItems.length));
        return;
      }
      if ((event.key === "Enter" || event.key === "Tab") && activeItem) {
        event.preventDefault();
        selectMenuItem(activeItem);
        return;
      }
      if (event.key === "Enter" && !activeItem) {
        event.preventDefault();
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setDismissedTriggerKey(triggerKey);
        return;
      }
    }

    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!composerDisabled) onSend();
    }
  }

  function handleHighlight(item) {
    const index = menuItems.findIndex((entry) => entry.id === item.id);
    if (index >= 0) setActiveIndex(index);
  }

  return (
    <footer className="composer">
      <ComposerInteractionPanel
        interaction={interaction}
        notice={interactionNotice}
        answerValue={answerValue}
        onAnswerChange={onAnswerChange}
        onRespond={onRespondInteraction}
      />
      <div className="composer-inner">
        <ComposerCommandMenu
          open={menuOpen}
          trigger={trigger}
          groups={menuGroups}
          activeItemId={activeItem?.id || ""}
          onHighlight={handleHighlight}
          onSelect={selectMenuItem}
          emptyText={trigger?.kind === "path" ? "No files found" : "No commands found"}
        />
        {currentMode && (
          <span className={`composer-mode-badge mode-${currentMode}`}>
            {currentMode}
          </span>
        )}
        <textarea
          ref={textareaRef}
          value={textValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onClick={(event) => recordCursor(event.target)}
          onKeyUp={(event) => recordCursor(event.target)}
          onSelect={(event) => recordCursor(event.target)}
          placeholder={t("composer.placeholder", lang)}
          aria-label={t("composer.placeholder", lang)}
          aria-expanded={menuOpen}
          aria-controls={menuOpen ? "composer-command-menu" : undefined}
          disabled={composerDisabled}
          rows={1}
          data-testid="composer-input"
        />
        <button
          className="composer-tool"
          type="button"
          onClick={onOpenCommandPalette}
          aria-label="Open command palette"
          disabled={composerDisabled}
          data-testid="composer-command-palette"
        >
          /
        </button>
        <ComposerPrimaryActions
          isRunning={isRunning}
          disabled={composerDisabled}
          canSend={Boolean(textValue.trim())}
          onSend={onSend}
          onStop={onStop}
          sendLabel={t("composer.send", lang)}
          stopLabel={t("composer.stop", lang)}
        />
      </div>
      <div className="composer-hint-bar" aria-hidden="true">
        <span className="hint-text">/ 命令</span>
        <span className="hint-text">@ 文件</span>
        <span className="hint-text">↑↓ 选择</span>
        <span className="hint-text">Shift+Enter 换行</span>
        {isRunning && (
          <span className="hint-text running-hint">● running 时禁用</span>
        )}
        {hasInteraction && !isRunning && (
          <span className="hint-text running-hint">● interaction pending</span>
        )}
      </div>
      <BranchToolbar model={branchToolbar} onRefresh={onRefreshSourceControl} />
    </footer>
  );
}
