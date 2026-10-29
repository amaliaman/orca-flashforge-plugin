# /// script
# requires-python = ">=3.12"
# dependencies = ["flashforge-python-api>=1.6"]
#
# [tool.orcaslicer.plugin]
# name = "Orca FlashForge Plugin"
# description = "Prototype printer manager for FlashForge Adventurer 5M."
# author = "Community contributors"
# version = "0.3.6"
# ///
"""Opt-in LAN UDP discovery. No printer commands or persistent secrets.

Printer entries exist only in memory and disappear when OrcaSlicer restarts.
"""

import ipaddress
import uuid
import asyncio
import threading
import socket
import time

from flashforge.discovery import PrinterDiscovery, DiscoveryOptions, PrinterModel
import ifaddr

import orca

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { font: 14px system-ui, sans-serif; margin: 24px; color: var(--orca-text, #e5e7eb); background: var(--orca-bg, #24272c); }
h1 { font-size: 22px; margin: 0 0 6px; } h2 { font-size: 17px; margin: 0 0 12px; }
p { line-height: 1.5; } .muted { opacity: .72; }
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
<p class="muted">v0.3.6 · LAN discovery prototype · No printer commands</p>
<section class="panel"><h2>Configured printers (temporary)</h2><div id="printers">No printers added yet.</div></section>
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
<p><button class="primary" id="add">Add printer (temporary)</button></p>
<p id="status" role="status" aria-live="polite"></p>
<p class="muted"><small>Entries are kept only in memory. No pairing code is requested or saved. The printer is not contacted.</small></p>
</section>
<script>
const $ = id => document.getElementById(id);
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
      $('status').textContent = 'Printer selected. Click Add printer to add it to the temporary list.';
      $('addpanel').scrollIntoView({behavior:'smooth', block:'start'});
      $('address').focus();
    });
    row.append(info, pick); root.append(row);
  });
}
function render(printers) {
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
    if (msg.command === 'printers') { render(msg.printers || []); $('status').textContent = msg.message || ''; }
    if (msg.command === 'error') $('status').textContent = msg.message || 'Invalid input';
    if (msg.command === 'discovered') showDiscovered(msg.printers || [], msg.error || '', msg.diagnostics || '');
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
        self.win = None
        self.scanning = False
        self.probing = False
        self.udp_testing = False

    def get_name(self):
        return "Manage FlashForge Printers"

    def execute(self):
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

    def on_message(self, msg):
        msg = msg or {}
        command = msg.get("command")
        if command == "list":
            self.post_list()
        elif command == "discover":
            if not self.scanning:
                self.scanning = True
                threading.Thread(target=self.discover_worker, daemon=True).start()
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
                self.printers.append({
                    "id": uuid.uuid4().hex,
                    "model": "ad5m",
                    "name": name,
                    "address": address,
                })
                self.post_list("Printer added to temporary list.")
            except ValueError as exc:
                self.win.post({"command": "error", "message": str(exc)})
        elif command == "remove":
            target = msg.get("id")
            self.printers = [p for p in self.printers if p["id"] != target]
            self.post_list("Printer removed from temporary list.")


@orca.plugin
class FlashForgePlugin(orca.base):
    def register_capabilities(self):
        orca.register_capability(PrinterManager)
