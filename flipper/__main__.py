"""
Flipper Zero standalone CLI entry point.

Usage examples:

    # Show device info
    python -m flipper status

    # Listen for a Sub-GHz signal on 433.92 MHz
    python -m flipper subghz-receive --freq 433920000

    # Transmit a Sub-GHz signal
    python -m flipper subghz-transmit --freq 433920000 --modulation AM270 --data "AB CD EF"

    # Detect an NFC card
    python -m flipper nfc-detect

    # Transmit an IR command (NEC protocol, address 0, command 16)
    python -m flipper ir-transmit --protocol NEC --address 0 --command 16

    # Run an arbitrary CLI command
    python -m flipper run-command --cmd "help"

All commands work in simulated mode when no ``--port`` is supplied.
"""

import argparse
import asyncio
import json
import logging
import sys

from .agent import FlipperAgent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flipper",
        description="Flipper Zero standalone CLI",
    )
    parser.add_argument(
        "--port", default=None,
        help="Serial port (e.g. /dev/ttyACM0).  Omit for simulated mode.",
    )
    parser.add_argument(
        "--log-level", default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Show device info and status")

    # subghz-receive
    rx = sub.add_parser("subghz-receive", help="Capture a Sub-GHz signal")
    rx.add_argument("--freq", type=float, default=433_920_000, help="Frequency in Hz")
    rx.add_argument("--timeout", type=float, default=5.0, help="Timeout in seconds")

    # subghz-transmit
    tx = sub.add_parser("subghz-transmit", help="Transmit a Sub-GHz signal")
    tx.add_argument("--freq", type=float, default=433_920_000)
    tx.add_argument("--modulation", default="RAW")
    tx.add_argument("--data", default="", help="Hex bytes (e.g. 'AB CD EF')")

    # nfc-detect
    sub.add_parser("nfc-detect", help="Detect a nearby NFC card")

    # ir-transmit
    ir = sub.add_parser("ir-transmit", help="Transmit an IR command")
    ir.add_argument("--protocol", default="NEC")
    ir.add_argument("--address", type=int, default=0)
    ir.add_argument("--command", type=int, default=0)

    # bad-usb-type
    but = sub.add_parser("bad-usb-type", help="Type text via Bad USB")
    but.add_argument("--text", required=True)
    but.add_argument("--delay-ms", type=int, default=50)

    # run-command
    rc = sub.add_parser("run-command", help="Run a raw Flipper CLI command")
    rc.add_argument("--cmd", required=True)

    return parser


async def _run(args: argparse.Namespace) -> dict:
    agent = FlipperAgent({"port": args.port})

    task_map = {
        "status": ("status", {}),
        "subghz-receive": (
            "subghz_receive",
            {"frequency_hz": args.freq, "timeout_s": args.timeout}
            if hasattr(args, "freq") else {},
        ),
        "subghz-transmit": (
            "subghz_transmit",
            {
                "frequency_hz": args.freq,
                "modulation": args.modulation,
                "data": args.data,
            },
        ),
        "nfc-detect": ("nfc_detect", {}),
        "ir-transmit": (
            "ir_transmit",
            {
                "protocol": args.protocol,
                "address": args.address,
                "command": args.command,
            },
        ),
        "bad-usb-type": (
            "bad_usb_type",
            {"text": args.text, "delay_ms": args.delay_ms},
        ),
        "run-command": ("run_command", {"command": args.cmd}),
    }

    task_name, params = task_map[args.command]
    results = await agent.run_standalone([{"task": task_name, "params": params}])
    return results[0]


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    result = asyncio.run(_run(args))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
