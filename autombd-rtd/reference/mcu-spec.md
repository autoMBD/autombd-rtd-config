# MCU Spec Reference

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-07-04 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Payload reference for configuring the Mcu module through RTD CfgFile CLI structured spec input. |

Read this file only when authoring or reviewing an `mcu set --spec` payload.

## Command

```text
rtd-config mcu set --project <dir> --spec <module-config.json> --configure --json
```

The spec may use the common envelope:

```json
{"module": "mcu", "action": "set", "payload": {}}
```

## Payload

| Field | Type | Notes |
| --- | --- | --- |
| `core_clk` | number | Core clock target in MHz. |
| `aips_plat_clk` | number | AIPS platform clock target in MHz. |
| `aips_slow_clk` | number | AIPS slow clock target in MHz. |
| `add_all_clock_reference_points` | boolean | Preserve existing reference points and add every selectable S32K344 clock by name. |

## Example

```json
{
  "module": "mcu",
  "action": "set",
  "payload": {
    "core_clk": 160,
    "aips_plat_clk": 80,
    "aips_slow_clk": 40,
    "add_all_clock_reference_points": true
  }
}
```

## Notes

Mcu owns the clock tree and peripheral clock reference points.

`mcu set` writes authoritative clock inputs: PLL configuration, MC_CGM dividers,
and clock reference points. Clocks-view `clock_output` values are a derived
display cache owned by ConfigTools and refreshed when the project is opened in
S32DS or when `validate` generates code. Do not hand-edit derived clock output
values.

## Diagnostics

- `mcu_config_set_not_found` means the target Mcu configuration set was not found.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-04 | 0.1.0 | Created Mcu structured spec reference. |
