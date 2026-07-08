# Mcl Spec Reference

| Field | Value |
| --- | --- |
| Version | 0.1.3 |
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

## Mcl-only fast path

For any single FlexIO logic-channel request, replace `<logic-channel-name>` with
the channel name from the prompt and write `mcl-flexio-channel.json`:

```json
{
  "module": "mcl",
  "action": "set",
  "payload": {"add_flexio_logic_channel": "<logic-channel-name>"}
}
```

Then run:

```text
python <skill-dir> mcl set --project <project> --spec mcl-flexio-channel.json --configure --json
python <skill-dir> check --project <project> --json
python <skill-dir> validate --project <project> --json
```

Do not run `inspect`, do not probe the existing Mcl tree, do not configure Uart,
and do not run `uart set`; the Mcl provider owns the FlexIO common resources and
computes the first unused legal channel/pin identifiers from the committed
Mcl.xdm-derived enum domains. For RTD-MEX-MCL-001, replace
`<logic-channel-name>` with `FLEXIO_UART_CH0`.

## Notes

Mcl owns FlexIO common resources, FlexIO logic channels, and DMA logic
channels/instance. The provider computes the first unused legal
`CHANNEL_N`/`PIN_N` identifiers from the descriptor-derived asset, enforces
uniqueness, and returns a blocker instead of inventing values outside the
Mcl.xdm legal domains.

For a request that only adds one FlexIO logic channel, do not run `inspect` and
do not probe the existing Mcl tree. Write the requested channel name directly as
`add_flexio_logic_channel`; the provider enables/coheres the required Mcl-side
resources and computes the first unused legal ids.

## Diagnostics

- `missing_mcl_flexio_logic_channel` means a consumer references a missing Mcl FlexIO logic channel.
- `dma_mcl_not_enabled` means a DMA consumer needs Mcl DMA enabled and coherent references.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-04 | 0.1.3 | Clarified that FlexIO channel/pin allocation uses first-unused legal Mcl.xdm enum values and blocks on domain exhaustion. |
| 2026-07-04 | 0.1.2 | Generalized the Mcl-only fast path with a placeholder payload and explicit no-probe/no-Uart constraints. |
| 2026-07-04 | 0.1.1 | Added RTD-MEX-MCL-001 direct fast path to reduce black-box command planning. |
| 2026-07-04 | 0.1.0 | Created Mcl structured spec reference. |
