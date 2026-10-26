# ChatGPT Bulk Delete Script

Deletes ChatGPT conversations from the sidebar using Playwright, attached to a
Brave browser that's already logged in. Runs hidden (no visible window) via Xvfb.

> **Deletion is permanent.** Always read the TARGETS list before typing `DELETE`.

---

## Requirements

- Linux (tested on Ubuntu 24.04)
- Brave browser at `/usr/bin/brave-browser`
- Python 3.9+
- `xvfb` (for running without a visible window)
- Python packages in `requirements.txt` (just `playwright`)

---

## One-time setup

```bash
# 1. Python env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Virtual display
sudo apt update
sudo apt install xvfb
```

No `playwright install` needed, since the script attaches to your own Brave
instead of launching a Playwright browser.

### Log in once (headed)

The login is saved in `~/.config/brave-playwright`.

```bash
/usr/bin/brave-browser \
--user-data-dir="$HOME/.config/brave-playwright" \
--remote-debugging-address=127.0.0.1 \
--remote-debugging-port=9222 \
--no-first-run \
--no-default-browser-check \
https://chatgpt.com
```

Log in to ChatGPT, then close Brave completely.

---

## Every time you use it

**1. Start Brave hidden** (terminal 1, leave it running):

```bash
pkill -f "remote-debugging-port=9222"   # clear any old instance

xvfb-run -a --server-args="-screen 0 1400x900x24" /usr/bin/brave-browser \
--user-data-dir="$HOME/.config/brave-playwright" \
--remote-debugging-address=127.0.0.1 \
--remote-debugging-port=9222 \
--no-first-run \
--no-default-browser-check \
https://chatgpt.com
```

**2. Check it loaded** (terminal 2, wait a few seconds first):

```bash
curl -s http://127.0.0.1:9222/json | grep -i chatgpt
```

You should see a `chatgpt.com` URL (a `/c/...` URL means you're logged in).

**3. Configure and run:**

Edit the top of `delete_chatgpt_convo.py`:

```python
START_AT = 15       # chats #1-#14 are kept; deletion starts at #15
DELETE_COUNT = 10   # how many to delete (None = everything from START_AT on)
```

```bash
source .venv/bin/activate
python3 delete_chatgpt_convo.py
```

Review the printed list, then type `DELETE` to start.

**4. Stop the hidden browser when done:**

```bash
pkill -f "remote-debugging-port=9222"
```

---

## Notes

- **Numbering** follows the sidebar order. Pinned chats count toward it, so keep
  `START_AT` above them.
- **Lazy loading:** the script scrolls the sidebar to load enough chats first.
- **Safety stops:** if the confirm dialog doesn't appear, or a deletion can't be
  verified (link still in sidebar), the script stops instead of continuing.
- Only one confirmation (`DELETE`) is asked per run, not per chat.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ChatGPT tab not found` | Brave isn't running or the page hasn't loaded. Wait, then check with `curl` above. |
| `Chat links found: 0` / `debug.png` saved | Open `debug.png`. Login page: redo the headed login. Cloudflare check: use Xvfb (not `--headless=new`). Collapsed sidebar: increase the wait after reload. |
| `Nothing to delete` | Fewer chats loaded than `START_AT`. Lower `START_AT` or check `debug.png`. |
| `options button not found` | ChatGPT changed its sidebar markup. Update the button selector in the script. |
| `Delete option not found` | The menu label changed. Update the `menuitem` name regex. |
| `apt` 404 errors on install | Run `sudo apt update` first. |
| Port 9222 already in use | `pkill -f "remote-debugging-port=9222"` |

### Why Xvfb instead of `--headless=new`?

Real headless mode can get a blocked or logged-out page (headless user agent,
Cloudflare checks, keyring/cookie decryption on Linux). Xvfb runs the normal
browser on a virtual screen, so the saved login works and no window appears.

---

## Files

```
delete_chatgpt_convo.py   # the script
requirements.txt          # Python dependencies
README.md                 # this file
debug.png                 # created only when something goes wrong
```
