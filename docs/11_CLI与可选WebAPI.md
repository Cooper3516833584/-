# 11 CLI 与可选 Web API

## 1. 第一版必须先做 CLI

本项目是单次审稿工具，CLI 最稳定、最容易交给 AI 编程体实现和测试。

命令：

```bash
review-tool review input/article.md
```

默认：

```text
project_root = 当前目录
output_dir = ./output
```

## 2. Typer CLI 结构

文件：

```text
src/review_tool/cli.py
```

命令：

```text
review-tool review ARTICLE_PATH
review-tool select-agents ARTICLE_PATH
review-tool validate-config
review-tool index
review-tool show-agents
```

## 3. review 命令

```python
@app.command()
def review(
    article_path: Path,
    project_root: Path = Path("."),
    output: Path = Path("output"),
    debug: bool = False,
):
    ...
```

行为：

```text
初始化 ReviewEngine。
运行 review_file。
在终端打印报告路径。
如果有 must_fix，终端显示数量。
如果有 warnings，终端显示 warnings。
```

终端输出示例：

```text
审稿完成。
run_id: 20260524_152300_a1b2c3
报告: output/20260524_152300_a1b2c3/report.md
必须修改: 2
建议修改: 5
警告: Selector Agent 失败，已使用兜底 Agent。
```

## 4. select-agents 命令

用途：只运行预处理和 Selector，不执行审稿。

```bash
review-tool select-agents input/article.md
```

输出：

```text
检测稿件类型：interview
识别标签：privacy, quote_integrity
启用 Agent：
- fact_checker：基础事实核查
- privacy_reviewer：稿件包含学生个人经历和照片
- interview_ethics_reviewer：疑似采访稿
```

实现：

```text
load article
preprocess
build hints
run selector
validate selector result
print selected_agent_ids
```

## 5. validate-config 命令

```bash
review-tool validate-config
```

检查：

```text
agents/ 是否存在
是否有 selector
是否只有一个 selector
agent_id 是否重复
AgentConfig 是否符合 schema
基础 Agent 是否存在
knowledge dirs 是否存在，不存在则 warning
```

如果有错误，退出码非 0。

## 6. index 命令

```bash
review-tool index
```

行为：

```text
加载 cases/rules/style_guides/risky_phrases/examples
切块
写 .cache/corpus_index.jsonl
打印文档数量和 chunk 数量
```

## 7. show-agents 命令

```bash
review-tool show-agents
```

输出：

```text
selector                 Agent选择器          enabled selector
fact_checker             事实与逻辑核查员      enabled reviewer
risk_reviewer            舆情风险审查员        enabled reviewer
privacy_reviewer         隐私与授权审查员      enabled reviewer
```

## 8. pyproject.toml

需要配置 console script：

```toml
[project.scripts]
review-tool = "review_tool.cli:app"
```

## 9. 可选 Web API

CLI 完成后再做。

最小 FastAPI：

```text
POST /review
```

请求：

```json
{
  "title": "...",
  "body": "...",
  "column": "校园生活",
  "article_type": "unknown"
}
```

响应：

```json
{
  "run_id": "...",
  "report_markdown": "...",
  "report": {...}
}
```

## 10. Web API 注意事项

既然不做权限系统，Web API 只适合本地或内网。

不要默认暴露公网。

启动：

```bash
uvicorn review_tool.api:app --host 127.0.0.1 --port 8000
```

## 11. 验收测试

必须写：

```text
test_cli_validate_config_success
test_cli_review_creates_output
test_cli_select_agents_prints_agents
test_cli_show_agents_lists_enabled_agents
```
