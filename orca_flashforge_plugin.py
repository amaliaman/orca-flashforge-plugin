# /// script
# requires-python = ">=3.12"
#
# [tool.orcaslicer.plugin]
# name = "Orca FlashForge Plugin"
# description = "Prototype: validate OrcaSlicer plugin loading and host UI."
# author = "Community contributors"
# version = "0.1.0"
# ///
"""Safe, offline-only smoke test for the OrcaSlicer Python plugin host.

No network calls, device commands, filesystem writes or background processes.
Based on OrcaSlicer's official Orca Inspector script-plugin example.
"""

import orca


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { font: 15px system-ui, sans-serif; margin: 28px;
         color: var(--orca-text, #e5e7eb);
         background: var(--orca-bg, #20242b); }
  .panel { border: 1px solid var(--orca-border, #555);
           border-radius: 12px; padding: 22px; }
  h1 { margin-top: 0; font-size: 21px; }
  p { line-height: 1.5; }
</style>
</head>
<body>
  <main class="panel">
    <h1>Plugin loaded successfully</h1>
    <p>Orca FlashForge Plugin v0.1.0</p>
    <p>This is a safe installation test. No printer connection has been made.</p>
  </main>
</body>
</html>"""


class FlashForgeSmokeTest(orca.script.ScriptPluginCapabilityBase):
    def get_name(self):
        return "Open FlashForge Plugin Test"

    def execute(self):
        orca.host.ui.create_window(
            title="Orca FlashForge Plugin",
            html=PAGE,
            width=560,
            height=340,
        )
        return orca.ExecutionResult.success("FlashForge plugin test opened.")


@orca.plugin
class FlashForgePlugin(orca.base):
    def register_capabilities(self):
        orca.register_capability(FlashForgeSmokeTest)
