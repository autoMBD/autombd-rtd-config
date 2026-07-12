# ADC Spec Reference

| Field | Value |
| --- | --- |
| Version | 0.1.1 |
| Date | 2026-07-12 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Payload reference for configuring the Adc module through RTD CfgFile CLI structured spec input. |

Read this file only when authoring or reviewing an `adc set --spec` payload.

## Command

```text
rtd-config adc set --project <dir> --spec <module-config.json> --configure --json
```

The spec may use the common envelope:

```json
{"module": "adc", "action": "set", "payload": {}}
```

For compatibility, ADC also accepts the raw payload object directly.

## Single-unit Payload

| Field | Type | Notes |
| --- | --- | --- |
| `unit` | string | Target ADC unit, for example `ADC1`. |
| `transfer` | string | `interrupt` or `dma`. |
| `sampling_time_us` | number | Requested sampling time in microseconds. The provider derives `AdcSamplingDuration`. |
| `groups` | array | Conversion groups. |
| `watchdog` | array | Optional per-channel watchdog thresholds. |
| `bctu` | object | Optional BCTU hardware trigger block. |

Group fields: `name`, `trigger`, `access`, `conv`, `num_samples`,
`notification`, and `channels`.

Watchdog fields: `channel`, `high`, `low`, and `notification`.

## Single-unit Example

```json
{
  "module": "adc",
  "action": "set",
  "payload": {
    "unit": "ADC1",
    "transfer": "interrupt",
    "sampling_time_us": 1,
    "groups": [
      {
        "name": "AdcGroup_0",
        "trigger": "sw",
        "access": "single",
        "conv": "oneshot",
        "num_samples": 1,
        "notification": "Autombd_AdcNotifi0",
        "channels": ["VREFL", "S10"]
      },
      {
        "trigger": "sw",
        "access": "streaming",
        "conv": "continuous",
        "num_samples": 10,
        "notification": "Autombd_AdcNotifi1",
        "channels": ["VREFH", "P5"]
      }
    ],
    "watchdog": [
      {
        "channel": "P5",
        "high": 3000,
        "low": 20,
        "notification": "Autombd_AdcNotifiWdg"
      }
    ]
  }
}
```

## Multi-unit Payload

Use `units` instead of `unit` for cases that configure more than one ADC unit.
Each item contains `unit` and `sampling_time_us`.

## Token Domains

- `transfer`: `interrupt`, `dma`
- `trigger`: `sw`, `hw`
- `access`: `single`, `streaming`
- `conv`: `oneshot`, `continuous`
- Channels accept short names such as `VREFL`, `S10`, and `P5`, or full literals such as `S10_ChanNum34`.
- S-channels start at `S8`; there is no `S0` through `S7`.

The provider resolves channel name to id, derives sampling duration, selects the
smallest valid prescaler, adds the unit `AdcHwConfiguration`, flips
`AdcEnableWatchdogApi` when watchdog thresholds are requested, and coerces a
software-triggered streaming one-shot group to continuous because the vendor
model requires that combination.

## BCTU Hardware Trigger

Add a `bctu` object to wire a Body Cross-Triggering Unit trigger. The provider
repoints `AdcHwTrigger_0`, populates the `BctuHwUnit` subtree, and flips the
required gating APIs: `AdcHwTriggerApi`, `AdcEnableCtuControlModeApi`, and, for
FIFO DMA, `CtuEnableDmaTransferMode`.

Single mode fields: `trigger_source`, `mode`, `target`, `channel`,
`destination`, and `new_data_notification`.

For a BCTU single-conversion trigger, the `channel` must also be present in one
of the target unit's `groups`. Do not author a BCTU-only payload: the provider
will block it with `adc_bctu_channel_not_on_unit` because the trigger cannot
reference a channel that the unit does not own. Use a one-shot hardware group
for the BCTU channel when the user prompt does not request another group.

```json
{
  "module": "adc",
  "action": "set",
  "payload": {
    "unit": "ADC1",
    "transfer": "interrupt",
    "sampling_time_us": 2,
    "groups": [
      {
        "name": "AdcGroup_0",
        "trigger": "hw",
        "access": "single",
        "conv": "oneshot",
        "num_samples": 1,
        "channels": ["S10"]
      }
    ],
    "bctu": {
      "trigger_source": "BCTU_EMIOS_2_15",
      "mode": "single",
      "target": "ADC1",
      "channel": "S10",
      "destination": "data_reg",
      "new_data_notification": "Autombd_BctuNewDataNotifi"
    },
    "watchdog": [
      {
        "channel": "S10",
        "high": 3000,
        "low": 20,
        "notification": "Autombd_AdcNotifiWdg"
      }
    ]
  }
}
```

List mode fields: `trigger_source`, `mode`, `targets`, `list`,
`trigger_order`, `destination`, `fifo_dma`, and `fifo_notification`.

```json
{
  "module": "adc",
  "action": "set",
  "payload": {
    "units": [
      {"unit": "ADC1", "sampling_time_us": 5},
      {"unit": "ADC2", "sampling_time_us": 6}
    ],
    "transfer": "interrupt",
    "bctu": {
      "trigger_source": "BCTU_EMIOS_1_20",
      "mode": "list",
      "targets": ["ADC1", "ADC2"],
      "list": ["VREFH", "VREFL", "S20", "S20", "P1", "P2", "P3", "P4"],
      "trigger_order": [2, 2, 4],
      "destination": "fifo1",
      "fifo_dma": true,
      "fifo_notification": "Autombd_BctuFifoNotifi"
    }
  }
}
```

BCTU token domains:

- `trigger_source`: `BCTU_EMIOS_{0,1,2}_{0..22}`, `EXT_TRIG`, or `AUX_EXT_TRIG`
- `mode`: `single`, `list`
- `destination`: `data_reg`, `fifo1`, `fifo2`

`trigger_order` partitions the list and its parts must sum to the list length.
When `fifo_dma` is true, the provider disables FIFO interrupt notifications,
sets the watermark so the final sample of the batch raises the request, and
declares the required Mcl DMA dependency.

## Notes

Adc owns the `AdcHwUnit` configuration tree, `AdcHwConfiguration` entries, and
the global `AdcEnableWatchdogApi` switch inside `<config_set name="Adc">`.
Interrupt mode is internal to the ADC peripheral for interrupt software groups;
it does not imply a Platform IRQ dependency.

## Diagnostics

- `adc_channel_not_in_device` means a channel name is not in the device enum.
- `adc_sampling_out_of_range` means the requested sampling time cannot be encoded as a valid duration.
- `adc_interrupt_not_enabled` means an interrupt-transfer unit lacks `AdcNormalInterruptEnable=true`.
- `adc_watchdog_api_disabled`, `adc_unit_wdg_threshold_disabled`, `adc_threshold_ref_incomplete`, and `adc_watchdog_notification_invalid` identify watchdog coherence gaps.
- `adc_dma_mcl_not_enabled` and `adc_dma_refs_incomplete` identify DMA dependency gaps.
- `adc_bctu_trigger_source_not_in_device`, `adc_bctu_channel_not_in_device`, and `adc_bctu_list_channel_not_in_device` identify invalid BCTU tokens.
- `adc_bctu_trigger_order_mismatch` means the `trigger_order` parts do not sum to the list length.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-12 | 0.1.1 | Clarified BCTU single-trigger payloads: the target channel must be present in the target unit's groups, and the example now shows the complete ADC1/S10 BCTU + watchdog payload to avoid a diagnostic-driven second edit attempt. |
| 2026-07-04 | 0.1.0 | Created ADC structured spec reference. |
