# rtd_config/backends/s32_mex/document.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


# The .mex root declares a default namespace. By default ElementTree rewrites
# every tag with an auto-generated "ns0:" prefix on write(), which would churn
# the entire document. Registering the default namespace at import time keeps
# writes clean and limits diffs to genuinely modified subtrees.
ET.register_namespace("", "http://mcuxpresso.nxp.com/XSD/mex_configuration_18")


@dataclass
class MexDocument:
    path: Path
    tree: ET.ElementTree

    @classmethod
    def load(cls, path: Path) -> "MexDocument":
        return cls(path=path, tree=ET.parse(path))

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

    def write(self, path: Path | None = None) -> None:
        target = path or self.path
        self.tree.write(target, encoding="utf-8", xml_declaration=True)
