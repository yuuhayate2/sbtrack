import requests
import time
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL    = os.getenv("WEBHOOK_URL", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "10"))
MESSAGE_ID     = None

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

ADMINS = [
    {"username": "ThunderMods"},
    {"username": "Hypernova"},
    {"username": "Chaotic_Mind"},
    {"username": "SoniSins"},
    {"username": "PomPomSaturin"},
    {"username": "mcdaggitt"},
    {"username": "Nismo"},
    {"username": "AlterRainbow"},
]

SB_LOGO = "https://cdn.discordapp.com/attachments/1491827323757006970/1496052039426510889/content.png"

def fetch_user(username):
    try:
        r = requests.get(
            f"https://scriptblox.com/api/user/info/{username}",
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[ERR] {username}: {e}")
    return None

def get_status_label(status):
    s = (status or "").lower()
    if s in ("online", "idle", "dnd"): return s.upper()
    return "OFFLINE"

def role_label(role):
    r = (role or "").lower()
    if "owner" in r: return "Owner"
    if "admin" in r: return "Admin"
    if "mod"   in r: return "Mod"
    return "Staff"

def get_last_active_ts(ts):
    if not ts:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except:
        return datetime.min.replace(tzinfo=timezone.utc)

def format_last_seen(ts):
    if not ts: return "unknown"
    try:
        last = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        diff = int((datetime.now(timezone.utc) - last).total_seconds())
        if diff < 60:      return f"{diff}s ago"
        if diff < 3600:    return f"{diff // 60}m ago"
        if diff < 86400:   return f"{diff // 3600}h ago"
        if diff < 2592000: return f"{diff // 86400}d ago"
        return f"{diff // 2592000}mo ago"
    except:
        return "unknown"

def get_presence(status, last_active_ts):
    s = (status or "").lower()
    if s == "online":
        return "🟢", "Online"
    if last_active_ts and last_active_ts != datetime.min.replace(tzinfo=timezone.utc):
        diff = int((datetime.now(timezone.utc) - last_active_ts).total_seconds())
        if diff <= 180:
            return "🟠", "Idle"
    return "🔴", "Offline"

def build_embed(results):
    online_entries  = []
    idle_entries    = []
    offline_entries = []

    for entry in results:
        username = entry["username"]
        data     = entry.get("data")

        if not data:
            offline_entries.append({
                "line": f"🔴 [{username}](https://scriptblox.com/u/{username}) — Staff · `Offline` · last seen: `unknown`",
                "ts":   datetime.min.replace(tzinfo=timezone.utc),
            })
            continue

        user       = data.get("user", {})
        status     = get_status_label(data.get("status", ""))
        role       = role_label(user.get("role", "staff"))
        last_seen  = format_last_seen(user.get("lastActive"))
        verified   = " ✓" if user.get("verified") else ""
        ts         = get_last_active_ts(user.get("lastActive"))
        dot, label = get_presence(status, ts)
        profile    = f"[{username}{verified}](https://scriptblox.com/u/{username})"
        line       = f"{dot} {profile} — {role} · `{label}` · last seen: `{last_seen}`"

        if label == "Online":
            online_entries.append({"line": line, "ts": ts})
        elif label == "Idle":
            idle_entries.append({"line": line, "ts": ts})
        else:
            offline_entries.append({"line": line, "ts": ts})

    for group in [online_entries, idle_entries, offline_entries]:
        group.sort(key=lambda x: x["ts"], reverse=True)

    online_lines  = [e["line"] for e in online_entries]
    idle_lines    = [e["line"] for e in idle_entries]
    offline_lines = [e["line"] for e in offline_entries]

    online_count  = len(online_lines)
    idle_count    = len(idle_lines)
    offline_count = len(offline_lines)
    total         = len(results)
    now_utc       = datetime.now(timezone.utc).strftime("%b %d, %Y  %H:%M UTC")

    desc  = f"🟢 **Online** — {online_count} active\n"
    desc += "──────────────────────────────────\n"
    desc += ("\n".join(online_lines) if online_lines else "*No staff currently online.*")
    desc += "\n\n"

    desc += f"🟠 **Idle** — {idle_count} recently active\n"
    desc += "──────────────────────────────────\n"
    desc += ("\n".join(idle_lines) if idle_lines else "*No staff idle.*")
    desc += "\n\n"

    desc += f"🔴 **Offline** — {offline_count} inactive\n"
    desc += "──────────────────────────────────\n"
    desc += ("\n".join(offline_lines) if offline_lines else "*All staff are online!*")

    return {
        "username":   "ScriptBlox Tracker",
        "avatar_url": SB_LOGO,
        "embeds": [{
            "author": {
                "name":     "ScriptBlox  ·  Staff Monitor",
                "icon_url": SB_LOGO,
            },
            "description": desc.strip(),
            "color":       0x00D4FF,
            "thumbnail":   {"url": SB_LOGO},
            "fields": [{
                "name":   "📊 Overview",
                "value":  f"🟢 `{online_count}` Online  ·  🟠 `{idle_count}` Idle  ·  🔴 `{offline_count}` Offline  ·  👥 `{total}` Total",
                "inline": False,
            }],
            "footer": {
                "text":     f"Refreshed: {now_utc}  ·  Every {CHECK_INTERVAL}s",
                "icon_url": SB_LOGO,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }

def send_or_edit_webhook(payload):
    global MESSAGE_ID

    if MESSAGE_ID:
        r = requests.patch(
            f"{WEBHOOK_URL}/messages/{MESSAGE_ID}",
            json=payload, timeout=10
        )
        if r.status_code in (200, 204):
            print(f"[OK] Edited ({MESSAGE_ID})")
            return
        print(f"[WARN] Edit failed ({r.status_code}), resending...")
        MESSAGE_ID = None

    r = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload, timeout=10)
    if r.status_code in (200, 204):
        MESSAGE_ID = r.json().get("id")
        print(f"[OK] Sent (ID: {MESSAGE_ID})")
    else:
        print(f"[ERR] Webhook failed: {r.status_code}")

def main():
    print("=" * 50)
    print("   SCRIPTBLOX STAFF TRACKER")
    print(f"   {len(ADMINS)} staff  •  refresh every {CHECK_INTERVAL}s")
    print("=" * 50)

    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking...")

        results = []
        for admin in ADMINS:
            data = fetch_user(admin["username"])
            results.append({
                "username": admin["username"],
                "data":     data,
            })
            print(f"  → {admin['username']}: {'✅' if data else '❌'}")
            time.sleep(0.3)

        send_or_edit_webhook(build_embed(results))
        print(f"[OK] Next check in {CHECK_INTERVAL}s...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
