"""多 Agent 并行执行器。"""

import asyncio
from ..schemas import (
    ArticleInput, ArticleSegment, AgentConfig, AgentResult, KnowledgeChunk,
)
from ..agents.registry import AgentRegistry
from ..agents.runner import AgentRunner
from ..knowledge.retriever import filter_context_for_agent
from ..llm.base import LLMClient
from ..config import ReviewSettings


async def run_review_agents(
    agent_ids: list[str],
    registry: AgentRegistry,
    article: ArticleInput,
    segments: list[ArticleSegment],
    retrieved_context: list[KnowledgeChunk],
    llm_client: LLMClient,
    settings: ReviewSettings,
) -> list[AgentResult]:
    """并行执行多个审稿 Agent。

    特性：
    - asyncio 并行
    - 信号量控制并发数
    - 每个 Agent 独立 try/except
    - 单个 Agent 失败不导致整体失败
    - 结果按 priority 排序
    """
    runner = AgentRunner(llm_client)
    semaphore = asyncio.Semaphore(settings.max_concurrency)

    agent_configs: list[AgentConfig] = []
    for aid in agent_ids:
        if registry.exists(aid):
            agent_configs.append(registry.get(aid))

    # 按 priority 降序
    agent_configs.sort(key=lambda a: (-a.priority, a.agent_id))

    async def _run_one(agent: AgentConfig) -> AgentResult:
        async with semaphore:
            try:
                ctx = filter_context_for_agent(retrieved_context, agent)
                result = await asyncio.wait_for(
                    runner.run_reviewer(agent, article, segments, ctx),
                    timeout=settings.agent_timeout_seconds,
                )
                return result
            except asyncio.TimeoutError:
                return AgentResult(
                    agent_id=agent.agent_id,
                    agent_name=agent.name,
                    status="timeout",
                    error_message=f"Agent 超时 ({settings.agent_timeout_seconds}s)",
                )
            except Exception as e:
                return AgentResult(
                    agent_id=agent.agent_id,
                    agent_name=agent.name,
                    status="failed",
                    error_message=str(e),
                )

    results = await asyncio.gather(*[_run_one(a) for a in agent_configs])
    return list(results)
