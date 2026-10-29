# Orca FlashForge Plugin

Experimental, community-maintained integration for FlashForge printers in OrcaSlicer.

> **Status: prototype only.** The first plugin verifies OrcaSlicer's Python plugin loader and host-owned UI. It does **not** connect to a printer, start a service, modify the Device tab, or control hardware.

## Compatibility

Initial development target: OrcaSlicer 2.5.0 Beta on macOS Apple Silicon, FlashForge Adventurer 5M with stock firmware in LAN-only mode. Other platforms and printers are not yet tested.

## Install the prototype

1. Download [`orca_flashforge_plugin.py`](orca_flashforge_plugin.py) using GitHub's **Raw** button.
2. In OrcaSlicer, open **Plugins**, use **Install plugin** to select the local Python file.
3. Activate the plugin if needed, then select its **Run** action.
4. A small window should open with the message **Plugin loaded successfully**.

This confirms the basic plugin entry point and UI. It does not yet integrate with the built-in Device tab.

## Design goals

- No firmware modification or OrcaSlicer fork.
- No embedded IP addresses, pairing codes, serial numbers or secrets.
- Local-only network services by default; validate targets and authenticate control operations.
- Camera integration must preserve FlashForge's working OEM-camera handling.
- Prefer documented host APIs over undocumented modifications to OrcaSlicer configuration.
- Review upstream licenses before incorporating third-party code.

## Next milestones

- Verify installation and execution on OrcaSlicer 2.5.0 Beta.
- Determine whether the plugin API can target the existing Device tab.
- Prototype LAN connection and read-only telemetry.
- Add camera and authenticated printer controls.
- Package automatic lifecycle management and onboarding.

## Upstream references

- [OrcaSlicer](https://github.com/OrcaSlicer/OrcaSlicer)
- [OrcaSlicer plugin example](https://github.com/OrcaSlicer/OrcaSlicer/blob/main/sandboxes/orca_inspector_plugin_any.py)
- [FlashForgeUI-Electron](https://github.com/Parallel-7/FlashForgeUI-Electron)

## Security

Do not commit pairing codes, printer identifiers, local configuration files, logs or screenshots containing credentials. Report security issues privately to the maintainer rather than posting credentials in public issues.

## License

MIT. See [LICENSE](LICENSE).


## v0.4.0 — Saved printer profiles (experimental)

The plugin now saves non-secret printer profiles (name, model, IPv4 address and local ID) to a user-owned JSON file. On macOS the location is `~/Library/Application Support/orca-flashforge-plugin/printers.json`; on Windows it uses `%APPDATA%/orca-flashforge-plugin/printers.json`, and on Linux `$XDG_CONFIG_HOME/orca-flashforge-plugin/printers.json` (or `~/.config`). The file is written atomically and, on POSIX systems, with owner-only permissions. No pairing codes, tokens, serial numbers, or printer commands are involved.

After installation, discover a printer, click Select, then Save printer. Close and reopen the plugin or restart OrcaSlicer and check whether the saved printer remains listed. This functionality has not yet been tested on every OrcaSlicer sandbox/runtime and may fail if the plugin runtime prohibits filesystem writes. The plugin will show an error instead of claiming the save succeeded. If a settings file is malformed, it is preserved rather than overwritten.
