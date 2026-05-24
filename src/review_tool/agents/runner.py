"""AgentRunner：执行单个审稿 Agent，构造 prompt、调用 LLM、校验输出。"""

import time
from ..schemas import (
    ArticleInput, ArticleSegment, AgentConfig, AgentResult, KnowledgeChunk,
    make_finding_id,
)
from ..llm.base import LLMClient
from ..llm.structured import call_with_schema, InvalidLLMOutputError
from .prompt_builder import build_reviewer_prompt


class AgentRunner:
    """执行单个审稿 Agent 的运行器。"""

    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    async def run_reviewer(
        self,
        agent: AgentConfig,
        article: ArticleInput,
        segments: list[ArticleSegment],
        context: list[KnowledgeChunk],
    ) -> AgentResult:
        """运行单个审稿 Agent。

        Args:
            agent: Agent 配置。
            article: 稿件。
            segments: 稿件分段。
            context: 该 Agent 所需的知识库上下文（已过滤）。

        Returns:
            AgentResult，即使失败也会返回 status=failed 的结果。
        """
        start = time.time()

        try:
            system, user = build_reviewer_prompt(agent, article, segments, context)

            parsed, response = await call_with_schema(
                llm_client=self._llm,
                system=system,
                user=user,
                schema_model=AgentResult,
                model=agent.model.name,
                temperature=agent.model.temperature,
                timeout_seconds=agent.model.timeout_seconds,
                max_retries=agent.model.max_retries,
            )

            latency = int((time.time() - start) * 1000)

            # 补全字段
            parsed.agent_id = agent.agent_id
            parsed.agent_name = agent.name
            if parsed.status == "success":
                parsed.status = "success"

            for f in parsed.findings:
                f.agent_id = agent.agent_id
                f.agent_name = agent.name
                if not f.finding_id:
                    f.finding_id = make_finding_id(
                        agent.agent_id, f.original_quote, f.issue_type
                    )

            parsed.latency_ms = latency
            parsed.token_usage = response.token_usage
            parsed.raw_output = response.text

            return parsed

        except InvalidLLMOutputError as e:
            latency = int((time.time() - start) * 1000)
            return AgentResult(
                agent_id=agent.agent_id,
                agent_name=agent.name,
                status="invalid_output",
                error_message=str(e),
                latency_ms=latency,
            )

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            return AgentResult(
                agent_id=agent.agent_id,
                agent_name=agent.name,
                status="failed",
                error_message=str(e),
                latency_ms=latency,
            )
