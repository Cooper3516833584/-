"""Agent 配置加载器：从 agents/*.txt 加载并校验所有 Agent 配置。"""

from pathlib import Path
from ..schemas import AgentConfig
from ..loaders.frontmatter import load_txt_with_frontmatter


def load_agent_configs(agent_dir: Path) -> list[AgentConfig]:
    """加载并校验 agents/ 目录下所有 Agent 配置。

    Args:
        agent_dir: agents/ 目录路径。

    Returns:
        排序后的 AgentConfig 列表。

    Raises:
        FileNotFoundError: 目录不存在。
        ValueError: 配置校验失败。
    """
    if not agent_dir.exists():
        raise FileNotFoundError(f"Agent 配置目录不存在: {agent_dir}")

    configs: list[AgentConfig] = []
    agent_ids: set[str] = set()
    selector_count = 0

    for txt_file in sorted(agent_dir.glob("*.txt")):
        try:
            metadata, prompt_body = load_txt_with_frontmatter(txt_file)
        except ValueError as e:
            raise ValueError(f"文件 {txt_file.name} 解析失败: {e}") from e

        if "agent_id" not in metadata:
            raise ValueError(f"文件 {txt_file.name} 缺少必填字段 agent_id")

        agent_id = str(metadata["agent_id"])

        if agent_id in agent_ids:
            raise ValueError(f"Agent ID 重复: {agent_id}")

        agent_ids.add(agent_id)

        config = AgentConfig(
            agent_id=agent_id,
            name=str(metadata.get("name", agent_id)),
            enabled=bool(metadata.get("enabled", True)),
            kind=str(metadata.get("kind", "reviewer")),
            priority=int(metadata.get("priority", 50)),
            applies_to=metadata.get("applies_to", {}),
            capabilities=metadata.get("capabilities", []),
            knowledge_sources=metadata.get("knowledge_sources", []),
            max_findings=int(metadata.get("max_findings", 8)),
            model=metadata.get("model", {}),
            output_schema=str(metadata.get("output_schema", "AgentResult")),
            prompt_body=prompt_body,
            metadata={k: v for k, v in metadata.items() if k not in {
                "agent_id", "name", "enabled", "kind", "priority",
                "applies_to", "capabilities", "knowledge_sources",
                "max_findings", "model", "output_schema",
            }},
        )

        if config.kind == "selector":
            selector_count += 1
            if not config.enabled:
                raise ValueError(f"Selector Agent ({agent_id}) 必须 enabled=true")

        configs.append(config)

    if selector_count == 0:
        raise ValueError("未找到 kind=selector 的 Agent，必须配置一个 Selector Agent")
    if selector_count > 1:
        raise ValueError(f"找到 {selector_count} 个 selector Agent，只允许一个")

    # 按 priority 降序，同 priority 按 agent_id 字母序
    configs.sort(key=lambda c: (-c.priority, c.agent_id))
    return configs
