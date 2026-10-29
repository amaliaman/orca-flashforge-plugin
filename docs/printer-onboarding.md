# Printer onboarding design

Status: proposal, not implemented.

## Scope

Initial supported model: FlashForge Adventurer 5M (stock firmware, LAN-only). Keep model support in a registry so other FlashForge models can be added without changing the onboarding flow.

## User flow

1. Open the plugin's printer manager.
2. Choose a model from the supported-printer registry (initially only Adventurer 5M).
3. Discover available printers on the local network **or** manually enter an IP/hostname. Discovery must be opt-in and constrained to local networks.
4. Verify printer identity and model, then request the device's pairing/check code where required.
5. Test a read-only connection and save the printer with a user-chosen display name.
6. Select the active printer for monitoring; multiple configured printers should be supported.
7. Allow edit, disconnect and remove operations without deleting OrcaSlicer printer presets.

## Data model (conceptual)

- `PrinterModel`: stable model ID, display name, protocol/driver identifier, capability flags.
- `PrinterConnection`: random local ID, model ID, friendly name, validated address, secret reference, connection preferences.
- `PrinterState`: runtime-only status, temperatures, progress, camera availability, errors.
- `ActivePrinterSelection`: local reference to one configured printer.

Do not conflate a configured connection with an OrcaSlicer printer preset. Automatic preset binding requires separately verifying the host plugin API.

## Security requirements

- Never commit actual device IPs, serial numbers, pairing codes or logs containing them.
- Store pairing secrets outside Git in OS-protected local storage if available.
- Use loopback-only binding for any companion HTTP service; reject remote browser origins and protect mutating endpoints against CSRF.
- Validate addresses before connecting; prevent arbitrary outbound URL requests.
- Keep discovery opt-in; do not silently scan arbitrary networks.
- Keep camera integration model-specific and avoid forcing the AD5M OEM stream through a generic HTTP camera mode.
- Fail safely when a printer disconnects; avoid issuing queued control commands after reconnect.
- Add printer controls only after read-only status and connection management are tested.

## Milestones

1. Prototype plugin loader (completed in v0.1.0).
2. Printer manager UI with model selection and local configuration.
3. Read-only LAN connectivity and printer discovery.
4. Camera and controls.
5. Device-tab integration or documented alternative, depending on OrcaSlicer's supported APIs.
