#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════╗
║          🧬  M a c D N A   v 3               ║
║     Capture · Deploy · Clone Your Mac         ║
╠══════════════════════════════════════════════╣
║  Author:   cyberspartan77                     ║
║  Version:  3.0 (Interactive Menu)             ║
║  Date:     March 2026                         ║
╠══════════════════════════════════════════════╣
║  Captures your Mac's full configuration DNA   ║
║  and deploys it to any new machine.           ║
║                                               ║
║  Just run: python3 macdna.py                  ║
╚══════════════════════════════════════════════╝
"""

import subprocess
import json
import os
import sys
import shutil
import platform
import datetime
import plistlib
import glob as globmod
from pathlib import Path

# ═══════════════════════════════════════════════
#  TERMINAL UI
# ═══════════════════════════════════════════════

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
BG_BLUE = "\033[44m"
BG_RESET = "\033[49m"

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(APP_DIR, "profiles")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")

# ═══════════════════════════════════════════════
#  SETTINGS ENGINE
# ═══════════════════════════════════════════════

DEFAULT_SETTINGS = {
    "profile_save_location": "",  # blank = ./profiles/
    "auto_backup_before_deploy": True,
    "dry_run_by_default": False,
    "compact_json": False,
    "color_output": True,
    "confirm_before_apply": True,
    "exclude_sensitive_dotfiles": True,
    "auto_name_profiles": False,
    "backup_directory": "",  # blank = ~/.macdna_backup/
    "default_capture_categories": "all",  # "all" or comma-separated keys
}

SENSITIVE_DOTFILES = {".netrc", ".npmrc", ".pypirc", ".docker/config.json"}


def load_settings():
    """Load settings from disk, merging with defaults for any missing keys."""
    settings = dict(DEFAULT_SETTINGS)
    if os.path.isfile(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
            settings.update(saved)
        except Exception:
            pass
    return settings


def save_settings(settings):
    """Write settings to disk."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def get_profiles_dir(settings):
    """Return the effective profiles directory."""
    custom = settings.get("profile_save_location", "").strip()
    return custom if custom else PROFILES_DIR


def get_backup_dir(settings):
    """Return the effective backup directory."""
    custom = settings.get("backup_directory", "").strip()
    return custom if custom else os.path.expanduser("~/.macdna_backup")


def clear():
    os.system("clear")


def banner():
    w = 46  # inner width between ║ walls
    top    = "  ╔" + "═" * w + "╗"
    bottom = "  ╚" + "═" * w + "╝"
    # Build lines with exact padding (emoji = 2 cols in terminal)
    l1_text = "🧬  M a c D N A   v 3"
    l2_text = "Capture  -  Deploy  -  Clone Your Mac"
    l3_text = "Author: cyberspartan77  |  v3.0  |  2026"
    # Pad accounting for emoji (2 display cols but 1 char)
    pad1 = w - len(l1_text) - 1  # -1 for emoji extra col
    pad2 = w - len(l2_text)
    pad3 = w - len(l3_text)
    line1  = "  ║" + l1_text.center(w)[:-1] + "║"  # trim 1 for emoji
    line2  = "  ║" + l2_text.center(w) + "║"
    mid    = "  ╠" + "═" * w + "╣"
    line3  = "  ║" + l3_text.center(w) + "║"
    print(f"""
{CYAN}{BOLD}{top}
{line1}
{line2}
{mid}
{line3}
{bottom}{RESET}
""")


def divider(title=""):
    if title:
        print(f"\n  {CYAN}{'─'*3} {BOLD}{title} {'─'*(40 - len(title))}{RESET}")
    else:
        print(f"  {DIM}{'─'*48}{RESET}")


def status(icon, msg, detail=""):
    d = f" {DIM}{detail}{RESET}" if detail else ""
    print(f"  {icon}  {msg}{d}")


def success(msg, detail=""):
    status(f"{GREEN}✓{RESET}", msg, detail)


def fail(msg, detail=""):
    status(f"{RED}✗{RESET}", msg, detail)


def warn(msg, detail=""):
    status(f"{YELLOW}!{RESET}", msg, detail)


def info(msg, detail=""):
    status(f"{CYAN}i{RESET}", msg, detail)


def spinner_line(msg):
    sys.stdout.write(f"\r  {YELLOW}⏳{RESET} {msg}...")
    sys.stdout.flush()


def spinner_done(msg):
    print(f"\r  {GREEN}✓{RESET}  {msg}        ")


def spinner_fail(msg, err=""):
    e = f" — {err}" if err else ""
    print(f"\r  {RED}✗{RESET}  {msg}{e}        ")


def prompt(msg, default=""):
    d = f" [{default}]" if default else ""
    try:
        val = input(f"\n  {CYAN}>{RESET} {msg}{d}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""
    return val or default


def pause():
    try:
        input(f"\n  {DIM}Press Enter to continue...{RESET}")
    except (EOFError, KeyboardInterrupt):
        pass


def show_menu(title, options, show_back=True):
    """Display a numbered menu and return the user's choice (1-based) or 0 for back/quit."""
    clear()
    banner()
    divider(title)
    print()
    for i, (label, desc) in enumerate(options, 1):
        print(f"    {BOLD}{CYAN}{i}{RESET}  {label}")
        if desc:
            print(f"       {DIM}{desc}{RESET}")
    if show_back:
        print(f"\n    {BOLD}{CYAN}0{RESET}  {DIM}{'Back' if show_back else 'Quit'}{RESET}")
    print()

    choice = prompt("Choose an option")
    try:
        return int(choice)
    except (ValueError, TypeError):
        return -1


def show_checklist(title, items, preselect_all=True):
    """
    Interactive checklist. User toggles items by number, then confirms.
    items: list of (key, label) tuples
    Returns list of selected keys.
    """
    selected = set(range(len(items))) if preselect_all else set()

    while True:
        clear()
        banner()
        divider(title)
        print(f"  {DIM}Toggle items by number. Press A=all, N=none, Enter=confirm.{RESET}\n")

        for i, (key, label) in enumerate(items):
            mark = f"{GREEN}[x]{RESET}" if i in selected else f"{DIM}[ ]{RESET}"
            print(f"    {mark} {BOLD}{i + 1}{RESET}  {label}")

        print(f"\n  {DIM}Selected: {len(selected)}/{len(items)}{RESET}")
        choice = prompt("Toggle # / A=all / N=none / Enter=GO")

        if choice == "":
            break
        elif choice.upper() == "A":
            selected = set(range(len(items)))
        elif choice.upper() == "N":
            selected.clear()
        else:
            try:
                nums = [int(x.strip()) - 1 for x in choice.replace(",", " ").split()]
                for n in nums:
                    if 0 <= n < len(items):
                        selected.symmetric_difference_update({n})
            except ValueError:
                pass

    return [items[i][0] for i in sorted(selected)]


# ═══════════════════════════════════════════════
#  SHELL HELPERS
# ═══════════════════════════════════════════════

def run(cmd, shell=True):
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except Exception:
        return ""


def defaults_read(domain, key=None):
    cmd = f"defaults read {domain}" + (f" {key}" if key else "")
    return run(cmd)


def defaults_write(domain, key, value, vtype=None):
    type_flag = f"-{vtype}" if vtype else ""
    cmd = f"defaults write {domain} {key} {type_flag} {value}"
    return run(cmd)


# ═══════════════════════════════════════════════
#  CAPTURE MODULES
# ═══════════════════════════════════════════════

def capture_meta():
    return {
        "captured_at": datetime.datetime.now().isoformat(),
        "hostname": run("scutil --get ComputerName"),
        "local_hostname": run("scutil --get LocalHostName"),
        "macos_version": platform.mac_ver()[0],
        "build": run("sw_vers -buildVersion"),
        "chip": run("uname -m"),
        "serial": run("system_profiler SPHardwareDataType | awk '/Serial Number/{print $NF}'"),
    }


def capture_system():
    return {
        "appearance": {
            "dark_mode": defaults_read("NSGlobalDomain", "AppleInterfaceStyle") == "Dark",
            "accent_color": defaults_read("NSGlobalDomain", "AppleAccentColor"),
            "highlight_color": defaults_read("NSGlobalDomain", "AppleHighlightColor"),
            "sidebar_icon_size": defaults_read("NSGlobalDomain", "NSTableViewDefaultSizeMode"),
            "reduce_motion": defaults_read("com.apple.universalaccess", "reduceMotion"),
        },
        "finder": {
            "show_extensions": defaults_read("NSGlobalDomain", "AppleShowAllExtensions"),
            "show_hidden_files": defaults_read("com.apple.finder", "AppleShowAllFiles"),
            "show_path_bar": defaults_read("com.apple.finder", "ShowPathbar"),
            "show_status_bar": defaults_read("com.apple.finder", "ShowStatusBar"),
            "default_view": defaults_read("com.apple.finder", "FXPreferredViewStyle"),
            "new_window_target": defaults_read("com.apple.finder", "NewWindowTarget"),
            "search_scope": defaults_read("com.apple.finder", "FXDefaultSearchScope"),
        },
        "trackpad": {
            "tap_to_click": defaults_read("com.apple.AppleMultitouchTrackpad", "Clicking"),
            "tracking_speed": defaults_read("NSGlobalDomain", "com.apple.trackpad.scaling"),
            "natural_scrolling": defaults_read("NSGlobalDomain", "com.apple.swipescrolldirection"),
        },
        "mouse": {
            "tracking_speed": defaults_read("NSGlobalDomain", "com.apple.mouse.scaling"),
        },
        "sounds": {
            "ui_sounds": defaults_read("NSGlobalDomain", "com.apple.sound.uiaudio.enabled"),
        },
        "screenshots": {
            "location": defaults_read("com.apple.screencapture", "location"),
            "format": defaults_read("com.apple.screencapture", "type"),
            "disable_shadow": defaults_read("com.apple.screencapture", "disable-shadow"),
        },
        "timezone": run("systemsetup -gettimezone 2>/dev/null | awk -F': ' '{print $2}'"),
    }


def capture_dock():
    dock_plist = os.path.expanduser("~/Library/Preferences/com.apple.dock.plist")
    apps = []
    try:
        with open(dock_plist, "rb") as f:
            dock_data = plistlib.load(f)
        for item in dock_data.get("persistent-apps", []):
            tile = item.get("tile-data", {})
            label = tile.get("file-label", "")
            path = tile.get("file-data", {}).get("_CFURLString", "")
            if label:
                apps.append({"label": label, "path": path})
    except Exception:
        pass

    return {
        "apps": apps,
        "position": defaults_read("com.apple.dock", "orientation"),
        "tile_size": defaults_read("com.apple.dock", "tilesize"),
        "autohide": defaults_read("com.apple.dock", "autohide"),
        "magnification": defaults_read("com.apple.dock", "magnification"),
        "minimize_effect": defaults_read("com.apple.dock", "mineffect"),
        "show_recents": defaults_read("com.apple.dock", "show-recents"),
    }


def capture_apps():
    brew_formulae = run("brew list --formula 2>/dev/null").splitlines() if shutil.which("brew") else []
    brew_casks = run("brew list --cask 2>/dev/null").splitlines() if shutil.which("brew") else []

    mas_apps = []
    if shutil.which("mas"):
        for line in run("mas list 2>/dev/null").splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                mas_apps.append({"id": parts[0], "name": parts[1].split("(")[0].strip()})

    all_apps = []
    for app_dir in ["/Applications", os.path.expanduser("~/Applications")]:
        if os.path.isdir(app_dir):
            for item in os.listdir(app_dir):
                if item.endswith(".app"):
                    all_apps.append(item.replace(".app", ""))

    return {
        "homebrew": {"formulae": brew_formulae, "casks": brew_casks},
        "mas": mas_apps,
        "all_installed": sorted(set(all_apps)),
    }


def capture_keyboard():
    return {
        "key_repeat": defaults_read("NSGlobalDomain", "KeyRepeat"),
        "initial_key_repeat": defaults_read("NSGlobalDomain", "InitialKeyRepeat"),
        "press_and_hold": defaults_read("NSGlobalDomain", "ApplePressAndHoldEnabled"),
        "fn_key_behavior": defaults_read("NSGlobalDomain", "com.apple.keyboard.fnState"),
        "auto_correct": defaults_read("NSGlobalDomain", "NSAutomaticSpellingCorrectionEnabled"),
        "auto_capitalize": defaults_read("NSGlobalDomain", "NSAutomaticCapitalizationEnabled"),
        "smart_quotes": defaults_read("NSGlobalDomain", "NSAutomaticQuoteSubstitutionEnabled"),
        "smart_dashes": defaults_read("NSGlobalDomain", "NSAutomaticDashSubstitutionEnabled"),
        "hot_corners": {
            "top_left": defaults_read("com.apple.dock", "wvous-tl-corner"),
            "top_right": defaults_read("com.apple.dock", "wvous-tr-corner"),
            "bottom_left": defaults_read("com.apple.dock", "wvous-bl-corner"),
            "bottom_right": defaults_read("com.apple.dock", "wvous-br-corner"),
        },
    }


def capture_security():
    return {
        "filevault": "On" in run("fdesetup status 2>/dev/null"),
        "firewall": defaults_read("/Library/Preferences/com.apple.alf", "globalstate"),
        "gatekeeper": "enabled" in run("spctl --status 2>/dev/null").lower(),
        "sip": "enabled" in run("csrutil status 2>/dev/null").lower(),
        "screen_lock": {
            "require_password": defaults_read("com.apple.screensaver", "askForPassword"),
            "delay_seconds": defaults_read("com.apple.screensaver", "askForPasswordDelay"),
        },
    }


def capture_shell():
    home = Path.home()
    dotfiles = {}
    for name in [".zshrc", ".bashrc", ".zprofile", ".bash_profile", ".aliases",
                 ".exports", ".functions", ".gitconfig", ".vimrc", ".tmux.conf"]:
        path = home / name
        if path.is_file():
            try:
                dotfiles[name] = path.read_text(errors="replace")
            except Exception:
                dotfiles[name] = f"[error reading {name}]"

    return {
        "default_shell": run("echo $SHELL"),
        "path": run("echo $PATH"),
        "oh_my_zsh": (home / ".oh-my-zsh").is_dir(),
        "prezto": (home / ".zprezto").is_dir(),
        "starship": shutil.which("starship") is not None,
        "dotfiles": dotfiles,
    }


def capture_login_items():
    items = []
    raw = run('osascript -e \'tell application "System Events" to get the name of every login item\'')
    if raw:
        items = [i.strip() for i in raw.split(",")]

    agents = []
    agent_dir = os.path.expanduser("~/Library/LaunchAgents")
    if os.path.isdir(agent_dir):
        agents = [f for f in os.listdir(agent_dir) if f.endswith(".plist")]

    return {"login_items": items, "launch_agents": agents}


def capture_fonts():
    user_fonts = []
    font_dir = os.path.expanduser("~/Library/Fonts")
    if os.path.isdir(font_dir):
        user_fonts = sorted(os.listdir(font_dir))
    return {"user_fonts": user_fonts}


def capture_network():
    dns = run("scutil --dns | grep 'nameserver\\[' | awk '{print $3}' | sort -u").splitlines()
    custom_hosts = []
    try:
        with open("/etc/hosts") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "localhost" not in line.lower():
                    custom_hosts.append(line)
    except Exception:
        pass

    return {
        "dns_servers": dns,
        "custom_hosts": custom_hosts,
        "wifi_network": run("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I 2>/dev/null | awk '/ SSID/{print $2}'"),
    }


# All capture modules
CAPTURE_MODULES = [
    ("meta",        "Machine Identity",   capture_meta),
    ("system",      "System Preferences", capture_system),
    ("dock",        "Dock Layout",        capture_dock),
    ("apps",        "Applications",       capture_apps),
    ("keyboard",    "Keyboard & Input",   capture_keyboard),
    ("security",    "Security",           capture_security),
    ("shell",       "Shell & Dotfiles",   capture_shell),
    ("login_items", "Login Items",        capture_login_items),
    ("fonts",       "Fonts",              capture_fonts),
    ("network",     "Network",            capture_network),
]


# ═══════════════════════════════════════════════
#  DEPLOY MODULES
# ═══════════════════════════════════════════════

def deploy_system(data, dry_run=False):
    results = []
    appearance = data.get("appearance", {})
    finder = data.get("finder", {})
    trackpad = data.get("trackpad", {})
    screenshots = data.get("screenshots", {})

    actions = []
    if appearance.get("dark_mode"):
        actions.append(("Dark Mode ON", 'osascript -e \'tell app "System Events" to tell appearance preferences to set dark mode to true\''))
    else:
        actions.append(("Dark Mode OFF", 'osascript -e \'tell app "System Events" to tell appearance preferences to set dark mode to false\''))

    if appearance.get("accent_color"):
        actions.append((f"Accent color -> {appearance['accent_color']}", f"defaults write NSGlobalDomain AppleAccentColor -int {appearance['accent_color']}"))
    if finder.get("show_extensions"):
        actions.append(("Show file extensions", "defaults write NSGlobalDomain AppleShowAllExtensions -bool true"))
    if finder.get("show_hidden_files"):
        actions.append(("Show hidden files", "defaults write com.apple.finder AppleShowAllFiles -bool true"))
    if finder.get("show_path_bar"):
        actions.append(("Show Finder path bar", "defaults write com.apple.finder ShowPathbar -bool true"))
    if finder.get("show_status_bar"):
        actions.append(("Show Finder status bar", "defaults write com.apple.finder ShowStatusBar -bool true"))
    if trackpad.get("tap_to_click") == "1":
        actions.append(("Tap to click ON", "defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true"))
    if screenshots.get("location"):
        actions.append((f"Screenshots -> {screenshots['location']}", f"defaults write com.apple.screencapture location -string \"{screenshots['location']}\""))
    if screenshots.get("format"):
        actions.append((f"Screenshot format -> {screenshots['format']}", f"defaults write com.apple.screencapture type -string {screenshots['format']}"))

    for label, cmd in actions:
        if dry_run:
            info(label, "[DRY RUN]")
        else:
            run(cmd)
            success(label)
        results.append(label)
    return results


def deploy_dock(data, dry_run=False):
    results = []
    pairs = [
        ("tile_size", "com.apple.dock", "tilesize", "int"),
        ("autohide", "com.apple.dock", "autohide", "bool"),
        ("show_recents", "com.apple.dock", "show-recents", "bool"),
    ]
    for key, domain, pref, vtype in pairs:
        val = data.get(key)
        if val:
            label = f"{pref} -> {val}"
            if dry_run:
                info(label, "[DRY RUN]")
            else:
                defaults_write(domain, pref, val, vtype)
                success(label)
            results.append(label)

    pos = data.get("position")
    if pos:
        label = f"Dock position -> {pos}"
        if dry_run:
            info(label, "[DRY RUN]")
        else:
            defaults_write("com.apple.dock", "orientation", f'"{pos}"')
            success(label)
        results.append(label)

    if not dry_run:
        run("killall Dock 2>/dev/null")
        info("Dock restarted")
    return results


def deploy_apps(data, dry_run=False):
    results = []
    brew = data.get("homebrew", {})
    formulae = brew.get("formulae", [])
    casks = brew.get("casks", [])
    mas_apps = data.get("mas", [])

    if not shutil.which("brew"):
        warn("Homebrew not installed — skipping app installs")
        return results

    if formulae:
        installed = set(run("brew list --formula").splitlines())
        to_install = [f for f in formulae if f not in installed]
        if to_install:
            label = f"{len(to_install)} brew formulae"
            if dry_run:
                info(label, "[DRY RUN]")
                for f in to_install:
                    print(f"       {DIM}{f}{RESET}")
            else:
                info(f"Installing {label}...")
                run(f"brew install {' '.join(to_install)}")
                success(label)
            results.append(label)
        else:
            success(f"All {len(formulae)} formulae already installed")

    if casks:
        installed = set(run("brew list --cask").splitlines())
        to_install = [c for c in casks if c not in installed]
        if to_install:
            label = f"{len(to_install)} brew casks"
            if dry_run:
                info(label, "[DRY RUN]")
                for c in to_install:
                    print(f"       {DIM}{c}{RESET}")
            else:
                info(f"Installing {label}...")
                run(f"brew install --cask {' '.join(to_install)}")
                success(label)
            results.append(label)
        else:
            success(f"All {len(casks)} casks already installed")

    if mas_apps and shutil.which("mas"):
        for app in mas_apps:
            label = f"{app['name']} (App Store #{app['id']})"
            if dry_run:
                info(label, "[DRY RUN]")
            else:
                run(f"mas install {app['id']}")
                success(label)
            results.append(label)
    return results


def deploy_keyboard(data, dry_run=False):
    results = []
    settings = {
        "key_repeat": ("NSGlobalDomain", "KeyRepeat", "int"),
        "initial_key_repeat": ("NSGlobalDomain", "InitialKeyRepeat", "int"),
        "press_and_hold": ("NSGlobalDomain", "ApplePressAndHoldEnabled", "bool"),
        "fn_key_behavior": ("NSGlobalDomain", "com.apple.keyboard.fnState", "bool"),
        "auto_correct": ("NSGlobalDomain", "NSAutomaticSpellingCorrectionEnabled", "bool"),
        "auto_capitalize": ("NSGlobalDomain", "NSAutomaticCapitalizationEnabled", "bool"),
        "smart_quotes": ("NSGlobalDomain", "NSAutomaticQuoteSubstitutionEnabled", "bool"),
        "smart_dashes": ("NSGlobalDomain", "NSAutomaticDashSubstitutionEnabled", "bool"),
    }
    for key, (domain, pref, vtype) in settings.items():
        val = data.get(key)
        if val:
            label = f"{pref} -> {val}"
            if dry_run:
                info(label, "[DRY RUN]")
            else:
                defaults_write(domain, pref, val, vtype)
                success(label)
            results.append(label)

    hc = data.get("hot_corners", {})
    for corner, pref in [("top_left", "wvous-tl-corner"), ("top_right", "wvous-tr-corner"),
                         ("bottom_left", "wvous-bl-corner"), ("bottom_right", "wvous-br-corner")]:
        val = hc.get(corner)
        if val:
            label = f"Hot corner {corner} -> {val}"
            if dry_run:
                info(label, "[DRY RUN]")
            else:
                defaults_write("com.apple.dock", pref, val, "int")
                success(label)
            results.append(label)
    return results


def deploy_security(data, dry_run=False):
    results = []
    lock = data.get("screen_lock", {})
    if lock.get("require_password"):
        label = "Require password after sleep"
        if dry_run:
            info(label, "[DRY RUN]")
        else:
            defaults_write("com.apple.screensaver", "askForPassword", "1", "int")
            success(label)
        results.append(label)

    if lock.get("delay_seconds"):
        label = f"Password delay -> {lock['delay_seconds']}s"
        if dry_run:
            info(label, "[DRY RUN]")
        else:
            defaults_write("com.apple.screensaver", "askForPasswordDelay", lock["delay_seconds"], "int")
            success(label)
        results.append(label)

    if data.get("filevault"):
        warn("FileVault was ON — enable manually in System Settings")
    if data.get("firewall"):
        warn(f"Firewall was state={data['firewall']} — enable via System Settings or socketfilterfw")
    return results


def deploy_shell(data, dry_run=False):
    results = []
    settings = load_settings()
    home = Path.home()
    dotfiles = data.get("dotfiles", {})
    if not dotfiles:
        info("No dotfiles in profile")
        return results

    do_backup = settings.get("auto_backup_before_deploy", True)
    bdir = get_backup_dir(settings)
    backup_dir = Path(bdir) / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    for name, content in dotfiles.items():
        target = home / name
        label = f"Restore {name}"
        if dry_run:
            exists = " (would backup existing)" if target.exists() else ""
            info(f"{label}{exists}", "[DRY RUN]")
        else:
            if target.exists() and do_backup:
                backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_dir / name)
                info(f"Backed up {name}")
            target.write_text(content)
            success(label)
        results.append(label)

    if not dry_run and do_backup and backup_dir.exists():
        info(f"Backups -> {backup_dir}")
    return results


DEPLOY_MODULES = [
    ("system",   "System Preferences", deploy_system),
    ("dock",     "Dock Layout",        deploy_dock),
    ("apps",     "Applications",       deploy_apps),
    ("keyboard", "Keyboard & Input",   deploy_keyboard),
    ("security", "Security",           deploy_security),
    ("shell",    "Shell & Dotfiles",   deploy_shell),
]


# ═══════════════════════════════════════════════
#  HTML REPORT GENERATOR
# ═══════════════════════════════════════════════

def generate_html_report(profile, filepath):
    """Generate an interactive HTML viewer for the captured profile."""
    meta = profile.get("meta", {})
    hostname = meta.get("hostname", "Unknown Mac")
    captured = meta.get("captured_at", "")
    macos_ver = meta.get("macos_version", "")
    chip = meta.get("chip", "")

    # Section icons and friendly names
    section_map = {
        "meta":        ("💻", "Machine Identity"),
        "system":      ("⚙️", "System Preferences"),
        "dock":        ("🚀", "Dock Layout"),
        "apps":        ("📦", "Applications"),
        "keyboard":    ("⌨️", "Keyboard & Input"),
        "security":    ("🔒", "Security"),
        "shell":       ("🐚", "Shell & Dotfiles"),
        "login_items": ("🔑", "Login Items"),
        "fonts":       ("🔤", "Fonts"),
        "network":     ("🌐", "Network"),
    }

    # Build section cards
    section_cards = ""
    for key in ["meta", "system", "dock", "apps", "keyboard", "security", "shell", "login_items", "fonts", "network"]:
        data = profile.get(key)
        if not data:
            continue
        icon, title = section_map.get(key, ("📄", key.title()))
        section_cards += _build_section_card(key, icon, title, data)

    # Stats for header
    n_apps = len(profile.get("apps", {}).get("all_installed", []))
    n_brew = len(profile.get("apps", {}).get("homebrew", {}).get("formulae", []))
    n_casks = len(profile.get("apps", {}).get("homebrew", {}).get("casks", []))
    n_dock = len(profile.get("dock", {}).get("apps", []))
    n_dots = len(profile.get("shell", {}).get("dotfiles", {}))
    n_fonts = len(profile.get("fonts", {}).get("user_fonts", []))
    dark = profile.get("system", {}).get("appearance", {}).get("dark_mode", False)

    profile_json_escaped = json.dumps(profile, indent=2, default=str).replace("</", "<\\/").replace("'", "\\'")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🧬 MacDNA — {hostname}</title>
<style>
  :root {{
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --dim: #8b949e;
    --cyan: #58a6ff;
    --green: #3fb950;
    --yellow: #d29922;
    --red: #f85149;
    --purple: #bc8cff;
    --font: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif;
    --mono: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 0;
  }}

  /* Header */
  .header {{
    background: linear-gradient(135deg, #161b22 0%, #1a2332 100%);
    border-bottom: 1px solid var(--border);
    padding: 2rem 2rem 1.5rem;
    text-align: center;
  }}
  .header h1 {{
    font-size: 2rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
  }}
  .header h1 span {{ color: var(--cyan); }}
  .header .subtitle {{
    color: var(--dim);
    font-size: 0.95rem;
  }}
  .header .meta-row {{
    display: flex;
    justify-content: center;
    gap: 2rem;
    margin-top: 1rem;
    flex-wrap: wrap;
  }}
  .header .meta-item {{
    font-size: 0.85rem;
    color: var(--dim);
  }}
  .header .meta-item strong {{
    color: var(--text);
  }}

  /* Stats bar */
  .stats {{
    display: flex;
    justify-content: center;
    gap: 1.5rem;
    padding: 1rem 2rem;
    background: var(--card);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }}
  .stat {{
    text-align: center;
    min-width: 80px;
  }}
  .stat .num {{
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--cyan);
  }}
  .stat .label {{
    font-size: 0.75rem;
    color: var(--dim);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}

  /* Search */
  .search-bar {{
    padding: 1rem 2rem;
    background: var(--bg);
    position: sticky;
    top: 0;
    z-index: 10;
    border-bottom: 1px solid var(--border);
  }}
  .search-bar input {{
    width: 100%;
    max-width: 500px;
    display: block;
    margin: 0 auto;
    padding: 0.6rem 1rem;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--card);
    color: var(--text);
    font-size: 0.95rem;
    font-family: var(--font);
    outline: none;
  }}
  .search-bar input:focus {{
    border-color: var(--cyan);
    box-shadow: 0 0 0 2px rgba(88,166,255,0.2);
  }}

  /* Main content */
  .container {{
    max-width: 900px;
    margin: 0 auto;
    padding: 1.5rem;
  }}

  /* Section cards */
  .section {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 1rem;
    overflow: hidden;
    transition: border-color 0.2s;
  }}
  .section:hover {{
    border-color: var(--cyan);
  }}
  .section-header {{
    display: flex;
    align-items: center;
    padding: 0.9rem 1.2rem;
    cursor: pointer;
    user-select: none;
    gap: 0.75rem;
    background: transparent;
    transition: background 0.15s;
  }}
  .section-header:hover {{
    background: rgba(88,166,255,0.05);
  }}
  .section-icon {{
    font-size: 1.3rem;
    width: 2rem;
    text-align: center;
    flex-shrink: 0;
  }}
  .section-title {{
    font-weight: 600;
    font-size: 1rem;
    flex: 1;
  }}
  .section-badge {{
    font-size: 0.75rem;
    padding: 0.15rem 0.6rem;
    border-radius: 10px;
    background: rgba(88,166,255,0.15);
    color: var(--cyan);
    font-weight: 500;
  }}
  .section-arrow {{
    color: var(--dim);
    transition: transform 0.2s;
    font-size: 0.8rem;
  }}
  .section.open .section-arrow {{
    transform: rotate(90deg);
  }}
  .section-body {{
    display: none;
    padding: 0 1.2rem 1.2rem;
    border-top: 1px solid var(--border);
  }}
  .section.open .section-body {{
    display: block;
    padding-top: 1rem;
  }}

  /* Data tables */
  .data-table {{
    width: 100%;
    border-collapse: collapse;
  }}
  .data-table tr {{
    border-bottom: 1px solid rgba(48,54,61,0.5);
  }}
  .data-table tr:last-child {{
    border-bottom: none;
  }}
  .data-table td {{
    padding: 0.45rem 0;
    vertical-align: top;
  }}
  .data-table td:first-child {{
    color: var(--dim);
    font-size: 0.85rem;
    width: 40%;
    padding-right: 1rem;
  }}
  .data-table td:last-child {{
    font-family: var(--mono);
    font-size: 0.85rem;
    word-break: break-word;
  }}

  /* Value styling */
  .val-true {{ color: var(--green); }}
  .val-false {{ color: var(--red); }}
  .val-empty {{ color: var(--dim); font-style: italic; }}
  .val-string {{ color: var(--text); }}
  .val-number {{ color: var(--purple); }}

  /* Lists */
  .item-list {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.3rem;
  }}
  .item-tag {{
    font-size: 0.8rem;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    background: rgba(88,166,255,0.1);
    color: var(--cyan);
    font-family: var(--mono);
    border: 1px solid rgba(88,166,255,0.15);
  }}
  .item-tag.app {{ background: rgba(63,185,80,0.1); color: var(--green); border-color: rgba(63,185,80,0.15); }}
  .item-tag.cask {{ background: rgba(188,140,255,0.1); color: var(--purple); border-color: rgba(188,140,255,0.15); }}
  .item-tag.dock {{ background: rgba(210,153,34,0.1); color: var(--yellow); border-color: rgba(210,153,34,0.15); }}

  /* Sub-sections */
  .subsection {{
    margin-top: 1rem;
  }}
  .subsection-title {{
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--dim);
    margin-bottom: 0.5rem;
    font-weight: 600;
  }}

  /* Code blocks for dotfiles */
  .code-block {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.8rem;
    font-family: var(--mono);
    font-size: 0.8rem;
    line-height: 1.5;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 300px;
    overflow-y: auto;
    color: var(--text);
    margin-top: 0.3rem;
  }}

  /* Footer */
  .footer {{
    text-align: center;
    padding: 2rem;
    color: var(--dim);
    font-size: 0.8rem;
    border-top: 1px solid var(--border);
    margin-top: 2rem;
  }}

  /* Raw JSON toggle */
  .raw-toggle {{
    text-align: center;
    margin: 1.5rem 0;
  }}
  .raw-toggle button {{
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--dim);
    padding: 0.5rem 1.5rem;
    border-radius: 8px;
    font-size: 0.85rem;
    cursor: pointer;
    font-family: var(--font);
    transition: all 0.2s;
  }}
  .raw-toggle button:hover {{
    border-color: var(--cyan);
    color: var(--cyan);
  }}
  .raw-json {{
    display: none;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
    margin-top: 1rem;
    max-height: 600px;
    overflow: auto;
  }}
  .raw-json pre {{
    font-family: var(--mono);
    font-size: 0.8rem;
    color: var(--text);
    white-space: pre-wrap;
    word-break: break-all;
  }}

  .hidden {{ display: none !important; }}
</style>
</head>
<body>

<div class="header">
  <h1>🧬 <span>MacDNA</span> Profile</h1>
  <div class="subtitle">{hostname} — captured {captured[:10] if captured else 'N/A'}</div>
  <div class="meta-row">
    <div class="meta-item">macOS <strong>{macos_ver}</strong></div>
    <div class="meta-item">Chip <strong>{chip}</strong></div>
    <div class="meta-item">Dark Mode <strong>{'Yes' if dark else 'No'}</strong></div>
    <div class="meta-item">Serial <strong>{meta.get('serial', 'N/A')}</strong></div>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="num">{n_apps}</div><div class="label">Apps</div></div>
  <div class="stat"><div class="num">{n_brew}</div><div class="label">Formulae</div></div>
  <div class="stat"><div class="num">{n_casks}</div><div class="label">Casks</div></div>
  <div class="stat"><div class="num">{n_dock}</div><div class="label">Dock</div></div>
  <div class="stat"><div class="num">{n_dots}</div><div class="label">Dotfiles</div></div>
  <div class="stat"><div class="num">{n_fonts}</div><div class="label">Fonts</div></div>
</div>

<div class="search-bar">
  <input type="text" id="search" placeholder="Search settings, apps, values..." autocomplete="off">
</div>

<div class="container">
{section_cards}

  <div class="raw-toggle">
    <button onclick="toggleRaw()">Show Raw JSON</button>
  </div>
  <div class="raw-json" id="rawJson">
    <pre>{json.dumps(profile, indent=2, default=str).replace('<', '&lt;').replace('>', '&gt;')}</pre>
  </div>
</div>

<div class="footer">
  🧬 MacDNA v3.0 — Author: cyberspartan77 — Generated {captured[:10] if captured else 'N/A'}
</div>

<script>
// Toggle sections
document.querySelectorAll('.section-header').forEach(h => {{
  h.addEventListener('click', () => {{
    h.parentElement.classList.toggle('open');
  }});
}});

// Search
document.getElementById('search').addEventListener('input', function() {{
  const q = this.value.toLowerCase();
  document.querySelectorAll('.section').forEach(s => {{
    if (!q) {{
      s.classList.remove('hidden');
      return;
    }}
    const text = s.textContent.toLowerCase();
    if (text.includes(q)) {{
      s.classList.remove('hidden');
      s.classList.add('open');
    }} else {{
      s.classList.add('hidden');
    }}
  }});
}});

// Raw JSON toggle
function toggleRaw() {{
  const el = document.getElementById('rawJson');
  el.style.display = el.style.display === 'block' ? 'none' : 'block';
}}

// Expand all on load for quick view
document.querySelectorAll('.section').forEach(s => s.classList.add('open'));
</script>
</body>
</html>"""

    with open(filepath, "w") as f:
        f.write(html)


def _format_value(val):
    """Format a value for HTML display."""
    if val is True:
        return '<span class="val-true">true ✓</span>'
    elif val is False:
        return '<span class="val-false">false ✗</span>'
    elif val is None or val == "":
        return '<span class="val-empty">(default)</span>'
    elif isinstance(val, (int, float)):
        return f'<span class="val-number">{val}</span>'
    else:
        s = str(val).replace('<', '&lt;').replace('>', '&gt;')
        return f'<span class="val-string">{s}</span>'


def _build_section_card(key, icon, title, data):
    """Build an HTML card for a profile section."""
    # Count items for badge
    badge = ""
    if isinstance(data, dict):
        badge = f'{len(data)} items'
    elif isinstance(data, list):
        badge = f'{len(data)} items'

    body_html = _render_data(key, data)

    return f"""
  <div class="section" data-key="{key}">
    <div class="section-header">
      <div class="section-icon">{icon}</div>
      <div class="section-title">{title}</div>
      <div class="section-badge">{badge}</div>
      <div class="section-arrow">▶</div>
    </div>
    <div class="section-body">{body_html}</div>
  </div>
"""


def _render_data(key, data, depth=0):
    """Recursively render data into HTML tables, lists, and code blocks."""
    if isinstance(data, dict):
        rows = ""
        for k, v in data.items():
            # Special handling for known list fields
            if key == "apps" and k == "all_installed" and isinstance(v, list):
                tags = "".join(f'<span class="item-tag app">{item}</span>' for item in v)
                rows += f'<div class="subsection"><div class="subsection-title">All Installed Apps ({len(v)})</div><div class="item-list">{tags}</div></div>'
            elif key == "apps" and k == "homebrew" and isinstance(v, dict):
                formulae = v.get("formulae", [])
                casks = v.get("casks", [])
                f_tags = "".join(f'<span class="item-tag">{item}</span>' for item in formulae)
                c_tags = "".join(f'<span class="item-tag cask">{item}</span>' for item in casks)
                rows += f'<div class="subsection"><div class="subsection-title">Homebrew Formulae ({len(formulae)})</div><div class="item-list">{f_tags}</div></div>'
                rows += f'<div class="subsection"><div class="subsection-title">Homebrew Casks ({len(casks)})</div><div class="item-list">{c_tags}</div></div>'
            elif key == "apps" and k == "mas" and isinstance(v, list):
                if v:
                    tags = "".join(f'<span class="item-tag app">{item.get("name", "")} (#{item.get("id", "")})</span>' for item in v)
                    rows += f'<div class="subsection"><div class="subsection-title">Mac App Store ({len(v)})</div><div class="item-list">{tags}</div></div>'
                else:
                    rows += f'<div class="subsection"><div class="subsection-title">Mac App Store</div><span class="val-empty">None captured (install mas CLI)</span></div>'
            elif key == "dock" and k == "apps" and isinstance(v, list):
                tags = "".join(f'<span class="item-tag dock">{item.get("label", "")}</span>' for item in v)
                rows += f'<div class="subsection"><div class="subsection-title">Dock Apps ({len(v)})</div><div class="item-list">{tags}</div></div>'
            elif key == "shell" and k == "dotfiles" and isinstance(v, dict):
                for fname, content in v.items():
                    safe = str(content).replace('<', '&lt;').replace('>', '&gt;')
                    rows += f'<div class="subsection"><div class="subsection-title">{fname}</div><div class="code-block">{safe}</div></div>'
            elif key == "login_items" and k == "login_items" and isinstance(v, list):
                tags = "".join(f'<span class="item-tag">{item}</span>' for item in v)
                rows += f'<div class="subsection"><div class="subsection-title">Login Items ({len(v)})</div><div class="item-list">{tags}</div></div>'
            elif key == "login_items" and k == "launch_agents" and isinstance(v, list):
                tags = "".join(f'<span class="item-tag">{item}</span>' for item in v)
                rows += f'<div class="subsection"><div class="subsection-title">Launch Agents ({len(v)})</div><div class="item-list">{tags}</div></div>'
            elif key == "fonts" and k == "user_fonts" and isinstance(v, list):
                if v:
                    tags = "".join(f'<span class="item-tag">{item}</span>' for item in v)
                    rows += f'<div class="subsection"><div class="subsection-title">User Fonts ({len(v)})</div><div class="item-list">{tags}</div></div>'
                else:
                    rows += '<div class="subsection"><div class="subsection-title">User Fonts</div><span class="val-empty">None installed</span></div>'
            elif key == "network" and k == "dns_servers" and isinstance(v, list):
                tags = "".join(f'<span class="item-tag">{item}</span>' for item in v)
                rows += f'<div class="subsection"><div class="subsection-title">DNS Servers</div><div class="item-list">{tags}</div></div>'
            elif key == "network" and k == "custom_hosts" and isinstance(v, list):
                if v:
                    lines = "\\n".join(str(h) for h in v)
                    safe = lines.replace('<', '&lt;').replace('>', '&gt;')
                    rows += f'<div class="subsection"><div class="subsection-title">Custom Hosts</div><div class="code-block">{safe}</div></div>'
            elif isinstance(v, dict):
                # Nested dict -> sub-table
                sub_rows = ""
                for sk, sv in v.items():
                    sub_rows += f'<tr><td>{sk}</td><td>{_format_value(sv)}</td></tr>'
                friendly = k.replace("_", " ").title()
                rows += f'<div class="subsection"><div class="subsection-title">{friendly}</div><table class="data-table">{sub_rows}</table></div>'
            elif isinstance(v, list):
                if v:
                    tags = "".join(f'<span class="item-tag">{item}</span>' for item in v)
                    friendly = k.replace("_", " ").title()
                    rows += f'<div class="subsection"><div class="subsection-title">{friendly} ({len(v)})</div><div class="item-list">{tags}</div></div>'
            else:
                rows += f'<table class="data-table"><tr><td>{k}</td><td>{_format_value(v)}</td></tr></table>'
        return rows

    elif isinstance(data, list):
        tags = "".join(f'<span class="item-tag">{item}</span>' for item in data)
        return f'<div class="item-list">{tags}</div>'
    else:
        return f'<p>{_format_value(data)}</p>'


# ═══════════════════════════════════════════════
#  MENU FLOWS
# ═══════════════════════════════════════════════

def profile_display_name(filepath):
    """Get a friendly display name from a profile path."""
    parent = os.path.basename(os.path.dirname(filepath))
    filename = os.path.basename(filepath)
    if filename == "profile.json":
        return parent  # folder name is the label
    return filename  # legacy flat file


def get_saved_profiles():
    """Find all profile.json files in profile subdirectories, plus legacy top-level .json files."""
    settings = load_settings()
    pdir = get_profiles_dir(settings)
    os.makedirs(pdir, exist_ok=True)
    # New format: profiles/<folder>/profile.json
    folder_profiles = sorted(globmod.glob(os.path.join(pdir, "*", "profile.json")), key=os.path.getmtime, reverse=True)
    # Legacy format: profiles/*.json (flat files)
    flat_profiles = sorted(globmod.glob(os.path.join(pdir, "*.json")), key=os.path.getmtime, reverse=True)
    return folder_profiles + flat_profiles


def flow_capture():
    """Full capture flow with category selection."""
    settings = load_settings()

    clear()
    banner()
    divider("CAPTURE — Select Categories")

    # Determine pre-selection from settings
    default_cats = settings.get("default_capture_categories", "all")
    if default_cats == "all":
        preselect = True
    else:
        preset_keys = {k.strip() for k in default_cats.split(",")}
        preselect = False  # we'll handle manually below

    # Let user pick which categories to capture
    checklist_items = [(key, label) for key, label, _ in CAPTURE_MODULES]

    if default_cats != "all" and not preselect:
        # Pre-select only the configured defaults
        selected_keys = show_checklist("Select categories to capture", checklist_items, preselect_all=False)
    else:
        selected_keys = show_checklist("Select categories to capture", checklist_items, preselect_all=True)

    if not selected_keys:
        warn("Nothing selected")
        pause()
        return

    # Run capture
    clear()
    banner()
    divider("CAPTURING")
    print()

    profile = {}
    for key, label, func in CAPTURE_MODULES:
        if key not in selected_keys:
            continue
        spinner_line(label)
        try:
            profile[key] = func()
            spinner_done(label)
        except Exception as e:
            profile[key] = {"error": str(e)}
            spinner_fail(label, str(e))

    # Filter sensitive dotfiles if setting is on
    if settings.get("exclude_sensitive_dotfiles", True) and "shell" in profile:
        dotfiles = profile["shell"].get("dotfiles", {})
        removed = []
        for sensitive in SENSITIVE_DOTFILES:
            if sensitive in dotfiles:
                del dotfiles[sensitive]
                removed.append(sensitive)
        if removed:
            warn(f"Excluded sensitive dotfiles: {', '.join(removed)}")

    # Save — create a folder per capture with JSON + HTML
    pdir = get_profiles_dir(settings)
    hostname_clean = profile.get("meta", {}).get("hostname", "Mac").replace(" ", "_").replace("'", "")
    date_str = datetime.date.today().isoformat()
    folder_name = f"{hostname_clean}_{date_str}"

    if not settings.get("auto_name_profiles", False):
        print()
        folder_name = prompt("Profile folder name", folder_name)

    folder_path = os.path.join(pdir, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # Write JSON
    json_path = os.path.join(folder_path, "profile.json")
    indent = None if settings.get("compact_json", False) else 2
    with open(json_path, "w") as f:
        json.dump(profile, f, indent=indent, default=str)

    # Write HTML viewer
    spinner_line("Generating HTML report")
    html_path = os.path.join(folder_path, "profile.html")
    generate_html_report(profile, html_path)
    spinner_done("HTML report generated")

    print()
    divider("CAPTURE COMPLETE")
    success(f"Folder: {folder_path}")
    info(f"JSON:   {os.path.getsize(json_path) / 1024:.1f} KB")
    info(f"HTML:   {os.path.getsize(html_path) / 1024:.1f} KB")

    # Quick stats
    apps = profile.get("apps", {}).get("all_installed", [])
    dots = profile.get("shell", {}).get("dotfiles", {})
    dock = profile.get("dock", {}).get("apps", [])
    fonts = profile.get("fonts", {}).get("user_fonts", [])
    if apps:
        info(f"Apps found: {len(apps)}")
    if dots:
        info(f"Dotfiles: {len(dots)}")
    if dock:
        info(f"Dock apps: {len(dock)}")
    if fonts:
        info(f"User fonts: {len(fonts)}")

    # Offer to open HTML
    open_it = prompt("Open HTML report in browser? (y/N)")
    if open_it.lower() == "y":
        run(f'open "{html_path}"')

    pause()


def flow_deploy():
    """Deploy flow: pick a profile, pick categories, apply."""
    settings = load_settings()
    profiles = get_saved_profiles()

    if not profiles:
        clear()
        banner()
        warn("No saved profiles found.")
        pdir = get_profiles_dir(settings)
        info(f"Capture a profile first, or place .json files in:\n       {pdir}")
        pause()
        return

    # Pick a profile
    options = []
    for p in profiles:
        name = profile_display_name(p)
        size = os.path.getsize(p) / 1024
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")
        options.append((name, f"{size:.1f} KB — {mtime}"))

    choice = show_menu("DEPLOY — Select a Profile", options)
    if choice <= 0 or choice > len(profiles):
        return

    profile_path = profiles[choice - 1]

    with open(profile_path) as f:
        profile = json.load(f)

    hostname = profile.get("meta", {}).get("hostname", "Unknown")
    captured = profile.get("meta", {}).get("captured_at", "?")

    # Show profile summary
    clear()
    banner()
    divider(f"Profile: {hostname}")
    info(f"Captured: {captured}")
    info(f"macOS: {profile.get('meta', {}).get('macos_version', '?')}")
    info(f"Chip: {profile.get('meta', {}).get('chip', '?')}")
    print()

    # Build checklist of available deploy categories
    available = []
    for key, label, func in DEPLOY_MODULES:
        if key in profile and profile[key]:
            count = ""
            if key == "apps":
                n = len(profile[key].get("all_installed", []))
                count = f" ({n} apps)"
            elif key == "shell":
                n = len(profile[key].get("dotfiles", {}))
                count = f" ({n} dotfiles)"
            available.append((key, f"{label}{count}"))

    if not available:
        warn("This profile has no deployable data")
        pause()
        return

    selected_keys = show_checklist("Select categories to deploy", available, preselect_all=True)
    if not selected_keys:
        warn("Nothing selected")
        pause()
        return

    # Dry run or live?
    if settings.get("dry_run_by_default", False):
        # Setting forces dry-run, but let user override
        clear()
        banner()
        divider("Deploy Mode")
        print()
        warn("Dry-Run is ON by default (change in Settings)")
        print()
        print(f"    {BOLD}{CYAN}1{RESET}  Dry Run   {DIM}(preview changes, touch nothing){RESET}")
        print(f"    {BOLD}{CYAN}2{RESET}  Apply     {DIM}(override — make changes to this Mac){RESET}")
        print(f"    {BOLD}{CYAN}0{RESET}  {DIM}Cancel{RESET}")
        mode = prompt("Choose mode", "1")
    else:
        clear()
        banner()
        divider("Deploy Mode")
        print()
        print(f"    {BOLD}{CYAN}1{RESET}  Dry Run   {DIM}(preview changes, touch nothing){RESET}")
        print(f"    {BOLD}{CYAN}2{RESET}  Apply     {DIM}(make changes to this Mac){RESET}")
        print(f"    {BOLD}{CYAN}0{RESET}  {DIM}Cancel{RESET}")
        mode = prompt("Choose mode")

    if mode == "0" or mode == "":
        return

    dry_run = mode != "2"

    if not dry_run and settings.get("confirm_before_apply", True):
        clear()
        banner()
        divider("CONFIRM DEPLOYMENT")
        print()
        warn(f"This will modify settings on THIS Mac.")
        info(f"Source profile: {hostname}")
        info(f"Categories: {len(selected_keys)}")
        if settings.get("auto_backup_before_deploy", True):
            info(f"Auto-backup: {GREEN}ON{RESET} — existing files will be backed up first")
        print()
        confirm = prompt("Type YES to proceed")
        if confirm != "YES":
            info("Cancelled.")
            pause()
            return
    elif not dry_run and not settings.get("confirm_before_apply", True):
        # No confirmation required — just a quick heads-up
        info("Confirm is OFF — applying immediately...")

    # Execute deployment
    clear()
    banner()
    mode_label = "DRY RUN" if dry_run else "APPLYING"
    divider(f"DEPLOYING — {mode_label}")

    all_results = {"applied": [], "skipped": [], "errors": []}

    for key, label, func in DEPLOY_MODULES:
        if key not in selected_keys:
            continue
        data = profile.get(key, {})
        if not data:
            all_results["skipped"].append(label)
            continue
        print()
        divider(label)
        try:
            results = func(data, dry_run=dry_run)
            all_results["applied"].append(label)
        except Exception as e:
            fail(f"{label}: {e}")
            all_results["errors"].append(f"{label}: {e}")

    # Report
    print()
    print(f"\n  {BOLD}{CYAN}{'═'*48}{RESET}")
    print(f"  {BOLD}  DEPLOYMENT REPORT{RESET}")
    print(f"  {BOLD}{CYAN}{'═'*48}{RESET}")
    print()
    if all_results["applied"]:
        for a in all_results["applied"]:
            success(a)
    if all_results["skipped"]:
        for s in all_results["skipped"]:
            warn(f"{s} (skipped — no data)")
    if all_results["errors"]:
        for e in all_results["errors"]:
            fail(e)

    # Manual attention
    manual = []
    if "apps" in profile:
        all_apps = profile["apps"].get("all_installed", [])
        brew_all = set(profile["apps"].get("homebrew", {}).get("formulae", []) +
                       profile["apps"].get("homebrew", {}).get("casks", []))
        mas_names = {a["name"] for a in profile["apps"].get("mas", [])}
        manual_apps = [a for a in all_apps if a not in brew_all and a not in mas_names]
        if manual_apps:
            manual.append(f"Manually installed apps: {', '.join(manual_apps[:8])}{'...' if len(manual_apps) > 8 else ''}")

    if "login_items" in profile:
        items = profile["login_items"].get("login_items", [])
        if items:
            manual.append(f"Login items to re-add: {', '.join(items)}")

    if "fonts" in profile:
        fonts = profile["fonts"].get("user_fonts", [])
        if fonts:
            manual.append(f"{len(fonts)} user fonts need manual copy from ~/Library/Fonts")

    if manual:
        print()
        divider("NEEDS MANUAL ATTENTION")
        for m in manual:
            warn(m)

    pause()


def flow_view_profile():
    """Browse and inspect a saved profile."""
    profiles = get_saved_profiles()
    if not profiles:
        clear()
        banner()
        warn("No saved profiles.")
        pause()
        return

    options = []
    for p in profiles:
        name = profile_display_name(p)
        size = os.path.getsize(p) / 1024
        options.append((name, f"{size:.1f} KB"))

    choice = show_menu("VIEW — Select a Profile", options)
    if choice <= 0 or choice > len(profiles):
        return

    with open(profiles[choice - 1]) as f:
        profile = json.load(f)

    # Show sections menu
    while True:
        sections = [(k, f"{len(str(v))} chars") for k, v in profile.items()]
        sec_choice = show_menu(f"Profile Sections — {profile_display_name(profiles[choice-1])}", sections)
        if sec_choice <= 0 or sec_choice > len(sections):
            break

        key = sections[sec_choice - 1][0]
        data = profile[key]

        clear()
        banner()
        divider(f"Section: {key}")
        print()
        print(json.dumps(data, indent=2, default=str))
        pause()


def flow_diff():
    """Compare two profiles side by side."""
    profiles = get_saved_profiles()
    if len(profiles) < 2:
        clear()
        banner()
        warn("Need at least 2 saved profiles to compare.")
        pause()
        return

    options = [(profile_display_name(p), "") for p in profiles]

    clear()
    banner()
    divider("DIFF — Select FIRST profile")
    for i, (label, _) in enumerate(options, 1):
        print(f"    {BOLD}{CYAN}{i}{RESET}  {label}")
    c1 = prompt("First profile #")
    try:
        idx1 = int(c1) - 1
    except (ValueError, TypeError):
        return

    clear()
    banner()
    divider("DIFF — Select SECOND profile")
    for i, (label, _) in enumerate(options, 1):
        marker = f" {YELLOW}<- first{RESET}" if i - 1 == idx1 else ""
        print(f"    {BOLD}{CYAN}{i}{RESET}  {label}{marker}")
    c2 = prompt("Second profile #")
    try:
        idx2 = int(c2) - 1
    except (ValueError, TypeError):
        return

    if idx1 == idx2:
        warn("Same profile selected twice")
        pause()
        return

    with open(profiles[idx1]) as f:
        p1 = json.load(f)
    with open(profiles[idx2]) as f:
        p2 = json.load(f)

    clear()
    banner()
    name1 = profile_display_name(profiles[idx1])
    name2 = profile_display_name(profiles[idx2])
    divider(f"DIFF: {name1} vs {name2}")
    print()

    all_keys = sorted(set(list(p1.keys()) + list(p2.keys())))
    diffs_found = 0

    for section in all_keys:
        d1 = p1.get(section)
        d2 = p2.get(section)
        if d1 == d2:
            success(f"{section}: identical")
            continue

        if d1 is None:
            warn(f"{section}: only in {name2}")
            diffs_found += 1
            continue
        if d2 is None:
            warn(f"{section}: only in {name1}")
            diffs_found += 1
            continue

        # Shallow diff for dicts
        if isinstance(d1, dict) and isinstance(d2, dict):
            changed = []
            for k in sorted(set(list(d1.keys()) + list(d2.keys()))):
                v1, v2 = d1.get(k), d2.get(k)
                if v1 != v2:
                    changed.append(k)
            if changed:
                fail(f"{section}: {len(changed)} differences")
                for k in changed[:5]:
                    print(f"       {DIM}{k}: {str(d1.get(k))[:40]} -> {str(d2.get(k))[:40]}{RESET}")
                if len(changed) > 5:
                    print(f"       {DIM}...and {len(changed) - 5} more{RESET}")
                diffs_found += len(changed)
        else:
            fail(f"{section}: different")
            diffs_found += 1

    print()
    if diffs_found == 0:
        success("Profiles are identical!")
    else:
        info(f"Total differences: {diffs_found}")

    pause()


def flow_delete_profile():
    """Delete a saved profile."""
    profiles = get_saved_profiles()
    if not profiles:
        clear()
        banner()
        warn("No saved profiles.")
        pause()
        return

    options = [(profile_display_name(p), f"{os.path.getsize(p)/1024:.1f} KB") for p in profiles]
    choice = show_menu("DELETE — Select a Profile", options)
    if choice <= 0 or choice > len(profiles):
        return

    target = profiles[choice - 1]
    name = profile_display_name(target)
    confirm = prompt(f"Delete {name}? Type DELETE to confirm")
    if confirm == "DELETE":
        # If it's a folder-based profile, delete the whole folder
        parent_dir = os.path.dirname(target)
        if os.path.basename(target) == "profile.json" and parent_dir != get_profiles_dir(load_settings()):
            shutil.rmtree(parent_dir)
            success(f"Deleted folder: {name}")
        else:
            os.remove(target)
            success(f"Deleted {name}")
    else:
        info("Cancelled")
    pause()


# ═══════════════════════════════════════════════
#  SETTINGS MENU
# ═══════════════════════════════════════════════

SETTINGS_DEFS = [
    # (key, label, description, type)
    ("profile_save_location",       "Profile Save Location",        "Where captured profiles are saved (blank = ./profiles/)",  "path"),
    ("backup_directory",            "Backup Directory",             "Where pre-deploy backups go (blank = ~/.macdna_backup/)",  "path"),
    ("auto_backup_before_deploy",   "Auto-Backup Before Deploy",    "Backup existing files before overwriting",                "bool"),
    ("dry_run_by_default",          "Dry-Run by Default",           "Always preview before applying changes",                  "bool"),
    ("confirm_before_apply",        "Confirm Before Apply",         "Require typing YES before deploy",                        "bool"),
    ("exclude_sensitive_dotfiles",  "Exclude Sensitive Dotfiles",   "Skip .netrc, .npmrc, .pypirc from capture",               "bool"),
    ("auto_name_profiles",          "Auto-Name Profiles",           "Skip 'save as' prompt, auto-generate filename",           "bool"),
    ("compact_json",                "Compact JSON",                 "Save profiles as compact (smaller) vs pretty-printed",    "bool"),
    ("color_output",                "Color Output",                 "Enable/disable terminal colors",                          "bool"),
    ("default_capture_categories",  "Default Capture Categories",   "Pre-selected categories (all or comma-separated keys)",   "text"),
]


def flow_settings():
    """Settings menu — view and toggle all app settings."""
    settings = load_settings()

    while True:
        clear()
        banner()
        divider("SETTINGS")
        print()

        for i, (key, label, desc, stype) in enumerate(SETTINGS_DEFS, 1):
            val = settings.get(key, DEFAULT_SETTINGS.get(key))

            # Format the display value
            if stype == "bool":
                if val:
                    display = f"{GREEN}ON{RESET}"
                else:
                    display = f"{RED}OFF{RESET}"
            elif stype == "path":
                if val:
                    display = f"{CYAN}{val}{RESET}"
                else:
                    default_hint = "./profiles/" if "profile" in key else "~/.macdna_backup/"
                    display = f"{DIM}{default_hint} (default){RESET}"
            else:
                display = f"{CYAN}{val}{RESET}"

            print(f"    {BOLD}{CYAN}{i:>2}{RESET}  {label}")
            print(f"        {DIM}{desc}{RESET}")
            print(f"        Current: {display}")
            print()

        print(f"    {BOLD}{CYAN} R{RESET}  {YELLOW}Reset All to Defaults{RESET}")
        print(f"    {BOLD}{CYAN} 0{RESET}  {DIM}Back to Main Menu{RESET}")
        print()

        choice = prompt("Setting # to change / R=reset / 0=back")

        if choice == "0" or choice == "":
            break
        elif choice.upper() == "R":
            confirm = prompt("Reset ALL settings to defaults? (y/N)")
            if confirm.lower() == "y":
                settings = dict(DEFAULT_SETTINGS)
                save_settings(settings)
                success("All settings reset to defaults")
                pause()
            continue

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(SETTINGS_DEFS):
                continue
        except ValueError:
            continue

        key, label, desc, stype = SETTINGS_DEFS[idx]

        if stype == "bool":
            # Toggle it
            current = settings.get(key, DEFAULT_SETTINGS.get(key))
            settings[key] = not current
            new_state = f"{GREEN}ON{RESET}" if settings[key] else f"{RED}OFF{RESET}"
            save_settings(settings)
            # Instant feedback — just redraw

        elif stype == "path":
            current = settings.get(key, "")
            print()
            info(f"Current: {current or '(default)'}")
            new_val = prompt(f"New path (blank = use default)")
            if new_val:
                # Expand ~ and validate
                expanded = os.path.expanduser(new_val)
                if not os.path.isdir(expanded):
                    create = prompt(f"Directory doesn't exist. Create it? (y/N)")
                    if create.lower() == "y":
                        try:
                            os.makedirs(expanded, exist_ok=True)
                            settings[key] = expanded
                            save_settings(settings)
                            success(f"Created and set: {expanded}")
                        except Exception as e:
                            fail(f"Could not create: {e}")
                        pause()
                    else:
                        settings[key] = expanded
                        save_settings(settings)
                else:
                    settings[key] = expanded
                    save_settings(settings)
            else:
                settings[key] = ""
                save_settings(settings)

        elif stype == "text":
            current = settings.get(key, "")
            print()
            info(f"Current: {current}")
            info("Enter 'all' for all categories, or comma-separated keys:")
            info(f"  Available: meta, system, dock, apps, keyboard, security, shell, login_items, fonts, network")
            new_val = prompt("New value", current)
            settings[key] = new_val.strip()
            save_settings(settings)


# ═══════════════════════════════════════════════
#  MAIN MENU LOOP
# ═══════════════════════════════════════════════

def main():
    while True:
        n_profiles = len(get_saved_profiles())
        profile_info = f"{n_profiles} saved" if n_profiles else "none yet"

        choice = show_menu("MAIN MENU", [
            ("Capture This Mac",   "Scan and save all settings to a profile"),
            ("Deploy to This Mac", "Apply a saved profile to this machine"),
            ("View Profile",       "Browse the contents of a saved profile"),
            ("Compare Profiles",   "Diff two profiles side by side"),
            ("Delete Profile",     f"Remove a saved profile ({profile_info})"),
            (f"{YELLOW}Settings{RESET}",  "Configure MacDNA preferences"),
            (f"{RED}Exit MacDNA{RESET}",  "Quit the application"),
        ], show_back=False)

        if choice == 1:
            flow_capture()
        elif choice == 2:
            flow_deploy()
        elif choice == 3:
            flow_view_profile()
        elif choice == 4:
            flow_diff()
        elif choice == 5:
            flow_delete_profile()
        elif choice == 6:
            flow_settings()
        elif choice == 7 or choice == 0:
            clear()
            print(f"\n  {CYAN}🧬 Thanks for using MacDNA. Your Mac's DNA is safe.{RESET}\n")
            sys.exit(0)
        elif choice == -1:
            # Invalid input, just redraw
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {DIM}Bye!{RESET}\n")
