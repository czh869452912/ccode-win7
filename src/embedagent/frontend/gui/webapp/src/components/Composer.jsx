import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  buildComposerInteractionModel,
  moveComposerMenuIndex,
  selectComposerMenuItem,
} from "../composer/composer-interaction-model.js";
import ComposerCommandMenu from "./composer/ComposerCommandMenu.jsx";
import ComposerInteractionPanel from "./composer/ComposerInteractionPanel.jsx";
import ComposerPrimaryActions from "./composer/ComposerPrimaryActions.jsx";
import BranchToolbar from "./workbench/BranchToolbar.jsx";
import { modeBadgeLabel, modeBadgeStyle } from "../session-runtime/mode-style.js";

const COMPOSER_INPUT_MAX_HEIGHT = 160;

function syncComposerTextareaSize(target) {
  if (!target) return;
  target.style.height = "auto";
  const nextHeight = Math.min(target.scrollHeight, COMPOSER_INPUT_MAX_HEIGHT);
  target.style.height = `${nextHeight}px`;
  target.style.overflowY = target.scrollHeight > COMPOSER_INPUT_MAX_HEIGHT ? "auto" : "hidden";
}

export default function Composer({
  chrome = {},
  value,
  onChange,
  onSend,
  onStop,
  isRunning,
  currentMode,
  modeCatalog = {},
  commandGroupLabels = {},
  commands = [],
  fileTree = [],
  onOpenCommandPalette,
  interaction = null,
  interactionNotice = null,
  interactionBusy = false,
  onRespondInteraction,
  branchToolbar = null,
  onRefreshSourceControl,
}) {
  const textareaRef = useRef(null);
  const [cursor, setCursor] = useState(String(value || "").length);
  const [activeIndex, setActiveIndex] = useState(0);
  const [dismissedTriggerKey, setDismissedTriggerKey] = useState("");

  const hasInteraction = Boolean(interaction || interactionNotice);
  const textValue = String(value || "");
  const commandMenuChrome = chrome.commandMenu || {};
  const interactionModel = useMemo(
    () =>
      buildComposerInteractionModel({
        value: textValue,
        cursor,
        commands,
        fileTree,
        currentMode,
        isRunning,
        hasInteraction,
        dismissedTriggerKey,
        activeIndex,
        commandMenuChrome,
        commandGroupLabels,
        hintDescriptors: chrome.hints || [],
      }),
    [
      activeIndex,
      commandGroupLabels,
      commandMenuChrome,
      commands,
      currentMode,
      cursor,
      dismissedTriggerKey,
      fileTree,
      hasInteraction,
      chrome.hints,
      isRunning,
      textValue,
    ],
  );
  const composerDisabled = interactionModel.disabled;
  const trigger = interactionModel.trigger;
  const triggerKey = interactionModel.triggerKey;
  const menuOpen = interactionModel.menu.open;
  const menuGroups = interactionModel.menu.groups;
  const menuItems = interactionModel.menu.items;
  const activeItem = interactionModel.menu.activeItem;

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

  useEffect(() => {
    syncComposerTextareaSize(textareaRef.current);
  }, [composerDisabled, textValue]);

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
      syncComposerTextareaSize(target);
      setCursor(nextCursor);
    });
  }

  function handleChange(event) {
    setDismissedTriggerKey("");
    recordCursor(event.target);
    onChange(event.target.value);
    syncComposerTextareaSize(event.target);
  }

  function selectMenuItem(item) {
    const next = selectComposerMenuItem({
      value: textValue,
      cursor,
      trigger,
      item,
    });
    if (!next) return;
    setDismissedTriggerKey("");
    onChange(next.text);
    focusAt(next.cursor);
  }

  function handleKeyDown(event) {
    if (menuOpen) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((index) => moveComposerMenuIndex(index, "next", menuItems.length));
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((index) => moveComposerMenuIndex(index, "previous", menuItems.length));
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
        chrome={chrome.interaction || {}}
        busy={interactionBusy}
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
          emptyText={interactionModel.menu.emptyText}
          chrome={commandMenuChrome}
        />
        {currentMode && (
          <span className="composer-mode-badge" style={modeBadgeStyle(currentMode, modeCatalog)}>
            {modeBadgeLabel(currentMode, modeCatalog)}
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
          placeholder={chrome.placeholder}
          aria-label={chrome.placeholder}
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
          aria-label={chrome.commandPaletteLabel}
          disabled={composerDisabled}
          data-testid="composer-command-palette"
        >
          /
        </button>
        <ComposerPrimaryActions
          isRunning={isRunning}
          disabled={composerDisabled}
          canSend={interactionModel.canSend}
          onSend={onSend}
          onStop={onStop}
          sendLabel={chrome.sendLabel}
          stopLabel={chrome.stopLabel}
        />
      </div>
      <div className="composer-hint-bar" aria-hidden="true">
        {interactionModel.hints.map((hint) => (
          <span
            className={`hint-text${hint.tone === "warning" ? " running-hint" : ""}`}
            key={hint.id}
          >
            {hint.tone === "warning" ? "● " : ""}
            {hint.label || hint.id}
          </span>
        ))}
      </div>
      <BranchToolbar model={branchToolbar} onRefresh={onRefreshSourceControl} />
    </footer>
  );
}
