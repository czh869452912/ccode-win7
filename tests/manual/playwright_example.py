"""Manual Playwright smoke for the current minimal GUI shell.

Start the GUI with ``--cdp-port=9222`` before using ``--quick``. The normal
entry point starts a local GUI process for the workspace passed on the command
line. Optional features are tested only through the generic contribution
dialog; their concrete renderer is product registration data.
"""

import os
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright


def start_gui(workspace: str, cdp_port: int = 9222) -> subprocess.Popen:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "embedagent.gui",
            "--cdp-port",
            str(cdp_port),
            "--workspace",
            workspace,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(3)
    return process


def connect(cdp_port: int):
    playwright = sync_playwright().start()
    browser = playwright.chromium.connect_over_cdp("http://127.0.0.1:%s" % cdp_port)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()
    return playwright, browser, page


def exercise_minimal_session(page) -> None:
    page.locator("[data-agent-shell]").wait_for(state="visible")
    page.get_by_role("button", name="New Session").click()
    page.locator('[data-testid="composer-input"]').fill("Analyze the current workspace")
    page.locator('[data-testid="composer-primary-action"]').click()
    page.locator("[data-session-timeline]").wait_for(state="visible")


def inspect_optional_contribution(page) -> None:
    contribution = page.locator('[data-testid="contribution-outlet"]')
    if contribution.count() == 0:
        return
    contribution.wait_for(state="visible")
    page.get_by_role("button", name="Close contribution").click()


def run(workspace: str, cdp_port: int = 9222, launch: bool = True) -> None:
    process = start_gui(workspace, cdp_port) if launch else None
    playwright = browser = None
    try:
        playwright, browser, page = connect(cdp_port)
        page.set_viewport_size({"width": 1280, "height": 720})
        exercise_minimal_session(page)
        inspect_optional_contribution(page)
        page.screenshot(path="tests/manual/gui-smoke.png")
    finally:
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()
        if process is not None:
            process.terminate()
            process.wait()


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    workspace_args = [item for item in sys.argv[1:] if item != "--quick"]
    workspace = os.path.abspath(workspace_args[0] if workspace_args else ".")
    run(workspace, launch=not quick)
