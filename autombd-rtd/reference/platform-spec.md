# Platform Spec Reference

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-07-04 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Payload reference for configuring the Platform module through RTD CfgFile CLI structured spec input. |

Read this file only when authoring or reviewing a `platform set --spec` payload.

## Command

```text
rtd-config platform set --project <dir> --spec <module-config.json> --configure --json
```

The spec may use the common envelope:

```json
{"module": "platform", "action": "set", "payload": {}}
```

## Payload

| Field | Type | Notes |
| --- | --- | --- |
| `peripheral` | string | Peripheral whose interrupt entry should be configured, for example `LPUART_3`. |
| `isr_name` | string | Exact ISR name. Use this when the peripheral alone is ambiguous. |
| `priority` | integer | ISR priority to write. |

Specify either `peripheral` or `isr_name`.

## Example

```json
{
  "module": "platform",
  "action": "set",
  "payload": {
    "peripheral": "LPUART_3",
    "priority": 2
  }
}
```

## Notes

Platform owns interrupt entries and ISR registration. The provider keeps the
target interrupt enabled when updating priority and registration.

For a Platform-only interrupt request, do not configure Uart and do not read
Uart assets. If the request names a peripheral or ISR and a priority, write
those values directly into the Platform spec and run the standard
`set --spec --configure --json`, `check`, `validate` sequence.

## Diagnostics

- `platform_isr_not_found` means the targeted ISR entry was not found.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-04 | 0.1.0 | Created Platform structured spec reference. |
