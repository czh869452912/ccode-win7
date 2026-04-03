"""
EmbedAgent GUI Playwright 测试示例

此文件演示如何使用 Playwright 测试 EmbedAgent GUI。
适用于 Claude Code 等智能体进行交互式 GUI 测试。

依赖:
    pip install playwright
    playwright install chromium

使用方式:
    1. 启动 GUI 并启用 CDP 端口:
       python -m embedagent.gui --cdp-port=9222 --workspace=D:/your-workspace

    2. 运行测试:
       python tests/manual/playwright_example.py
"""

from playwright.sync_api import sync_playwright
import subprocess
import sys
import time


def start_gui(workspace: str, cdp_port: int = 9222) -> subprocess.Popen:
    """启动 GUI 并返回进程对象"""
    proc = subprocess.Popen([
        sys.executable, "-m", "embedagent.gui",
        "--cdp-port", str(cdp_port),
        "--workspace", workspace,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 等待 GUI 启动
    time.sleep(3)
    return proc


def connect_to_gui(cdp_port: int = 9222):
    """使用 Playwright 连接到 GUI"""
    p = sync_playwright().start()

    # 连接到 PyWebView 的 Chromium (通过 CDP)
    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")

    # 获取第一个页面 (GUI 窗口)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()

    return p, browser, page


def test_basic_interaction(page):
    """测试基本交互: 创建 session 并发送消息"""
    print("测试: 基本交互")

    # 截图: 初始状态
    page.screenshot(path="tests/manual/screenshots/01_initial.png")
    print("  - 已截图: 01_initial.png")

    # 点击 "New Session" 按钮
    page.click('[data-testid="new-session-btn"]')
    time.sleep(0.5)
    page.screenshot(path="tests/manual/screenshots/02_new_session.png")
    print("  - 已截图: 02_new_session.png")

    # 在 Composer 中输入消息
    page.fill('[data-testid="composer-input"]', "分析代码结构")
    time.sleep(0.3)
    page.screenshot(path="tests/manual/screenshots/03_typed_message.png")
    print("  - 已截图: 03_typed_message.png")

    # 点击发送按钮
    page.click('[data-testid="send-button"]')
    time.sleep(1)
    page.screenshot(path="tests/manual/screenshots/04_message_sent.png")
    print("  - 已截图: 04_message_sent.png")

    print("  测试完成!")


def test_inspector_tabs(page):
    """测试 Inspector 标签切换"""
    print("\n测试: Inspector 标签切换")

    tabs = ["todos", "plan", "artifacts", "runtime", "log"]
    for tab in tabs:
        try:
            page.click(f'[data-testid="inspector-tab--{tab}"]')
            time.sleep(0.3)
            page.screenshot(path=f"tests/manual/screenshots/05_inspector_{tab}.png")
            print(f"  - 已截图: 05_inspector_{tab}.png")
        except Exception as e:
            print(f"  - 跳过 {tab}: {e}")

    print("  测试完成!")


def test_sidebar_interaction(page):
    """测试 Sidebar 交互"""
    print("\n测试: Sidebar 交互")

    # 切换到 Files 标签
    page.click('[data-testid="sidebar-tab--files"]')
    time.sleep(0.5)
    page.screenshot(path="tests/manual/screenshots/06_sidebar_files.png")
    print("  - 已截图: 06_sidebar_files.png")

    # 切换回 Chats 标签
    page.click('[data-testid="sidebar-tab--chats"]')
    time.sleep(0.3)
    page.screenshot(path="tests/manual/screenshots/07_sidebar_chats.png")
    print("  - 已截图: 07_sidebar_chats.png")

    print("  测试完成!")


def main():
    """主函数: 演示完整的测试流程"""
    workspace = "D:/Project/coding_agent"  # 修改为你的工作区路径
    cdp_port = 9222

    # 确保截图目录存在
    import os
    os.makedirs("tests/manual/screenshots", exist_ok=True)

    # 启动 GUI
    print(f"启动 GUI: workspace={workspace}, cdp_port={cdp_port}")
    proc = start_gui(workspace, cdp_port)

    try:
        # 连接 Playwright
        print(f"连接到 CDP 端口 {cdp_port}...")
        p, browser, page = connect_to_gui(cdp_port)

        # 设置视口大小
        page.set_viewport_size({"width": 1400, "height": 900})

        print("\n=== 开始测试 ===\n")

        # 运行测试
        test_basic_interaction(page)
        test_inspector_tabs(page)
        test_sidebar_interaction(page)

        print("\n=== 所有测试完成 ===")
        print(f"截图保存在: tests/manual/screenshots/")

        # 关闭浏览器
        browser.close()
        p.stop()

    finally:
        # 关闭 GUI
        print("\n关闭 GUI...")
        proc.terminate()
        proc.wait()


def quick_test():
    """
    快速测试: 假设 GUI 已在运行 (--cdp-port=9222)
    适用于 Claude Code 等智能体直接测试
    """
    cdp_port = 9222

    with sync_playwright() as p:
        # 连接到已运行的 GUI
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
        page = browser.contexts[0].pages[0]

        # 示例 1: 点击新建 Session
        page.click('[data-testid="new-session-btn"]')
        print("已点击: 新建 Session")

        # 示例 2: 输入消息并发送
        page.fill('[data-testid="composer-input"]', "分析代码")
        page.click('[data-testid="send-button"]')
        print("已发送消息")

        # 示例 3: 截图查看结果
        page.screenshot(path="quick_test_result.png")
        print("已截图: quick_test_result.png")

        # 示例 4: 检查 Timeline 中是否有助手响应
        try:
            page.wait_for_selector('[data-testid="timeline-assistant-message"]', timeout=30000)
            print("检测到助手响应!")
        except:
            print("等待助手响应超时")

        # 不要关闭浏览器，保持 GUI 运行


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        # 快速测试模式 (GUI 已在运行)
        quick_test()
    else:
        # 完整测试模式 (自动启动 GUI)
        main()
