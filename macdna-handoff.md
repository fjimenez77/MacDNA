# 🧬 MacDNA — Full Project Briefing
### Context handoff from Claude.ai → Claude Code
### Date: March 9, 2026

---

## WHO I AM & WHAT I WANT

I'm a Mac user who switches machines every 1-2 years and is tired of 
manually recreating my setup every time. I also manage others who face 
the same problem.

I want a tool called **MacDNA** that:
- Captures a Mac's complete setup (every preference, app, setting)
- Saves it as a portable profile file
- Can deploy that profile to any new Mac and mirror the original

I want this as a real CLI tool — not a GUI, not a website — something 
I can keep on a USB drive forever and run with one command.

---

## WHAT WE'VE ALREADY BUILT (in Claude.ai chat)

We've built two versions of MacDNA as static shell scripts. 
These are reference — not the final product. They show the direction.

### Version 1 — Static Setup Scripts
A folder of modular shell scripts with a README.
- `run.sh` — entry point, runs everything in order
- `modules/01_homebrew.sh` — installs Homebrew
- `modules/02_apps.sh` — installs a hardcoded list of apps
- `modules/03_macos_defaults.sh` — applies hardcoded system preferences
- `modules/04_dock.sh` — builds a hardcoded dock
- `modules/05_cleanup.sh` — removes Apple bloatware
**Problem with v1:** Everything is hardcoded. Not personalized.

### Version 2 — Interactive Wizard
Same concept but with a full terminal UI and interactive menus.
- `run.sh` — opens a menu, lets user choose which modules to run
- `lib/ui.sh` — UI library: colors, menus, checklists, spinners, prompts
- `modules/01_system_prefs.sh` — asks questions, sets preferences interactively
- `modules/02_account.sh` — computer name, profile photo, Apple ID prompt
- `modules/03_security.sh` — FileVault, firewall, screen lock, privacy
- `modules/04_shortcuts.sh` — hot corners picker, shortcut reference sheet
- `modules/05_apps.sh` — checklist of apps by category, installs selected ones
- `modules/06_dock.sh` — dock position, size, magnification, app picker
- `modules/07_cleanup.sh` — checklist of bloatware to remove

**Problem with v2:** Still asks questions instead of reading your actual Mac.
The app checklist is a fixed list of common apps — not YOUR apps.

### What We Want in Version 3
Instead of asking questions or using hardcoded lists — READ THE MAC.
Crawl everything. Capture it. Save it. Deploy it elsewhere.

---

## THE CORE CONCEPT — CAPTURE & DEPLOY

### TWO MODES

**CAPTURE MODE** — run on your existing/source Mac
- Crawls the entire system silently
- Reads every preference, every installed app, every setting
- Outputs a single human-readable JSON "profile" file
- Example: `macdna capture` → saves `macbook-pro-2026-03-09.json`

**DEPLOY MODE** — run on a new/target Mac
- You copy the profile JSON to the new machine
- Run: `macdna deploy my-profile.json`
- It shows a summary of what it found in the profile
- You choose via checklist what to apply
- It installs apps, applies settings, rebuilds dock, restores shell config
- Generates a final report of what worked / what needs manual steps

### THE USE CASES

1. **New Mac setup** — run capture on old Mac, deploy on new Mac
2. **Team setup** — capture the "gold standard" Mac, deploy to everyone's machines
3. **Backup your setup** — capture periodically so you can always roll back
4. **Compare two Macs** — diff two profiles to see what's different
5. **Document your setup** — the JSON is human-readable, put it in GitHub

---

## WHAT CAPTURE MUST READ

### 1. System Identity
- Computer name, hostname, local hostname
- macOS version + build number
- Chip type (Apple Silicon vs Intel)
- Current username
- Timezone, language, region, date/time format
- Capture timestamp

### 2. All macOS Defaults Domains
Read these fully using `defaults export <domain> -`:
- NSGlobalDomain (global settings — dark mode, font size, etc.)
- com.apple.dock
- com.apple.finder
- com.apple.screencapture
- com.apple.screensaver
- com.apple.menuextra.clock
- com.apple.menuextra.battery
- com.apple.AppleMultitouchTrackpad
- com.apple.driver.AppleBluetoothMultitouch.trackpad
- com.apple.mouse
- com.apple.keyboard
- com.apple.universalaccess
- com.apple.LaunchServices
- com.apple.loginwindow
- com.apple.WindowManager
- com.apple.spaces

### 3. Installed Apps
- Homebrew casks: `brew list --cask`
- Homebrew formulae: `brew list --formula`
- Mac App Store apps: `mas list` (install mas first if needed)
- Apps in /Applications not from Homebrew (name + bundle ID)
- Apps in ~/Applications
- Brewfile: `brew bundle dump --file=-`
- Developer tools: node version, python version, ruby version

### 4. Dock
- Full ordered list of app paths
- Position (bottom/left/right)
- Icon size, magnification on/off, magnification size
- Auto-hide on/off and delay
- Show recent apps on/off
- Minimize animation effect

### 5. Security Settings
- FileVault status: `fdesetup status`
- Firewall: `socketfilterfw --getglobalstate`
- Firewall stealth mode
- Screen lock timing
- Password required after sleep/screensaver
- Gatekeeper: `spctl --status`
- SIP status: `csrutil status`
- Lock screen message text

### 6. Keyboard & Shortcuts
- Key repeat speed and initial delay
- Hot corners (all 4 corners + their actions)
- Modifier key remapping
- Input sources / keyboard layouts

### 7. Shell & Terminal Environment
- Current shell: `echo $SHELL`
- Full contents of: ~/.zshrc, ~/.bashrc, ~/.zprofile, ~/.aliases, ~/.exports
- Current $PATH value
- Detected shell frameworks (oh-my-zsh, prezto, etc.)

### 8. Login Items (apps that launch at startup)
- Via osascript: `tell application "System Events" to get the name of every login item`
- Files in ~/Library/LaunchAgents/
- Files in /Library/LaunchDaemons/ (user-added only)

### 9. Fonts (non-system only)
- Files in ~/Library/Fonts/
- User-added files in /Library/Fonts/

### 10. Network (safe parts only — NO passwords, NO credentials)
- Custom /etc/hosts entries (skip Apple/localhost defaults)
- Preferred DNS server addresses
- Network interface names

---

## PROFILE JSON SCHEMA

The capture output is a single pretty-printed JSON file:

```json
{
  "meta": {
    "version": "1.0",
    "captured_at": "2026-03-09T10:30:00Z",
    "macdna_version": "3.0",
    "source": {
      "computer_name": "Johns MacBook Pro",
      "hostname": "Johns-MacBook-Pro",
      "macos_version": "15.2",
      "macos_name": "Sequoia",
      "chip": "Apple Silicon",
      "user": "john"
    }
  },
  "system": {
    "NSGlobalDomain": { ... all keys from defaults export ... },
    "dock": { ... },
    "finder": { ... },
    "screencapture": { ... },
    "keyboard": { ... },
    "trackpad": { ... }
  },
  "apps": {
    "homebrew_casks": ["google-chrome", "1password", "claude", ...],
    "homebrew_formulae": ["git", "node", "mas", ...],
    "brewfile": "cask 'google-chrome'\ncask '1password'\n...",
    "app_store": [
      { "id": "1333542190", "name": "1Password 7", "version": "7.x" }
    ],
    "manual_installs": [
      { "name": "Xcode", "bundle_id": "com.apple.dt.Xcode", "path": "/Applications/Xcode.app" }
    ],
    "developer_tools": {
      "node": "20.11.0",
      "python": "3.12.1",
      "ruby": "3.3.0",
      "xcode_cli": true
    }
  },
  "dock": {
    "position": "bottom",
    "size": 48,
    "magnification": true,
    "magnification_size": 70,
    "autohide": false,
    "autohide_delay": 0,
    "show_recents": false,
    "minimize_effect": "genie",
    "apps": [
      "/Applications/Finder.app",
      "/Applications/Google Chrome.app",
      "/Applications/Claude.app"
    ]
  },
  "security": {
    "filevault": "FileVault is On.",
    "firewall_enabled": true,
    "firewall_stealth": true,
    "screen_lock_delay": 0,
    "gatekeeper": "assessments enabled",
    "lock_screen_message": "If found call: 555-1234"
  },
  "keyboard": {
    "key_repeat": 2,
    "initial_key_repeat": 15,
    "hot_corners": {
      "top_left": 2,
      "top_right": 12,
      "bottom_left": 11,
      "bottom_right": 13
    }
  },
  "shell": {
    "current_shell": "/bin/zsh",
    "zshrc": "# full contents of .zshrc ...",
    "zprofile": "# full contents of .zprofile ...",
    "path": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
    "frameworks": ["oh-my-zsh"]
  },
  "login_items": ["Raycast", "1Password", "Dropbox"],
  "fonts": {
    "user_fonts": ["JetBrainsMono-Regular.ttf", "FiraCode-Retina.ttf"],
    "library_fonts": []
  },
  "network": {
    "custom_hosts": ["127.0.0.1 mydevsite.local"],
    "dns_servers": ["1.1.1.1", "8.8.8.8"]
  }
}
```

---

## DEPLOY — HOW IT WORKS

### Step 1: Parse & Preview
Read the profile JSON and display a summary:
```
  Source: Johns MacBook Pro  (macOS 15.2 Sequoia, Apple Silicon)
  Captured: March 9, 2026

  Found:
  ✓  143 system settings
  ✓   34 Homebrew apps + 8 App Store apps
  ✓   12 Dock apps
  ✓    6 security settings
  ✓    4 hot corners + key repeat config
  ✓   .zshrc, .zprofile
  ✓    3 custom hosts entries
  ⚠    5 apps not on Homebrew — manual install links will be provided
```

### Step 2: Checklist — choose what to apply
```
  [✓] System Preferences   (143 settings)
  [✓] Install Apps          (34 Homebrew, 8 App Store)
  [✓] Dock Layout           (12 apps)
  [✓] Security Settings     (6 settings)
  [✓] Keyboard & Shortcuts  (key repeat, 4 hot corners)
  [✓] Shell Config          (.zshrc, .zprofile)
  [ ] Login Items           (review manually — recommended)
  [ ] Fonts                 (12 custom fonts)
  [ ] Network/Hosts         (3 custom entries)
```

### Step 3: Dry Run option
`--dry-run` flag → print every command that WOULD run, don't execute

### Step 4: Execute
Apply each selected category. For conflicts (e.g. existing .zshrc):
- Ask: overwrite / append / skip
- Always back up originals first (.zshrc → .zshrc.bak)

### Step 5: Final Report
Terminal output + saves markdown to ~/Desktop/macdna-deploy-report.md:
```
  ✅ Applied:   143 system settings
  ✅ Installed:  34 Homebrew apps
  ✅ Rebuilt:    Dock with 12 apps
  ✅ Restored:  .zshrc, .zprofile
  ⚠  Skipped:    8 App Store apps (sign in to App Store first)
  ⚠  Manual:     3 apps not on Homebrew (links below)
  ❌ Failed:     1 setting (details below)

  → Restart Mac to apply all changes.
```

---

## FILE STRUCTURE FOR V3

```
macdna/
├── macdna.sh                  ← Main CLI entry point
├── lib/
│   ├── ui.sh                   ← Terminal UI (colors, menus, spinners)
│   ├── capture.sh              ← Orchestrates all capture modules
│   ├── deploy.sh               ← Orchestrates all deploy modules
│   └── utils.sh                ← Shared helper functions
├── capture/
│   ├── system.sh               ← macOS defaults, hostname, timezone
│   ├── apps.sh                 ← Homebrew, App Store, manual apps
│   ├── dock.sh                 ← Dock layout and settings
│   ├── security.sh             ← FileVault, firewall, screen lock
│   ├── shortcuts.sh            ← Hot corners, keyboard shortcuts
│   ├── shell.sh                ← .zshrc, .zprofile, PATH, frameworks
│   ├── fonts.sh                ← Non-system fonts
│   ├── network.sh              ← Hosts file, DNS (no passwords)
│   └── login_items.sh          ← Startup items
├── deploy/
│   ├── system.sh               ← Apply defaults writes
│   ├── apps.sh                 ← brew install + mas install
│   ├── dock.sh                 ← Rebuild dock from profile
│   ├── security.sh             ← Apply security settings
│   ├── shortcuts.sh            ← Apply hot corners + shortcuts
│   ├── shell.sh                ← Restore shell config with backup
│   └── report.sh               ← Generate final deploy report
├── profiles/                   ← Where captured profiles are saved
└── README.md
```

---

## CLI INTERFACE

```bash
macdna                              # Interactive main menu
macdna capture                      # Run capture, save to profiles/
macdna capture --output ~/my.json   # Save to custom path
macdna deploy profile.json          # Deploy with interactive checklist
macdna deploy profile.json --dry-run  # Preview only, run nothing
macdna diff profile1.json profile2.json  # Compare two profiles
macdna edit profile.json            # Interactively edit a profile
```

---

## TERMINAL UI — WHAT WE ALREADY HAVE IN V2

The lib/ui.sh we already built has these functions — replicate and expand:
- `dna_header` — clears screen and shows the MacDNA banner
- `dna_section` — prints a colored section title bar
- `dna_ok / dna_warn / dna_info / dna_skip` — status line helpers
- `dna_ask` — yes/no prompt with default
- `dna_input` — text input with default value
- `dna_menu` — numbered single-choice menu, sets $MENU_CHOICE
- `dna_checklist` — multi-select toggle list, returns $CHECKLIST_SELECTED array
- `dna_progress` — progress bar (current/total)
- `dna_spinner` — animated spinner while a background process runs
- `dna_summary` — bordered summary box
- `dna_pause` — "press enter to continue"

---

## WHAT THE APPS CHECKLIST LOOKED LIKE IN V2
(for reference — v3 doesn't use this, it reads the actual Mac instead)

Categories we had:
- Browsers: Chrome, Firefox, Brave, Arc, Safari
- AI Tools: Claude, ChatGPT, Perplexity, Ollama
- Security: 1Password, Bitwarden, Little Snitch, Malwarebytes
- Productivity: Raycast, Rectangle, Notion, Obsidian, Fantastical, Things, Bear
- Communication: Slack, Discord, Zoom, WhatsApp, Telegram
- Media: Spotify, VLC, IINA, Plex
- Dev Tools: VS Code, Cursor, iTerm2, Docker, Postman, TablePlus, Warp
- Utilities: AppCleaner, The Unarchiver, CleanMyMac, Bartender, Amphetamine

---

## QUALITY REQUIREMENTS

1. Works on macOS 12 Monterey through 15 Sequoia
2. Works on Apple Silicon AND Intel
3. NEVER captures passwords, private keys, tokens, or credentials
4. Every destructive operation (overwrite, delete) asks for confirmation
5. Shell files always backed up before overwrite (.zshrc → .zshrc.bak)
6. Errors are caught, logged, never crash silently
7. Profile JSON is pretty-printed and human-readable
8. Safe to run capture multiple times (non-destructive, just reads)
9. Safe to re-run deploy (skips already-installed apps, etc.)

---

## WHAT I WANT YOU TO DO IN CLAUDE CODE

**Do not run anything yet.** 

First, read all of this and confirm you understand the full scope.
Then lay out your build plan — the exact order you'll build each file,
and what you'll test after each one.

Once I approve the plan, we'll start building file by file.

We are building MacDNA v3 from scratch in this folder.
Everything described above is the spec. Ask me anything you're unclear on
before we start writing code.
