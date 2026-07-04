# Dio Spec Reference

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-07-04 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Payload reference for configuring the Dio module through RTD CfgFile CLI structured spec input. |

Read this file only when authoring or reviewing a `dio set --spec` payload.

## Command

```text
rtd-config dio set --project <dir> --spec <module-config.json> --configure --json
```

The spec may use the common envelope:

```json
{"module": "dio", "action": "set", "payload": {}}
```

## Payload

| Field | Type | Notes |
| --- | --- | --- |
| `add_channel` | string | Dio channel name to add. |
| `pin` | string | GPIO pad for the channel. |
| `direction` | string | Currently `output`. |

## Example

```json
{
  "module": "dio",
  "action": "set",
  "payload": {
    "add_channel": "LED_CTRL",
    "pin": "PTA5",
    "direction": "output"
  }
}
```

## Notes

Dio owns the Dio channel. The provider creates the pin's `DioPort` container
when absent and configures the related Port-side GPIO direction automatically.

## Diagnostics

- `dio_config_set_not_found` means the target Dio configuration set was not found.
- `port_illegal_pin` can appear when the requested GPIO pad cannot be configured.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-04 | 0.1.0 | Created Dio structured spec reference. |
