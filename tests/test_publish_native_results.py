import xml.etree.ElementTree as ET

from publish_native_results import publish


def test_public_outcomes_preserve_failures_but_exclude_private_payloads(tmp_path):
    source = tmp_path / "input.xml"
    source.write_text(
        '<testsuites><testsuite tests="1" failures="1" hostname="private-node">'
        '<properties><property name="private-property" value="private-value"/></properties>'
        '<testcase name="case" classname="native" time="1.2">'
        '<failure message="private-error">private-transcript</failure>'
        "<system-out>private-logs</system-out></testcase></testsuite></testsuites>"
    )
    output = tmp_path / "published.xml"
    publish(source, output)
    root = ET.parse(output).getroot()
    assert root.find("testsuite").get("failures") == "1"
    assert root.find("testsuite/testcase/failure") is not None
    assert root.find("testsuite/testcase").get("time") == "1.2"
    assert "private-" not in output.read_text()
