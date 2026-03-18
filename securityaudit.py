#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════╗
║     MacDNA — Security & Asset Audit Engine   ║
║     Author: cyberspartan77  |  v3.0  |  2026 ║
╚══════════════════════════════════════════════╝
"""

import subprocess
import json
import os
import sys
import re
import platform
import datetime
import hashlib
import getpass
import plistlib
import glob as globmod
from pathlib import Path

# ═══════════════════════════════════════════════
#  TERMINAL UI (mirrors macdna.py)
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


def _run(cmd, shell=True, timeout=30):
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _run_lines(cmd, timeout=30):
    return [l for l in _run(cmd, timeout=timeout).splitlines() if l.strip()]


def spinner_line(msg):
    sys.stdout.write(f"\r  {YELLOW}~{RESET} {msg}...")
    sys.stdout.flush()


def spinner_done(msg):
    print(f"\r  {GREEN}+{RESET}  {msg}        ")


def spinner_fail(msg, err=""):
    e = f" -- {err}" if err else ""
    print(f"\r  {RED}x{RESET}  {msg}{e}        ")


# ═══════════════════════════════════════════════
#  SECTION 1: ASSET INTELLIGENCE
# ═══════════════════════════════════════════════

def audit_asset_intelligence():
    spinner_line("Asset Intelligence — Hardware")
    data = {}

    # CPU
    data["cpu"] = {
        "model": _run("sysctl -n machdep.cpu.brand_string"),
        "cores_physical": _run("sysctl -n hw.physicalcpu"),
        "cores_logical": _run("sysctl -n hw.logicalcpu"),
        "architecture": _run("uname -m"),
    }

    # RAM
    mem_bytes = _run("sysctl -n hw.memsize")
    try:
        data["ram_gb"] = round(int(mem_bytes) / (1024**3), 1)
    except (ValueError, TypeError):
        data["ram_gb"] = mem_bytes

    # GPU
    gpu_raw = _run("system_profiler SPDisplaysDataType 2>/dev/null")
    gpus = []
    current_gpu = {}
    for line in gpu_raw.splitlines():
        line = line.strip()
        if line.startswith("Chipset Model:"):
            if current_gpu:
                gpus.append(current_gpu)
            current_gpu = {"model": line.split(":", 1)[1].strip()}
        elif line.startswith("VRAM") and current_gpu:
            current_gpu["vram"] = line.split(":", 1)[1].strip()
        elif line.startswith("Metal Support:") and current_gpu:
            current_gpu["metal"] = line.split(":", 1)[1].strip()
    if current_gpu:
        gpus.append(current_gpu)
    data["gpu"] = gpus

    # Storage volumes
    spinner_line("Asset Intelligence — Storage")
    volumes = []
    diskutil_raw = _run("diskutil list -plist 2>/dev/null")
    # Simpler approach: parse diskutil info for mounted volumes
    df_lines = _run_lines("df -h")
    for line in df_lines[1:]:  # skip header
        # Use regex to handle mount points with spaces:
        # /dev/diskXsY  SIZE  USED  AVAIL  CAP%  /mount point
        m = re.match(r'^(/dev/\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+%)\s+(.+)$', line)
        if m:
            volumes.append({
                "device": m.group(1),
                "size": m.group(2),
                "used": m.group(3),
                "available": m.group(4),
                "use_percent": m.group(5),
                "mount": m.group(6),
            })

    # FileVault / encryption
    fv_status = _run("fdesetup status 2>/dev/null")
    data["storage"] = {
        "volumes": volumes,
        "filevault": "On" in fv_status,
        "apfs": "apfs" in _run("diskutil info / 2>/dev/null").lower(),
    }

    # Battery
    spinner_line("Asset Intelligence — Battery")
    batt_raw = _run("system_profiler SPPowerDataType 2>/dev/null")
    battery = {}
    for line in batt_raw.splitlines():
        line = line.strip()
        if "Cycle Count:" in line:
            battery["cycle_count"] = line.split(":", 1)[1].strip()
        elif "Condition:" in line:
            battery["condition"] = line.split(":", 1)[1].strip()
        elif "Maximum Capacity:" in line:
            battery["max_capacity"] = line.split(":", 1)[1].strip()
        elif "Fully Charged:" in line:
            battery["fully_charged"] = line.split(":", 1)[1].strip()
    data["battery"] = battery

    # Display
    spinner_line("Asset Intelligence — Displays")
    displays = []
    disp_raw = _run("system_profiler SPDisplaysDataType 2>/dev/null")
    current_disp = {}
    for line in disp_raw.splitlines():
        line = line.strip()
        if "Resolution:" in line:
            current_disp["resolution"] = line.split(":", 1)[1].strip()
        elif "Display Type:" in line:
            current_disp["type"] = line.split(":", 1)[1].strip()
        elif "Main Display:" in line:
            current_disp["main"] = "Yes" in line
            displays.append(current_disp)
            current_disp = {}
    if current_disp:
        displays.append(current_disp)
    data["displays"] = displays

    # USB devices
    spinner_line("Asset Intelligence — USB/Thunderbolt")
    usb_raw = _run("system_profiler SPUSBDataType 2>/dev/null")
    usb_devices = []
    for line in usb_raw.splitlines():
        line = line.strip()
        if line.endswith(":") and not line.startswith("USB") and "Hub" not in line:
            name = line.rstrip(":")
            if name and len(name) > 2:
                usb_devices.append(name)
    data["usb_devices"] = usb_devices

    # Thunderbolt
    tb_raw = _run("system_profiler SPThunderboltDataType 2>/dev/null")
    tb_devices = []
    for line in tb_raw.splitlines():
        line = line.strip()
        if "Device Name:" in line:
            tb_devices.append(line.split(":", 1)[1].strip())
    data["thunderbolt_devices"] = tb_devices

    # Bluetooth
    spinner_line("Asset Intelligence — Bluetooth")
    bt_raw = _run("system_profiler SPBluetoothDataType 2>/dev/null")
    bt_devices = []
    in_devices = False
    for line in bt_raw.splitlines():
        stripped = line.strip()
        if "Connected:" in stripped or "Paired:" in stripped:
            continue
        if stripped.endswith(":") and len(stripped) > 3 and "Bluetooth" not in stripped and "Apple" not in stripped:
            name = stripped.rstrip(":")
            if name and not name.startswith("Address") and not name.startswith("Firmware"):
                bt_devices.append(name)
    data["bluetooth_devices"] = list(set(bt_devices))

    # Printers
    printers = _run_lines("lpstat -p 2>/dev/null")
    printer_names = []
    for line in printers:
        if line.startswith("printer"):
            parts = line.split()
            if len(parts) >= 2:
                printer_names.append(parts[1])
    data["printers"] = printer_names

    # Identity
    data["serial"] = _run("system_profiler SPHardwareDataType | awk '/Serial Number/{print $NF}'")
    data["model_id"] = _run("sysctl -n hw.model")
    # Try ioreg for Intel Macs, fall back to sysctl for Apple Silicon
    _board = _run("ioreg -d2 -c IOPlatformExpertDevice | awk -F'\"' '/board-id/{print $4}'")
    if not _board:
        _board = _run("sysctl -n hw.target 2>/dev/null")
    data["board_id"] = _board if _board else "Unknown"
    data["hostname"] = _run("scutil --get ComputerName")
    data["macos_version"] = platform.mac_ver()[0]
    data["build"] = _run("sw_vers -buildVersion")

    spinner_done("Asset Intelligence")
    return data


# ═══════════════════════════════════════════════
#  SECTION 2: USER ACCOUNTS & ACCESS
# ═══════════════════════════════════════════════

def audit_user_accounts():
    spinner_line("User Accounts & Access")
    data = {}

    # All local users
    users = []
    raw_users = _run_lines("dscl . list /Users | grep -v '^_'")
    for username in raw_users:
        username = username.strip()
        if not username or username == "daemon" or username == "nobody":
            continue
        user_info = {
            "username": username,
            "uid": _run(f"dscl . -read /Users/{username} UniqueID 2>/dev/null | awk '{{print $2}}'"),
            "gid": _run(f"dscl . -read /Users/{username} PrimaryGroupID 2>/dev/null | awk '{{print $2}}'"),
            "home": _run(f"dscl . -read /Users/{username} NFSHomeDirectory 2>/dev/null | awk '{{print $2}}'"),
            "shell": _run(f"dscl . -read /Users/{username} UserShell 2>/dev/null | awk '{{print $2}}'"),
            "admin": username in _run("dscl . -read /Groups/admin GroupMembership 2>/dev/null").replace("GroupMembership:", "").strip().split(),
            "hidden": _run(f"dscl . -read /Users/{username} IsHidden 2>/dev/null | awk '{{print $2}}'") == "1",
        }
        # Last login
        last_raw = _run(f"last -1 {username} 2>/dev/null | head -1")
        user_info["last_login"] = last_raw if last_raw and username in last_raw else "Never/Unknown"
        users.append(user_info)
    data["local_users"] = users

    # Hidden accounts check
    data["hidden_accounts"] = [u for u in users if u.get("hidden")]

    # Sudoers
    spinner_line("User Accounts — Sudoers")
    sudoers_content = _run("cat /etc/sudoers 2>/dev/null")
    sudoers_d = _run_lines("ls /etc/sudoers.d/ 2>/dev/null")
    sudoers_custom = {}
    for f in sudoers_d:
        f = f.strip()
        if f and not f.startswith("."):
            content = _run(f"cat /etc/sudoers.d/{f} 2>/dev/null")
            if content:
                sudoers_custom[f] = content
    data["sudoers"] = {
        "main_file_lines": len(sudoers_content.splitlines()) if sudoers_content else 0,
        "custom_rules_files": sudoers_d,
        "custom_rules": sudoers_custom,
        "admin_group_members": _run("dscl . -read /Groups/admin GroupMembership 2>/dev/null").replace("GroupMembership:", "").strip().split(),
    }

    # SSH
    spinner_line("User Accounts — SSH")
    home = str(Path.home())
    ssh_dir = os.path.join(home, ".ssh")
    ssh_data = {
        "sshd_running": "sshd" in _run("launchctl list 2>/dev/null | grep ssh"),
        "remote_login": "enabled" if _run("launchctl list com.openssh.sshd 2>/dev/null") else "disabled",
    }

    # SSH config hosts
    ssh_config = os.path.join(ssh_dir, "config")
    if os.path.isfile(ssh_config):
        hosts = []
        try:
            with open(ssh_config) as f:
                for line in f:
                    line = line.strip()
                    if line.lower().startswith("host ") and "*" not in line:
                        hosts.append(line.split(None, 1)[1])
        except Exception:
            pass
        ssh_data["config_hosts"] = hosts
    else:
        ssh_data["config_hosts"] = []

    # Authorized keys
    auth_keys = os.path.join(ssh_dir, "authorized_keys")
    if os.path.isfile(auth_keys):
        try:
            with open(auth_keys) as f:
                keys = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            ssh_data["authorized_keys_count"] = len(keys)
            # Show just the comment/type for each key
            ssh_data["authorized_keys"] = []
            for k in keys:
                parts = k.split()
                if len(parts) >= 3:
                    ssh_data["authorized_keys"].append(f"{parts[0]} ...{parts[-1]}")
                elif len(parts) >= 1:
                    ssh_data["authorized_keys"].append(parts[0][:30])
        except Exception:
            ssh_data["authorized_keys_count"] = 0
    else:
        ssh_data["authorized_keys_count"] = 0

    # Known hosts count
    known_hosts = os.path.join(ssh_dir, "known_hosts")
    if os.path.isfile(known_hosts):
        try:
            with open(known_hosts) as f:
                ssh_data["known_hosts_count"] = sum(1 for l in f if l.strip() and not l.startswith("#"))
        except Exception:
            ssh_data["known_hosts_count"] = 0
    else:
        ssh_data["known_hosts_count"] = 0

    data["ssh"] = ssh_data
    spinner_done("User Accounts & Access")
    return data


# ═══════════════════════════════════════════════
#  SECTION 3: CERTIFICATES
# ═══════════════════════════════════════════════

def audit_certificates():
    spinner_line("Certificates — Scanning Keychains")
    data = {"system_certs": [], "expiring_30d": [], "expiring_60d": [], "expiring_90d": [], "expired": [], "self_signed": []}

    now = datetime.datetime.now()
    d30 = now + datetime.timedelta(days=30)
    d60 = now + datetime.timedelta(days=60)
    d90 = now + datetime.timedelta(days=90)

    # Get all certs from system keychain
    raw = _run("security find-certificate -a -p /Library/Keychains/System.keychain 2>/dev/null", timeout=60)
    if not raw:
        spinner_done("Certificates (no system keychain access)")
        return data

    # Split into individual PEM certs
    certs_pem = re.findall(r'(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)', raw, re.DOTALL)

    for i, pem in enumerate(certs_pem):
        cert_info = _parse_cert_pem(pem)
        if cert_info:
            data["system_certs"].append(cert_info)

            # Check expiry
            expiry = cert_info.get("not_after_dt")
            if expiry:
                if expiry < now:
                    data["expired"].append(cert_info)
                elif expiry < d30:
                    data["expiring_30d"].append(cert_info)
                elif expiry < d60:
                    data["expiring_60d"].append(cert_info)
                elif expiry < d90:
                    data["expiring_90d"].append(cert_info)

            if cert_info.get("self_signed"):
                data["self_signed"].append(cert_info)

        if i % 20 == 0:
            spinner_line(f"Certificates — {i}/{len(certs_pem)}")

    data["total_certs"] = len(data["system_certs"])
    spinner_done(f"Certificates — {len(data['system_certs'])} found")
    return data


def _parse_cert_pem(pem):
    """Parse a single PEM certificate using openssl."""
    try:
        proc = subprocess.run(
            ["openssl", "x509", "-noout", "-subject", "-issuer", "-dates", "-fingerprint"],
            input=pem, capture_output=True, text=True, timeout=10
        )
        if proc.returncode != 0:
            return None

        info = {}
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("subject="):
                info["subject"] = line.split("=", 1)[1].strip()
            elif line.startswith("issuer="):
                info["issuer"] = line.split("=", 1)[1].strip()
            elif line.startswith("notBefore="):
                info["not_before"] = line.split("=", 1)[1].strip()
            elif line.startswith("notAfter="):
                raw_date = line.split("=", 1)[1].strip()
                info["not_after"] = raw_date
                # Parse date
                for fmt in ["%b %d %H:%M:%S %Y %Z", "%b  %d %H:%M:%S %Y %Z"]:
                    try:
                        info["not_after_dt"] = datetime.datetime.strptime(raw_date, fmt)
                        break
                    except ValueError:
                        continue
            elif "Fingerprint=" in line:
                info["fingerprint"] = line.split("=", 1)[1].strip()

        info["self_signed"] = info.get("subject", "") == info.get("issuer", "") and info.get("subject", "") != ""
        return info
    except Exception:
        return None


# ═══════════════════════════════════════════════
#  SECTION 4: NETWORK & CONNECTIONS
# ═══════════════════════════════════════════════

def audit_network():
    spinner_line("Network — Listening Ports")
    data = {}

    # Listening TCP ports
    listening = []
    lsof_lines = _run_lines("lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null")
    for line in lsof_lines[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 9:
            listening.append({
                "process": parts[0],
                "pid": parts[1],
                "user": parts[2],
                "address": parts[8],
            })
    data["listening_tcp"] = listening

    # Established connections
    spinner_line("Network — Active Connections")
    established = []
    est_lines = _run_lines("lsof -iTCP -sTCP:ESTABLISHED -P -n 2>/dev/null")
    for line in est_lines[1:]:
        parts = line.split()
        if len(parts) >= 9:
            established.append({
                "process": parts[0],
                "pid": parts[1],
                "user": parts[2],
                "connection": parts[8],
            })
    data["established_tcp"] = established

    # UDP listeners
    spinner_line("Network — UDP")
    udp = []
    udp_lines = _run_lines("lsof -iUDP -P -n 2>/dev/null")
    for line in udp_lines[1:]:
        parts = line.split()
        if len(parts) >= 9:
            udp.append({
                "process": parts[0],
                "pid": parts[1],
                "address": parts[8],
            })
    data["udp_listeners"] = udp

    # Network interfaces
    spinner_line("Network — Interfaces")
    interfaces = []
    ifconfig_raw = _run("ifconfig 2>/dev/null")
    current_iface = None
    for line in ifconfig_raw.splitlines():
        if not line.startswith("\t") and ":" in line:
            name = line.split(":")[0]
            current_iface = {"name": name, "ips": [], "mac": "", "status": ""}
            interfaces.append(current_iface)
        elif current_iface:
            line = line.strip()
            if line.startswith("inet "):
                ip = line.split()[1]
                current_iface["ips"].append(ip)
            elif line.startswith("inet6 "):
                ip6 = line.split()[1]
                current_iface["ips"].append(ip6)
            elif line.startswith("ether "):
                current_iface["mac"] = line.split()[1]
            elif line.startswith("status:"):
                current_iface["status"] = line.split(":", 1)[1].strip()
    # Filter to only active/interesting interfaces
    data["interfaces"] = [i for i in interfaces if i.get("ips") or i.get("status") == "active"]

    # VPN tunnels — use scutil for actual VPN connections, supplement with ipsec/ppp interfaces
    vpn_connections = []
    scutil_vpn = _run("scutil --nc list 2>/dev/null")
    if scutil_vpn:
        for vline in scutil_vpn.splitlines():
            vline = vline.strip()
            if vline and ("Connected" in vline or "Connecting" in vline):
                vpn_connections.append({"name": vline, "source": "scutil"})
    # Also include ipsec/ppp interfaces (these are always VPN), and utun only if they have a routable IP
    for i in interfaces:
        if i["name"].startswith(("ipsec", "ppp")):
            vpn_connections.append(i)
        elif i["name"].startswith("utun"):
            # Only include utun interfaces with a routable (non-link-local) IP
            routable_ips = [ip for ip in i.get("ips", []) if not ip.startswith("fe80::")]
            if routable_ips:
                vpn_connections.append(i)
    data["vpn_tunnels"] = vpn_connections

    # Routing table (summary)
    spinner_line("Network — Routes")
    routes = _run_lines("netstat -rn 2>/dev/null | head -30")
    data["routing_table_summary"] = routes

    # Sharing services
    spinner_line("Network — Sharing Services")
    sharing = {}
    sharing["file_sharing"] = "running" in _run("launchctl list com.apple.smbd 2>/dev/null").lower() or _run("sharing -l 2>/dev/null") != ""
    sharing["screen_sharing"] = _run("defaults read /var/db/launchd.db/com.apple.launchd/overrides.plist com.apple.screensharing 2>/dev/null") != ""
    sharing["remote_login"] = bool(_run("launchctl list com.openssh.sshd 2>/dev/null"))
    sharing["remote_management"] = "running" in _run("launchctl list com.apple.ARDAgent 2>/dev/null").lower()
    sharing["printer_sharing"] = "is shared" in _run("cupsctl 2>/dev/null").lower()
    sharing["bluetooth_sharing"] = _run("defaults read /Library/Preferences/com.apple.Bluetooth PrefKeyServicesEnabled 2>/dev/null") == "1"
    data["sharing_services"] = sharing

    spinner_done("Network & Connections")
    return data


# ═══════════════════════════════════════════════
#  SECTION 5: DOMAIN & MANAGEMENT
# ═══════════════════════════════════════════════

def audit_domain_management():
    spinner_line("Domain & Management")
    data = {}

    # Active Directory
    ad_info = _run("dsconfigad -show 2>/dev/null")
    data["active_directory"] = {
        "bound": bool(ad_info),
        "details": ad_info if ad_info else "Not bound to Active Directory",
    }

    # LDAP
    ldap_raw = _run("ldapsearch -x -H ldap://localhost -b '' -s base 2>/dev/null")
    data["ldap"] = {
        "configured": bool(ldap_raw and "result" in ldap_raw.lower()),
        "details": ldap_raw[:500] if ldap_raw else "No LDAP configuration detected",
    }

    # MDM enrollment
    mdm_profiles = _run("profiles status -type enrollment 2>/dev/null")
    data["mdm"] = {
        "enrolled": "MDM enrollment" in mdm_profiles.lower() or "Yes" in mdm_profiles,
        "details": mdm_profiles if mdm_profiles else "Not enrolled in MDM",
    }

    # Configuration profiles
    spinner_line("Domain & Management — Profiles")
    config_profiles = _run("profiles list -output stdout-xml 2>/dev/null")
    profile_names = []
    if config_profiles:
        # Try to parse plist
        try:
            pdata = plistlib.loads(config_profiles.encode())
            for p in pdata.get("_computerlevel", []):
                profile_names.append({
                    "name": p.get("ProfileDisplayName", "Unknown"),
                    "identifier": p.get("ProfileIdentifier", ""),
                    "organization": p.get("ProfileOrganization", ""),
                })
        except Exception:
            # Fallback to text parsing
            for line in config_profiles.splitlines():
                if "profileIdentifier" in line.lower() or "displayname" in line.lower():
                    profile_names.append({"raw": line.strip()})
    data["configuration_profiles"] = profile_names

    # Managed preferences
    managed_prefs = _run("mcxquery 2>/dev/null")
    data["managed_preferences"] = managed_prefs if managed_prefs else "None detected"

    spinner_done("Domain & Management")
    return data


# ═══════════════════════════════════════════════
#  SECTION 6: THREAT DETECTION & IOCs
# ═══════════════════════════════════════════════

# Known suspicious process patterns
REVERSE_SHELL_PATTERNS = [
    r"bash\s+-i\s+>&\s+/dev/tcp",
    r"nc\s+-e\s+/bin/(ba)?sh",
    r"ncat.*-e.*sh",
    r"python.*socket.*connect",
    r"ruby.*TCPSocket",
    r"perl.*socket.*INET",
    r"php.*fsockopen",
    r"socat.*TCP",
    r"0<&\d+-",
    r"/dev/tcp/",
]

KNOWN_MALWARE_NAMES = [
    "xmrig", "coinhive", "minerd", "cpuminer", "kworker-", "bioset",
    "cryptonight", "stratum", "kdevtmpfsi", "kinsing", "dovecat",
    "sysrv", "tsunami", "mirai", "gafgyt", "hajime",
    "OSX.Shlayer", "OSX.Bundlore", "OSX.Pirrit",
]

SUSPICIOUS_PORTS = [4444, 5555, 6666, 1337, 31337, 8888, 9999, 12345, 54321, 6667, 6697]


def audit_threat_detection(alert_level="medium"):
    spinner_line("Threat Detection — Process Analysis")
    data = {"findings": [], "severity_counts": {"critical": 0, "warning": 0, "info": 0}}

    # Get running processes
    ps_lines = _run_lines("ps aux 2>/dev/null")

    # 6.1 Reverse shell detection
    for line in ps_lines:
        for pattern in REVERSE_SHELL_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                data["findings"].append({
                    "severity": "critical",
                    "category": "Reverse Shell",
                    "detail": f"Suspicious pattern matched: {line[:120]}",
                })
                data["severity_counts"]["critical"] += 1
                break

    # 6.2 Processes from suspicious directories
    spinner_line("Threat Detection — Suspicious Paths")
    suspicious_dirs = ["/tmp/", "/var/tmp/", "/dev/shm/"]
    for line in ps_lines[1:]:
        parts = line.split()
        if len(parts) >= 11:
            cmd = " ".join(parts[10:])
            for sd in suspicious_dirs:
                if sd in cmd:
                    data["findings"].append({
                        "severity": "warning",
                        "category": "Suspicious Process Path",
                        "detail": f"Process running from {sd}: {cmd[:100]}",
                    })
                    data["severity_counts"]["warning"] += 1
                    break
            # Hidden directory processes
            if "/." in cmd and "/Library" not in cmd and "/.Trash" not in cmd:
                data["findings"].append({
                    "severity": "warning",
                    "category": "Hidden Directory Process",
                    "detail": f"Process from hidden dir: {cmd[:100]}",
                })
                data["severity_counts"]["warning"] += 1

    # 6.3 Unsigned binaries with network access
    spinner_line("Threat Detection — Unsigned Network Binaries")
    net_procs = set()
    for line in _run_lines("lsof -iTCP -P -n 2>/dev/null")[1:]:
        parts = line.split()
        if len(parts) >= 2:
            net_procs.add(parts[1])  # PID

    checked_pids = set()
    for pid in list(net_procs)[:30]:  # limit to avoid slowness
        if pid in checked_pids:
            continue
        checked_pids.add(pid)
        exe_path = _run(f"ps -p {pid} -o comm= 2>/dev/null")
        if exe_path and os.path.isfile(exe_path):
            codesign = _run(f"codesign -v '{exe_path}' 2>&1")
            if "not signed" in codesign.lower() or "invalid" in codesign.lower():
                data["findings"].append({
                    "severity": "warning",
                    "category": "Unsigned Network Binary",
                    "detail": f"PID {pid}: {exe_path}",
                })
                data["severity_counts"]["warning"] += 1

    # 6.4 Crypto miner indicators
    spinner_line("Threat Detection — Crypto Miners")
    for line in ps_lines:
        lower_line = line.lower()
        for miner in ["xmrig", "minerd", "cpuminer", "cryptonight", "stratum+tcp", "coinhive"]:
            if miner in lower_line:
                data["findings"].append({
                    "severity": "critical",
                    "category": "Crypto Miner",
                    "detail": f"Miner indicator: {line[:120]}",
                })
                data["severity_counts"]["critical"] += 1
                break

    # 6.5 Known malware process names
    for line in ps_lines:
        lower_line = line.lower()
        for mal in KNOWN_MALWARE_NAMES:
            if mal.lower() in lower_line:
                data["findings"].append({
                    "severity": "critical",
                    "category": "Known Malware",
                    "detail": f"Matched '{mal}': {line[:120]}",
                })
                data["severity_counts"]["critical"] += 1
                break

    # 6.6 Non-standard listening ports
    spinner_line("Threat Detection — Suspicious Ports")
    lsof_listen = _run_lines("lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null")
    for line in lsof_listen[1:]:
        for port in SUSPICIOUS_PORTS:
            if f":{port}" in line:
                data["findings"].append({
                    "severity": "warning",
                    "category": "Suspicious Port",
                    "detail": f"Listening on known-bad port {port}: {line[:100]}",
                })
                data["severity_counts"]["warning"] += 1

    # 6.7 Connections to unusual port ranges
    est_lines = _run_lines("lsof -iTCP -sTCP:ESTABLISHED -P -n 2>/dev/null")
    for line in est_lines[1:]:
        match = re.search(r'->[\d.]+:(\d+)', line)
        if match:
            remote_port = int(match.group(1))
            if remote_port > 10000 and remote_port not in [443, 8443, 10443]:
                if alert_level != "low":
                    data["findings"].append({
                        "severity": "info",
                        "category": "High Port Connection",
                        "detail": f"Connection to port {remote_port}: {line[:100]}",
                    })
                    data["severity_counts"]["info"] += 1

    # 6.8 Recently created user accounts (last 30 days)
    spinner_line("Threat Detection — Recent Accounts")
    raw_users = _run_lines("dscl . list /Users | grep -v '^_'")
    for username in raw_users:
        username = username.strip()
        if not username or username in ("daemon", "nobody", "root"):
            continue
        # Check creation date via user record
        created = _run(f"dscl . -read /Users/{username} DateCreated 2>/dev/null")
        if created:
            # If we can parse a date and it's recent, flag it
            data["findings"].append({
                "severity": "info",
                "category": "User Account Audit",
                "detail": f"Account '{username}' — created: {created.replace('DateCreated:', '').strip()[:40]}",
            })

    # 6.9 Cron jobs & at jobs
    spinner_line("Threat Detection — Cron Jobs")
    cron_data = {}
    # Current user crontab
    user_cron = _run("crontab -l 2>/dev/null")
    cron_data["user_crontab"] = user_cron if user_cron else "No user crontab"

    # System cron directories
    cron_dirs = ["/etc/crontab", "/etc/periodic/daily", "/etc/periodic/weekly", "/etc/periodic/monthly"]
    cron_data["system_cron_files"] = {}
    for cdir in cron_dirs:
        if os.path.isfile(cdir):
            cron_data["system_cron_files"][cdir] = _run(f"cat '{cdir}' 2>/dev/null")[:500]
        elif os.path.isdir(cdir):
            cron_data["system_cron_files"][cdir] = os.listdir(cdir)

    # At jobs
    at_jobs = _run("atq 2>/dev/null")
    cron_data["at_jobs"] = at_jobs if at_jobs else "No at jobs"
    data["cron_jobs"] = cron_data

    # 6.10 Unusual LaunchDaemons / LaunchAgents
    spinner_line("Threat Detection — LaunchDaemons")
    launch_findings = []
    for ldir in ["/Library/LaunchDaemons", "/Library/LaunchAgents",
                 os.path.expanduser("~/Library/LaunchAgents")]:
        if os.path.isdir(ldir):
            for f in os.listdir(ldir):
                if f.endswith(".plist"):
                    full = os.path.join(ldir, f)
                    # Check if Apple-signed
                    if not f.startswith("com.apple."):
                        launch_findings.append({
                            "path": full,
                            "name": f,
                            "non_apple": True,
                        })
    data["launch_items"] = launch_findings

    # 6.11 Browser extensions
    spinner_line("Threat Detection — Browser Extensions")
    extensions = {"chrome": [], "firefox": [], "safari": []}

    # Chrome
    chrome_ext_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/Extensions")
    if os.path.isdir(chrome_ext_dir):
        for ext_id in os.listdir(chrome_ext_dir):
            ext_path = os.path.join(chrome_ext_dir, ext_id)
            if os.path.isdir(ext_path):
                # Try to get name from manifest
                name = ext_id
                for version_dir in os.listdir(ext_path):
                    manifest = os.path.join(ext_path, version_dir, "manifest.json")
                    if os.path.isfile(manifest):
                        try:
                            with open(manifest) as mf:
                                mdata = json.load(mf)
                                name = mdata.get("name", ext_id)
                                if name.startswith("__MSG_"):
                                    name = ext_id
                        except Exception:
                            pass
                        break
                extensions["chrome"].append({"id": ext_id, "name": name})

    # Firefox
    ff_profiles = os.path.expanduser("~/Library/Application Support/Firefox/Profiles")
    if os.path.isdir(ff_profiles):
        for prof in os.listdir(ff_profiles):
            ext_json = os.path.join(ff_profiles, prof, "extensions.json")
            if os.path.isfile(ext_json):
                try:
                    with open(ext_json) as f:
                        edata = json.load(f)
                    for addon in edata.get("addons", []):
                        extensions["firefox"].append({
                            "id": addon.get("id", ""),
                            "name": addon.get("defaultLocale", {}).get("name", addon.get("id", "")),
                        })
                except Exception:
                    pass

    # Safari
    safari_ext_dir = os.path.expanduser("~/Library/Safari/Extensions")
    if os.path.isdir(safari_ext_dir):
        for f in os.listdir(safari_ext_dir):
            if f.endswith(".safariextz") or f.endswith(".appex"):
                extensions["safari"].append({"name": f})
    data["browser_extensions"] = extensions

    # 6.12 Environment variable anomalies
    spinner_line("Threat Detection — Environment")
    env_findings = []
    env_vars = os.environ.copy()

    # Check for suspicious env vars
    suspicious_env = ["DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH",
                      "LD_PRELOAD", "LD_LIBRARY_PATH"]
    for var in suspicious_env:
        if var in env_vars:
            env_findings.append({
                "severity": "warning",
                "variable": var,
                "value": env_vars[var],
            })
            data["findings"].append({
                "severity": "warning",
                "category": "Suspicious Environment",
                "detail": f"{var}={env_vars[var][:100]}",
            })
            data["severity_counts"]["warning"] += 1

    # Check PATH for suspicious entries
    path_val = env_vars.get("PATH", "")
    for p in path_val.split(":"):
        if p.startswith("/tmp") or p.startswith("/var/tmp") or "/." in p:
            env_findings.append({
                "severity": "warning",
                "variable": "PATH (suspicious entry)",
                "value": p,
            })
            data["findings"].append({
                "severity": "warning",
                "category": "Suspicious PATH",
                "detail": f"PATH contains: {p}",
            })
            data["severity_counts"]["warning"] += 1

    data["environment_anomalies"] = env_findings

    # 6.13 Recently modified system files (last 7 days)
    spinner_line("Threat Detection — Recent System Modifications")
    recent_mods = []
    system_dirs = ["/usr/local/bin", "/Library/LaunchDaemons", "/Library/LaunchAgents",
                   "/Library/StartupItems", "/etc"]
    for sdir in system_dirs:
        if os.path.isdir(sdir):
            found = _run(f"find '{sdir}' -maxdepth 2 -mtime -7 -type f 2>/dev/null", timeout=15)
            for f in found.splitlines():
                f = f.strip()
                if f:
                    recent_mods.append(f)
    data["recently_modified_system_files"] = recent_mods[:50]  # cap at 50

    spinner_done("Threat Detection & IOCs")
    return data


# ═══════════════════════════════════════════════
#  SECTION 7: EDR / COMPLIANCE POSTURE
# ═══════════════════════════════════════════════

def audit_compliance():
    spinner_line("Compliance — Security Checks")
    checks = []

    def _check(name, cmd, expected, contains=True):
        result = _run(cmd)
        if contains:
            passed = expected.lower() in result.lower() if expected else bool(result)
        else:
            passed = expected.lower() not in result.lower() if expected else not bool(result)
        checks.append({
            "check": name,
            "status": "pass" if passed else "fail",
            "detail": result[:200] if result else "(no output)",
        })
        return passed

    # 7.1 FileVault
    _check("FileVault Encryption", "fdesetup status 2>/dev/null", "FileVault is On")

    # 7.2 SIP
    _check("System Integrity Protection", "csrutil status 2>/dev/null", "enabled")

    # 7.3 Gatekeeper
    _check("Gatekeeper", "spctl --status 2>/dev/null", "assessments enabled")

    # 7.4 Firewall — use socketfilterfw (works on all macOS versions)
    fw_out = _run("/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null")
    fw_on = fw_out and "enabled" in fw_out.lower()
    checks.append({
        "check": "Firewall",
        "status": "pass" if fw_on else "fail",
        "detail": fw_out.strip() if fw_out else "Not configured",
    })

    # Stealth mode — use socketfilterfw
    stealth_out = _run("/usr/libexec/ApplicationFirewall/socketfilterfw --getstealthmode 2>/dev/null")
    stealth_on = stealth_out and "on" in stealth_out.lower()
    checks.append({
        "check": "Firewall Stealth Mode",
        "status": "pass" if stealth_on else "fail",
        "detail": stealth_out.strip() if stealth_out else "Not configured",
    })

    # 7.5 Auto-update
    spinner_line("Compliance — Updates & Policies")
    auto_update = _run("defaults read /Library/Preferences/com.apple.SoftwareUpdate AutomaticCheckEnabled 2>/dev/null")
    checks.append({
        "check": "Automatic Updates",
        "status": "pass" if auto_update == "1" else "fail",
        "detail": "Enabled" if auto_update == "1" else "Disabled or not set",
    })

    # 7.6 Screen lock / password on wake
    pwd_wake = _run("defaults read com.apple.screensaver askForPassword 2>/dev/null")
    checks.append({
        "check": "Password on Wake",
        "status": "pass" if pwd_wake == "1" else "fail",
        "detail": "Required" if pwd_wake == "1" else "Not required",
    })

    pwd_delay = _run("defaults read com.apple.screensaver askForPasswordDelay 2>/dev/null")
    checks.append({
        "check": "Password Delay",
        "status": "pass" if pwd_delay == "0" else "warning",
        "detail": f"{pwd_delay}s delay" if pwd_delay else "Not set (uses default)",
    })

    # 7.7 Remote login (avoid systemsetup which requires sudo)
    remote_ssh = _run("launchctl list com.openssh.sshd 2>/dev/null")
    ssh_enabled = bool(remote_ssh)
    checks.append({
        "check": "Remote Login (SSH)",
        "status": "warning" if ssh_enabled else "pass",
        "detail": "Remote Login: On" if ssh_enabled else "Remote Login: Off",
    })

    # 7.8 Guest account
    guest = _run("defaults read /Library/Preferences/com.apple.loginwindow GuestEnabled 2>/dev/null")
    checks.append({
        "check": "Guest Account",
        "status": "pass" if guest == "0" or not guest else "warning",
        "detail": "Disabled" if guest == "0" or not guest else "Enabled",
    })

    # 7.9 AirDrop
    airdrop = _run("defaults read com.apple.NetworkBrowser DisableAirDrop 2>/dev/null")
    checks.append({
        "check": "AirDrop",
        "status": "pass" if airdrop == "1" else "info",
        "detail": "Disabled" if airdrop == "1" else "Enabled (default)",
    })

    # 7.10 Pending software updates
    spinner_line("Compliance — Software Updates")
    pending = _run("softwareupdate -l 2>&1", timeout=60)
    has_updates = "Software Update found" in pending or "* " in pending
    checks.append({
        "check": "Pending Software Updates",
        "status": "warning" if has_updates else "pass",
        "detail": "Updates available" if has_updates else "Up to date",
    })

    # 7.11 Unsigned kexts
    kexts = _run_lines("kextstat 2>/dev/null | grep -v com.apple")
    checks.append({
        "check": "Third-Party Kernel Extensions",
        "status": "info" if kexts else "pass",
        "detail": f"{len(kexts)} non-Apple kexts loaded" if kexts else "None",
    })

    # 7.12 Hidden admin accounts
    admin_members = _run("dscl . -read /Groups/admin GroupMembership 2>/dev/null").replace("GroupMembership:", "").strip().split()
    all_users = _run_lines("dscl . list /Users | grep -v '^_'")
    hidden_admins = []
    for u in admin_members:
        hidden = _run(f"dscl . -read /Users/{u} IsHidden 2>/dev/null | awk '{{print $2}}'")
        if hidden == "1":
            hidden_admins.append(u)
    checks.append({
        "check": "Hidden Admin Accounts",
        "status": "critical" if hidden_admins else "pass",
        "detail": f"Found: {', '.join(hidden_admins)}" if hidden_admins else "None",
    })

    # 7.13 Time Machine
    spinner_line("Compliance — Time Machine")
    tm_dest = _run("tmutil destinationinfo 2>/dev/null")
    tm_latest = _run("tmutil latestbackup 2>/dev/null")
    checks.append({
        "check": "Time Machine Backup",
        "status": "pass" if tm_latest else "warning",
        "detail": f"Latest: {tm_latest}" if tm_latest else "No backup destination configured",
    })

    # 7.14 Secure boot
    secure_boot = _run("csrutil authenticated-root status 2>/dev/null")
    if not secure_boot:
        secure_boot = _run("bputil -d 2>/dev/null")
    checks.append({
        "check": "Secure Boot",
        "status": "pass" if "enabled" in (secure_boot or "").lower() else "info",
        "detail": secure_boot[:100] if secure_boot else "Unable to determine",
    })

    spinner_done("Compliance Posture")
    return {"checks": checks, "total": len(checks),
            "passed": sum(1 for c in checks if c["status"] == "pass"),
            "failed": sum(1 for c in checks if c["status"] == "fail"),
            "warnings": sum(1 for c in checks if c["status"] == "warning")}


# ═══════════════════════════════════════════════
#  SECTION 8: LOGS & FORENSIC SNAPSHOT
# ═══════════════════════════════════════════════

def audit_logs_forensics():
    spinner_line("Logs & Forensics — Failed Logins")
    data = {}

    # 8.1 Failed login attempts (last 48h) — use /var/log/system.log and last
    failed_logins = _run("grep -i 'authentication failure\\|Failed to authenticate\\|FAILED LOGIN' /var/log/system.log 2>/dev/null | tail -30", timeout=15)
    if not failed_logins:
        # Try unified log for failed auth events (last 48h)
        failed_logins = _run("log show --predicate 'eventMessage CONTAINS \"failed\" AND eventMessage CONTAINS \"auth\"' --style syslog --last 48h 2>/dev/null | tail -20", timeout=30)
    data["failed_logins_48h"] = failed_logins.splitlines() if failed_logins else ["No failed logins detected (48h)"]

    # 8.2 Sudo usage (last 48h) — use /var/log/system.log
    spinner_line("Logs & Forensics — Sudo History")
    sudo_log = _run("grep 'sudo' /var/log/system.log 2>/dev/null | tail -30", timeout=15)
    if not sudo_log:
        sudo_log = _run("grep 'sudo' /var/log/install.log 2>/dev/null | tail -15", timeout=10)
    data["sudo_usage_48h"] = sudo_log.splitlines() if sudo_log else ["None detected"]

    # 8.3 SSH login history
    spinner_line("Logs & Forensics — SSH History")
    ssh_log = _run("last | grep -i ssh | head -20 2>/dev/null")
    data["ssh_history"] = ssh_log.splitlines() if ssh_log else ["No SSH logins found"]

    # 8.4 Kernel panics (last 30 days)
    spinner_line("Logs & Forensics — Kernel Panics")
    panic_dir = "/Library/Logs/DiagnosticReports"
    panics = []
    if os.path.isdir(panic_dir):
        thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        for f in os.listdir(panic_dir):
            if "panic" in f.lower():
                full = os.path.join(panic_dir, f)
                try:
                    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(full))
                    if mtime > thirty_days_ago:
                        panics.append({"file": f, "date": mtime.isoformat()})
                except Exception:
                    pass
    data["kernel_panics_30d"] = panics if panics else []

    # 8.5 App crashes (last 7 days)
    spinner_line("Logs & Forensics — App Crashes")
    crash_dirs = [
        "/Library/Logs/DiagnosticReports",
        os.path.expanduser("~/Library/Logs/DiagnosticReports"),
    ]
    crashes = []
    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    for cdir in crash_dirs:
        if os.path.isdir(cdir):
            for f in os.listdir(cdir):
                if f.endswith(".crash") or f.endswith(".ips"):
                    full = os.path.join(cdir, f)
                    try:
                        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(full))
                        if mtime > seven_days_ago:
                            crashes.append({"file": f, "date": mtime.isoformat(), "dir": cdir})
                    except Exception:
                        pass
    data["app_crashes_7d"] = crashes[:20] if crashes else []

    # 8.6 Recently downloaded files + quarantine
    spinner_line("Logs & Forensics — Downloads & Quarantine")
    downloads = os.path.expanduser("~/Downloads")
    recent_downloads = []
    if os.path.isdir(downloads):
        three_days_ago = datetime.datetime.now() - datetime.timedelta(days=3)
        for f in os.listdir(downloads):
            full = os.path.join(downloads, f)
            try:
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(full))
                if mtime > three_days_ago:
                    recent_downloads.append({"name": f, "date": mtime.isoformat()})
            except Exception:
                pass
    data["recent_downloads"] = sorted(recent_downloads, key=lambda x: x["date"], reverse=True)[:20]

    # Quarantine events
    quarantine = _run("sqlite3 ~/Library/Preferences/com.apple.LaunchServices.QuarantineEventsV2 'SELECT LSQuarantineAgentName, LSQuarantineDataURLString, LSQuarantineTimeStamp FROM LSQuarantineEvent ORDER BY LSQuarantineTimeStamp DESC LIMIT 20' 2>/dev/null", timeout=10)
    data["quarantine_events"] = quarantine.splitlines() if quarantine else ["No quarantine data available"]

    # 8.7 Recently modified files in system directories
    spinner_line("Logs & Forensics — System File Changes")
    recent_sys = _run("find /usr/local/bin /Library/LaunchDaemons /Library/LaunchAgents -maxdepth 1 -mtime -7 -type f 2>/dev/null", timeout=15)
    data["recent_system_modifications"] = recent_sys.splitlines() if recent_sys else ["None"]

    # 8.8 Mounted volumes & disk images
    spinner_line("Logs & Forensics — Mounted Volumes")
    mounts = _run_lines("mount 2>/dev/null")
    # Only flag actual disk image mounts, not system volumes like Macintosh HD
    system_volumes = {"Macintosh HD", "Macintosh HD - Data", "Preboot", "Recovery", "VM", "Update"}
    dmg_mounts = []
    for m in mounts:
        if "disk image" in m.lower():
            dmg_mounts.append(m)
        elif "/Volumes/" in m:
            # Extract volume name and skip known system volumes
            vol_match = re.search(r'/Volumes/([^/\s]+)', m)
            if vol_match:
                vol_name = vol_match.group(1)
                if vol_name not in system_volumes:
                    dmg_mounts.append(m)
    data["mounted_volumes"] = mounts
    data["disk_images"] = dmg_mounts if dmg_mounts else ["None"]

    spinner_done("Logs & Forensic Snapshot")
    return data


# ═══════════════════════════════════════════════
#  AUDIT ORCHESTRATOR
# ═══════════════════════════════════════════════

AUDIT_SECTIONS = [
    ("asset_intelligence",   "Asset Intelligence",        audit_asset_intelligence),
    ("user_accounts",        "User Accounts & Access",    audit_user_accounts),
    ("certificates",         "Certificates",              audit_certificates),
    ("network",              "Network & Connections",      audit_network),
    ("domain_management",    "Domain & Management",        audit_domain_management),
    ("threat_detection",     "Threat Detection & IOCs",    audit_threat_detection),
    ("compliance",           "EDR / Compliance Posture",   audit_compliance),
    ("logs_forensics",       "Logs & Forensic Snapshot",   audit_logs_forensics),
]


def is_root():
    """Check if running with sudo / root privileges."""
    return os.geteuid() == 0


def run_full_audit(selected_sections=None, alert_level="medium"):
    """Run the full security audit and return a dict of all results."""
    running_as_root = is_root()
    if not running_as_root:
        print(f"\n  {YELLOW}!{RESET} Running without sudo — some checks will have limited results.")
        print(f"  {DIM}For full audit, run: sudo python3 macdna.py{RESET}\n")

    results = {
        "audit_meta": {
            "timestamp": datetime.datetime.now().isoformat(),
            "hostname": _run("scutil --get ComputerName"),
            "macos_version": platform.mac_ver()[0],
            "current_user": getpass.getuser(),
            "alert_level": alert_level,
            "elevated": running_as_root,
        }
    }

    for key, label, func in AUDIT_SECTIONS:
        if selected_sections and key not in selected_sections:
            continue
        try:
            if key == "threat_detection":
                results[key] = func(alert_level=alert_level)
            else:
                results[key] = func()
        except Exception as e:
            results[key] = {"error": str(e)}
            spinner_fail(label, str(e))

    # Generate guidance & remediation
    results["guidance"] = generate_guidance(results)

    return results


# ═══════════════════════════════════════════════
#  GUIDANCE & REMEDIATION ENGINE
# ═══════════════════════════════════════════════

# Maps compliance check names → { risk, fix, cis }
COMPLIANCE_GUIDANCE = {
    "FileVault Encryption": {
        "risk": "Without FileVault, anyone with physical access can read your disk — including stolen laptops.",
        "fix": "sudo fdesetup enable",
        "settings": "System Settings → Privacy & Security → FileVault → Turn On",
        "cis": "CIS 5.1.1 — Ensure FileVault Is Enabled",
    },
    "System Integrity Protection": {
        "risk": "SIP prevents malware from modifying protected system files and kernel extensions. Disabling it leaves your OS exposed.",
        "fix": "Boot to Recovery Mode (Cmd+R) → Terminal → csrutil enable",
        "settings": "Requires Recovery Mode — cannot be changed from normal boot",
        "cis": "CIS 5.1.2 — Ensure System Integrity Protection Is Enabled",
    },
    "Gatekeeper": {
        "risk": "Gatekeeper blocks unsigned/unnotarized apps. Without it, malicious apps can run unchecked.",
        "fix": "sudo spctl --master-enable",
        "settings": "System Settings → Privacy & Security → Allow apps from: App Store and identified developers",
        "cis": "CIS 5.1.3 — Ensure Gatekeeper Is Enabled",
    },
    "Firewall": {
        "risk": "Without the firewall, all incoming connections are allowed — any listening service is exposed to the network.",
        "fix": "sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on",
        "settings": "System Settings → Network → Firewall → Turn On",
        "cis": "CIS 2.2.1 — Ensure Firewall Is Enabled",
    },
    "Firewall Stealth Mode": {
        "risk": "Without stealth mode, your Mac responds to ICMP probes (pings), making it visible for reconnaissance.",
        "fix": "sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on",
        "settings": "System Settings → Network → Firewall → Options → Enable stealth mode",
        "cis": "CIS 2.2.2 — Ensure Firewall Stealth Mode Is Enabled",
    },
    "Automatic Updates": {
        "risk": "Missing security patches leaves known vulnerabilities exploitable. Critical patches should apply automatically.",
        "fix": "sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticCheckEnabled -bool true && sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticDownload -bool true",
        "settings": "System Settings → General → Software Update → Automatic Updates → Turn on all",
        "cis": "CIS 1.2 — Ensure Auto Update Is Enabled",
    },
    "Password on Wake": {
        "risk": "Without password on wake, anyone can access your session by opening the laptop lid or waking the screen.",
        "fix": "sysadminctl -screenLock immediate -password -",
        "settings": "System Settings → Lock Screen → Require password after screen saver begins → Immediately",
        "cis": "CIS 6.1.2 — Ensure Screen Lock on Wake",
    },
    "Password Delay": {
        "risk": "A delay before requiring password means someone can access your Mac briefly after it locks.",
        "fix": "defaults write com.apple.screensaver askForPasswordDelay -int 0",
        "settings": "System Settings → Lock Screen → Require password → Immediately",
        "cis": "CIS 6.1.3 — Ensure Lock Screen Password Delay Is Immediate",
    },
    "Remote Login (SSH)": {
        "risk": "SSH allows remote terminal access. If not needed, it should be disabled to reduce attack surface.",
        "fix": "sudo systemsetup -setremotelogin off",
        "settings": "System Settings → General → Sharing → Remote Login → Off",
        "cis": "CIS 2.4.8 — Ensure Remote Login Is Disabled",
    },
    "Guest Account": {
        "risk": "Guest accounts allow unauthenticated access to the Mac with limited privileges but potential data exposure.",
        "fix": "sudo defaults write /Library/Preferences/com.apple.loginwindow GuestEnabled -bool false",
        "settings": "System Settings → Users & Groups → Guest User → Off",
        "cis": "CIS 6.1.5 — Ensure Guest Account Is Disabled",
    },
    "AirDrop": {
        "risk": "AirDrop in 'Everyone' mode allows strangers nearby to send you files — potential social engineering vector.",
        "fix": "defaults write com.apple.sharingd DiscoverableMode -string 'Contacts Only'",
        "settings": "System Settings → General → AirDrop & Handoff → AirDrop → Contacts Only",
        "cis": "CIS 2.4.10 — Ensure AirDrop Is Contacts Only or Disabled",
    },
    "Pending Software Updates": {
        "risk": "Unapplied updates may include critical security patches for actively exploited vulnerabilities.",
        "fix": "sudo softwareupdate -ia",
        "settings": "System Settings → General → Software Update → Update Now",
        "cis": "CIS 1.1 — Ensure All Software Updates Are Installed",
    },
    "Third-Party Kernel Extensions": {
        "risk": "Kernel extensions run with full system privileges. Unsigned or third-party kexts can be rootkit vectors.",
        "fix": "Review loaded kexts with: kextstat | grep -v com.apple\nRemove unwanted kexts with: sudo kextunload -b <bundle-id>",
        "settings": "System Settings → Privacy & Security → Allow third-party kexts only from trusted vendors",
        "cis": "CIS 5.1.5 — Review Loaded Kernel Extensions",
    },
    "Hidden Admin Accounts": {
        "risk": "Hidden admin accounts may indicate compromise — attackers create hidden accounts for persistent access.",
        "fix": "List hidden accounts: dscl . list /Users IsHidden | grep 1\nRemove with: sudo dscl . -delete /Users/<username>",
        "settings": "Review via System Settings → Users & Groups or Directory Utility",
        "cis": "CIS 6.1.4 — Ensure No Hidden Admin Accounts Exist",
    },
    "Time Machine Backup": {
        "risk": "Without backups, data loss from ransomware, hardware failure, or accidental deletion is permanent.",
        "fix": "tmutil setdestination /Volumes/<BackupDrive>",
        "settings": "System Settings → General → Time Machine → Add Backup Disk",
        "cis": "CIS 2.7.1 — Ensure Backup Is Configured",
    },
    "Secure Boot": {
        "risk": "Without secure boot, malware could inject itself into the boot chain before the OS loads.",
        "fix": "Boot to Recovery Mode → Startup Security Utility → Full Security",
        "settings": "Requires Recovery Mode — Startup Security Utility",
        "cis": "CIS 5.1.4 — Ensure Secure Boot Is Enabled",
    },
}

# Maps threat finding categories → { risk, fix }
THREAT_GUIDANCE = {
    "Reverse Shell": {
        "risk": "A reverse shell allows an attacker to remotely control this Mac. This is a critical indicator of active compromise.",
        "fix": "1. Identify the PID from the finding detail\n2. Kill it: sudo kill -9 <PID>\n3. Investigate: lsof -p <PID> to find the source binary\n4. Check persistence: look in LaunchDaemons/LaunchAgents for the binary\n5. Consider forensic imaging before remediation",
    },
    "Hidden Directory Process": {
        "risk": "Processes running from hidden directories (starting with '.') could be legitimate tools or malware hiding in dotfiles.",
        "fix": "1. Verify the process: codesign -v <binary-path>\n2. If unknown: kill the process and investigate the binary\n3. Known safe: npm tools (firebase, playwright) and .app crashpad handlers are typically benign\n4. Check VirusTotal for the binary hash if suspicious",
    },
    "Suspicious Temp Process": {
        "risk": "Legitimate software rarely runs from /tmp or /var/tmp. Malware commonly drops payloads there to avoid detection.",
        "fix": "1. Identify the process: ps aux | grep <PID>\n2. Check the binary: file /tmp/<binary-name>\n3. Verify signature: codesign -v /tmp/<binary-name>\n4. Kill if suspicious: sudo kill -9 <PID>\n5. Remove the binary and check for persistence mechanisms",
    },
    "Unsigned Network Binary": {
        "risk": "Unsigned binaries with network access could be exfiltrating data or communicating with C2 servers.",
        "fix": "1. Check what it's connecting to: lsof -i -p <PID>\n2. Verify the application: codesign -dv --verbose=4 <path>\n3. If legitimate (e.g., MEGAsync): consider it a false positive\n4. If unknown: block with firewall and investigate",
    },
    "Crypto Miner": {
        "risk": "Crypto miners steal CPU/GPU resources and dramatically increase power consumption. Often installed via malware.",
        "fix": "1. Kill the miner process: sudo kill -9 <PID>\n2. Find and delete the binary\n3. Check crontabs and LaunchAgents for persistence\n4. Scan with Malwarebytes: https://www.malwarebytes.com/mac",
    },
    "Known Malware": {
        "risk": "A known malware process name was matched. This requires immediate investigation and remediation.",
        "fix": "1. STOP — do not ignore this\n2. Kill the process: sudo kill -9 <PID>\n3. Isolate the Mac from the network\n4. Run Malwarebytes full scan\n5. Check for data exfiltration in network logs\n6. Consider reimaging the Mac if confirmed",
    },
    "Suspicious Port": {
        "risk": "Certain ports are commonly used by malware, RATs, or unauthorized services (e.g., 4444, 5555, 31337).",
        "fix": "1. Identify what's listening: lsof -i :<port>\n2. If unauthorized: kill the process and check persistence\n3. Block the port: sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add <app-path> --blockapp",
    },
    "High Port Connection": {
        "risk": "Connections to unusual high ports (>10000) may indicate C2 communication or data exfiltration.",
        "fix": "1. Inspect the connection: lsof -i -p <PID>\n2. Look up the remote IP: whois <IP> or check https://abuseipdb.com\n3. If suspicious: block with Little Snitch or the macOS firewall",
    },
    "Suspicious PATH": {
        "risk": "Modified PATH can cause the system to run attacker-controlled binaries instead of legitimate system tools.",
        "fix": "1. Review your PATH: echo $PATH\n2. Check ~/.zshrc, ~/.bash_profile, /etc/paths.d/ for modifications\n3. Remove unknown directories from PATH\n4. .local/bin is usually safe (pip user installs) but verify contents: ls -la ~/.local/bin",
    },
    "User Account Audit": {
        "risk": "Recently created accounts should be verified — attackers may create accounts for persistent access.",
        "fix": "1. Verify the account is expected: dscl . -read /Users/<username>\n2. If unauthorized: sudo dscl . -delete /Users/<username>\n3. Check if it has admin rights: dsmemberutil checkmembership -U <username> -G admin",
    },
}

# Maps certificate conditions → guidance
CERT_GUIDANCE = {
    "expired": {
        "risk": "Expired certificates cause trust failures, broken services, and potential security warnings.",
        "fix": "1. For Apple dev certs: Renew in developer.apple.com → Certificates\n2. For system identity certs: Usually auto-renewed by macOS\n3. For custom certs: Contact your CA or regenerate with openssl",
    },
    "self_signed": {
        "risk": "Self-signed certificates aren't validated by a trusted CA. They're normal for local system identity but suspicious for other purposes.",
        "fix": "1. System Identity certs (com.apple.*): These are normal — macOS generates them\n2. Other self-signed certs: Replace with CA-signed certificates from Let's Encrypt or your org's CA",
    },
    "expiring_soon": {
        "risk": "Certificates expiring soon will cause service disruptions if not renewed before expiry.",
        "fix": "1. Identify the service using this cert\n2. Request renewal from your CA\n3. Install the new cert: security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain <cert.pem>",
    },
}


def generate_guidance(audit_data):
    """Analyze audit data and generate actionable remediation guidance."""
    guidance = {
        "total_issues": 0,
        "critical_actions": [],
        "recommended_actions": [],
        "informational": [],
    }

    # Compliance failures
    compliance = audit_data.get("compliance", {})
    for check in compliance.get("checks", []):
        status = check.get("status", "")
        name = check.get("check", "")
        detail = check.get("detail", "")

        if status in ("fail", "warning") and name in COMPLIANCE_GUIDANCE:
            g = COMPLIANCE_GUIDANCE[name]
            entry = {
                "category": "Compliance",
                "check": name,
                "status": status,
                "current": detail,
                "risk": g["risk"],
                "fix_command": g["fix"],
                "fix_gui": g.get("settings", ""),
                "reference": g.get("cis", ""),
            }
            if status == "fail":
                guidance["critical_actions"].append(entry)
            else:
                guidance["recommended_actions"].append(entry)
            guidance["total_issues"] += 1

    # Threat findings
    threats = audit_data.get("threat_detection", {})
    for finding in threats.get("findings", []):
        sev = finding.get("severity", "info")
        cat = finding.get("category", "")
        detail = finding.get("detail", "")

        if cat in THREAT_GUIDANCE:
            g = THREAT_GUIDANCE[cat]
            entry = {
                "category": "Threat Detection",
                "check": cat,
                "status": sev,
                "current": detail,
                "risk": g["risk"],
                "fix_command": g["fix"],
                "fix_gui": "",
                "reference": "",
            }
            if sev == "critical":
                guidance["critical_actions"].append(entry)
            elif sev == "warning":
                guidance["recommended_actions"].append(entry)
            else:
                guidance["informational"].append(entry)
            guidance["total_issues"] += 1

    # Certificate issues
    certs = audit_data.get("certificates", {})
    for label, key in [("expired", "expired"), ("self_signed", "self_signed"),
                       ("expiring_soon", "expiring_30d")]:
        items = certs.get(key, [])
        if items and label in CERT_GUIDANCE:
            g = CERT_GUIDANCE[label]
            entry = {
                "category": "Certificates",
                "check": f"{len(items)} {label.replace('_',' ').title()} Certificate(s)",
                "status": "fail" if label == "expired" else "warning",
                "current": ", ".join(c.get("subject", "")[:50] for c in items[:3]),
                "risk": g["risk"],
                "fix_command": g["fix"],
                "fix_gui": "",
                "reference": "",
            }
            if label == "expired":
                guidance["critical_actions"].append(entry)
            else:
                guidance["recommended_actions"].append(entry)
            guidance["total_issues"] += 1

    # Sharing services warnings
    network = audit_data.get("network", {})
    sharing = network.get("sharing_services", {})
    for svc, enabled in sharing.items():
        if enabled and svc in ("screen_sharing", "remote_management"):
            guidance["recommended_actions"].append({
                "category": "Network",
                "check": f"{svc.replace('_',' ').title()} Enabled",
                "status": "warning",
                "current": "Service is ON",
                "risk": "Remote access services increase attack surface. Disable if not actively needed.",
                "fix_command": f"sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.screensharing.plist" if "screen" in svc else "",
                "fix_gui": f"System Settings → General → Sharing → {svc.replace('_',' ').title()} → Off",
                "reference": "",
            })
            guidance["total_issues"] += 1

    return guidance


def _render_guidance_html(guidance):
    """Render the guidance section for the HTML report."""
    html = ""
    total = guidance["total_issues"]
    n_critical = len(guidance["critical_actions"])
    n_recommended = len(guidance["recommended_actions"])
    n_info = len(guidance["informational"])

    if total == 0:
        html += '<div style="color:var(--green);font-weight:600;padding:1rem 0;font-size:1.1rem">No remediation actions needed — your Mac is well configured.</div>'
        return html

    # Summary bar
    html += f'<div style="margin-bottom:1.5rem">'
    html += f'<span class="tag tag-critical" style="font-size:0.9rem;padding:0.3rem 0.8rem">{n_critical} Critical Fix{"es" if n_critical != 1 else ""}</span> '
    html += f'<span class="tag tag-warning" style="font-size:0.9rem;padding:0.3rem 0.8rem">{n_recommended} Recommended</span> '
    html += f'<span class="tag tag-info" style="font-size:0.9rem;padding:0.3rem 0.8rem">{n_info} Informational</span>'
    html += '</div>'

    # Critical actions
    if guidance["critical_actions"]:
        html += '<div class="subsection"><div class="subsection-title" style="color:var(--red);font-size:0.9rem">CRITICAL — Fix These Now</div>'
        for item in guidance["critical_actions"]:
            html += _render_guidance_card(item, "red")
        html += '</div>'

    # Recommended actions
    if guidance["recommended_actions"]:
        html += '<div class="subsection"><div class="subsection-title" style="color:var(--yellow);font-size:0.9rem">RECOMMENDED — Should Address</div>'
        for item in guidance["recommended_actions"]:
            html += _render_guidance_card(item, "yellow")
        html += '</div>'

    # Informational
    if guidance["informational"]:
        html += '<div class="subsection"><div class="subsection-title" style="color:var(--cyan);font-size:0.9rem">INFORMATIONAL — Review When Possible</div>'
        for item in guidance["informational"]:
            html += _render_guidance_card(item, "cyan")
        html += '</div>'

    return html


def _render_guidance_card(item, color):
    """Render a single guidance card."""
    border_color = {"red": "var(--red)", "yellow": "var(--yellow)", "cyan": "var(--cyan)"}.get(color, "var(--border)")

    html = f'<div style="border-left:3px solid {border_color};padding:0.8rem 1rem;margin:0.6rem 0;background:rgba(255,255,255,0.02);border-radius:0 6px 6px 0">'

    # Title line
    status_tag = {"fail": "tag-fail", "critical": "tag-critical", "warning": "tag-warning", "info": "tag-info"}.get(item["status"], "tag-info")
    html += f'<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.4rem">'
    html += f'<span class="tag {status_tag}">{item["status"].upper()}</span>'
    html += f'<strong style="font-size:0.95rem">{_esc(item["check"])}</strong>'
    if item.get("reference"):
        html += f'<span style="font-size:0.7rem;color:var(--dim);margin-left:auto">{_esc(item["reference"])}</span>'
    html += '</div>'

    # Current state
    if item.get("current"):
        html += f'<div style="font-size:0.8rem;color:var(--dim);margin-bottom:0.4rem">Current: {_esc(item["current"][:120])}</div>'

    # Risk
    html += f'<div style="font-size:0.85rem;margin-bottom:0.5rem"><strong style="color:var(--orange)">Why it matters:</strong> {_esc(item["risk"])}</div>'

    # Fix command
    if item.get("fix_command"):
        html += f'<div style="margin-bottom:0.3rem"><strong style="font-size:0.8rem;color:var(--green)">Terminal Fix:</strong></div>'
        html += f'<div class="code-block" style="max-height:150px">{_esc(item["fix_command"])}</div>'

    # GUI fix
    if item.get("fix_gui"):
        html += f'<div style="margin-top:0.3rem;font-size:0.8rem"><strong style="color:var(--cyan)">GUI:</strong> {_esc(item["fix_gui"])}</div>'

    html += '</div>'
    return html


# ═══════════════════════════════════════════════
#  AUDIT HTML REPORT GENERATOR
# ═══════════════════════════════════════════════

def generate_audit_html(audit_data, filepath):
    """Generate an interactive HTML report for the security audit."""
    meta = audit_data.get("audit_meta", {})
    hostname = meta.get("hostname", "Unknown Mac")
    timestamp = meta.get("timestamp", "")
    macos_ver = meta.get("macos_version", "")
    user = meta.get("current_user", "")
    alert_level = meta.get("alert_level", "medium")

    # Count findings
    threats = audit_data.get("threat_detection", {})
    sev = threats.get("severity_counts", {})
    n_critical = sev.get("critical", 0)
    n_warning = sev.get("warning", 0)
    n_info = sev.get("info", 0)

    compliance = audit_data.get("compliance", {})
    n_passed = compliance.get("passed", 0)
    n_failed = compliance.get("failed", 0)
    n_comp_warn = compliance.get("warnings", 0)
    n_total_checks = compliance.get("total", 0)

    # Build section HTML
    sections_html = ""

    # --- Asset Intelligence ---
    asset = audit_data.get("asset_intelligence", {})
    if asset:
        sections_html += _audit_section("Asset Intelligence", "server", _render_asset(asset))

    # --- User Accounts ---
    users = audit_data.get("user_accounts", {})
    if users:
        sections_html += _audit_section("User Accounts & Access", "users", _render_users(users))

    # --- Certificates ---
    certs = audit_data.get("certificates", {})
    if certs:
        sections_html += _audit_section("Certificates", "shield", _render_certs(certs))

    # --- Network ---
    network = audit_data.get("network", {})
    if network:
        sections_html += _audit_section("Network & Connections", "wifi", _render_network(network))

    # --- Domain ---
    domain = audit_data.get("domain_management", {})
    if domain:
        sections_html += _audit_section("Domain & Management", "building", _render_generic(domain))

    # --- Threat Detection ---
    if threats:
        sections_html += _audit_section("Threat Detection & IOCs", "alert-triangle", _render_threats(threats))

    # --- Compliance ---
    if compliance:
        sections_html += _audit_section("EDR / Compliance Posture", "check-circle", _render_compliance(compliance))

    # --- Logs ---
    logs = audit_data.get("logs_forensics", {})
    if logs:
        sections_html += _audit_section("Logs & Forensic Snapshot", "file-text", _render_logs(logs))

    # --- Guidance & Remediation ---
    guidance = generate_guidance(audit_data)
    if guidance["total_issues"] > 0:
        sections_html += _audit_section("Guidance & Remediation", "clipboard", _render_guidance_html(guidance))

    # Overall threat score
    if n_critical > 0:
        overall_color = "#f85149"
        overall_label = "CRITICAL FINDINGS"
        overall_icon = "!!!"
    elif n_failed > 2 or n_warning > 5:
        overall_color = "#d29922"
        overall_label = "NEEDS ATTENTION"
        overall_icon = "!"
    else:
        overall_color = "#3fb950"
        overall_label = "LOOKING GOOD"
        overall_icon = "OK"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MacDNA Security Audit — {hostname}</title>
<style>
  :root {{
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --text: #e6edf3; --dim: #8b949e;
    --cyan: #58a6ff; --green: #3fb950; --yellow: #d29922;
    --red: #f85149; --purple: #bc8cff; --orange: #f0883e;
    --font: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
    --mono: 'SF Mono', 'Menlo', 'Monaco', monospace;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.6; }}

  .header {{
    background: linear-gradient(135deg, #161b22, #1a2332);
    border-bottom: 1px solid var(--border);
    padding: 2rem; text-align: center;
  }}
  .header h1 {{ font-size: 2rem; }}
  .header h1 .accent {{ color: var(--cyan); }}
  .header .subtitle {{ color: var(--dim); font-size: 0.95rem; margin-top: 0.25rem; }}
  .header .meta-row {{
    display: flex; justify-content: center; gap: 2rem;
    margin-top: 1rem; flex-wrap: wrap;
  }}
  .header .meta-item {{ font-size: 0.85rem; color: var(--dim); }}
  .header .meta-item strong {{ color: var(--text); }}

  .overall-score {{
    text-align: center; padding: 1.5rem;
    background: var(--card); border-bottom: 1px solid var(--border);
  }}
  .score-badge {{
    display: inline-block; padding: 0.5rem 2rem; border-radius: 10px;
    font-weight: 700; font-size: 1.1rem; letter-spacing: 1px;
  }}

  .stats {{
    display: flex; justify-content: center; gap: 1.5rem; padding: 1rem 2rem;
    background: var(--card); border-bottom: 1px solid var(--border); flex-wrap: wrap;
  }}
  .stat {{ text-align: center; min-width: 90px; }}
  .stat .num {{ font-size: 1.5rem; font-weight: 700; }}
  .stat .label {{ font-size: 0.75rem; color: var(--dim); text-transform: uppercase; letter-spacing: 0.5px; }}
  .stat .num.red {{ color: var(--red); }}
  .stat .num.yellow {{ color: var(--yellow); }}
  .stat .num.green {{ color: var(--green); }}
  .stat .num.cyan {{ color: var(--cyan); }}

  .search-bar {{
    padding: 1rem 2rem; background: var(--bg);
    position: sticky; top: 0; z-index: 10;
    border-bottom: 1px solid var(--border);
  }}
  .search-bar input {{
    width: 100%; max-width: 500px; display: block; margin: 0 auto;
    padding: 0.6rem 1rem; border-radius: 8px;
    border: 1px solid var(--border); background: var(--card);
    color: var(--text); font-size: 0.95rem; outline: none;
  }}
  .search-bar input:focus {{ border-color: var(--cyan); }}

  .container {{ max-width: 1000px; margin: 0 auto; padding: 1.5rem; }}

  .section {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; margin-bottom: 1rem; overflow: hidden;
  }}
  .section:hover {{ border-color: var(--cyan); }}
  .section-header {{
    display: flex; align-items: center; padding: 0.9rem 1.2rem;
    cursor: pointer; user-select: none; gap: 0.75rem;
  }}
  .section-header:hover {{ background: rgba(88,166,255,0.05); }}
  .section-icon {{ font-size: 1.2rem; width: 2rem; text-align: center; }}
  .section-title {{ font-weight: 600; font-size: 1rem; flex: 1; }}
  .section-arrow {{ color: var(--dim); transition: transform 0.2s; font-size: 0.8rem; }}
  .section.open .section-arrow {{ transform: rotate(90deg); }}
  .section-body {{
    display: none; padding: 0 1.2rem 1.2rem;
    border-top: 1px solid var(--border);
  }}
  .section.open .section-body {{ display: block; padding-top: 1rem; }}

  table.audit-table {{ width: 100%; border-collapse: collapse; }}
  table.audit-table th {{
    text-align: left; font-size: 0.75rem; text-transform: uppercase;
    color: var(--dim); padding: 0.5rem 0.5rem; border-bottom: 1px solid var(--border);
    letter-spacing: 0.5px;
  }}
  table.audit-table td {{
    padding: 0.45rem 0.5rem; border-bottom: 1px solid rgba(48,54,61,0.3);
    font-size: 0.85rem; vertical-align: top;
  }}
  table.audit-table tr:last-child td {{ border-bottom: none; }}

  .tag {{
    display: inline-block; padding: 0.15rem 0.5rem; border-radius: 6px;
    font-size: 0.75rem; font-weight: 600;
  }}
  .tag-pass {{ background: rgba(63,185,80,0.15); color: var(--green); }}
  .tag-fail {{ background: rgba(248,81,73,0.15); color: var(--red); }}
  .tag-warning {{ background: rgba(210,153,34,0.15); color: var(--yellow); }}
  .tag-info {{ background: rgba(88,166,255,0.15); color: var(--cyan); }}
  .tag-critical {{ background: rgba(248,81,73,0.2); color: var(--red); font-weight: 700; }}

  .finding-row {{ padding: 0.5rem 0; border-bottom: 1px solid rgba(48,54,61,0.3); }}
  .finding-row:last-child {{ border-bottom: none; }}
  .finding-category {{ font-weight: 600; font-size: 0.85rem; }}
  .finding-detail {{ font-size: 0.8rem; color: var(--dim); font-family: var(--mono); margin-top: 0.2rem; word-break: break-all; }}

  .kv-row {{ display: flex; padding: 0.3rem 0; border-bottom: 1px solid rgba(48,54,61,0.2); }}
  .kv-row:last-child {{ border-bottom: none; }}
  .kv-key {{ width: 40%; color: var(--dim); font-size: 0.85rem; }}
  .kv-val {{ width: 60%; font-family: var(--mono); font-size: 0.85rem; word-break: break-all; }}

  .subsection {{ margin-top: 1rem; }}
  .subsection-title {{
    font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--dim); margin-bottom: 0.5rem; font-weight: 600;
  }}

  .item-list {{ display: flex; flex-wrap: wrap; gap: 0.4rem; }}
  .item-tag {{
    font-size: 0.8rem; padding: 0.2rem 0.6rem; border-radius: 6px;
    background: rgba(88,166,255,0.1); color: var(--cyan);
    font-family: var(--mono); border: 1px solid rgba(88,166,255,0.15);
  }}

  .code-block {{
    background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
    padding: 0.8rem; font-family: var(--mono); font-size: 0.8rem;
    overflow-x: auto; white-space: pre-wrap; word-break: break-all;
    max-height: 300px; overflow-y: auto; color: var(--text); margin-top: 0.3rem;
  }}

  .footer {{
    text-align: center; padding: 2rem; color: var(--dim);
    font-size: 0.8rem; border-top: 1px solid var(--border); margin-top: 2rem;
  }}
  .hidden {{ display: none !important; }}
</style>
</head>
<body>

<div class="header">
  <h1><span class="accent">MacDNA</span> Security Audit</h1>
  <div class="subtitle">{hostname} — {timestamp[:10]}</div>
  <div class="meta-row">
    <div class="meta-item">macOS <strong>{macos_ver}</strong></div>
    <div class="meta-item">User <strong>{user}</strong></div>
    <div class="meta-item">Alert Level <strong>{alert_level.upper()}</strong></div>
  </div>
</div>

<div class="overall-score">
  <div class="score-badge" style="background: {overall_color}22; color: {overall_color}; border: 2px solid {overall_color};">
    {overall_icon} {overall_label}
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="num red">{n_critical}</div><div class="label">Critical</div></div>
  <div class="stat"><div class="num yellow">{n_warning}</div><div class="label">Warnings</div></div>
  <div class="stat"><div class="num cyan">{n_info}</div><div class="label">Info</div></div>
  <div class="stat"><div class="num green">{n_passed}</div><div class="label">Checks Passed</div></div>
  <div class="stat"><div class="num red">{n_failed}</div><div class="label">Checks Failed</div></div>
  <div class="stat"><div class="num yellow">{n_comp_warn}</div><div class="label">Check Warnings</div></div>
</div>

<div class="search-bar">
  <input type="text" id="search" placeholder="Search audit results..." autocomplete="off">
</div>

<div class="container">
{sections_html}
</div>

<div class="footer">
  MacDNA v3.0 Security Audit — Author: cyberspartan77 — Generated {timestamp[:10]}
</div>

<script>
document.querySelectorAll('.section-header').forEach(h => {{
  h.addEventListener('click', () => h.parentElement.classList.toggle('open'));
}});
document.getElementById('search').addEventListener('input', function() {{
  const q = this.value.toLowerCase();
  document.querySelectorAll('.section').forEach(s => {{
    if (!q) {{ s.classList.remove('hidden'); return; }}
    if (s.textContent.toLowerCase().includes(q)) {{
      s.classList.remove('hidden'); s.classList.add('open');
    }} else {{ s.classList.add('hidden'); }}
  }});
}});
document.querySelectorAll('.section').forEach(s => s.classList.add('open'));
</script>
</body>
</html>"""

    with open(filepath, "w") as f:
        f.write(html)


# ── HTML section builder helpers ──

def _audit_section(title, icon_name, body_html):
    icons = {
        "server": "&#x1F5A5;", "users": "&#x1F465;", "shield": "&#x1F6E1;",
        "wifi": "&#x1F310;", "building": "&#x1F3E2;", "alert-triangle": "&#x26A0;",
        "check-circle": "&#x2705;", "file-text": "&#x1F4C4;", "clipboard": "&#x1F4CB;",
    }
    icon = icons.get(icon_name, "&#x1F4CB;")
    return f"""
  <div class="section">
    <div class="section-header">
      <div class="section-icon">{icon}</div>
      <div class="section-title">{title}</div>
      <div class="section-arrow">&#x25B6;</div>
    </div>
    <div class="section-body">{body_html}</div>
  </div>
"""


def _esc(val):
    return str(val).replace("<", "&lt;").replace(">", "&gt;")


def _render_asset(data):
    html = ""
    # CPU
    cpu = data.get("cpu", {})
    html += '<div class="subsection"><div class="subsection-title">CPU</div>'
    html += '<div class="kv-row"><div class="kv-key">Model</div><div class="kv-val">' + _esc(cpu.get("model", "")) + '</div></div>'
    html += '<div class="kv-row"><div class="kv-key">Physical Cores</div><div class="kv-val">' + _esc(cpu.get("cores_physical", "")) + '</div></div>'
    html += '<div class="kv-row"><div class="kv-key">Logical Cores</div><div class="kv-val">' + _esc(cpu.get("cores_logical", "")) + '</div></div>'
    html += '<div class="kv-row"><div class="kv-key">Architecture</div><div class="kv-val">' + _esc(cpu.get("architecture", "")) + '</div></div>'
    html += '</div>'

    # RAM + identity
    html += '<div class="subsection"><div class="subsection-title">Memory & Identity</div>'
    html += '<div class="kv-row"><div class="kv-key">RAM</div><div class="kv-val">' + _esc(data.get("ram_gb", "")) + ' GB</div></div>'
    html += '<div class="kv-row"><div class="kv-key">Serial</div><div class="kv-val">' + _esc(data.get("serial", "")) + '</div></div>'
    html += '<div class="kv-row"><div class="kv-key">Model ID</div><div class="kv-val">' + _esc(data.get("model_id", "")) + '</div></div>'
    html += '<div class="kv-row"><div class="kv-key">Board ID</div><div class="kv-val">' + _esc(data.get("board_id", "")) + '</div></div>'
    html += '<div class="kv-row"><div class="kv-key">macOS</div><div class="kv-val">' + _esc(data.get("macos_version", "")) + ' (' + _esc(data.get("build", "")) + ')</div></div>'
    html += '</div>'

    # GPU
    gpus = data.get("gpu", [])
    if gpus:
        html += '<div class="subsection"><div class="subsection-title">GPU</div>'
        for g in gpus:
            html += '<div class="kv-row"><div class="kv-key">' + _esc(g.get("model", "")) + '</div><div class="kv-val">'
            if g.get("vram"):
                html += 'VRAM: ' + _esc(g["vram"]) + ' '
            if g.get("metal"):
                html += 'Metal: ' + _esc(g["metal"])
            html += '</div></div>'
        html += '</div>'

    # Storage
    storage = data.get("storage", {})
    vols = storage.get("volumes", [])
    if vols:
        html += '<div class="subsection"><div class="subsection-title">Storage Volumes</div>'
        html += '<table class="audit-table"><tr><th>Device</th><th>Size</th><th>Used</th><th>Avail</th><th>Mount</th></tr>'
        for v in vols:
            html += f'<tr><td>{_esc(v.get("device",""))}</td><td>{_esc(v.get("size",""))}</td><td>{_esc(v.get("used",""))}</td><td>{_esc(v.get("available",""))}</td><td>{_esc(v.get("mount",""))}</td></tr>'
        html += '</table>'
        fv_tag = '<span class="tag tag-pass">ON</span>' if storage.get("filevault") else '<span class="tag tag-fail">OFF</span>'
        html += f'<div class="kv-row"><div class="kv-key">FileVault</div><div class="kv-val">{fv_tag}</div></div>'
        html += '</div>'

    # Battery
    batt = data.get("battery", {})
    if batt:
        html += '<div class="subsection"><div class="subsection-title">Battery</div>'
        for k, v in batt.items():
            html += f'<div class="kv-row"><div class="kv-key">{_esc(k.replace("_"," ").title())}</div><div class="kv-val">{_esc(v)}</div></div>'
        html += '</div>'

    # Peripherals
    for label, key in [("USB Devices", "usb_devices"), ("Thunderbolt", "thunderbolt_devices"),
                       ("Bluetooth", "bluetooth_devices"), ("Printers", "printers")]:
        items = data.get(key, [])
        if items:
            html += f'<div class="subsection"><div class="subsection-title">{label} ({len(items)})</div><div class="item-list">'
            for i in items:
                html += f'<span class="item-tag">{_esc(i)}</span>'
            html += '</div></div>'

    return html


def _render_users(data):
    html = ""
    users = data.get("local_users", [])
    if users:
        html += '<table class="audit-table"><tr><th>User</th><th>UID</th><th>Admin</th><th>Hidden</th><th>Shell</th><th>Last Login</th></tr>'
        for u in users:
            admin_tag = '<span class="tag tag-warning">ADMIN</span>' if u.get("admin") else '<span class="tag tag-info">user</span>'
            hidden_tag = '<span class="tag tag-critical">HIDDEN</span>' if u.get("hidden") else ""
            html += f'<tr><td>{_esc(u.get("username",""))}</td><td>{_esc(u.get("uid",""))}</td><td>{admin_tag}</td><td>{hidden_tag}</td><td>{_esc(u.get("shell",""))}</td><td style="font-size:0.75rem">{_esc(u.get("last_login","")[:60])}</td></tr>'
        html += '</table>'

    # SSH
    ssh = data.get("ssh", {})
    if ssh:
        html += '<div class="subsection"><div class="subsection-title">SSH Configuration</div>'
        ssh_status = "Running" if ssh.get("sshd_running") else "Not running"
        html += f'<div class="kv-row"><div class="kv-key">SSHD</div><div class="kv-val">{_esc(ssh_status)}</div></div>'
        html += f'<div class="kv-row"><div class="kv-key">Remote Login</div><div class="kv-val">{_esc(ssh.get("remote_login",""))}</div></div>'
        html += f'<div class="kv-row"><div class="kv-key">Config Hosts</div><div class="kv-val">{_esc(", ".join(ssh.get("config_hosts",[])) or "None")}</div></div>'
        html += f'<div class="kv-row"><div class="kv-key">Authorized Keys</div><div class="kv-val">{ssh.get("authorized_keys_count", 0)}</div></div>'
        html += f'<div class="kv-row"><div class="kv-key">Known Hosts</div><div class="kv-val">{ssh.get("known_hosts_count", 0)}</div></div>'
        html += '</div>'

    # Sudoers
    sudoers = data.get("sudoers", {})
    if sudoers:
        html += '<div class="subsection"><div class="subsection-title">Sudoers</div>'
        admins = sudoers.get("admin_group_members", [])
        html += f'<div class="kv-row"><div class="kv-key">Admin Group</div><div class="kv-val">{_esc(", ".join(admins))}</div></div>'
        custom = sudoers.get("custom_rules_files", [])
        html += f'<div class="kv-row"><div class="kv-key">Custom Rules Files</div><div class="kv-val">{_esc(", ".join(custom) if custom else "None")}</div></div>'
        html += '</div>'

    return html


def _render_certs(data):
    html = f'<div class="kv-row"><div class="kv-key">Total Certificates</div><div class="kv-val">{data.get("total_certs", 0)}</div></div>'

    for label, key, tag_class in [
        ("Expired", "expired", "tag-critical"),
        ("Expiring < 30 days", "expiring_30d", "tag-fail"),
        ("Expiring < 60 days", "expiring_60d", "tag-warning"),
        ("Expiring < 90 days", "expiring_90d", "tag-info"),
        ("Self-Signed", "self_signed", "tag-warning"),
    ]:
        items = data.get(key, [])
        if items:
            html += f'<div class="subsection"><div class="subsection-title"><span class="tag {tag_class}">{len(items)}</span> {label}</div>'
            html += '<table class="audit-table"><tr><th>Subject</th><th>Issuer</th><th>Expires</th></tr>'
            for c in items[:15]:
                html += f'<tr><td>{_esc(c.get("subject","")[:60])}</td><td>{_esc(c.get("issuer","")[:60])}</td><td>{_esc(c.get("not_after",""))}</td></tr>'
            if len(items) > 15:
                html += f'<tr><td colspan="3" style="color:var(--dim)">...and {len(items)-15} more</td></tr>'
            html += '</table></div>'

    return html


def _render_network(data):
    html = ""

    # Listening
    listening = data.get("listening_tcp", [])
    if listening:
        html += f'<div class="subsection"><div class="subsection-title">Listening TCP Ports ({len(listening)})</div>'
        html += '<table class="audit-table"><tr><th>Process</th><th>PID</th><th>User</th><th>Address</th></tr>'
        for l in listening:
            html += f'<tr><td>{_esc(l.get("process",""))}</td><td>{_esc(l.get("pid",""))}</td><td>{_esc(l.get("user",""))}</td><td>{_esc(l.get("address",""))}</td></tr>'
        html += '</table></div>'

    # Established
    est = data.get("established_tcp", [])
    if est:
        html += f'<div class="subsection"><div class="subsection-title">Established Connections ({len(est)})</div>'
        html += '<table class="audit-table"><tr><th>Process</th><th>PID</th><th>User</th><th>Connection</th></tr>'
        for e in est[:30]:
            html += f'<tr><td>{_esc(e.get("process",""))}</td><td>{_esc(e.get("pid",""))}</td><td>{_esc(e.get("user",""))}</td><td>{_esc(e.get("connection",""))}</td></tr>'
        html += '</table></div>'

    # Interfaces
    ifaces = data.get("interfaces", [])
    if ifaces:
        html += f'<div class="subsection"><div class="subsection-title">Network Interfaces</div>'
        html += '<table class="audit-table"><tr><th>Name</th><th>IPs</th><th>MAC</th><th>Status</th></tr>'
        for i in ifaces:
            html += f'<tr><td>{_esc(i.get("name",""))}</td><td>{_esc(", ".join(i.get("ips",[])))}</td><td>{_esc(i.get("mac",""))}</td><td>{_esc(i.get("status",""))}</td></tr>'
        html += '</table></div>'

    # Sharing
    sharing = data.get("sharing_services", {})
    if sharing:
        html += '<div class="subsection"><div class="subsection-title">Sharing Services</div>'
        for k, v in sharing.items():
            tag = '<span class="tag tag-warning">ON</span>' if v else '<span class="tag tag-pass">OFF</span>'
            html += f'<div class="kv-row"><div class="kv-key">{_esc(k.replace("_"," ").title())}</div><div class="kv-val">{tag}</div></div>'
        html += '</div>'

    return html


def _render_threats(data):
    html = ""
    findings = data.get("findings", [])
    sev = data.get("severity_counts", {})

    html += f'<div style="margin-bottom:1rem">'
    html += f'<span class="tag tag-critical">{sev.get("critical",0)} Critical</span> '
    html += f'<span class="tag tag-warning">{sev.get("warning",0)} Warnings</span> '
    html += f'<span class="tag tag-info">{sev.get("info",0)} Info</span>'
    html += '</div>'

    if not findings:
        html += '<div style="color:var(--green);font-weight:600;padding:1rem 0">No threats detected</div>'
    else:
        # Group by severity
        for severity in ["critical", "warning", "info"]:
            group = [f for f in findings if f.get("severity") == severity]
            if group:
                tag_class = {"critical": "tag-critical", "warning": "tag-warning", "info": "tag-info"}[severity]
                html += f'<div class="subsection"><div class="subsection-title">{severity.upper()} ({len(group)})</div>'
                for f in group:
                    html += f'<div class="finding-row"><span class="tag {tag_class}">{_esc(f.get("category",""))}</span>'
                    html += f'<div class="finding-detail">{_esc(f.get("detail",""))}</div></div>'
                html += '</div>'

    # Cron
    cron = data.get("cron_jobs", {})
    if cron:
        html += '<div class="subsection"><div class="subsection-title">Cron Jobs</div>'
        html += f'<div class="code-block">{_esc(cron.get("user_crontab",""))}</div>'
        html += '</div>'

    # Launch items
    launch = data.get("launch_items", [])
    if launch:
        html += f'<div class="subsection"><div class="subsection-title">Non-Apple Launch Items ({len(launch)})</div>'
        html += '<div class="item-list">'
        for l in launch:
            html += f'<span class="item-tag">{_esc(l.get("name",""))}</span>'
        html += '</div></div>'

    # Browser extensions
    ext = data.get("browser_extensions", {})
    for browser, exts in ext.items():
        if exts:
            html += f'<div class="subsection"><div class="subsection-title">{browser.title()} Extensions ({len(exts)})</div>'
            html += '<div class="item-list">'
            for e in exts:
                html += f'<span class="item-tag">{_esc(e.get("name", e.get("id","")))}</span>'
            html += '</div></div>'

    # Environment
    env = data.get("environment_anomalies", [])
    if env:
        html += '<div class="subsection"><div class="subsection-title">Environment Anomalies</div>'
        for e in env:
            html += f'<div class="kv-row"><div class="kv-key"><span class="tag tag-warning">{_esc(e.get("variable",""))}</span></div><div class="kv-val">{_esc(e.get("value",""))}</div></div>'
        html += '</div>'

    # Recent mods
    mods = data.get("recently_modified_system_files", [])
    if mods:
        html += f'<div class="subsection"><div class="subsection-title">Recently Modified System Files ({len(mods)})</div>'
        html += '<div class="item-list">'
        for m in mods:
            html += f'<span class="item-tag">{_esc(m)}</span>'
        html += '</div></div>'

    return html


def _render_compliance(data):
    html = ""
    checks = data.get("checks", [])
    if not checks:
        return '<div style="color:var(--dim)">No compliance data</div>'

    html += '<table class="audit-table"><tr><th>Check</th><th>Status</th><th>Detail</th></tr>'
    for c in checks:
        status = c.get("status", "")
        tag_map = {"pass": "tag-pass", "fail": "tag-fail", "warning": "tag-warning",
                   "info": "tag-info", "critical": "tag-critical"}
        tag = tag_map.get(status, "tag-info")
        html += f'<tr><td>{_esc(c.get("check",""))}</td><td><span class="tag {tag}">{status.upper()}</span></td><td style="font-size:0.8rem;color:var(--dim)">{_esc(c.get("detail",""))}</td></tr>'
    html += '</table>'

    return html


def _render_logs(data):
    html = ""

    for title, key in [
        ("Failed Logins (48h)", "failed_logins_48h"),
        ("Sudo Usage (48h)", "sudo_usage_48h"),
        ("SSH History", "ssh_history"),
    ]:
        lines = data.get(key, [])
        if lines:
            content = "\n".join(str(l) for l in lines[:20])
            html += f'<div class="subsection"><div class="subsection-title">{title}</div><div class="code-block">{_esc(content)}</div></div>'

    # Kernel panics
    panics = data.get("kernel_panics_30d", [])
    if panics and panics != ["None"]:
        html += f'<div class="subsection"><div class="subsection-title"><span class="tag tag-critical">{len(panics)}</span> Kernel Panics (30d)</div>'
        for p in panics:
            if isinstance(p, dict):
                html += f'<div class="kv-row"><div class="kv-key">{_esc(p.get("file",""))}</div><div class="kv-val">{_esc(p.get("date",""))}</div></div>'
        html += '</div>'
    else:
        html += '<div class="subsection"><div class="subsection-title">Kernel Panics (30d)</div><span class="tag tag-pass">None</span></div>'

    # Crashes
    crashes = data.get("app_crashes_7d", [])
    if crashes and crashes != ["None"]:
        html += f'<div class="subsection"><div class="subsection-title"><span class="tag tag-warning">{len(crashes)}</span> App Crashes (7d)</div>'
        html += '<table class="audit-table"><tr><th>File</th><th>Date</th></tr>'
        for c in crashes:
            if isinstance(c, dict):
                html += f'<tr><td>{_esc(c.get("file",""))}</td><td>{_esc(c.get("date",""))}</td></tr>'
        html += '</table></div>'

    # Downloads
    dl = data.get("recent_downloads", [])
    if dl:
        html += f'<div class="subsection"><div class="subsection-title">Recent Downloads ({len(dl)})</div>'
        html += '<div class="item-list">'
        for d in dl:
            html += f'<span class="item-tag">{_esc(d.get("name",""))}</span>'
        html += '</div></div>'

    # Quarantine
    q = data.get("quarantine_events", [])
    if q and q != ["No quarantine data available"]:
        content = "\n".join(str(l) for l in q[:15])
        html += f'<div class="subsection"><div class="subsection-title">Quarantine Events</div><div class="code-block">{_esc(content)}</div></div>'

    # Mounted
    mounts = data.get("disk_images", [])
    if mounts and mounts != ["None"]:
        html += f'<div class="subsection"><div class="subsection-title">Mounted Disk Images</div>'
        for m in mounts:
            html += f'<div style="font-family:var(--mono);font-size:0.8rem;padding:0.2rem 0">{_esc(m)}</div>'
        html += '</div>'

    return html


def _render_generic(data):
    """Fallback renderer for dict data."""
    html = ""
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                html += f'<div class="subsection"><div class="subsection-title">{_esc(k.replace("_"," ").title())}</div>'
                for sk, sv in v.items():
                    html += f'<div class="kv-row"><div class="kv-key">{_esc(sk)}</div><div class="kv-val">{_esc(str(sv)[:200])}</div></div>'
                html += '</div>'
            elif isinstance(v, list):
                html += f'<div class="subsection"><div class="subsection-title">{_esc(k.replace("_"," ").title())} ({len(v)})</div>'
                if v and isinstance(v[0], dict):
                    for item in v:
                        for ik, iv in item.items():
                            html += f'<div class="kv-row"><div class="kv-key">{_esc(ik)}</div><div class="kv-val">{_esc(str(iv)[:200])}</div></div>'
                else:
                    html += '<div class="item-list">'
                    for item in v:
                        html += f'<span class="item-tag">{_esc(str(item))}</span>'
                    html += '</div>'
                html += '</div>'
            else:
                html += f'<div class="kv-row"><div class="kv-key">{_esc(k.replace("_"," ").title())}</div><div class="kv-val">{_esc(str(v)[:200])}</div></div>'
    return html
