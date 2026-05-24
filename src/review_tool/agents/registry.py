"""AgentRegistry：Agent 注册与查询中心。"""

from ..schemas import AgentConfig


class AgentRegistry:
    """管理所有 Agent 配置的注册表。"""

    def __init__(self, configs: list[AgentConfig]):
        self._configs: dict[str, AgentConfig] = {}
        self._selector: AgentConfig | None = None

        for c in configs:
            self._configs[c.agent_id] = c
            if c.kind == "selector":
                self._selector = c

    def get(self, agent_id: str) -> AgentConfig:
        """获取指定 Agent 配置。"""
        if agent_id not in self._configs:
            raise KeyError(f"Agent 不存在: {agent_id}")
        return self._configs[agent_id]

    def exists(self, agent_id: str) -> bool:
        """检查 Agent 是否存在。"""
        return agent_id in self._configs

    def list_enabled_reviewers(self) -> list[AgentConfig]:
        """列出所有启用的 reviewer Agent。"""
        return [
            c for c in self._configs.values()
            if c.enabled and c.kind == "reviewer"
        ]

    def get_selector(self) -> AgentConfig:
        """获取 Selector Agent 配置。"""
        if self._selector is None:
            raise ValueError("未配置 Selector Agent")
        return self._selector

    def build_catalog_for_selector(self) -> list[dict]:
        """为 Selector Agent 构建轻量 Agent 目录。

        只返回 agent_id, name, priority, capabilities, applies_to, knowledge_sources。
        不返回 prompt_body。
        """
        catalog = []
        for c in self._configs.values():
            if not c.enabled:
                continue
            if c.kind == "selector":
                continue
            catalog.append({
                "agent_id": c.agent_id,
                "name": c.name,
                "priority": c.priority,
                "capabilities": c.capabilities,
                "applies_to": {
                    "article_types": c.applies_to.article_types,
                    "columns": c.applies_to.columns,
                },
                "knowledge_sources": c.knowledge_sources,
            })
        return catalog

    def __len__(self) -> int:
        return len(self._configs)

    def __contains__(self, agent_id: str) -> bool:
        return agent_id in self._configs
