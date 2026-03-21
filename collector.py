#!/usr/bin/env python3
"""
Hermes Training Data Collector

Collects successful agent interactions from Hermes session logs
and formats them as JSONL training data for fine-tuning a small
specialized model.

Scans:
- ~/.hermes/logs/ (gateway logs with tool calls)
- ~/.hermes/sessions/ (session transcripts)
- Cron job logs

Outputs:
- ~/projects/hermes-model/data/agent_interactions.jsonl
"""

import json
import os
import re
import glob
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

OUTPUT_DIR = Path("/root/projects/hermes-model/data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIRS = [
    Path.home() / ".hermes" / "logs",
]

SESSION_DIRS = [
    Path.home() / ".hermes" / "sessions",
]


def extract_tool_calls_from_log(log_path: Path) -> List[Dict[str, Any]]:
    """Extract successful tool call patterns from gateway logs."""
    interactions = []
    try:
        content = log_path.read_text(errors="replace")
    except (OSError, PermissionError):
        return interactions

    # Pattern: tool call with successful result
    tool_pattern = re.compile(
        r'(?:INFO|DEBUG).*?(?:tool_call|execute_tool|calling)\s+(\w+).*?'
        r'(?:result|output|success).*?(.{20,200})',
        re.IGNORECASE | re.DOTALL
    )

    for match in tool_pattern.finditer(content):
        interactions.append({
            "type": "tool_call",
            "tool": match.group(1),
            "result_preview": match.group(2).strip()[:200],
            "source": str(log_path.name),
        })

    return interactions


def extract_session_conversations(session_dir: Path) -> List[Dict[str, Any]]:
    """Extract conversation patterns from session files."""
    interactions = []

    for session_file in session_dir.glob("*.json"):
        try:
            data = json.loads(session_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        messages = data.get("messages", []) or data.get("conversation", [])
        if not messages:
            continue

        # Extract user-assistant pairs that resulted in tool use
        for i, msg in enumerate(messages):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Get the user message that preceded this
                user_msg = None
                for j in range(i - 1, max(0, i - 5), -1):
                    if messages[j].get("role") == "user":
                        user_msg = messages[j].get("content", "")
                        break

                if user_msg:
                    interactions.append({
                        "type": "agent_interaction",
                        "user_request": user_msg[:500],
                        "tools_used": [
                            tc.get("function", {}).get("name", "unknown")
                            for tc in msg["tool_calls"]
                        ],
                        "assistant_response": msg.get("content", "")[:500],
                        "source": session_file.name,
                    })

    return interactions


def format_as_training_example(interaction: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Convert an interaction to a training example format."""
    if interaction["type"] == "tool_call":
        return {
            "messages": json.dumps([
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant that uses tools to complete tasks."
                },
                {
                    "role": "user",
                    "content": f"Use the {interaction['tool']} tool to help with this task."
                },
                {
                    "role": "assistant",
                    "content": f"I'll use the {interaction['tool']} tool.",
                    "tool_calls": [{"function": {"name": interaction["tool"]}}]
                }
            ]),
            "source": interaction.get("source", "unknown"),
            "collected_at": datetime.utcnow().isoformat(),
        }

    elif interaction["type"] == "agent_interaction":
        return {
            "messages": json.dumps([
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant that uses tools to complete tasks."
                },
                {
                    "role": "user",
                    "content": interaction["user_request"]
                },
                {
                    "role": "assistant",
                    "content": interaction["assistant_response"],
                    "tool_calls": [
                        {"function": {"name": tool}}
                        for tool in interaction["tools_used"]
                    ]
                }
            ]),
            "source": interaction.get("source", "unknown"),
            "collected_at": datetime.utcnow().isoformat(),
        }

    return None


def run_collection():
    """Main collection pipeline."""
    all_interactions = []

    # Collect from logs
    for log_dir in LOG_DIRS:
        if log_dir.exists():
            for log_file in log_dir.glob("*.log"):
                all_interactions.extend(extract_tool_calls_from_log(log_file))

    # Collect from sessions
    for session_dir in SESSION_DIRS:
        if session_dir.exists():
            all_interactions.extend(
                extract_session_conversations(session_dir)
            )

    # Format as training data
    training_examples = []
    seen = set()
    for interaction in all_interactions:
        example = format_as_training_example(interaction)
        if example:
            key = json.dumps(example, sort_keys=True)
            if key not in seen:
                seen.add(key)
                training_examples.append(example)

    # Write JSONL
    output_file = OUTPUT_DIR / "agent_interactions.jsonl"
    with open(output_file, "w") as f:
        for example in training_examples:
            f.write(json.dumps(example, ensure_ascii=False) + "\n")

    # Stats
    stats = {
        "total_interactions_found": len(all_interactions),
        "unique_training_examples": len(training_examples),
        "output_file": str(output_file),
        "collected_at": datetime.utcnow().isoformat(),
        "sources": list(set(e.get("source", "unknown") for e in training_examples)),
    }

    stats_file = OUTPUT_DIR / "collection_stats.json"
    stats_file.write_text(json.dumps(stats, indent=2))

    print(f"Collected {len(all_interactions)} interactions")
    print(f"Generated {len(training_examples)} unique training examples")
    print(f"Output: {output_file}")
    return stats


if __name__ == "__main__":
    run_collection()
