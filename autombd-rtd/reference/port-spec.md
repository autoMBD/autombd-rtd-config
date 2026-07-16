# Port Spec Reference

| Field | Value |
| --- | --- |
| Version | 0.2.0 |
| Date | 2026-07-16 |
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

## One-query pin selection fast path

Run `pin-options` exactly once before writing the payload:

```text
rtd-config pin-options --bundle-id nxp-s32-mex-s32k344-mapbga257-rtd-7.0.1 --peripheral <peripheral> --json
```

The command returns an `options` array. Select the requested transmit pin from
the item whose `options[].signal` is `TX`, and the receive pin from the item
whose `options[].signal` is `RX`; copy each selected `options[].pin` value into
`payload.pins.tx` or `payload.pins.rx`. The CLI/provider rechecks the selected
pair against the same committed bundle during configuration, so never guess a
pin or bypass a blocked diagnostic.

Do not run `pin-options --help`. Do not run `inspect`, pass `--project` to
`pin-options`, or retry partial selector combinations. The released Skill
already identifies the complete asset bundle. After the one query, write the
spec and run the direct flow:

```text
rtd-config port set --project <dir> --spec <module-config.json> --configure --json
rtd-config check --project <dir> --json
rtd-config validate --project <dir> --json
```

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
| 2026-07-16 | 0.2.0 | Added the complete bundle-id pin query and direct one-query Port fast path. |
| 2026-07-04 | 0.1.0 | Created Port structured spec reference. |
