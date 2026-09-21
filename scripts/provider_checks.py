"""Exercise upstream classifier or detailed judge against a synthetic probe."""

import argparse
import json
import logging
from dataclasses import asdict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["holmes", "sregym"])
    args = parser.parse_args()
    if args.kind == "holmes":
        from tests.llm.utils.classifiers import evaluate_correctness

        class Caplog:
            def set_level(self, level, logger):
                logging.getLogger(logger).setLevel(level)

        # No benchmark oracle or held-out fault data used for provider validation.
        result = evaluate_correctness(
            ["The synthetic probe value is 7."],
            "The synthetic probe value is 7.",
            None,
            Caplog(),
        )
        print(
            json.dumps(
                {"classifier_score": result.score, "metadata": result.metadata},
                default=str,
            )
        )
        assert result.score == 1
    else:
        from sregym.conductor.oracles.llm_as_a_judge.judge import DiagnosisJudge

        judge = DiagnosisJudge()
        result = judge.judge_detailed(
            solution="The synthetic demo API is down because its demo database hostname is invalid.",
            expectation="The synthetic demo API is down because its demo database hostname is invalid.",
        )
        print(json.dumps(asdict(result), default=str))
        assert result.verdict is not None


if __name__ == "__main__":
    main()
