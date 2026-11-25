"""Stage 6 (thin-module pass) diagram for module eng-ci-configs.

ci-config-check-chain — the four checks of the module's config-ci job in run order (yamllint, check-jsonschema on
                        fleet.yaml, check-jsonschema --builtin-schema vendor.github-workflows, tools/check_configs.py)
                        and, under each, what it catches; cases A-E of run_ci_lab.sh mark what fired locally (yamllint and the workflow
                        schema passed in all cases):
                        A - 6 invariant errors on the SITL export, C - FS_THR_ENABLE 0 mutation, D - 4.5.3 diff under
                        firmware 2025.12.5, E - stack: inav / firmware "4.7" rejected by the schema. Any red step
                        stops the job (&&), exit code 1 blocks the merge.
"""
from __future__ import annotations

from svg import Box, flow


def build(D: dict) -> None:
    D["ci-config-check-chain"] = flow("Четыре проверки job config-ci и что каждая ловит (A, C, D, E — случаи лабораторной)", [
        Box("lint", ["yamllint --strict", "весь репозиторий"], 10, 16, 160, 48),
        Box("sch", ["check-jsonschema", "fleet.yaml"], 190, 16, 160, 48),
        Box("wf", ["check-jsonschema", "workflow (builtin)"], 370, 16, 160, 48),
        Box("inv", ["check_configs.py", "инварианты"], 550, 16, 160, 48, accent=True),
        Box("c1", ["стиль YAML:", "отступы, truthy"], 10, 110, 160, 48),
        Box("c2", ["E: stack: inav,", "firmware \"4.7\""], 190, 110, 160, 48),
        Box("c3", ["опечатка в ключе", "job / step"], 370, 110, 160, 48),
        Box("c4", ["A: 6 ошибок экспорта", "C: FS_THR_ENABLE = 0", "D: 4.5.3 под 2025.12"], 542.5, 110, 175, 62),
        Box("red", ["exit 1: PR не сливается"], 280, 200, 200, 36, accent=True),
    ], [("lint", "sch", "&&"), ("sch", "wf", "&&"), ("wf", "inv", "&&"),
        ("lint", "c1", "", False, "v"), ("sch", "c2", "", False, "v"), ("wf", "c3", "", False, "v"),
        ("inv", "c4", "", False, "v"), ("c2", "red", "", True, "v"), ("c4", "red", "", True, "v")],
        720, 262, notes=[(10, 256, "Первая красная проверка останавливает job; зелёный — только когда прошли все четыре.", "m t")])
