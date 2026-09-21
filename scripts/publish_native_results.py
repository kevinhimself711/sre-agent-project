"""Publish native smoke test outcomes without logs, prompts or node metadata."""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def publish(source, destination):
    original = ET.parse(source).getroot()
    root = ET.Element("testsuites")
    suites = [original] if original.tag == "testsuite" else original.findall("testsuite")
    for suite in suites:
        result = ET.SubElement(
            root,
            "testsuite",
            {
                k: v
                for k, v in suite.attrib.items()
                if k in {"name", "tests", "failures", "errors", "skipped", "time"}
            },
        )
        for case in suite.findall("testcase"):
            outcome = ET.SubElement(
                result,
                "testcase",
                {k: v for k, v in case.attrib.items() if k in {"name", "classname", "time"}},
            )
            for tag in ("failure", "error", "skipped"):
                if case.find(tag) is not None:
                    ET.SubElement(
                        outcome, tag, {"message": "Details retained in private node artifacts"}
                    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    publish(args.source, args.destination)
