# Port Spec Reference

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-07-04 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Payload reference for configuring the Port module through RTD CfgFile CLI structured spec input. |

Read this file only when authoring or reviewing a `port set --spec` payload.

## Command

```text
rtd-config port set --project <dir> --spec <module-config.json> --configure --json
```

The spec may use the common envelope:

```json
{"module": "port", "action": "set", "payload": {}}
```

## Payload

| Field | Type | Notes |
| --- | --- | --- |
| `peripheral` | string | Peripheral whose TX/RX pins should be routed, for example `LPUART_3`. |
| `pins.tx` | string | TX pin signal name. |
| `pins.rx` | string | RX pin signal name. |

For pin choices, run `rtd-config pin-options --device s32k344 --package default
--peripheral <peripheral> --json` before writing the payload.

## Example

```json
{
  "module": "port",
  "action": "set",
  "payload": {
    "peripheral": "LPUART_3",
    "pins": {
      "tx": "PTB10",
      "rx": "PTB11"
    }
  }
}
```

## Notes

Port owns pin mux, electrical configuration, and direction for routed pins.
Consumers request pins through explicit dependencies.

## Diagnostics

- `port_illegal_pin` means the requested pin is not valid for that peripheral signal.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-04 | 0.1.0 | Created Port structured spec reference. |
