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
# Version:     0.4.0
# Description: Unified structured input collector for Agent environment
#              initialization. Its explicit --gui mode collects target
#              platforms, operation mode, required external dependency paths,
#              and optional skill imports in a tkinter dialog. Outputs
#              deployment-ready JSON and validates pre-collected input.
# =================================================================================

from __future__ import annotations

import argparse
import json
import re
import sys
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SUPPORTED_PLATFORMS = ("codex", "claude", "opencode")

PLATFORM_LABELS: dict[str, str] = {
    "codex": "Codex",
    "claude": "Claude",
    "opencode": "OpenCode",
}

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class LocalSkillCandidate:
    name: str
    source: Path


@dataclass(frozen=True)
class LocalSkillIssue:
    source: Path
    message: str


@dataclass(frozen=True)
class LocalSkillDiscovery:
    candidates: tuple[LocalSkillCandidate, ...]
    issues: tuple[LocalSkillIssue, ...]


def _manifest_skill_name(skill_dir: Path) -> str:
    manifest = skill_dir / "SKILL.md"
    if not manifest.is_file():
        raise ValueError(f"Skill source lacks SKILL.md: {skill_dir}")
    text = manifest.read_text(encoding="utf-8-sig")
    match = re.search(
        r"(?m)^name:\s*([a-z0-9]+(?:-[a-z0-9]+)*)\s*$", text
    )
    if not match:
        raise ValueError(f"Skill manifest lacks a valid name: {manifest}")
    name = match.group(1)
    if name != skill_dir.name:
        raise ValueError(
            f"Skill name {name!r} does not match directory {skill_dir.name!r}"
        )
    return name


def _is_within(path: Path, roots: Iterable[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def discover_local_skills(roots: Iterable[str | Path]) -> LocalSkillDiscovery:
    canonical_roots: list[Path] = []
    issues: list[LocalSkillIssue] = []
    for raw_root in roots:
        root = Path(raw_root).expanduser().resolve(strict=False)
        if root in canonical_roots:
            continue
        canonical_roots.append(root)
        if not root.is_dir():
            issues.append(LocalSkillIssue(root, f"Skill root is not a directory: {root}"))

    by_identity: dict[tuple[str, Path], LocalSkillCandidate] = {}
    sources_by_name: dict[str, set[Path]] = {}
    for root in canonical_roots:
        if not root.is_dir():
            continue
        try:
            manifests = sorted(root.rglob("SKILL.md"))
        except OSError as exc:
            issues.append(LocalSkillIssue(root, f"Cannot scan Skill root {root}: {exc}"))
            continue
        for manifest in manifests:
            source = manifest.parent.resolve(strict=True)
            try:
                name = _manifest_skill_name(source)
            except (OSError, UnicodeError, ValueError) as exc:
                issues.append(LocalSkillIssue(source, str(exc)))
                continue
            by_identity[(name, source)] = LocalSkillCandidate(name, source)
            sources_by_name.setdefault(name, set()).add(source)

    conflicting_names = {
        name for name, sources in sources_by_name.items() if len(sources) > 1
    }
    for name in sorted(conflicting_names):
        sources = sorted(sources_by_name[name], key=lambda path: path.as_posix())
        issues.append(
            LocalSkillIssue(
                sources[0],
                f"duplicate Skill name {name!r}: "
                + " and ".join(path.as_posix() for path in sources),
            )
        )

    candidates = tuple(
        sorted(
            (
                candidate
                for candidate in by_identity.values()
                if candidate.name not in conflicting_names
            ),
            key=lambda candidate: (candidate.name, candidate.source.as_posix()),
        )
    )
    return LocalSkillDiscovery(
        candidates,
        tuple(sorted(issues, key=lambda issue: (issue.source.as_posix(), issue.message))),
    )


class LocalSkillSelectionModel:
    def __init__(self) -> None:
        self._roots: list[Path] = []
        self.discovery = LocalSkillDiscovery((), ())
        self._selected: set[tuple[str, Path]] = set()

    @property
    def roots(self) -> tuple[Path, ...]:
        return tuple(self._roots)

    def add_root(self, root: str | Path) -> None:
        canonical = Path(root).expanduser().resolve(strict=False)
        if canonical not in self._roots:
            self._roots.append(canonical)
        self.rescan()

    def remove_root(self, root: str | Path) -> None:
        canonical = Path(root).expanduser().resolve(strict=False)
        self._roots = [existing for existing in self._roots if existing != canonical]
        self.rescan()

    def rescan(self) -> None:
        self.discovery = discover_local_skills(self._roots)
        available = {
            (candidate.name, candidate.source)
            for candidate in self.discovery.candidates
        }
        self._selected.intersection_update(available)

    def set_selected(self, name: str, source: str | Path, selected: bool) -> None:
        identity = (name, Path(source).expanduser().resolve(strict=False))
        if selected:
            if identity not in {
                (candidate.name, candidate.source)
                for candidate in self.discovery.candidates
            }:
                raise ValueError(f"Unknown local Skill selection: {identity}")
            self._selected.add(identity)
        else:
            self._selected.discard(identity)

    def select_all(self) -> None:
        self._selected = {
            (candidate.name, candidate.source)
            for candidate in self.discovery.candidates
        }

    def clear_all(self) -> None:
        self._selected.clear()

    def is_selected(self, candidate: LocalSkillCandidate) -> bool:
        return (candidate.name, candidate.source) in self._selected

    def selected_entries(self) -> tuple[dict[str, str], ...]:
        return tuple(
            {"name": name, "source": source.as_posix()}
            for name, source in sorted(
                self._selected, key=lambda item: (item[0], item[1].as_posix())
            )
        )

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


def validate_local_skill_import(spec: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["'local_skill_import' must be an object"]

    raw_roots = spec.get("roots")
    if not isinstance(raw_roots, list) or not raw_roots:
        return ["'local_skill_import.roots' must be a non-empty list"]

    roots: list[Path] = []
    for index, raw_root in enumerate(raw_roots):
        if not isinstance(raw_root, str) or not raw_root.strip():
            errors.append(
                f"'local_skill_import.roots[{index}]' must be a non-empty path"
            )
            continue
        root = Path(raw_root).expanduser().resolve(strict=False)
        if not root.is_dir():
            errors.append(f"local Skill root is not a directory: {root}")
        elif root not in roots:
            roots.append(root)

    selected = spec.get("selected")
    if not isinstance(selected, list) or not selected:
        errors.append("'local_skill_import' requires at least one selected Skill")
        return errors

    sources_by_name: dict[str, Path] = {}
    seen_identities: set[tuple[str, Path]] = set()
    for index, entry in enumerate(selected):
        if not isinstance(entry, dict):
            errors.append(
                f"'local_skill_import.selected[{index}]' must be an object"
            )
            continue
        name = entry.get("name")
        raw_source = entry.get("source")
        if not isinstance(name, str) or not SKILL_NAME_PATTERN.fullmatch(name):
            errors.append(
                f"'local_skill_import.selected[{index}].name' is invalid"
            )
            continue
        if not isinstance(raw_source, str) or not raw_source.strip():
            errors.append(
                f"'local_skill_import.selected[{index}].source' must be a path"
            )
            continue
        source = Path(raw_source).expanduser().resolve(strict=False)
        identity = (name, source)
        if identity in seen_identities:
            continue
        seen_identities.add(identity)
        previous = sources_by_name.get(name)
        if previous is not None and previous != source:
            errors.append(
                f"duplicate selected Skill name {name!r}: {previous} and {source}"
            )
            continue
        sources_by_name[name] = source
        if not source.is_dir():
            errors.append(f"selected Skill source is not a directory: {source}")
            continue
        if roots and not _is_within(source, roots):
            errors.append(f"selected Skill source is outside submitted roots: {source}")
            continue
        try:
            actual_name = _manifest_skill_name(source)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if actual_name != name:
            errors.append(
                f"selected Skill name {name!r} does not match manifest {actual_name!r}"
            )
    return errors


def validate_input(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    version = data.get("version", 1)
    if version not in (1, 2):
        errors.append("'version' must be 1 or 2")

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

    workflows: list[str] = []
    if version == 2:
        raw_workflows = data.get("additional_skill_workflows")
        if not isinstance(raw_workflows, list) or not raw_workflows:
            errors.append(
                "'additional_skill_workflows' must be a non-empty list for version 2"
            )
        else:
            workflows = [str(value) for value in raw_workflows]
            unknown_workflows = sorted(
                set(workflows).difference({"skip", "local", "online"})
            )
            if unknown_workflows:
                errors.append(
                    "unknown additional_skill_workflows: "
                    + ", ".join(unknown_workflows)
                )
            if len(set(workflows)) != len(workflows):
                errors.append("'additional_skill_workflows' must not contain duplicates")
            if "skip" in workflows and len(workflows) > 1:
                errors.append("Skip cannot be combined with local or online workflows")

    if "local_skill_import" in data:
        errors.extend(validate_local_skill_import(data["local_skill_import"]))
        if version == 2 and "local" not in workflows:
            errors.append("local_skill_import requires the local workflow")
    elif version == 2 and "local" in workflows:
        errors.append("the local workflow requires local_skill_import")

    for field in ("online_skill_request", "supplemental_task"):
        if field in data:
            value = data[field]
            if not isinstance(value, str) or not value.strip():
                errors.append(f"'{field}' must be a non-empty string when provided")
    if "online_skill_request" in data:
        if version == 2 and "online" not in workflows:
            errors.append("online_skill_request requires the online workflow")
    elif version == 2 and "online" in workflows:
        errors.append("the online workflow requires online_skill_request")

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

        self._skip_import_var = tk.BooleanVar(value=False)
        self._local_import_var = tk.BooleanVar(value=False)
        self._online_import_var = tk.BooleanVar(value=False)
        self._local_skill_model = LocalSkillSelectionModel()
        self._skill_vars: dict[tuple[str, Path], tk.BooleanVar] = {}
        self._root_entry_var = tk.StringVar()

        self._build_ui()
        self._on_mode_change()
        self._on_import_change()

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

        cb_skip = ttk.Checkbutton(
            import_frame, text="Skip — do not import additional skills",
            variable=self._skip_import_var, command=self._on_skip_import_change,
        )
        cb_skip.pack(anchor="w")

        cb_local = ttk.Checkbutton(
            import_frame, text="Import from local directories",
            variable=self._local_import_var, command=self._on_import_change,
        )
        cb_local.pack(anchor="w")

        cb_online = ttk.Checkbutton(
            import_frame, text="Install from online source",
            variable=self._online_import_var, command=self._on_import_change,
        )
        cb_online.pack(anchor="w")

        self._import_local_frame = ttk.Frame(import_frame)
        path_row = ttk.Frame(self._import_local_frame)
        path_row.pack(fill="x", pady=(4, 4))
        ttk.Label(path_row, text="Directory:").pack(side="left")
        ttk.Entry(
            path_row, textvariable=self._root_entry_var, width=48
        ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ttk.Button(path_row, text="Add", command=self._add_import_path).pack(
            side="left"
        )
        ttk.Button(
            path_row, text="Browse...", command=self._browse_import_dir
        ).pack(side="left", padx=(4, 0))

        roots_row = ttk.Frame(self._import_local_frame)
        roots_row.pack(fill="x", pady=(4, 0))
        self._root_list = tk.Listbox(roots_row, height=3, width=58)
        self._root_list.pack(side="left", fill="x", expand=True)
        root_buttons = ttk.Frame(roots_row)
        root_buttons.pack(side="left", padx=(6, 0))
        ttk.Button(
            root_buttons, text="Remove directory", command=self._remove_import_dir
        ).pack(fill="x")
        ttk.Button(root_buttons, text="Rescan", command=self._rescan_import_dirs).pack(
            fill="x", pady=(3, 0)
        )

        selection_buttons = ttk.Frame(self._import_local_frame)
        selection_buttons.pack(fill="x", pady=(6, 2))
        ttk.Label(selection_buttons, text="Discovered Skills:").pack(side="left")
        ttk.Button(
            selection_buttons, text="Select all", command=self._select_all_skills
        ).pack(side="right")
        ttk.Button(
            selection_buttons, text="Clear all", command=self._clear_all_skills
        ).pack(side="right", padx=(0, 4))

        skill_canvas_frame = ttk.Frame(self._import_local_frame)
        skill_canvas_frame.pack(fill="both", expand=True)
        self._skill_canvas = tk.Canvas(
            skill_canvas_frame, height=110, highlightthickness=1
        )
        skill_scroll = ttk.Scrollbar(
            skill_canvas_frame, orient="vertical", command=self._skill_canvas.yview
        )
        self._skill_canvas.configure(yscrollcommand=skill_scroll.set)
        skill_scroll.pack(side="right", fill="y")
        self._skill_canvas.pack(side="left", fill="both", expand=True)
        self._skill_check_frame = ttk.Frame(self._skill_canvas)
        self._skill_canvas_window = self._skill_canvas.create_window(
            (0, 0), window=self._skill_check_frame, anchor="nw"
        )
        self._skill_check_frame.bind(
            "<Configure>",
            lambda _event: self._skill_canvas.configure(
                scrollregion=self._skill_canvas.bbox("all")
            ),
        )
        self._skill_canvas.bind(
            "<Configure>",
            lambda event: self._skill_canvas.itemconfigure(
                self._skill_canvas_window, width=event.width
            ),
        )
        self._skill_issue_var = tk.StringVar()
        ttk.Label(
            self._import_local_frame,
            textvariable=self._skill_issue_var,
            foreground="red",
            wraplength=560,
        ).pack(fill="x", pady=(3, 0))

        self._import_online_frame = ttk.Frame(import_frame)
        ttk.Label(
            self._import_online_frame,
            text="Skill names, package references, URLs, or discovery request:",
        ).pack(anchor="w", pady=(4, 2))
        self._online_request_text = tk.Text(
            self._import_online_frame, width=66, height=4, wrap="word"
        )
        self._online_request_text.pack(fill="x")

        # ── supplemental task ──
        supplemental_frame = ttk.LabelFrame(
            main, text="Supplemental Initialization Task (optional)", padding=(10, 8)
        )
        supplemental_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(
            supplemental_frame,
            text=(
                "Runs after successful deployment, verification, and requested "
                "online Skill installation."
            ),
        ).pack(anchor="w")
        self._supplemental_text = tk.Text(
            supplemental_frame, width=66, height=4, wrap="word"
        )
        self._supplemental_text.pack(fill="x", pady=(4, 0))

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
        if self._local_import_var.get() or self._online_import_var.get():
            self._skip_import_var.set(False)
        self._import_local_frame.pack_forget()
        self._import_online_frame.pack_forget()
        if self._local_import_var.get():
            self._import_local_frame.pack(fill="both", expand=True)
        if self._online_import_var.get():
            self._import_online_frame.pack(fill="x")

    def _on_skip_import_change(self) -> None:
        if self._skip_import_var.get():
            self._local_import_var.set(False)
            self._online_import_var.set(False)
        self._on_import_change()

    def _browse_s32ds(self) -> None:
        path = filedialog.askdirectory(title="Select S32DS Installation Root")
        if path:
            self._s32ds_var.set(Path(path).resolve().as_posix())

    def _browse_rtd(self) -> None:
        path = filedialog.askdirectory(title="Select RTD Installation Path")
        if path:
            self._rtd_var.set(Path(path).resolve().as_posix())

    def _add_import_path(self) -> None:
        path = self._root_entry_var.get().strip().strip("\"'")
        if not path:
            messagebox.showwarning(
                "Missing Skill Directory", "Enter or browse to a local Skill directory."
            )
            return
        self._local_skill_model.add_root(path)
        self._root_entry_var.set("")
        self._refresh_local_skill_widgets()

    def _browse_import_dir(self) -> None:
        path = filedialog.askdirectory(title="Add Local Skill Search Directory")
        if path:
            self._root_entry_var.set(Path(path).resolve().as_posix())
            self._add_import_path()

    def _remove_import_dir(self) -> None:
        selected = self._root_list.curselection()
        if not selected:
            return
        self._sync_local_skill_selections()
        roots = self._local_skill_model.roots
        for index in reversed(selected):
            self._local_skill_model.remove_root(roots[index])
        self._refresh_local_skill_widgets()

    def _rescan_import_dirs(self) -> None:
        self._sync_local_skill_selections()
        self._local_skill_model.rescan()
        self._refresh_local_skill_widgets()

    def _sync_local_skill_selections(self) -> None:
        for (name, source), var in self._skill_vars.items():
            self._local_skill_model.set_selected(name, source, var.get())

    def _select_all_skills(self) -> None:
        self._local_skill_model.select_all()
        self._refresh_local_skill_widgets()

    def _clear_all_skills(self) -> None:
        self._local_skill_model.clear_all()
        self._refresh_local_skill_widgets()

    def _refresh_local_skill_widgets(self) -> None:
        self._root_list.delete(0, tk.END)
        for root in self._local_skill_model.roots:
            self._root_list.insert(tk.END, root.as_posix())

        for child in self._skill_check_frame.winfo_children():
            child.destroy()
        self._skill_vars.clear()
        for candidate in self._local_skill_model.discovery.candidates:
            identity = (candidate.name, candidate.source)
            var = tk.BooleanVar(
                value=self._local_skill_model.is_selected(candidate)
            )
            self._skill_vars[identity] = var
            ttk.Checkbutton(
                self._skill_check_frame,
                text=f"{candidate.name}  —  {candidate.source.as_posix()}",
                variable=var,
            ).pack(anchor="w", fill="x")

        issues = self._local_skill_model.discovery.issues
        self._skill_issue_var.set("\n".join(issue.message for issue in issues))

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

        local_skill_import: dict[str, Any] | None = None
        online_skill_request = ""
        if not any(
            (
                self._skip_import_var.get(),
                self._local_import_var.get(),
                self._online_import_var.get(),
            )
        ):
            messagebox.showwarning(
                "Additional Skills Choice Required",
                "Select Skip, local import, online installation, or both local and online.",
            )
            return
        if self._local_import_var.get():
            self._sync_local_skill_selections()
            if not self._local_skill_model.roots:
                messagebox.showwarning(
                    "Missing Skill Directory", "Add at least one local Skill directory."
                )
                return
            if self._local_skill_model.discovery.issues:
                messagebox.showwarning(
                    "Local Skill Scan Failed",
                    "Resolve the reported local Skill scan errors before continuing.",
                )
                return
            selected = self._local_skill_model.selected_entries()
            if not selected:
                messagebox.showwarning(
                    "No Local Skills Selected", "Select at least one discovered Skill."
                )
                return
            local_skill_import = {
                "roots": [
                    root.as_posix() for root in self._local_skill_model.roots
                ],
                "selected": list(selected),
            }
        if self._online_import_var.get():
            online_skill_request = self._online_request_text.get("1.0", "end").strip()
            if not online_skill_request:
                messagebox.showwarning(
                    "Missing Online Skill Request",
                    "Enter Skill names, package references, URLs, or a discovery request.",
                )
                return

        supplemental_task = self._supplemental_text.get("1.0", "end").strip()

        self.result = {
            "version": 2,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "platforms": platforms,
            "mode": mode,
            "reset_confirmed": (mode == "reset" and self._reset_confirmed_var.get()),
            "s32ds_path": s32ds_path.replace("\\", "/"),
            "rtd_path": rtd_path.replace("\\", "/"),
            "additional_skill_workflows": (
                ["skip"]
                if self._skip_import_var.get()
                else [
                    workflow
                    for workflow, selected_workflow in (
                        ("local", self._local_import_var.get()),
                        ("online", self._online_import_var.get()),
                    )
                    if selected_workflow
                ]
            ),
        }
        if local_skill_import is not None:
            self.result["local_skill_import"] = local_skill_import
        if online_skill_request:
            self.result["online_skill_request"] = online_skill_request
        if supplemental_task:
            self.result["supplemental_task"] = supplemental_task

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
    local_skill_import: dict[str, Any] | None = None
    online_skill_request = ""
    import_choices = _choose_multi(
        "Select additional Skill workflows (multiple allowed):",
        [
            "Skip — do not import additional skills",
            "Import from local directory",
            "Install from online source",
        ],
    )
    if not import_choices:
        print("An explicit additional-Skill choice is required.", file=sys.stderr)
        return None
    skip_selected = any("Skip" in choice for choice in import_choices)
    local_selected = any("local" in choice for choice in import_choices)
    online_selected = any("online" in choice for choice in import_choices)
    if skip_selected and (local_selected or online_selected):
        print("Skip cannot be combined with local or online import.", file=sys.stderr)
        return None
    if local_selected:
        roots: list[str] = []
        print("Add local Skill directories; press Enter when finished.")
        while True:
            local = _ask_path_optional("Local Skill directory path")
            if not local:
                break
            if local not in roots:
                roots.append(local)
        discovery = discover_local_skills(roots)
        if discovery.issues:
            for issue in discovery.issues:
                print(f"  ERROR: {issue.message}", file=sys.stderr)
            return None
        labels = [
            f"{candidate.name} — {candidate.source.as_posix()}"
            for candidate in discovery.candidates
        ]
        selected_labels = _choose_multi("Select local Skills to deploy:", labels)
        selected_set = set(selected_labels)
        selected = [
            {"name": candidate.name, "source": candidate.source.as_posix()}
            for candidate, label in zip(discovery.candidates, labels, strict=True)
            if label in selected_set
        ]
        if not selected:
            print("No local Skills selected.", file=sys.stderr)
            return None
        local_skill_import = {"roots": roots, "selected": selected}
    if online_selected:
        online_skill_request = _safe_input(
            "Online Skill names, references, URLs, or discovery request: "
        ).strip()
        if not online_skill_request:
            print("Online Skill request is required.", file=sys.stderr)
            return None

    supplemental_task = _safe_input(
        "Supplemental Agent-environment initialization task (optional): "
    ).strip()

    return {
        "version": 2,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "platforms": platforms,
        "mode": "update" if "Update" in mode else "reset",
        "reset_confirmed": reset_confirmed,
        "s32ds_path": s32ds_path.replace("\\", "/"),
        "rtd_path": rtd_path.replace("\\", "/"),
        "additional_skill_workflows": (
            ["skip"]
            if skip_selected
            else [
                workflow
                for workflow, selected_workflow in (
                    ("local", local_selected),
                    ("online", online_selected),
                )
                if selected_workflow
            ]
        ),
        **(
            {"local_skill_import": local_skill_import}
            if local_skill_import is not None
            else {}
        ),
        **(
            {"online_skill_request": online_skill_request}
            if online_skill_request
            else {}
        ),
        **({"supplemental_task": supplemental_task} if supplemental_task else {}),
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
        except tk.TclError as exc:
            print(f"tkinter GUI unavailable: {exc}", file=sys.stderr)
            return 1
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
