---
name: trace-debuger
description: End-to-end trace debugging from trace_id. Fetch Jaeger trace and Elasticsearch logs, analyze possible bugs (optionally with local repository context), and generate a fixed-structure Markdown report for CI or tickets.
---

# Trace Debuger

Use this skill to generate a self-contained Markdown trace debug report.

## Inputs

- `trace_id` (required)
- `jaeger_url` (optional, default `http://127.0.0.1:16686`)
- `es_url` (optional, default `http://127.0.0.1:9200`)
- `repo_path` (optional, absolute path, default `/Users/noodles/Desktop/code/go-components/examples/tracer`)
- `output_path` (optional, default `./trace_debug_report_{trace_id}.md`)
- `es_index` (optional, default `filebeat-tracer-*`)
- `es_size` (optional, default `2000`)

## Run

```bash
python3 skills/trace_debuger/scripts/trace_debuger.py \
  --trace-id <TRACE_ID> \
  [--jaeger-url http://127.0.0.1:16686] \
  [--es-url http://127.0.0.1:9200] \
  [--repo-path /Users/noodles/Desktop/code/go-components/examples/tracer] \
  [--output-path ./trace_debug_report_<TRACE_ID>.md]
```

## Output

- Writes Markdown report to `output_path`
- Prints fixed summary lines to stdout:

```text
trace_id: <trace_id>
status: SUCCESS/FAIL
jaeger_url: <jaeger_url>
es_url: <es_url>
代码仓库路径：<repo_path|N/A>
关键结论摘要：<summary>
```

## Notes

- Keep logs sorted by timestamp ascending.
- After fetching ES logs, run Codex in repository root (automated via `codex exec` equivalent to TUI paste workflow) with this prompt:
  - `这是我的日志，请根据日志结合代码帮我排查分析bug，输出bug原因及解决方案,必须保持固定的格式。`
- If repository is provided, include code-context hints and file matches for suspected bug areas.
- If repository is not provided, base bug hypotheses on logs + spans only.
- After analysis in chat workflow: send the generated Markdown file to the user through the chat window, then delete the local Markdown file.
