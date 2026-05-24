"""Mock LLM 客户端：用于测试和无 API key 环境。"""

from .base import LLMClient, LLMResponse


class MockLLMClient(LLMClient):
    """Mock LLM 客户端。根据 system/user 中的关键词返回固定 JSON。"""

    async def complete_json(
        self,
        system: str,
        user: str,
        model: str = "default",
        temperature: float = 0.2,
        timeout_seconds: int = 90,
    ) -> LLMResponse:
        import time
        start = time.time()

        text = _generate_mock_response(system, user)
        latency = int((time.time() - start) * 1000)

        return LLMResponse(
            text=text,
            raw={"choices": [{"message": {"content": text}}]},
            token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            latency_ms=latency,
        )


def _generate_mock_response(system: str, user: str) -> str:
    """根据 prompt 内容生成 mock JSON 响应。"""
    combined = (system + " " + user).lower()

    if "selector" in combined or "selectorresult" in combined:
        return _mock_selector_result()

    if "risk" in combined:
        return _mock_findings("risk_reviewer", "舆情风险审查员", "high", "标题可能引发误读")

    if "privacy" in combined:
        return _mock_findings("privacy_reviewer", "隐私与授权审查员", "high", "包含可识别个人信息")

    if "fact" in combined:
        return _mock_findings("fact_checker", "事实与逻辑核查员", "medium", "时间表述不一致")

    if "format" in combined:
        return _mock_findings("format_reviewer", "文本校对与格式审查员", "low", "标点符号不一致")

    if "audience" in combined:
        return _mock_findings("audience_reviewer", "校园受众体验官", "medium", "语气偏官腔")

    # 默认返回空 findings
    return _mock_empty_result()


def _mock_selector_result() -> str:
    import json
    return json.dumps({
        "status": "success",
        "detected_article_type": "news",
        "detected_tags": ["news", "campus"],
        "selected_agents": [
            {"agent_id": "fact_checker", "reason": "基础事实核查", "priority": 80},
            {"agent_id": "risk_reviewer", "reason": "舆情风险评估", "priority": 90},
            {"agent_id": "privacy_reviewer", "reason": "隐私授权检查", "priority": 85},
            {"agent_id": "audience_reviewer", "reason": "受众体验", "priority": 60},
            {"agent_id": "format_reviewer", "reason": "文本校对", "priority": 50},
        ],
        "context_queries": ["校园新闻", "事实核查", "舆情风险"],
        "reasoning_summary": "稿件为校园新闻，建议启用基础审查 Agent。",
        "warnings": [],
    }, ensure_ascii=False)


def _mock_findings(agent_id: str, agent_name: str, risk: str, issue: str) -> str:
    import json
    return json.dumps({
        "agent_id": agent_id,
        "agent_name": agent_name,
        "status": "success",
        "findings": [
            {
                "finding_id": None,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "risk_level": risk,
                "confidence": "high",
                "issue_type": issue,
                "original_quote": "示例原文摘录",
                "segment_id": "s001",
                "problem": f"发现{issue}问题",
                "possible_consequence": "可能引发读者误解",
                "suggestion": f"建议修改{issue}相关内容",
                "evidence": [
                    {"source_type": "article", "source_id": None, "quote": "示例原文摘录"},
                ],
                "tags": [issue],
                "requires_attention": risk == "high",
            }
        ],
        "summary": f"发现 1 条{issue}相关问题。",
    }, ensure_ascii=False)


def _mock_empty_result() -> str:
    import json
    return json.dumps({
        "agent_id": "unknown",
        "agent_name": "未知审稿员",
        "status": "success",
        "findings": [],
        "summary": "未发现明显问题。",
    }, ensure_ascii=False)
