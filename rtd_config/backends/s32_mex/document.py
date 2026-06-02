# rtd_config/backends/s32_mex/document.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.parsers import expat


# The .mex root declares a default namespace. By default ElementTree rewrites
# every tag with an auto-generated "ns0:" prefix on write(), which would churn
# the entire document. Registering the default namespace at import time keeps
# the fallback writer clean and limits ns churn to genuinely modified subtrees.
ET.register_namespace("", "http://mcuxpresso.nxp.com/XSD/mex_configuration_18")


@dataclass
class _ElementSource:
    """Byte span of an element's start tag plus its attributes at load time.

    ``start``/``tag_end`` are byte offsets into the original file bytes; the
    start tag is ``raw[start : tag_end + 1]`` and always ends at the ``>`` of
    ``<...>`` or ``<.../>``. ``attrib`` is a snapshot taken before any edit so
    the writer can detect exactly which elements changed.
    """

    start: int
    tag_end: int
    attrib: dict


@dataclass
class MexDocument:
    path: Path
    tree: ET.ElementTree
    # Original file bytes and per-element source spans, captured at load time so
    # write() can rewrite only the start tags that actually changed and copy
    # everything else verbatim. _aligned is False when the expat start-tag count
    # does not match the ElementTree element count (unexpected document shape),
    # in which case write() falls back to full reserialization.
    _raw: bytes = field(default=b"", repr=False, compare=False)
    _sources: list[_ElementSource] = field(default_factory=list, repr=False, compare=False)
    _aligned: bool = field(default=False, repr=False, compare=False)

    @classmethod
    def load(cls, path: Path) -> "MexDocument":
        path = Path(path)
        raw = path.read_bytes()
        doc = cls(path=path, tree=ET.parse(path), _raw=raw)
        doc._capture_sources()
        return doc

    @property
    def root(self) -> ET.Element:
        return self.tree.getroot()

    def enabled_instance_names(self) -> set[str]:
        names: set[str] = set()
        for element in self.root.iter():
            if element.tag.endswith("instance") and element.attrib.get("enabled", "true") != "false":
                name = element.attrib.get("name")
                if name:
                    names.add(name)
        return names

    def find_first_with_attribute(self, attribute: str) -> ET.Element | None:
        for element in self.root.iter():
            if attribute in element.attrib:
                return element
        return None

    def iter_instances(self) -> "list[ET.Element]":
        """Return every <instance> element (enabled or not)."""
        return [e for e in self.root.iter() if e.tag.endswith("instance")]

    def find_config_set(self, name: str) -> ET.Element | None:
        """Return the <config_set name="..."> element for a module.

        Targeted config-set lookup is a backend responsibility so providers do
        not manipulate the XML tree ad hoc.
        """
        for element in self.root.iter():
            if element.tag.endswith("config_set") and element.attrib.get("name") == name:
                return element
        return None

    def find_uart_channel(self, config_set: ET.Element, channel_id: int) -> ET.Element | None:
        """Return the Uart channel <struct> whose UartChannelId matches.

        The Uart channel array index equals UartChannelId, but matching on the
        setting value is robust against reordering.
        """
        for array in config_set.iter():
            if array.tag.endswith("array") and array.attrib.get("name") == "UartChannel":
                for channel in array:
                    if not channel.tag.endswith("struct"):
                        continue
                    for setting in channel:
                        if (
                            setting.tag.endswith("setting")
                            and setting.attrib.get("name") == "UartChannelId"
                            and setting.attrib.get("value") == str(channel_id)
                        ):
                            return channel
        return None

    def find_child_setting(self, container: ET.Element, name: str) -> ET.Element | None:
        """Return a descendant <setting name="..."> within a container."""
        for setting in container.iter():
            if setting.tag.endswith("setting") and setting.attrib.get("name") == name:
                return setting
        return None

    def find_nearest_quick_selection_ancestor(self, element: ET.Element) -> ET.Element | None:
        """Return the nearest ancestor (including self) carrying quick_selection.

        ElementTree has no parent pointers, so we walk a child->parent map built
        from the current tree.
        """
        parents = {child: parent for parent in self.root.iter() for child in parent}
        current: ET.Element | None = element
        while current is not None:
            if "quick_selection" in current.attrib:
                return current
            current = parents.get(current)
        return None

    def mark_modified(self, element: ET.Element) -> None:
        element.attrib.pop("quick_selection", None)

    # ---- Narrow, byte-faithful writer -----------------------------------

    def _capture_sources(self) -> None:
        """Record each element's start-tag byte span and load-time attributes.

        expat fires StartElementHandler in document (preorder) order, exactly
        like ElementTree's root.iter(); the i-th start tag therefore matches the
        i-th element. We only edit attributes (never add/remove elements) in M1,
        so this 1:1 correspondence holds through write().
        """
        starts: list[int] = []
        parser = expat.ParserCreate()
        parser.StartElementHandler = lambda name, attrs: starts.append(parser.CurrentByteIndex)
        try:
            parser.Parse(self._raw, True)
        except expat.ExpatError:
            self._aligned = False
            return

        elements = list(self.root.iter())
        if len(starts) != len(elements):
            self._aligned = False
            return

        sources: list[_ElementSource] = []
        for start, element in zip(starts, elements):
            tag_end = self._scan_start_tag_end(start)
            if tag_end is None:
                self._aligned = False
                return
            sources.append(_ElementSource(start=start, tag_end=tag_end, attrib=dict(element.attrib)))
        self._sources = sources
        self._aligned = True

    def _scan_start_tag_end(self, start: int) -> int | None:
        """Return the byte index of the '>' that closes the start tag at ``start``.

        Scans the raw bytes from the opening '<', skipping any '>' that appears
        inside a quoted attribute value. Comments/CDATA cannot occur inside a
        start tag, so quote tracking alone is sufficient.
        """
        data = self._raw
        n = len(data)
        i = start + 1
        quote: int | None = None
        while i < n:
            c = data[i]
            if quote is not None:
                if c == quote:
                    quote = None
            elif c in (0x22, 0x27):  # " or '
                quote = c
            elif c == 0x3E:  # >
                return i
            i += 1
        return None

    def write(self, path: Path | None = None) -> None:
        target = Path(path) if path is not None else self.path
        data = self._render_minimal() if self._aligned else None
        if data is not None:
            target.write_bytes(data)
            return
        # Fallback: full reserialization. Well-formed but not byte-faithful; only
        # reached for documents whose shape we could not map at load time.
        self.tree.write(target, encoding="utf-8", xml_declaration=True)

    def _render_minimal(self) -> bytes | None:
        """Rebuild the file bytes, rewriting only start tags that changed.

        Returns None to request the reserialization fallback if the element set
        diverged from the captured spans or a tag could not be edited in place.
        """
        elements = list(self.root.iter())
        if len(elements) != len(self._sources):
            return None
        out = bytearray()
        cursor = 0
        for element, src in zip(elements, self._sources):
            if element.attrib == src.attrib:
                continue  # unchanged: bytes copied verbatim in the next bulk slice
            new_tag = self._rewrite_start_tag(src, element.attrib)
            if new_tag is None:
                return None
            out += self._raw[cursor:src.start]
            out += new_tag
            cursor = src.tag_end + 1
        out += self._raw[cursor:]
        return bytes(out)

    def _rewrite_start_tag(self, src: _ElementSource, new_attrib: dict) -> bytes | None:
        """Apply attribute value changes / removals to an original start tag.

        Edits are surgical: only the targeted attribute's value text or the
        removed attribute is touched, preserving the original quote characters,
        attribute order, and whitespace of everything else. Returns None (force
        fallback) if an attribute was added, which M1 edits never do.
        """
        tag = self._raw[src.start : src.tag_end + 1].decode("utf-8")
        old = src.attrib
        for name, value in new_attrib.items():
            if name not in old:
                return None  # attribute added; cannot place it faithfully
            if old[name] != value:
                tag = _sub_attr_value(tag, name, value)
                if tag is None:
                    return None
        for name in old:
            if name not in new_attrib:
                tag = _remove_attr(tag, name)
                if tag is None:
                    return None
        return tag.encode("utf-8")


def _xml_escape_attr(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def _sub_attr_value(tag: str, name: str, new_value: str) -> str | None:
    """Replace only the value text of attribute ``name`` inside a start tag."""
    pattern = re.compile(
        r"(?<![\w:.\-])" + re.escape(name) + r"\s*=\s*([\"'])(.*?)\1",
        re.DOTALL,
    )
    match = pattern.search(tag)
    if match is None:
        return None
    return tag[: match.start(2)] + _xml_escape_attr(new_value) + tag[match.end(2) :]


def _remove_attr(tag: str, name: str) -> str | None:
    """Remove attribute ``name`` (and its leading whitespace) from a start tag."""
    pattern = re.compile(
        r"\s+" + re.escape(name) + r"\s*=\s*([\"']).*?\1",
        re.DOTALL,
    )
    new_tag, count = pattern.subn("", tag, count=1)
    if count == 0:
        return None
    return new_tag
