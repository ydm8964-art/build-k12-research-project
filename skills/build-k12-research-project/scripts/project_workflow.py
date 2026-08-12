#!/usr/bin/env python3
"""Run the teacher-profile → topic → intake → package → job-plan workflow."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from build_material_generation_plan import build as build_plan
from generate_topic_candidates import generate, to_markdown
from initialize_project_package import initialize
from select_topic_and_prepare_intake import prepare

PROFILE_NAME = "teacher-profile.json"
TOPICS_NAME = "topic-candidates.json"
TOPICS_MD_NAME = "topic-candidates.md"
SELECTION_NAME = "topic-selection.json"
INTAKE_NAME = "project-intake.json"
STATE_NAME = "workflow-state.json"
PACKAGE_NAME = "project-package"
PLAN_NAME = "material-generation-plan.json"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_state(root: Path, state: str, **extra) -> dict:
    value = {"schema_version": "1.0", "state": state, **extra}
    write_json(root / STATE_NAME, value)
    return value


def start(profile_path: Path, root: Path, count: int) -> dict:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    conflicts = [root / name for name in (PROFILE_NAME, TOPICS_NAME, TOPICS_MD_NAME, STATE_NAME) if (root / name).exists()]
    if conflicts:
        raise FileExistsError("拒绝覆盖已有选题工作区：" + "，".join(str(path) for path in conflicts))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    result = generate(profile, count)
    shutil.copy2(profile_path, root / PROFILE_NAME)
    write_json(root / TOPICS_NAME, result)
    (root / TOPICS_MD_NAME).write_text(to_markdown(result), encoding="utf-8")
    return write_state(root, "awaiting-topic-selection", candidate_count=len(result["candidates"]),
                       next_action="请用户选择TOPIC-01至TOPIC-08中的一个候选ID，或先修改题目")


def select(root: Path, topic_id: str, title: str | None = None) -> tuple[dict, int]:
    root = root.resolve()
    profile = json.loads((root / PROFILE_NAME).read_text(encoding="utf-8"))
    topics = json.loads((root / TOPICS_NAME).read_text(encoding="utf-8"))
    result = prepare(profile, topics, topic_id, title)
    write_json(root / SELECTION_NAME, result)
    if not result["ready_for_initialization"]:
        state = write_state(root, "awaiting-project-details", selected_topic_id=topic_id,
                            missing=result["missing_after_selection"], next_action=result["next_action"])
        return state, 3
    write_json(root / INTAKE_NAME, result["project_intake"])
    state = write_state(root, "ready-to-initialize", selected_topic_id=topic_id,
                        selected_title=result["selected_title"], next_action="运行initialize子命令")
    return state, 0


def initialize_workspace(root: Path, skill_root: Path) -> dict:
    root = root.resolve()
    package_root = root / PACKAGE_NAME
    manifest_path = initialize(root / INTAKE_NAME, package_root, skill_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plan = build_plan(manifest)
    control_root = root / "workflow-control"
    control_root.mkdir(exist_ok=True)
    write_json(control_root / PLAN_NAME, plan)
    return write_state(root, "package-in-progress", package_root=PACKAGE_NAME,
                       manifest=f"{PACKAGE_NAME}/project-manifest.json", plan=f"workflow-control/{PLAN_NAME}",
                       next_jobs=plan["next_jobs"], blocked_jobs=plan["blocked_jobs"],
                       next_action="由Agent处理next_jobs，登记材料后重新运行plan子命令")


def refresh_plan(root: Path) -> dict:
    root = root.resolve()
    package_root = root / PACKAGE_NAME
    manifest = json.loads((package_root / "project-manifest.json").read_text(encoding="utf-8"))
    plan = build_plan(manifest)
    control_root = root / "workflow-control"
    control_root.mkdir(exist_ok=True)
    write_json(control_root / PLAN_NAME, plan)
    state_name = "package-complete" if not plan["unfinished_jobs"] else "package-in-progress"
    return write_state(root, state_name, package_root=PACKAGE_NAME, next_jobs=plan["next_jobs"],
                       blocked_jobs=plan["blocked_jobs"], next_action="继续处理可执行任务或补齐阻断项")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--profile", type=Path, required=True)
    start_parser.add_argument("--root", type=Path, required=True)
    start_parser.add_argument("--count", type=int, default=6)
    select_parser = subparsers.add_parser("select")
    select_parser.add_argument("--root", type=Path, required=True)
    select_parser.add_argument("--topic-id", required=True)
    select_parser.add_argument("--title", help="可选：用户确认修改后的最终题目")
    init_parser = subparsers.add_parser("initialize")
    init_parser.add_argument("--root", type=Path, required=True)
    init_parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--root", type=Path, required=True)
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        code = 0
        if args.command == "start":
            state = start(args.profile, args.root, args.count)
        elif args.command == "select":
            state, code = select(args.root, args.topic_id, args.title)
        elif args.command == "initialize":
            state = initialize_workspace(args.root, args.skill_root.resolve())
        elif args.command == "plan":
            state = refresh_plan(args.root)
        else:
            state = json.loads((args.root.resolve() / STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"工作流失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
