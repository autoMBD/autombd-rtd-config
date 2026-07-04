# BaseNXP Spec Reference

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-07-04 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Payload reference for configuring the BaseNXP module through RTD CfgFile CLI structured spec input. |

Read this file only when authoring or reviewing a `basenxp set --spec` payload.

## Command

```text
rtd-config basenxp set --project <dir> --spec <module-config.json> --configure --json
```

The spec may use the common envelope:

```json
{"module": "basenxp", "action": "set", "payload": {}}
```

## Payload

| Field | Type | Notes |
| --- | --- | --- |
| `enable_system_timer` | boolean | Enable the OsIf system timer and insert one `OsIfCounterConfig`. |
| `user_mode_support` | boolean | Set BaseNXP-owned OsIfGeneral user-mode support. |
| `dev_error_detect` | boolean | Set BaseNXP-owned OsIfGeneral DET support. |
| `custom_timer` | boolean | Set BaseNXP-owned custom timer selection. |
| `get_user_id` | string | Use `GET_CORE_ID` or the provider-supported custom token. |
| `instance_id` | integer | OsIf instance id, range 0..255. |
| `get_physical_core_id` | boolean | Set physical core id support. |
| `software_semaphore` | boolean | Set software semaphore support. |

## Example

```json
{
  "module": "basenxp",
  "action": "set",
  "payload": {
    "enable_system_timer": true,
    "user_mode_support": true,
    "dev_error_detect": false,
    "custom_timer": false,
    "get_user_id": "GET_CORE_ID",
    "instance_id": 0,
    "get_physical_core_id": true,
    "software_semaphore": false
  }
}
```

## Notes

BaseNXP owns the OsIf system-timer counter and BaseNXP-owned OsIfGeneral
scalars. The OsIf counter is a shared time base for driver timeouts.

## Diagnostics

- `basenxp_config_set_not_found` means the target BaseNXP configuration set was not found.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-04 | 0.1.0 | Created BaseNXP structured spec reference. |
