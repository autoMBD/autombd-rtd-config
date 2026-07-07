# Uart Spec Reference

| Field | Value |
| --- | --- |
| Version | 0.1.2 |
| Date | 2026-07-07 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Payload reference for configuring the Uart module through RTD CfgFile CLI structured spec input. |

Read this file only when authoring or reviewing a `uart set --spec` payload or
using the legacy `uart add-flexio-channel` helper.

## RTD-MEX-UART-002 fast path

For the E2E request to add one FlexIO UART Tx/Rx pair with 8-bit words,
921600 baud, interrupt mode, one stop bit, no parity, and callback
`Autombd_UartCallback`, use the reference-declared compatibility helper
directly:

```text
python <skill-dir> uart add-flexio-channel --project <project> --baud 921600 --word-length 8 --mode interrupt --callback Autombd_UartCallback --configure --json
python <skill-dir> check --project <project> --json
python <skill-dir> validate --project <project> --json
```

Do not create a JSON spec file for this helper path. Do not run `inspect`, do
not run `uart set --help`, do not spawn exploration tasks.
Also do not read CLI source files, list the skill tree, or read bundled assets.
The helper/provider resolves the Uart channels, Mcl FlexIO logic channels,
Platform FlexIO ISR, and Mcu FlexIO clock dependency. If the prompt asks for
`BLACKBOX_RESULT`, emit it immediately after `validate` from the configure,
check, and validate statuses.

## Command

```text
rtd-config uart set --project <dir> --spec <module-config.json> --configure --json
```

The spec may use the common envelope:

```json
{"module": "uart", "action": "set", "payload": {}}
```

## Payload

| Field | Type | Notes |
| --- | --- | --- |
| `hw` | string | Existing hardware channel, such as `LPUART_3` or `FLEXIO_0`. |
| `mode` | string | `interrupt` or `dma`. RTD 7.0.1 has no Uart polling `.mex` value. |
| `baud` | integer | Baud rate. |
| `pins.tx` | string | TX pin. Query `pin-options` before choosing. |
| `pins.rx` | string | RX pin. Query `pin-options` before choosing. |
| `using` | string | `LPUART_IP` or `FLEXIO_IP`. |
| `channel_id` | integer | Uart channel id. |
| `callback` | string | C callback identifier. `NULL_PTR` is rejected. |
| `parity` | string | Provider-supported enum token or shortcut. |
| `stop_bits` | string | Provider-supported enum token or shortcut. |
| `word_length` | string | Provider-supported enum token or shortcut. |
| `priority` | integer | Platform ISR priority. |

## Example

```json
{
  "module": "uart",
  "action": "set",
  "payload": {
    "hw": "LPUART_3",
    "mode": "interrupt",
    "baud": 115200,
    "pins": {
      "tx": "PTB10",
      "rx": "PTB11"
    },
    "using": "LPUART_IP",
    "channel_id": 0,
    "callback": "Autombd_UartCallback",
    "parity": "LPUART_UART_IP_PARITY_DISABLED",
    "stop_bits": "LPUART_UART_IP_ONE_STOP_BIT",
    "word_length": "LPUART_UART_IP_8_BITS_PER_CHAR",
    "priority": 2
  }
}
```

## Modes

Interrupt mode enables and registers the Platform LPUART/FlexIO ISR with the
chosen priority.

DMA mode sets the Uart DMA method, enables `UartDmaEnable`, points Tx/Rx
references at Mcl DMA logic channels, enables `MclEnableDma`, and registers
Platform DMATCD completion ISRs.

## Legacy helper

`rtd-config uart add-flexio-channel` creates a new FlexIO-backed Uart Tx/Rx
channel pair plus two Mcl FlexIO logic channels. It accepts `--baud`,
`--word-length`, `--callback`, `--tx-name`, and `--rx-name`. Prefer `uart set
--spec` for normal module configuration work.

## Notes

Uart owns channel settings and Uart-side references. It declares explicit Mcu,
Port, Platform, and Mcl dependencies as needed.

For a request that already names the hardware instance, communication settings,
mode, and callback, do not run `inspect`, do not run `uart set --help`, and do
not read `assets/nxp/s32k3/uart/uart.json`. Write the payload directly from the
request and this reference; the provider resolves declared dependencies.

## Diagnostics

- `duplicate_lpuart_hw_channel` means two active LPUART channels share one instance.
- `invalid_uart_callback` means the callback is not a valid C identifier.
- `stale_flexio_uart_hw_channel_ref` means a FlexIO Uart reference points at a stale Mcl channel.
- `dma_refs_incomplete` means DMA mode lacks complete Tx/Rx DMA references.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-07 | 0.1.2 | Promoted the RTD-MEX-UART-002 fast path before generic payload guidance. |
| 2026-07-07 | 0.1.1 | Added the RTD-MEX-UART-002 no-exploration fast path for the compatibility helper. |
| 2026-07-04 | 0.1.0 | Created Uart structured spec reference. |
