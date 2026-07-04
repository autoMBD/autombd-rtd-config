# Mcl Spec Reference

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-07-04 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Payload reference for configuring the Mcl module through RTD CfgFile CLI structured spec input. |

Read this file only when authoring or reviewing an `mcl set --spec` payload.

## Command

```text
rtd-config mcl set --project <dir> --spec <module-config.json> --configure --json
```

The spec may use the common envelope:

```json
{"module": "mcl", "action": "set", "payload": {}}
```

## Payload

| Field | Type | Notes |
| --- | --- | --- |
| `add_flexio_logic_channel` | string | FlexIO logic channel name to append. |

## Example

```json
{
  "module": "mcl",
  "action": "set",
  "payload": {
    "add_flexio_logic_channel": "UART2_TX"
  }
}
```

## Notes

Mcl owns FlexIO common resources, FlexIO logic channels, and DMA logic
channels/instance. The provider computes the next free `CHANNEL_N`/`PIN_N`
identifiers and enforces uniqueness.

For a request that only adds one FlexIO logic channel, do not run `inspect` and
do not probe the existing Mcl tree. Write the requested channel name directly as
`add_flexio_logic_channel`; the provider enables/coheres the required Mcl-side
resources and computes the next ids.

## Diagnostics

- `missing_mcl_flexio_logic_channel` means a consumer references a missing Mcl FlexIO logic channel.
- `dma_mcl_not_enabled` means a DMA consumer needs Mcl DMA enabled and coherent references.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-04 | 0.1.0 | Created Mcl structured spec reference. |
