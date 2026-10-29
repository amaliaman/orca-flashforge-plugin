# /// script
# requires-python = ">=3.12"
#
# [tool.orcaslicer.plugin]
# name = "Orca FlashForge Plugin"
# description = "Prototype printer manager for FlashForge Adventurer 5M."
# author = "Community contributors"
# version = "0.2.0"
# ///
"""Experimental printer manager. No network calls, filesystem writes, or commands.

Printer entries exist only in memory and disappear when OrcaSlicer restarts.
"""

import ipaddress
import uuid

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
<p class="muted">v0.2.0 · Local setup prototype · No connection is made yet</p>
<section class="panel"><h2>Configured printers (temporary)</h2><div id="printers">No printers added yet.</div></section>
<section class="panel"><h2>Add printer</h2>
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

    def on_message(self, msg):
        msg = msg or {}
        command = msg.get("command")
        if command == "list":
            self.post_list()
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
