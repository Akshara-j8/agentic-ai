import json
from pathlib import Path

from agent.graph import run_agent


SCENARIOS_PATH = Path(__file__).resolve().parent / "scenarios.json"


def score_scenarios() -> dict:
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    results = []
    for scenario in scenarios:
        response = run_agent(scenario["message"])
        passed = scenario["expected_contains"].lower() in response.lower()
        results.append({"id": scenario["id"], "passed": passed, "response": response})
    return {
        "passed": sum(1 for result in results if result["passed"]),
        "total": len(results),
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(score_scenarios(), indent=2))

