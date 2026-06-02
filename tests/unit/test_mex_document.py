# tests/unit/test_mex_document.py
from rtd_config.backends.s32_mex.document import MexDocument
from tests.fixtures import copy_uart_fixture


def test_mex_document_loads_and_detects_enabled_instances(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")
    instances = doc.enabled_instance_names()
    # The real S32K344 Uart fixture enables exactly these six module instances.
    # There is no Dio instance in this fixture (the Dio provider arrives in a
    # later milestone task).
    for name in ("Mcu", "BaseNXP", "Platform", "Port", "Mcl", "Uart"):
        assert name in instances


def test_mex_document_write_preserves_xml_well_formedness(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)
    doc.write(mex)
    MexDocument.load(mex)


def test_mex_document_removes_quick_selection_from_modified_element(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)
    element = doc.find_first_with_attribute("quick_selection")
    assert element is not None

    doc.mark_modified(element)

    assert "quick_selection" not in element.attrib
