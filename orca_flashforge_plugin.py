# /// script
# requires-python = ">=3.12"
# dependencies = ["flashforge-python-api>=1.6"]
#
# [tool.orcaslicer.plugin]
# name = "Orca FlashForge Plugin"
# description = "Prototype printer manager for FlashForge Adventurer 5M."
# author = "Community contributors"
# version = "0.6.0"
# ///
"""Opt-in LAN discovery and locally saved printer profiles. No printer commands or pairing secrets."""

import ipaddress
import uuid
import asyncio
import threading
import socket
import time
import json
import os
import sys
import tempfile
from pathlib import Path

from flashforge.discovery import PrinterDiscovery, DiscoveryOptions, PrinterModel
import ifaddr
from flashforge.client import FlashForgeClient

import orca

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { font: 14px system-ui, sans-serif; margin: 24px; color: var(--orca-text, #e5e7eb); background: var(--orca-bg, #24272c); }
h1 { font-size: 22px; margin: 0 0 6px; } h2 { font-size: 17px; margin: 0 0 12px; }
p { line-height: 1.5; } .dash { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin-top:16px; } .tile { border:1px solid #6666; border-radius:8px; padding:14px; } .tile .value { font-size:20px; font-weight:650; margin-top:6px; overflow-wrap:anywhere; } progress { width:100%; height:16px; accent-color:#087e74; } .controls { display:flex; gap:10px; flex-wrap:wrap; } .muted { opacity: .72; }
.panel { border: 1px solid var(--orca-border, #555); padding: 20px; border-radius: 10px; margin-top: 16px; }
label { display: block; margin: 10px 0 5px; }
input, select, button { font: inherit; border-radius: 6px; padding: 9px; }
input, select { box-sizing: border-box; width: 100%; background: var(--orca-bg, #24272c); color: inherit; border: 1px solid #777; }
button { cursor: pointer; border: 1px solid #888; background: #374151; color: white; }
button.primary { background: #087e74; border-color: #087e74; }
button:disabled { opacity: .5; cursor: default; }
.entry { padding: 10px 0; border-bottom: 1px solid #6666; display: flex; justify-content: space-between; gap: 12px; align-items: center; }
small { opacity: .7; } #status { min-height: 1.4em; }
</style></head><body>
<h1>FlashForge Printers</h1>
<p class="muted">v0.6.0 · Read-only live status preview · No control commands</p>
<section class="panel"><h2>Saved printers</h2><div id="printers">No printers added yet.</div></section>
<section class="panel" id="statuspanel"><h2>Live printer status</h2>
<p class="muted">Enter the printer check code once per monitoring session. Status updates automatically every 5 seconds. Nothing is saved to disk.</p>
<label for="activeprinter">Saved printer</label><select id="activeprinter"><option value="">Choose a printer</option></select>
<label for="checkcode">Printer check code</label><input id="checkcode" type="password" autocomplete="off" placeholder="Code shown on printer">
<p class="controls"><button id="connect" class="primary">Start monitoring</button><button id="stop" disabled>Stop monitoring</button><button id="refresh" disabled>Refresh now</button></p><p id="livestatus" role="status" aria-live="polite"></p><p id="lastupdate" class="muted"></p>
<div id="statusdetails"></div></section>
<section class="panel"><h2>Find printers on your network</h2>
<p class="muted">Search only when you click the button. If broadcast fails, a limited scan of your Mac's local subnet runs automatically.</p>
<button id="scan">Discover printers</button><p id="scanstatus" role="status" aria-live="polite"></p>
<div id="discovered"></div></section>
<section class="panel"><h2>Network diagnostics</h2><p class="muted">Checks whether the printer accepts TCP connections on its local control ports. No commands are sent.</p><label for="probeip">Printer IP address</label><input id="probeip" placeholder="192.168.x.x" inputmode="decimal"><p><button id="probe">Test connectivity</button></p><p id="probestatus" role="status" aria-live="polite"></p></section>
<p><button id="udpdiag">Diagnose UDP discovery</button></p><p id="udpstatus" role="status" aria-live="polite"></p></section>
<section class="panel" id="addpanel"><h2>Add printer manually</h2>
<label for="model">Printer model</label><select id="model"><option value="ad5m">FlashForge Adventurer 5M</option></select>
<label for="name">Display name</label><input id="name" maxlength="60" value="My Adventurer 5M">
<label for="address">Printer IPv4 address</label><input id="address" placeholder="192.168.x.x" inputmode="decimal">
<p><button class="primary" id="add">Save printer</button></p>
<p id="status" role="status" aria-live="polite"></p>
<p class="muted"><small>Printer names and addresses are stored locally on this Mac. Check codes are used only for a read-only status request and are not saved. Saving a printer does not contact it.</small></p>
</section>
<script>
const $ = id => document.getElementById(id);
let monitoring = false, pending = false, refreshTimer = null, activeSession = 0;
function send(message) {
  if (!window.orca || !window.orca.postMessage) { $('status').textContent = 'Orca plugin bridge unavailable.'; return; }
  window.orca.postMessage(message);
}
$('add').addEventListener('click', () => {
  $('status').textContent = 'Validating…';
  send({command:'add', model:$('model').value, name:$('name').value, address:$('address').value});
});
$('scan').addEventListener('click', () => {
  $('scan').disabled = true;
  $('scanstatus').textContent = 'Searching local network…';
  $('discovered').replaceChildren();
  send({command:'discover'});
});
$('probe').addEventListener('click', () => {
  $('probe').disabled = true;
  $('probestatus').textContent = 'Testing…';
  send({command:'probe', address:$('probeip').value});
});
$('udpdiag').addEventListener('click', () => {
  $('udpdiag').disabled = true;
  $('udpstatus').textContent = 'Checking UDP responses…';
  send({command:'udpdiag', address:$('probeip').value});
});
function showDiscovered(printers, error, diagnostics) {
  $('scan').disabled = false;
  const root = $('discovered'); root.replaceChildren();
  $('scanstatus').textContent = error || (printers.length ? 'Select a printer to fill the form below.' : 'No supported Adventurer 5M found. See diagnostic details below, or add manually.');
  if (diagnostics) {
    const detail = document.createElement('p'); detail.className = 'muted';
    detail.textContent = diagnostics;
    root.append(detail);
  }
  printers.forEach(p => {
    const row = document.createElement('div'); row.className = 'entry';
    const info = document.createElement('div');
    const title = document.createElement('strong'); title.textContent = p.name || 'Adventurer 5M';
    const meta = document.createElement('div'); meta.className = 'muted'; meta.textContent = 'Adventurer 5M · ' + p.address;
    info.append(title, meta);
    const pick = document.createElement('button'); pick.textContent = 'Select';
    pick.addEventListener('click', () => {
      $('model').value = 'ad5m';
      $('name').value = p.name || 'Adventurer 5M';
      $('address').value = p.address;
      $('scanstatus').textContent = 'Selected ' + (p.name || 'Adventurer 5M') + '. Review the details below.';
      $('status').textContent = 'Printer selected. Click Save printer to store it locally.';
      $('addpanel').scrollIntoView({behavior:'smooth', block:'start'});
      $('address').focus();
    });
    row.append(info, pick); root.append(row);
  });
}
function stopMonitoring(notify = true) {
  if (refreshTimer !== null) { clearInterval(refreshTimer); refreshTimer = null; }
  monitoring = false; pending = false; activeSession++;
  $('connect').disabled = false; $('stop').disabled = true; $('refresh').disabled = true;
  if (notify) { send({command:'stop_monitoring'}); $('livestatus').textContent = 'Monitoring stopped.'; }
}
function requestStatus() {
  if (!monitoring || pending) return;
  pending = true;
  send({command:'read_status', id:$('activeprinter').value, session:activeSession});
}
$('connect').addEventListener('click', () => {
  const id = $('activeprinter').value, code = $('checkcode').value.trim();
  if (!id || !code) { $('livestatus').textContent = 'Choose a saved printer and enter its check code.'; return; }
  stopMonitoring(false);
  monitoring = true; pending = true;
  $('connect').disabled = true; $('stop').disabled = false; $('refresh').disabled = false;
  $('livestatus').textContent = 'Connecting…'; $('lastupdate').textContent = '';
  $('statusdetails').replaceChildren();
  send({command:'start_monitoring', id, check_code:code, session:activeSession});
  $('checkcode').value = '';
  refreshTimer = setInterval(requestStatus, 5000);
});
$('stop').addEventListener('click', () => stopMonitoring());
$('refresh').addEventListener('click', requestStatus);
$('activeprinter').addEventListener('change', () => { if (monitoring) stopMonitoring(); });
function showStatus(msg) {
  if (!monitoring || msg.session !== activeSession) return;
  pending = false;
  $('livestatus').textContent = msg.message || '';
  const root = $('statusdetails');
  if (!msg.status) return;
  $('lastupdate').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
  root.replaceChildren();
  const dash = document.createElement('div'); dash.className = 'dash';
  const fields = [['State',msg.status.state], ['Nozzle',msg.status.nozzle],['Bed',msg.status.bed],
                  ['Progress',msg.status.progress],['File',msg.status.file],['Firmware',msg.status.firmware]];
  fields.forEach(([label,value]) => {
    if (value === null || value === undefined || value === '') return;
    const tile = document.createElement('div'); tile.className = 'tile';
    const heading = document.createElement('div'); heading.className = 'muted'; heading.textContent = label;
    const val = document.createElement('div'); val.className = 'value'; val.textContent = String(value);
    tile.append(heading,val); dash.append(tile);
  });
  root.append(dash);
  const number = Number.parseFloat(msg.status.progress);
  if (Number.isFinite(number)) {
    const bar = document.createElement('progress'); bar.max = 100; bar.value = Math.max(0,Math.min(100,number));
    bar.setAttribute('aria-label','Print progress'); root.append(bar);
  }
}
function render(printers) {
  const active = $('activeprinter');
  const selected = active.value;
  active.replaceChildren();
  const placeholder = document.createElement('option'); placeholder.value = ''; placeholder.textContent = 'Choose a printer';
  active.append(placeholder);
  printers.forEach(p => {
    const option = document.createElement('option'); option.value = p.id; option.textContent = p.name;
    active.append(option);
  });
  if (printers.some(p => p.id === selected)) active.value = selected;
  else if (printers.length === 1) active.value = printers[0].id;
  const root = $('printers'); root.replaceChildren();
  if (!printers.length) { root.textContent = 'No printers added yet.'; return; }
  printers.forEach(p => {
    const row = document.createElement('div'); row.className = 'entry';
    const details = document.createElement('div');
    const title = document.createElement('strong'); title.textContent = p.name;
    const meta = document.createElement('div'); meta.className = 'muted';
    meta.textContent = 'Adventurer 5M · ' + p.address;
    details.append(title, meta);
    const remove = document.createElement('button'); remove.textContent = 'Remove';
    remove.addEventListener('click', () => send({command:'remove', id:p.id}));
    row.append(details, remove); root.append(row);
  });
}
if (window.orca && window.orca.onMessage) {
  window.orca.onMessage(msg => {
    if (msg.command === 'printers') { if (monitoring && !(msg.printers || []).some(p => p.id === $('activeprinter').value)) stopMonitoring(); render(msg.printers || []); $('status').textContent = msg.message || ''; }
    if (msg.command === 'error') $('status').textContent = msg.message || 'Invalid input';
    if (msg.command === 'discovered') showDiscovered(msg.printers || [], msg.error || '', msg.diagnostics || '');
    if (msg.command === 'status_result') showStatus(msg);
    if (msg.command === 'probe_result') { $('probe').disabled = false; $('probestatus').textContent = msg.message || 'Test completed.'; }
    if (msg.command === 'udpdiag_result') { $('udpdiag').disabled = false; $('udpstatus').textContent = msg.message || 'UDP test completed.'; }
  });
}
send({command:'list'});
</script></body></html>"""


def validate_ipv4(value):
    """Accept only private, non-loopback IPv4 addresses in this prototype."""
    try:
        addr = ipaddress.IPv4Address(str(value).strip())
    except ipaddress.AddressValueError:
        raise ValueError("Enter a valid IPv4 address.")
    if not addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_unspecified:
        raise ValueError("Use a private LAN IPv4 address (for example 192.168.x.x).")
    return str(addr)


class PrinterManager(orca.script.ScriptPluginCapabilityBase):
    def __init__(self):
        super().__init__()
        self.printers = []
        self.load_error = None
        self.config_path = self.get_config_path()
        self.load_printers()
        self.win = None
        self.scanning = False
        self.probing = False
        self.udp_testing = False
        self.reading_status = False
        self.discovered_serials = {}
        self.monitoring = None
        self.monitor_generation = 0

    @staticmethod
    def get_config_path():
        """Store non-secret settings in a user-owned application support folder."""
        if sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        elif os.name == "nt":
            base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        return base / "orca-flashforge-plugin" / "printers.json"

    def load_printers(self):
        """Reject malformed config rather than silently replacing it."""
        if not self.config_path.exists():
            return
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("schema_version") != 1:
                raise ValueError("Unsupported printer configuration format.")
            entries = raw.get("printers")
            if not isinstance(entries, list) or len(entries) > 100:
                raise ValueError("Invalid printer list.")
            validated = []
            seen = set()
            for item in entries:
                if not isinstance(item, dict) or item.get("model") != "ad5m":
                    raise ValueError("Invalid printer entry.")
                address = validate_ipv4(item.get("address", ""))
                name = item.get("name")
                ident = item.get("id")
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
                    raise ValueError("Invalid printer name.")
                if not isinstance(ident, str) or len(ident) != 32 or any(c not in "0123456789abcdef" for c in ident):
                    raise ValueError("Invalid printer identifier.")
                if address in seen:
                    raise ValueError("Duplicate printer address.")
                seen.add(address)
                validated.append({"id": ident, "model": "ad5m", "name": name.strip(), "address": address})
            self.printers = validated
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.load_error = "Saved printer settings could not be loaded. The existing file was not changed."

    def save_printers(self, entries):
        """Atomic, user-private config write. No pairing credentials."""
        parent = self.config_path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".printers-", suffix=".tmp", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                os.chmod(temporary, 0o600)
                json.dump({"schema_version": 1, "printers": entries}, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.config_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def get_name(self):
        return "Manage FlashForge Printers"

    def execute(self):
        self.monitoring = None
        self.monitor_generation += 1
        if self.win is not None and self.win.is_open():
            self.win.close()
        self.win = orca.host.ui.create_window(
            title="Orca FlashForge Plugin",
            html=PAGE,
            width=740,
            height=760,
            on_message=self.on_message,
        )
        return orca.ExecutionResult.success("FlashForge printer manager opened.")

    def post_list(self, message=""):
        if self.load_error:
            message = self.load_error + (" " + message if message else "")
        if self.win is not None:
            self.win.post({"command": "printers", "printers": self.printers, "message": message})

    @staticmethod
    def local_scan_targets():
        """Only probe private, directly attached IPv4 networks, capped at /24."""
        targets = set()
        for adapter in ifaddr.get_adapters():
            for entry in adapter.ips:
                if not entry.is_IPv4 or not isinstance(entry.ip, str):
                    continue
                try:
                    ip = ipaddress.IPv4Address(entry.ip)
                    prefix = entry.network_prefix
                    if not ip.is_private or ip.is_loopback or ip.is_link_local:
                        continue
                    if not isinstance(prefix, int) or not 1 <= prefix <= 30:
                        continue
                    attached = ipaddress.IPv4Network((ip, prefix), strict=False)
                    subnet = attached if attached.prefixlen >= 24 else ipaddress.IPv4Network((ip, 24), strict=False)
                    targets.update(str(host) for host in subnet.hosts() if host != ip)
                except (ValueError, TypeError):
                    continue
        return sorted(targets, key=lambda x: int(ipaddress.IPv4Address(x)))[:512]

    @staticmethod
    def targeted_subnet_discovery(targets):
        """Read-only UDP discovery, bounded to local subnet addresses."""
        if not targets:
            return [], 0
        parser = PrinterDiscovery()
        found = {}
        raw_responses = 0
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("0.0.0.0", 0))
            sock.settimeout(0.2)
            for address in targets:
                for port in (48899, 19000):
                    try:
                        sock.sendto(b"", (address, port))
                    except OSError:
                        pass
            deadline = time.monotonic() + 5.0
            allowed = set(targets)
            while time.monotonic() < deadline:
                try:
                    payload, peer = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if peer[0] not in allowed:
                    continue
                raw_responses += 1
                try:
                    printer = parser.parse_discovery_response(payload, peer[0])
                    if printer is not None:
                        found[peer[0]] = printer
                except Exception:
                    continue
        return list(found.values()), raw_responses

    def discover_worker(self):
        try:
            options = DiscoveryOptions(timeout=6000, idle_timeout=6000, max_retries=1)
            results = asyncio.run(PrinterDiscovery().discover(options))
            broadcast_count = len(results)
            targets = []
            raw_responses = 0
            if not any(p.model == PrinterModel.ADVENTURER_5M for p in results):
                targets = self.local_scan_targets()
                additional, raw_responses = self.targeted_subnet_discovery(targets)
                results.extend(additional)
            matches = []
            seen = set()
            model_counts = {}
            for printer in results:
                model = str(printer.model.value)
                model_counts[model] = model_counts.get(model, 0) + 1
                if printer.model != PrinterModel.ADVENTURER_5M:
                    continue
                try:
                    address = validate_ipv4(printer.ip_address)
                except ValueError:
                    continue
                if address in seen:
                    continue
                seen.add(address)
                if printer.serial_number:
                    self.discovered_serials[address] = str(printer.serial_number)
                matches.append({"name": str(printer.name or "Adventurer 5M")[:60], "address": address})
            diagnostics = (
                "Broadcast: " + str(broadcast_count) + " parsed. Fallback: " +
                str(len(targets)) + " local addresses probed, " +
                str(raw_responses) + " UDP replies. Models: " +
                (", ".join(str(k) + " (" + str(v) + ")" for k, v in sorted(model_counts.items()))
                 if model_counts else "none") + "."
            )
            if self.win is not None and self.win.is_open():
                self.win.post({"command": "discovered", "printers": matches, "diagnostics": diagnostics})
        except Exception as exc:
            if self.win is not None and self.win.is_open():
                self.win.post({"command": "discovered", "printers": [],
                               "error": "Discovery failed. You can still add a printer manually.",
                               "diagnostics": "Error type: " + type(exc).__name__})
        finally:
            self.scanning = False

    def probe_worker(self, address):
        try:
            address = validate_ipv4(address)
            results = []
            for port in (8898, 8899):
                try:
                    with socket.create_connection((address, port), timeout=2.0):
                        results.append("TCP " + str(port) + ": reachable")
                except (OSError, TimeoutError):
                    results.append("TCP " + str(port) + ": no connection")
            message = " | ".join(results) + ". This tests connectivity only, not pairing."
        except ValueError as exc:
            message = str(exc)
        except Exception:
            message = "Connectivity test failed unexpectedly."
        finally:
            self.probing = False
        try:
            if self.win is not None and self.win.is_open():
                self.win.post({"command": "probe_result", "message": message})
        except Exception:
            pass

    def udp_diag_worker(self, address):
        """Send opt-in read-only discovery datagrams to one supplied LAN host."""
        try:
            address = validate_ipv4(address)
            received = []
            sent = []
            # The upstream discovery implementation sends empty datagrams.
            # A legacy FlashForge discovery implementation also documents this probe.
            legacy_probe = bytes.fromhex("7777772e757372226536c0000000000000000000")
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(("0.0.0.0", 0))
                sock.settimeout(0.4)
                for port in (48899, 8899, 19000):
                    for payload in (b"", legacy_probe):
                        try:
                            sock.sendto(payload, (address, port))
                            sent.append(str(port) + ("/empty" if not payload else "/legacy"))
                        except OSError:
                            continue
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline:
                    try:
                        data, peer = sock.recvfrom(4096)
                        if peer[0] == address:
                            received.append((len(data), peer[1]))
                    except socket.timeout:
                        continue
            if received:
                message = ("UDP replies from target: " + str(len(received)) +
                           "; packet sizes/source ports: " +
                           ", ".join(str(size) + "B/" + str(port) for size, port in received[:8]))
            else:
                message = "No UDP replies from this printer after " + str(len(sent)) + " targeted discovery probes."
        except ValueError as exc:
            message = str(exc)
        except OSError:
            message = "UDP socket error. Check local network access."
        except Exception:
            message = "UDP diagnostic failed unexpectedly."
        finally:
            self.udp_testing = False
        try:
            if self.win is not None and self.win.is_open():
                self.win.post({"command": "udpdiag_result", "message": message})
        except Exception:
            pass

    @staticmethod
    def lookup_serial(address):
        """Read serial from a targeted UDP discovery reply, never from a file."""
        parser = PrinterDiscovery()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("0.0.0.0", 0))
            sock.settimeout(0.3)
            for port in (48899, 19000):
                sock.sendto(b"", (address, port))
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                try:
                    payload, peer = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                if peer[0] != address:
                    continue
                printer = parser.parse_discovery_response(payload, address)
                if printer and printer.model == PrinterModel.ADVENTURER_5M and printer.serial_number:
                    return str(printer.serial_number)
        return None

    def status_worker(self, printer, check_code, session, generation):
        try:
            address = validate_ipv4(printer["address"])
            serial = self.discovered_serials.get(address) or self.lookup_serial(address)
            if not serial:
                raise ValueError("Could not identify printer serial via LAN discovery. Try Discover printers first.")
            async def read():
                client = FlashForgeClient(address, serial, check_code)
                try:
                    info = await asyncio.wait_for(client.info.get(), timeout=12)
                    if info is None:
                        return None
                    def temp(value):
                        if value is None:
                            return None
                        return str(round(float(value.current), 1)) + "°C / " + str(round(float(value.set), 1)) + "°C target"
                    return {
                        "state": str(info.status or ""),
                        "nozzle": temp(info.extruder),
                        "bed": temp(info.print_bed),
                        "progress": str(info.print_progress_int) + "%",
                        "file": str(info.print_file_name or ""),
                        "firmware": str(info.firmware_version or ""),
                    }
                finally:
                    await client.dispose()
            result = asyncio.run(read())
            if result is None:
                response = {"command": "status_result", "message": "Printer did not return readable status. Check its check code."}
            else:
                response = {"command": "status_result", "message": "Read-only status received.", "status": result}
        except ValueError as exc:
            response = {"command": "status_result", "message": str(exc)}
        except Exception as exc:
            response = {"command": "status_result", "message": "Status request failed (" + type(exc).__name__ + "). Check the code and network."}
        finally:
            check_code = None
            self.reading_status = False
        try:
            if self.monitoring is not None and self.monitor_generation == generation and self.win is not None and self.win.is_open():
                response["session"] = session
                self.win.post(response)
        except Exception:
            pass

    def on_message(self, msg):
        msg = msg or {}
        command = msg.get("command")
        if command == "list":
            self.post_list()
        elif command == "discover":
            if not self.scanning:
                self.scanning = True
                threading.Thread(target=self.discover_worker, daemon=True).start()
        elif command == "start_monitoring":
            ident = msg.get("id")
            printer = next((p for p in self.printers if p["id"] == ident), None)
            code = msg.get("check_code")
            session = msg.get("session")
            if printer is None or not isinstance(code, str) or not 1 <= len(code) <= 64 or not isinstance(session, int):
                self.win.post({"command": "status_result", "session": session, "message": "Invalid printer or check code."})
                return
            self.monitor_generation += 1
            self.monitoring = {"id": ident, "code": code, "session": session}
            if not self.reading_status:
                self.reading_status = True
                threading.Thread(target=self.status_worker, args=(printer.copy(), code, session, self.monitor_generation), daemon=True).start()
        elif command == "stop_monitoring":
            self.monitor_generation += 1
            self.monitoring = None
        elif command == "read_status":
            session = msg.get("session")
            monitor = self.monitoring
            if self.reading_status or monitor is None or monitor["id"] != msg.get("id") or monitor["session"] != session:
                return
            printer = next((p for p in self.printers if p["id"] == monitor["id"]), None)
            if printer is None:
                return
            self.reading_status = True
            threading.Thread(target=self.status_worker, args=(printer.copy(), monitor["code"], session, self.monitor_generation), daemon=True).start()
        elif command == "probe":
            if not self.probing:
                self.probing = True
                threading.Thread(target=self.probe_worker, args=(msg.get("address", ""),), daemon=True).start()
        elif command == "udpdiag":
            if not self.udp_testing:
                self.udp_testing = True
                threading.Thread(target=self.udp_diag_worker, args=(msg.get("address", ""),), daemon=True).start()
        elif command == "add":
            try:
                if msg.get("model") != "ad5m":
                    raise ValueError("Unsupported printer model.")
                name = str(msg.get("name", "")).strip()
                if not 1 <= len(name) <= 60:
                    raise ValueError("Display name must contain 1–60 characters.")
                address = validate_ipv4(msg.get("address", ""))
                if any(p["address"] == address for p in self.printers):
                    raise ValueError("This printer address is already in the list.")
                if self.load_error:
                    raise ValueError("Cannot save while the existing configuration cannot be loaded.")
                updated = self.printers + [{
                    "id": uuid.uuid4().hex,
                    "model": "ad5m",
                    "name": name,
                    "address": address,
                }]
                self.save_printers(updated)
                self.printers = updated
                self.post_list("Printer saved on this Mac.")
            except (ValueError, OSError) as exc:
                message = str(exc) if isinstance(exc, ValueError) else "Could not write local printer settings."
                self.win.post({"command": "error", "message": message})
        elif command == "remove":
            target = msg.get("id")
            if self.load_error:
                self.post_list()
                return
            updated = [p for p in self.printers if p["id"] != target]
            if len(updated) == len(self.printers):
                self.post_list("Printer not found.")
                return
            try:
                self.save_printers(updated)
                self.printers = updated
                self.post_list("Saved printer removed.")
            except OSError:
                self.post_list("Could not update local printer settings.")


@orca.plugin
class FlashForgePlugin(orca.base):
    def register_capabilities(self):
        orca.register_capability(PrinterManager)
