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

    def mark_modified(self, element: ET.Element) -> None:
        element.attrib.pop("quick_selection", None)

    def write(self, path: Path | None = None) -> None:
        target = path or self.path
        self.tree.write(target, encoding="utf-8", xml_declaration=True)
