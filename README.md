# 🧬 MacDNA v3

**Capture your Mac's complete configuration DNA and deploy it to any new machine.**

MacDNA scans your current Mac — preferences, apps, dock layout, dotfiles, security settings, keyboard, fonts, network — and saves everything into a portable profile. Take that profile to a brand new Mac, deploy it, and your setup is restored.

No dependencies. Pure Python. Runs from a USB stick.

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/fjimenez77/MacDNA.git
cd MacDNA

# Run it
python3 macdna.py
```

That's it. You get an interactive menu:

```
╔══════════════════════════════════════════════╗
║        🧬  M a c D N A   v 3                ║
║   Capture  -  Deploy  -  Clone Your Mac      ║
╠══════════════════════════════════════════════╣
║  Author: cyberspartan77  |  v3.0  |  2026    ║
╚══════════════════════════════════════════════╝

─── MAIN MENU ────────────────────────────────

  1  Capture This Mac
  2  Deploy to This Mac
  3  View Profile
  4  Compare Profiles
  5  Delete Profile
  6  Settings
  7  Exit MacDNA
```

## What It Captures

| Category | What's Grabbed |
|----------|---------------|
| **Machine Identity** | Hostname, macOS version, chip type, serial |
| **System Preferences** | Dark mode, Finder settings, trackpad, mouse, screenshots |
| **Dock** | All dock apps, position, size, autohide, magnification |
| **Applications** | Homebrew formulae & casks, Mac App Store apps, all /Applications |
| **Keyboard & Input** | Key repeat, hot corners, auto-correct, smart quotes |
| **Security** | FileVault, firewall, Gatekeeper, SIP, screen lock |
| **Shell & Dotfiles** | .zshrc, .bashrc, .gitconfig, .vimrc, PATH, oh-my-zsh detection |
| **Login Items** | Login apps + LaunchAgents |
| **Fonts** | User-installed fonts in ~/Library/Fonts |
| **Network** | DNS servers, custom /etc/hosts entries |

## Output

Each capture creates a folder with two files:

```
profiles/
  CyberSpartan77s_MacBook_Pro_2026-03-17/
    profile.json    ← machine-readable, used for deploy
    profile.html    ← interactive browser viewer
```

### HTML Viewer
The HTML report is a dark-themed, searchable, expandable viewer you can open in any browser — no server needed. It shows:
- Stats dashboard (app count, formulae, casks, dock apps, dotfiles, fonts)
- Collapsible sections for every category
- Color-coded tags for apps, casks, dock items
- Syntax-highlighted dotfile contents
- Full raw JSON toggle
- Search bar to find any setting

## Deploy

Pick a saved profile → select which categories to apply → dry-run or live.

- **Dry Run** — previews every change, touches nothing
- **Apply** — writes settings via `defaults write`, installs apps via `brew`/`mas`, restores dotfiles
- **Auto-backup** — existing dotfiles are backed up to `~/.macdna_backup/` before overwrite
- **Idempotent** — skips already-installed apps
- **Confirmation** — requires typing `YES` before any changes

## Settings

Configurable via the in-app Settings menu (option 6):

| Setting | Default |
|---------|---------|
| Profile save location | `./profiles/` |
| Backup directory | `~/.macdna_backup/` |
| Auto-backup before deploy | ON |
| Dry-run by default | OFF |
| Confirm before apply | ON |
| Exclude sensitive dotfiles (.netrc, .npmrc) | ON |
| Auto-name profiles | OFF |
| Compact JSON | OFF |
| Color output | ON |
| Default capture categories | All |

Settings persist in `settings.json`.

## Security

- **Never captures** passwords, tokens, SSH keys, keychains, or credentials
- **Sensitive dotfiles** (.netrc, .npmrc, .pypirc) excluded by default
- **Profiles stay local** — .gitignore excludes them from version control
- **Capture is read-only** — safe to run anytime
- **Deploy is cautious** — confirmation required, dry-run available

## Requirements

- macOS 12+ (Monterey through Sequoia)
- Python 3 (pre-installed on macOS)
- Apple Silicon or Intel
- Optional: [Homebrew](https://brew.sh) (for app install/restore)
- Optional: [mas](https://github.com/mas-cli/mas) (for App Store app capture)

## Author

**cyberspartan77** — [github.com/fjimenez77](https://github.com/fjimenez77)

## License

MIT
