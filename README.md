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
