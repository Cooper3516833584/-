# 高校学生媒体单次智能审稿工具：Markdown 实现包

本压缩包用于交给 AI 智能编程体实现项目。它不是产品说明书，而是工程实现任务书。

## 项目边界

本项目只做“单次智能审稿工具”，不做完整采编工作流，不做用户权限，不做组织管理，不做发布系统。

项目目标：输入一篇稿件，系统自动读取本地 txt 知识材料，Selector Agent 先判断稿件类型和应启用的审稿 Agent，随后并行执行多个审稿 Agent，合并与仲裁结果，输出结构化审稿报告。

## 你要求的关键存储方式

项目根目录下直接分多个文件夹存储可编辑 txt 文件：

```text
project-root/
  agents/             # Agent 配置 txt；包含 Selector Agent 和各审稿 Agent
  cases/              # 历史翻车案例 txt
  rules/              # 规矩、校规、审稿规范 txt
  style_guides/       # 栏目风格、媒体语气、写作规范 txt
  risky_phrases/      # 高风险表达、禁用表达、易误读表达 txt
  examples/           # 优秀稿件、改写样例、正例 txt
  input/              # 待审稿件，可选
  output/             # 审稿报告输出
```

## 文档阅读顺序

建议 AI 编程体按以下顺序执行：

1. `docs/00_实施总览.md`
2. `docs/01_项目边界与最终能力.md`
3. `docs/02_根目录txt存储结构.md`
4. `docs/03_数据结构与Schema.md`
5. `docs/04_Agent配置文件规范.md`
6. `docs/05_SelectorAgent自动选Agent机制.md`
7. `docs/06_知识库txt加载与检索.md`
8. `docs/07_审稿引擎主流程.md`
9. `docs/08_LLM调用与结构化输出校验.md`
10. `docs/09_并行执行与失败降级.md`
11. `docs/10_仲裁去重评分与报告分层.md`
12. `docs/11_CLI与可选WebAPI.md`
13. `docs/12_测试样例与验收标准.md`
14. `docs/13_分阶段开发任务清单.md`
15. `docs/14_可复制模板.md`

## 实现原则

- Prompt 以后可以细化，但现在必须先固定输入输出协议。
- 所有 Agent 输出必须统一成 Finding 结构。
- Selector Agent 可以自主选择 Agent，但必须有代码级兜底策略。
- 本地 txt 文件是知识和配置的主要载体，不依赖数据库。
- 每次审稿都是独立运行，结果写到 `output/`。
- 不做用户权限，不做长期工作流，不做复杂审批系统。
