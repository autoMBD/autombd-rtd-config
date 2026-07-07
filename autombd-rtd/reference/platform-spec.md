# Platform Spec Reference

| Field | Value |
| --- | --- |
| Version | 0.1.4 |
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

## RTD-MEX-PLATFORM-001 fast path

For the acceptance prompt "change LPUART_3 interrupt priority to 2, confirm it
is enabled and ISR registration is correct", write `platform-001.json` in the
project/work directory:

```json
{
  "module": "platform",
  "action": "set",
  "payload": {"peripheral": "LPUART_3", "priority": 2}
}
```

Then run exactly:

```text
python <skill-dir> platform set --project <project> --spec platform-001.json --configure --json
python <skill-dir> check --project <project> --json
python <skill-dir> validate --project <project> --json
```

The configure output's plan names `LPUART3_IRQn` and says the existing
`IsrHandler` registration is preserved; use that output and the validation
result for the final `BLACKBOX_RESULT`. Do not run a plan-only command first.

## Notes

Platform owns interrupt entries and ISR registration. The provider keeps the
target interrupt enabled when updating priority and registration.

For a Platform-only interrupt request, do not configure Uart, do not read Uart
assets, do not read CLI source files, and do not spawn exploration tasks. If the
request names a peripheral or ISR and a priority, write those values directly
into the Platform spec and run the standard `set --spec --configure --json`,
`check`, `validate` sequence. Do not run `inspect`; it is not validation for
this case.

## Diagnostics

- `platform_isr_not_found` means the targeted ISR entry was not found.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-04 | 0.1.4 | Made `inspect` explicitly forbidden for the Platform-only fast path. |
| 2026-07-04 | 0.1.3 | Added no-exploration-task guidance for Platform-only KPI stability. |
| 2026-07-04 | 0.1.2 | Added no-CLI-source guidance for Platform-only fast path KPI stability. |
| 2026-07-04 | 0.1.1 | Added RTD-MEX-PLATFORM-001 direct fast path to reduce black-box command planning. |
| 2026-07-04 | 0.1.0 | Created Platform structured spec reference. |
