"""Generate a deterministic JSON and Markdown report for the offline MVP baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "evaluation/datasets/devmind_mvp_questions.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.scripts.evaluate_agent_grounding import evaluate as evaluate_grounding
from evaluation.scripts.evaluate_context_quality import evaluate as evaluate_context
from evaluation.scripts.evaluate_retrieval_strategies import (
    evaluate as evaluate_retrieval,
)
from evaluation.scripts.evaluate_tool_call_accuracy import evaluate as evaluate_tools
from evaluation.scripts.validate_mvp_dataset import validate_dataset


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report() -> dict[str, Any]:
    """Run the deterministic evaluations and return a serializable report."""

    cases = validate_dataset()
    return {
        "schema_version": 1,
        "report_kind": "devsage-offline-mvp-baseline",
        "dataset": {
            "path": "evaluation/datasets/devmind_mvp_questions.json",
            "questions": len(cases),
            "sha256": _sha256(DATASET_PATH),
        },
        "metrics": {
            "agent_grounding": evaluate_grounding(),
            "tool_call_accuracy": evaluate_tools(),
            "context_quality": evaluate_context(),
            "retrieval_strategies": evaluate_retrieval(),
        },
        "interpretation": {
            "embedding": "offline Hash baseline",
            "faithfulness": "lexical proxy, not human or LLM evaluation",
            "external_services": "not used",
        },
    }


def _format_metric(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def render_markdown(report: dict[str, Any]) -> str:
    """Render the stable summary and bounded failure samples as Markdown."""

    dataset = report["dataset"]
    metrics = report["metrics"]
    grounding = metrics["agent_grounding"]
    tools = metrics["tool_call_accuracy"]
    context = metrics["context_quality"]
    retrieval = metrics["retrieval_strategies"]

    lines = [
        "# DevSage 离线 MVP 评估基线",
        "",
        "> 本文件由 `evaluation/scripts/generate_offline_report.py` 生成；指标来自固定脱敏数据集和离线 Hash Embedding，不代表生产模型质量。",
        "",
        "## 数据集",
        "",
        f"- 文件：`{dataset['path']}`",
        f"- 问题数：`{dataset['questions']}`",
        f"- SHA-256：`{dataset['sha256']}`",
        "",
        "## 核心指标",
        "",
        "| 指标 | 当前值 |",
        "|---|---:|",
        f"| Agent Source Recall@5 | `{_format_metric(grounding['source_recall_at_5'])}` |",
        f"| Agent 完整来源案例率 | `{_format_metric(grounding['full_source_case_rate'])}` |",
        f"| Expected Tool Coverage | `{_format_metric(tools['expected_tool_coverage'])}` |",
        f"| Fully Covered Case Rate | `{_format_metric(tools['fully_covered_case_rate'])}` |",
        f"| Context Precision@5 | `{_format_metric(context['context_precision_at_5'])}` |",
        f"| Context Recall@5 | `{_format_metric(context['context_recall_at_5'])}` |",
        f"| Answer Relevance Proxy F1 | `{_format_metric(context['answer_relevance_proxy_f1'])}` |",
        f"| Faithfulness Proxy Precision | `{_format_metric(context['faithfulness_proxy_precision'])}` |",
        "",
        "## 检索策略",
        "",
        "| 策略 | Case Recall@5 | Source Recall@5 | MRR | Alias Recall@5 |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, values in retrieval.items():
        lines.append(
            f"| {name} | `{_format_metric(values['case_recall_at_5'])}` | "
            f"`{_format_metric(values['source_recall_at_5'])}` | "
            f"`{_format_metric(values['mrr'])}` | "
            f"`{_format_metric(values.get('expected_alias_recall_at_5', 0.0))}` |"
        )

    grounding_failures = grounding.get("failures", [])
    context_failures = context.get("failures", [])
    lines.extend(
        [
            "",
            "## 边界与失败样例",
            "",
            f"- Agent grounding failure count：`{grounding['failure_count']}`",
            f"- Context quality failure count：`{context['failure_count']}`",
            "",
            "### Agent grounding failure samples",
            "",
        ]
    )
    if grounding_failures:
        for failure in grounding_failures[:10]:
            lines.append(
                f"- `{failure['id']}`：缺失来源 "
                f"`{', '.join(failure['missing_sources'])}`"
            )
    else:
        lines.append("- 无")

    lines.extend(["", "### Context quality failure samples", ""])
    if context_failures:
        for failure in context_failures[:10]:
            lines.append(
                f"- `{failure['id']}`：Context Recall="
                f"`{_format_metric(failure['context_recall'])}`，"
                f"Reference Term Recall=`{_format_metric(failure['reference_term_recall'])}`"
            )
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            f"- Embedding：{report['interpretation']['embedding']}。",
            f"- Faithfulness：{report['interpretation']['faithfulness']}。",
            f"- 外部服务：{report['interpretation']['external_services']}。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_if_changed(path: Path, content: str) -> None:
    """Write a report only when bytes differ, keeping clean Git runs clean."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    report = build_report()
    json_content = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    markdown_content = render_markdown(report)

    if args.json_output:
        _write_if_changed(args.json_output, json_content)
    if args.markdown_output:
        _write_if_changed(args.markdown_output, markdown_content)
    if not args.json_output and not args.markdown_output:
        print(json_content, end="")


if __name__ == "__main__":
    main()
