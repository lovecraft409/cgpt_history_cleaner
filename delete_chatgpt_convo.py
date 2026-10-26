import re
from playwright.sync_api import sync_playwright

# ===== CONFIGURATION =====
START_AT = 15       # Chats #1-#14 are kept; deletion starts at #15
DELETE_COUNT = 20   # How many to delete in total (None = everything from START_AT on)
# ========================

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    context = browser.contexts[0]

    page = next(
        (pg for pg in context.pages if pg.url.rstrip("/") == "https://chatgpt.com"),
        None,
    ) or next((pg for pg in context.pages if "chatgpt.com" in pg.url), None)
    if not page:
        raise SystemExit("ChatGPT tab not found.")

    page.bring_to_front()
    page.set_viewport_size({"width": 1400, "height": 900})
    links = page.locator('a[href*="/c/"]')

    def scroll_sidebar():
        links.last.evaluate("""
            el => {
                let node = el.parentElement;
                while (node && node !== document.body) {
                    const s = getComputedStyle(node).overflowY;
                    if ((s === 'auto' || s === 'scroll') &&
                        node.scrollHeight > node.clientHeight) {
                        node.scrollTop = node.scrollHeight;
                        return;
                    }
                    node = node.parentElement;
                }
            }
        """)
        box = links.last.bounding_box()
        if box:
            page.mouse.move(box["x"] + 20, box["y"] + 10)
            page.mouse.wheel(0, 3000)

    def load_conversations(needed):
        """Reload the page and return as many chats as the sidebar will load."""
        page.reload()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(4000)

        for label in ["Open sidebar", "Show sidebar", "Expand sidebar"]:
            btn = page.get_by_role("button", name=label)
            if btn.count() and btn.first.is_visible():
                btn.first.click()
                page.wait_for_timeout(1500)
                break

        if links.count() == 0:
            page.screenshot(path="debug.png")
            return []

        last_count, stale = -1, 0
        while stale < 5:
            count = links.count()
            if needed is not None and count >= needed:
                break
            stale = stale + 1 if count == last_count else 0
            last_count = count
            scroll_sidebar()
            page.wait_for_timeout(1500)

        convs, seen = [], set()
        for i in range(links.count()):
            link = links.nth(i)
            href = link.get_attribute("href")
            title = (link.inner_text() or "").strip()
            if href and title and href not in seen:
                seen.add(href)
                convs.append({"title": title, "href": href})
        return convs

    def delete_chat(chat):
        """Returns 'ok', 'skip', or 'stop'."""
        target = page.locator(f'a[href="{chat["href"]}"]').first
        if not target.count():
            return "skip"

        target.scroll_into_view_if_needed()
        target.hover()
        page.wait_for_timeout(300)

        row = target.locator("xpath=ancestor::*[.//button][1]")
        options_btn = row.locator(
            'button[data-testid$="-options"], '
            'button[aria-label="Chat actions"], '
            'button[aria-label*="options" i], '
            'button[aria-haspopup="menu"]'
        ).first
        if not options_btn.count():
            return "skip"

        options_btn.click(force=True)
        page.wait_for_timeout(500)

        menu_delete = page.get_by_role("menuitem", name=re.compile(r"^delete", re.I))
        try:
            menu_delete.first.wait_for(state="visible", timeout=3000)
        except Exception:
            page.keyboard.press("Escape")
            return "skip"

        menu_delete.first.click()
        page.wait_for_timeout(500)

        dialog = page.get_by_role("dialog")
        try:
            dialog.wait_for(state="visible", timeout=3000)
        except Exception:
            print("Confirmation dialog not found; stopping for safety.")
            return "stop"

        confirm_btn = dialog.get_by_role("button", name=re.compile(r"^delete", re.I)).first
        if not confirm_btn.count():
            confirm_btn = dialog.locator(
                '[data-testid="delete-conversation-confirm-button"]'
            ).first
        confirm_btn.click()

        try:
            page.locator(f'a[href="{chat["href"]}"]').first.wait_for(
                state="detached", timeout=5000
            )
        except Exception:
            print("Could not verify deletion; stopping for safety.")
            return "stop"

        page.wait_for_timeout(800)
        return "ok"

    remaining = DELETE_COUNT
    total_deleted = 0
    confirmed = False
    round_no = 0

    while remaining is None or remaining > 0:
        round_no += 1
        needed = None if remaining is None else START_AT - 1 + remaining
        convs = load_conversations(needed)
        print(f"\n[Round {round_no}] Chats loaded: {len(convs)}")

        end = None if remaining is None else START_AT - 1 + remaining
        selected = convs[START_AT - 1:end]
        if not selected:
            print("Nothing more to delete.")
            break

        print("TARGETS — REVIEW CAREFULLY")
        for i, chat in enumerate(selected, START_AT):
            print(f"#{i}: {chat['title']} ({chat['href']})")

        if not confirmed:
            goal = "everything from here on" if remaining is None else f"{remaining} total"
            print(f"\nGoal: delete {goal}, in rounds as the sidebar loads more.")
            if input("Type DELETE to start: ") != "DELETE":
                raise SystemExit("Cancelled; nothing deleted.")
            confirmed = True

        round_deleted, stopped = 0, False
        for number, chat in enumerate(selected, START_AT):
            result = delete_chat(chat)
            if result == "ok":
                round_deleted += 1
                total_deleted += 1
                print(f"Deleted #{number}: {chat['title']} (total {total_deleted})")
            elif result == "skip":
                print(f"#{number} skipped: {chat['title']}")
            else:
                stopped = True
                break

        if remaining is not None:
            remaining -= round_deleted
        if stopped or round_deleted == 0:
            break

    print(f"\nFinished. Deleted {total_deleted} conversation(s).")