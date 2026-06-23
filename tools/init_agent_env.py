# =================================================================================
# The MIT License
# MIT许可证
#
# <https://opensource.org/license/mit>
#
# SPDX short identifier / SPDX 短标识符：MIT
#
# Copyright (c) 2026 autoMBD
# 版权所有 (c) 2026 autoMBD
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
# 特此向获得本软件及相关文档（合称"本软件"）副本的任何人免费授予不受限制地利用本软
# 件的许可，包括而不限于：使用、复制、修改、合并、发布、分发、分许可和/或销售本软
# 件副本，并允许本软件的接收者也获得前述许可，但须遵守以下条件：
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
# 以上版权声明及本许可声明应包含在本软件的所有副本或主要部分中。
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALLTHE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# 本软件系"按原样"提供，不包含任何形式的明示或默示保证，包括但不限于适销性、特定
# 目的适用性及不侵权的保证。在任何情况下，无论是在合同、侵权或其他案件中，作者或版
# 权持有人均不对因本软件、或因本软件的使用或其他利用而引起的、引发的或与之相关的任
# 何权利主张、损害赔偿或其他责任承担责任。
# =================================================================================
# Project:     RTD CfgFile CLI <https://github.com/autoMBD/autombd-rtd-config>
# File:        init_agent_env.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-24
# Version:     0.3.0
# Description: Unified structured input collector for Agent environment
#              initialization. Its explicit --gui mode collects target
#              platforms, operation mode, required external dependency paths,
#              and optional skill imports in a tkinter dialog. Outputs
#              deployment-ready JSON and validates pre-collected input.
# =================================================================================

from __future__ import annotations

import argparse
import json
import sys
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUPPORTED_PLATFORMS = ("codex", "claude", "opencode")

PLATFORM_LABELS: dict[str, str] = {
    "codex": "Codex",
    "claude": "Claude",
    "opencode": "OpenCode",
}

# ── validation utilities ──────────────────────────────────────────────


def _verify_s32ds_root(path: str) -> bool:
    if not path:
        return False
    p = Path(path)
    if not p.is_dir():
        return False
    markers = [p / "eclipse", p / "S32DS"]
    return any(m.is_dir() for m in markers)


def _verify_rtd_root(path: str) -> bool:
    if not path:
        return False
    p = Path(path)
    if not p.is_dir():
        return False
    entries = list(p.iterdir())
    rtd_packages = [e for e in entries if e.is_dir() and "_TS_T" in e.name]
    return len(rtd_packages) > 0


def validate_input(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    platforms = data.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        errors.append("'platforms' must be a non-empty list")
    else:
        unknown = [p for p in platforms if p not in SUPPORTED_PLATFORMS]
        if unknown:
            errors.append(
                f"Unknown platforms: {unknown}. Supported: {list(SUPPORTED_PLATFORMS)}"
            )

    mode = data.get("mode")
    if mode not in ("update", "reset"):
        errors.append("'mode' must be 'update' or 'reset'")

    if mode == "reset" and not data.get("reset_confirmed", False):
        errors.append("'reset_confirmed' must be true for reset mode")

    s32ds_path = data.get("s32ds_path")
    if not isinstance(s32ds_path, str) or not _verify_s32ds_root(s32ds_path):
        errors.append("'s32ds_path' must be a verified S32DS installation root")

    rtd_path = data.get("rtd_path")
    if not isinstance(rtd_path, str) or not _verify_rtd_root(rtd_path):
        errors.append("'rtd_path' must be a verified RTD package root")

    return errors


# ── tkinter GUI ────────────────────────────────────────────────────────


class InitDialog(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("RTD CfgFile CLI — Agent Environment Initialization")
        self.resizable(False, False)

        self.result: dict[str, Any] | None = None

        self._platform_vars: dict[str, tk.BooleanVar] = {}
        self._mode_var = tk.StringVar(value="update")
        self._reset_confirmed_var = tk.BooleanVar(value=False)

        self._s32ds_var = tk.StringVar()
        self._rtd_var = tk.StringVar()

        self._import_var = tk.StringVar(value="skip")
        self._import_path_var = tk.StringVar()
        self._import_url_var = tk.StringVar()

        self._build_ui()
        self._on_mode_change()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda _e: self._on_cancel())

        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

        self.grab_set()
        self.focus_force()

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=(16, 12, 16, 12))
        main.pack(fill="both", expand=True)

        # ── platforms ──
        plat_frame = ttk.LabelFrame(main, text="Target Agent Platforms", padding=(10, 8))
        plat_frame.pack(fill="x", pady=(0, 10))

        for pid in SUPPORTED_PLATFORMS:
            var = tk.BooleanVar(value=False)
            self._platform_vars[pid] = var
            cb = ttk.Checkbutton(plat_frame, text=PLATFORM_LABELS[pid], variable=var)
            cb.pack(anchor="w")

        # ── mode ──
        mode_frame = ttk.LabelFrame(main, text="Operation Mode", padding=(10, 8))
        mode_frame.pack(fill="x", pady=(0, 10))

        rb_update = ttk.Radiobutton(
            mode_frame, text="Update — preserve existing; change only what is entered",
            variable=self._mode_var, value="update", command=self._on_mode_change,
        )
        rb_update.pack(anchor="w")

        rb_reset = ttk.Radiobutton(
            mode_frame, text="Reset — clear project-level environment & .agent-state/, then reinitialize",
            variable=self._mode_var, value="reset", command=self._on_mode_change,
        )
        rb_reset.pack(anchor="w")

        self._reset_frame = ttk.Frame(mode_frame)
        self._reset_frame.pack(fill="x", pady=(4, 0))
        ttk.Label(
            self._reset_frame,
            text="Reset clears ONLY project-level files (not user/global).",
            foreground="red",
        ).pack(anchor="w")
        cb_reset = ttk.Checkbutton(
            self._reset_frame,
            text="I confirm — clear project-level Agent environment and .agent-state/",
            variable=self._reset_confirmed_var,
        )
        cb_reset.pack(anchor="w")

        # ── external deps ──
        deps_frame = ttk.LabelFrame(main, text="External Dependencies (required)", padding=(10, 8))
        deps_frame.pack(fill="x", pady=(0, 10))

        self._deps_content = ttk.Frame(deps_frame)
        self._deps_content.pack(fill="x")

        row_s32 = ttk.Frame(self._deps_content)
        row_s32.pack(fill="x", pady=(0, 4))
        ttk.Label(row_s32, text="S32DS root:").pack(side="left")
        ttk.Entry(row_s32, textvariable=self._s32ds_var, width=45).pack(side="left", padx=(4, 4))
        ttk.Button(row_s32, text="Browse...", command=self._browse_s32ds).pack(side="left")

        row_rtd = ttk.Frame(self._deps_content)
        row_rtd.pack(fill="x")
        ttk.Label(row_rtd, text="RTD path:   ").pack(side="left")
        ttk.Entry(row_rtd, textvariable=self._rtd_var, width=45).pack(side="left", padx=(4, 4))
        ttk.Button(row_rtd, text="Browse...", command=self._browse_rtd).pack(side="left")

        # ── additional skills ──
        import_frame = ttk.LabelFrame(main, text="Additional Skills (optional)", padding=(10, 8))
        import_frame.pack(fill="x", pady=(0, 12))

        rb_skip = ttk.Radiobutton(
            import_frame, text="Skip — do not import additional skills",
            variable=self._import_var, value="skip", command=self._on_import_change,
        )
        rb_skip.pack(anchor="w")

        rb_local = ttk.Radiobutton(
            import_frame, text="Import from local directory",
            variable=self._import_var, value="local", command=self._on_import_change,
        )
        rb_local.pack(anchor="w")

        rb_online = ttk.Radiobutton(
            import_frame, text="Install from online source",
            variable=self._import_var, value="online", command=self._on_import_change,
        )
        rb_online.pack(anchor="w")

        self._import_local_frame = ttk.Frame(import_frame)
        row_local = ttk.Frame(self._import_local_frame)
        row_local.pack(fill="x", pady=(4, 0))
        ttk.Label(row_local, text="Directory:").pack(side="left")
        ttk.Entry(row_local, textvariable=self._import_path_var, width=40).pack(side="left", padx=(4, 4))
        ttk.Button(row_local, text="Browse...", command=self._browse_import_dir).pack(side="left")

        self._import_online_frame = ttk.Frame(import_frame)
        row_url = ttk.Frame(self._import_online_frame)
        row_url.pack(fill="x", pady=(4, 0))
        ttk.Label(row_url, text="URL:").pack(side="left")
        ttk.Entry(row_url, textvariable=self._import_url_var, width=52).pack(side="left", padx=(4, 4))

        # ── buttons ──
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="right")

    # ── event handlers ──────────────────────────────────────────────

    def _on_mode_change(self) -> None:
        if self._mode_var.get() == "reset":
            for child in self._reset_frame.winfo_children():
                child.configure(state="normal")
        else:
            for child in self._reset_frame.winfo_children():
                child.configure(state="disabled")
            self._reset_confirmed_var.set(False)

    def _on_import_change(self) -> None:
        val = self._import_var.get()
        if val == "local":
            self._import_local_frame.pack(fill="x", before=self._import_online_frame)
            self._import_online_frame.pack_forget()
        elif val == "online":
            self._import_online_frame.pack(fill="x", before=self._import_local_frame)
            self._import_local_frame.pack_forget()
        else:
            self._import_local_frame.pack_forget()
            self._import_online_frame.pack_forget()

    def _browse_s32ds(self) -> None:
        path = filedialog.askdirectory(title="Select S32DS Installation Root")
        if path:
            self._s32ds_var.set(Path(path).resolve().as_posix())

    def _browse_rtd(self) -> None:
        path = filedialog.askdirectory(title="Select RTD Installation Path")
        if path:
            self._rtd_var.set(Path(path).resolve().as_posix())

    def _browse_import_dir(self) -> None:
        path = filedialog.askdirectory(title="Select Skill Directory")
        if path:
            self._import_path_var.set(Path(path).resolve().as_posix())

    # ── actions ─────────────────────────────────────────────────────

    def _on_ok(self) -> None:
        platforms = [pid for pid, var in self._platform_vars.items() if var.get()]
        if not platforms:
            messagebox.showwarning("No Platforms", "Please select at least one target platform.")
            return

        mode = self._mode_var.get()

        if mode == "reset" and not self._reset_confirmed_var.get():
            messagebox.showwarning(
                "Reset Not Confirmed",
                "Please confirm the reset by checking the confirmation box.",
            )
            return

        s32ds_path = self._s32ds_var.get().strip()
        rtd_path = self._rtd_var.get().strip()

        if not _verify_s32ds_root(s32ds_path):
            messagebox.showwarning(
                "Invalid S32DS Path",
                "Select an existing S32DS root containing eclipse/ or S32DS/.",
            )
            return

        if not _verify_rtd_root(rtd_path):
            messagebox.showwarning(
                "Invalid RTD Path",
                "Select an existing RTD root containing *_TS_T* package directories.",
            )
            return

        import_skills: dict[str, Any] | None = None
        import_type = self._import_var.get()
        if import_type == "local":
            local_path = self._import_path_var.get().strip()
            if not local_path:
                messagebox.showwarning("Missing Skill Directory", "Select a local Skill directory.")
                return
            import_skills = {
                "type": "local",
                "path": local_path,
                "description": f"Import skills from local directory: {local_path}",
            }
        elif import_type == "online":
            url = self._import_url_var.get().strip()
            if not url:
                messagebox.showwarning("Missing Skill URL", "Enter an online Skill source URL.")
                return
            import_skills = {
                "type": "online",
                "url": url,
                "description": f"Install skills from online source: {url}",
            }

        self.result = {
            "version": 1,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "platforms": platforms,
            "mode": mode,
            "reset_confirmed": (mode == "reset" and self._reset_confirmed_var.get()),
            "s32ds_path": s32ds_path.replace("\\", "/"),
            "rtd_path": rtd_path.replace("\\", "/"),
        }
        if import_skills is not None:
            self.result["import_skills"] = import_skills

        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


def run_gui() -> dict[str, Any] | None:
    app = InitDialog()
    app.mainloop()
    return app.result


# ── CLI interactive fallback ────────────────────────────────────────────


def _safe_input(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        print("\nInput interrupted.", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)


def _choose_multi(label: str, options: list[str]) -> list[str]:
    print(f"\n{label}")
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")
    print(f"  [0] Done / none")

    selected: list[str] = []
    while True:
        raw = _safe_input("Enter number (0 when done): ").strip()
        if raw == "":
            continue
        try:
            n = int(raw)
        except ValueError:
            print(f"  Invalid number: {raw!r}")
            continue
        if n == 0:
            break
        if 1 <= n <= len(options):
            name = options[n - 1]
            if name not in selected:
                selected.append(name)
                print(f"  Added: {name}")
            else:
                print(f"  Already selected: {name}")
        else:
            print(f"  Out of range [1..{len(options)}]")
    return selected


def _choose_one(label: str, options: list[str]) -> str:
    print(f"\n{label}")
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")

    while True:
        raw = _safe_input("Enter number: ").strip()
        try:
            n = int(raw)
        except ValueError:
            print(f"  Invalid number: {raw!r}")
            continue
        if 1 <= n <= len(options):
            return options[n - 1]
        print(f"  Out of range [1..{len(options)}]")


def _choose_yes_no(question: str) -> bool:
    while True:
        raw = _safe_input(f"{question} [y/N]: ").strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no", ""):
            return False
        print("  Please answer y or n.")


def _ask_path_optional(prompt: str) -> str:
    raw = _safe_input(f"{prompt} (press Enter to skip): ").strip().strip("\"'")
    if not raw:
        return ""
    p = Path(raw).expanduser()
    return str(p.resolve())


def run_cli() -> dict[str, Any] | None:
    print("=" * 60)
    print("  RTD CfgFile CLI — Agent Environment Initialization")
    print("=" * 60)

    platforms = _choose_multi(
        "Select target Agent platforms (multiple allowed):",
        list(SUPPORTED_PLATFORMS),
    )
    if not platforms:
        print("No platforms selected. Exiting.", file=sys.stderr)
        return None

    mode = _choose_one(
        "Select operation mode:",
        [
            "Update — preserve existing environment; change only what is explicitly entered",
            "Reset — clear project-level Agent environment and .agent-state/ for selected platforms, then reinitialize",
        ],
    )

    reset_confirmed = False
    if "Reset" in mode:
        print(f"\n  RESET will clear the following for platforms: {', '.join(platforms)}")
        print("    - Skill symlinks and subagent files under project-level directories")
        print("    - The entire .agent-state/ cache")
        print("  User-level and global Agent environments will NOT be affected.")
        reset_confirmed = _choose_yes_no("  Confirm reset?")
        if not reset_confirmed:
            print("Reset cancelled. Switching to Update mode.")
            mode = "update"

    print("\n--- External Dependencies (required) ---")
    s32ds_path = _ask_path_optional("S32DS installation root")
    if not _verify_s32ds_root(s32ds_path):
        print(f"  ERROR: {s32ds_path or '<empty>'} is not a valid S32DS root.")
        return None

    rtd_path = _ask_path_optional("RTD installation path")
    if not _verify_rtd_root(rtd_path):
        print(f"  ERROR: {rtd_path or '<empty>'} is not a valid RTD package root.")
        return None

    print("\n--- Additional Skills Import (optional) ---")
    import_skills: dict[str, Any] | None = None
    import_choice = _choose_one(
        "Import additional skills?",
        [
            "Skip — do not import additional skills",
            "Import from local directory",
            "Install from online source",
        ],
    )
    if "local" in import_choice:
        local = _ask_path_optional("Local skill directory path")
        if local:
            import_skills = {
                "type": "local",
                "path": local,
                "description": f"Import skills from local directory: {local}",
            }
    elif "online" in import_choice:
        url = _safe_input("Online skill source URL: ").strip()
        if url:
            import_skills = {
                "type": "online",
                "url": url,
                "description": f"Install skills from online source: {url}",
            }

    return {
        "version": 1,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "platforms": platforms,
        "mode": "update" if "Update" in mode else "reset",
        "reset_confirmed": reset_confirmed,
        "s32ds_path": s32ds_path.replace("\\", "/"),
        "rtd_path": rtd_path.replace("\\", "/"),
        **({"import_skills": import_skills} if import_skills is not None else {}),
    }


# ── CLI entry point ────────────────────────────────────────────────────


def load_input_file(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        print(f"Input file not found: {p}", file=sys.stderr)
        raise SystemExit(1)
    with open(p, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect structured input for RTD CfgFile CLI Agent environment initialization."
    )
    parser.add_argument(
        "--input",
        type=str,
        metavar="FILE",
        help="Read pre-collected input from JSON file (non-interactive mode)",
    )
    parser.add_argument(
        "--output",
        type=str,
        metavar="FILE",
        help="Write collected input as JSON to file instead of stdout",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate an existing input file without interactive collection (requires --input)",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Open tkinter GUI dialog instead of text prompts (requires desktop display)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.validate_only:
        if not args.input:
            print("--validate-only requires --input", file=sys.stderr)
            return 2
        data = load_input_file(args.input)
        errors = validate_input(data)
        if errors:
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print("Input is valid.")
        return 0

    if args.input:
        data = load_input_file(args.input)
        errors = validate_input(data)
        if errors:
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
            return 1
    elif args.gui:
        try:
            result = run_gui()
        except tk.TclError:
            print("tkinter unavailable — falling back to text mode", file=sys.stderr)
            result = run_cli()
        if result is None:
            print("Cancelled by user.", file=sys.stderr)
            return 130
        data = result
    else:
        result = run_cli()
        if result is None:
            return 130
        data = result

    json_text = json.dumps(data, indent=2, ensure_ascii=False)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_text, encoding="utf-8")
        print(f"Input saved to {out}")
    else:
        print(json_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
