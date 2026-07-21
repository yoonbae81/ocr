from ports.output import PageExporter


def test_output_port_is_available_from_ports_package() -> None:
    assert PageExporter.__name__ == "PageExporter"
