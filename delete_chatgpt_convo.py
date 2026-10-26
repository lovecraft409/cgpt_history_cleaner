import re
from playwright.sync_api import sync_playwright

# ===== CONFIGURATION =====
START_AT = 15       # Chats #1-#14 are kept; deletion starts at #15
DELETE_COUNT = 10   # Counts of convo to delete
# ========================

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    context = browser.contexts[0]

    # Prefer the home tab, fall back to any chatgpt.com tab
    page = next(
        (pg for pg in context.pages if pg.url.rstrip("/") == "https://chatgpt.com"),
        None,
    ) or next((pg for pg in context.pages if "chatgpt.com" in pg.url), None)
    if not page:
        raise SystemExit("ChatGPT tab not found.")

    page.bring_to_front()
    page.set_viewport_size({"width": 1400, "height": 900})
    page.reload()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(4000)

    # Open the sidebar if it's collapsed
    for label in ["Open sidebar", "Show sidebar", "Expand sidebar"]:
        btn = page.get_by_role("button", name=label)
        if btn.count() and btn.first.is_visible():
            btn.first.click()
            page.wait_for_timeout(1500)
            break

    links = page.locator('a[href*="/c/"]')
    print("Tab:", page.url)
    print("Chat links found:", links.count())

    if links.count() == 0:
        page.screenshot(path="debug.png")
        raise SystemExit("No chat links found. Saved debug.png to show what headless sees.")

    # Scroll the sidebar so enough chats are loaded (it lazy-loads)
    needed = None if DELETE_COUNT is None else START_AT - 1 + DELETE_COUNT
    last_count, stale = -1, 0
    while stale < 3:
        count = links.count()
        if needed is not None and count >= needed:
            break
        stale = stale + 1 if count == last_count else 0
        last_count = count
        if count:
            links.nth(count - 1).scroll_into_view_if_needed()
        page.wait_for_timeout(800)

    conversations = []
    seen = set()
    for i in range(links.count()):
        link = links.nth(i)
        href = link.get_attribute("href")
        title = (link.inner_text() or "").strip()
        if href and title and href not in seen:
            seen.add(href)
            conversations.append({"title": title, "href": href})

    print("Total chats loaded:", len(conversations))

    end = None if DELETE_COUNT is None else START_AT - 1 + DELETE_COUNT
    selected = conversations[START_AT - 1:end]

    if not selected:
        page.screenshot(path="debug.png")
        raise SystemExit(
            f"Nothing to delete (only {len(conversations)} chats loaded). "
            "Saved debug.png."
        )

    print("\nTARGETS — REVIEW CAREFULLY")
    for i, chat in enumerate(selected, START_AT):
        print(f"#{i}: {chat['title']} ({chat['href']})")
    print(f"\n{len(selected)} conversation(s) will be deleted.")

    if input("Type DELETE to start: ") != "DELETE":
        raise SystemExit("Cancelled; nothing deleted.")

    deleted = 0

    for number, chat in enumerate(selected, START_AT):
        target = page.locator(f'a[href="{chat["href"]}"]').first
        if not target.count():
            print(f"#{number} no longer available; skipped.")
            continue

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
            print(f"#{number} options button not found; skipped.")
            continue

        options_btn.click(force=True)
        page.wait_for_timeout(500)

        menu_delete = page.get_by_role("menuitem", name=re.compile(r"^delete", re.I))
        try:
            menu_delete.first.wait_for(state="visible", timeout=3000)
        except Exception:
            print(f"#{number} delete option not found; skipped.")
            page.keyboard.press("Escape")
            continue

        menu_delete.first.click()
        page.wait_for_timeout(500)

        dialog = page.get_by_role("dialog")
        try:
            dialog.wait_for(state="visible", timeout=3000)
        except Exception:
            print("Confirmation dialog not found; stopping for safety.")
            break

        confirm_btn = dialog.get_by_role(
            "button", name=re.compile(r"^delete", re.I)
        ).first
        if not confirm_btn.count():
            confirm_btn = dialog.locator(
                '[data-testid="delete-conversation-confirm-button"]'
            ).first

        confirm_btn.click()

        try:
            page.locator(f'a[href="{chat["href"]}"]').first.wait_for(
                state="detached", timeout=5000
            )
            deleted += 1
            print(f"Deleted #{number}: {chat['title']} ({deleted}/{len(selected)})")
        except Exception:
            print("Could not verify deletion; stopping for safety.")
            break

        page.wait_for_timeout(800)

    print(f"\nFinished. Deleted {deleted} conversation(s).")