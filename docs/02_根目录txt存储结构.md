# 02 根目录 txt 存储结构

## 1. 设计原则

用户明确希望项目根目录下分多个文件夹储存 Agent 配置、翻车案例、规矩等 txt 文件。因此本项目不把这些内容塞进数据库，也不要求使用后台管理页面。

设计原则：

```text
可直接用文本编辑器修改
可被 Git 版本管理
格式足够简单
代码可以稳定解析
新增材料不需要改代码
```

## 2. 根目录结构

项目根目录必须包含以下文件夹：

```text
agents/             Agent 配置 txt
cases/              翻车案例 txt
rules/              规矩、校规、审稿规范 txt
style_guides/       风格规范 txt
risky_phrases/      高风险表达 txt
examples/           正例样稿 txt
input/              待审稿件
output/             审稿输出
.cache/             自动生成的索引缓存，不手工编辑
```

其中 `.cache/` 可加入 `.gitignore`。

## 3. txt 文件通用格式

所有 txt 文件推荐使用 YAML front matter + 正文的方式。

格式：

```text
---
id: unique_id
title: 文件标题
type: 文件类型
tags:
  - 标签1
  - 标签2
---

正文内容……
```

解析规则：

```text
如果文件以 --- 开头，则读取第一段 --- 与第二段 --- 之间作为 YAML metadata。
第二段 --- 后面的全部文本作为 content。
如果文件没有 front matter，则 metadata 自动补默认值：
  id = 文件名不含扩展名
  title = 文件名
  type = 根据所在文件夹推断
  tags = []
```

## 4. agents/ 目录

示例结构：

```text
agents/
  00_selector_agent.txt
  fact_checker.txt
  risk_reviewer.txt
  audience_reviewer.txt
  format_reviewer.txt
  privacy_reviewer.txt
  copyright_reviewer.txt
  interview_ethics_reviewer.txt
  title_reviewer.txt
  custom_example.txt
```

### 4.1 命名规则

```text
Selector Agent 固定命名：00_selector_agent.txt
普通 Agent 文件名建议等于 agent_id：risk_reviewer.txt
自定义 Agent 也使用英文 snake_case：club_activity_reviewer.txt
```

### 4.2 Agent 配置 txt 示例

```text
---
agent_id: privacy_reviewer
name: 隐私与授权审查员
enabled: true
kind: reviewer
priority: 80
applies_to:
  article_types: [news, interview, activity, social_post, unknown]
  columns: ["*"]
capabilities:
  - privacy
  - authorization
  - portrait_rights
knowledge_sources:
  - rules
  - cases
  - risky_phrases
max_findings: 8
model:
  name: default
  temperature: 0.2
  timeout_seconds: 90
output_schema: AgentResult
---

# Role
这里写角色描述。具体 prompt 后续可以继续细化。

# Review Focus
- 检查是否暴露学生姓名、学号、班级、宿舍等个人信息。
- 检查图片、采访、截图是否涉及授权问题。

# Output Requirement
必须输出符合 AgentResult schema 的 JSON。
```

## 5. cases/ 目录

用于保存历史翻车案例。

示例：

```text
cases/
  case_2024_title_conflict.txt
  case_2024_privacy_photo.txt
  case_2023_interview_quote.txt
```

推荐格式：

```text
---
case_id: case_2024_privacy_photo
title: 活动照片未打码引发投诉
case_type: privacy
severity: high
tags:
  - photo
  - privacy
  - complaint
related_agent_ids:
  - privacy_reviewer
  - copyright_reviewer
---

【事件概述】
某活动推文使用近距离学生照片，未征得当事人授权，也未对敏感场景进行处理。

【引发问题】
当事人认为照片发布未经许可，要求删除并道歉。

【复盘结论】
涉及可识别个人形象的照片，尤其是近景、表情明显、场景敏感时，应确认授权或使用模糊处理。

【避坑建议】
审稿时重点检查图片说明、照片主体、截图、聊天记录等内容。
```

## 6. rules/ 目录

用于保存规矩、制度、审稿规范。

示例：

```text
rules/
  school_publicity_rules.txt
  student_media_internal_review_rules.txt
  interview_authorization_rules.txt
```

推荐格式：

```text
---
rule_id: school_publicity_rules
title: 学校宣传内容规范摘要
rule_type: school_rule
authority_level: high
effective_from: 2025-09-01
tags:
  - publicity
  - school_image
  - review
---

正文……
```

代码要求：

```text
rules/ 下的文档在检索结果中权重高于 examples/。
authority_level=high 的材料在仲裁评分中加权。
```

## 7. style_guides/ 目录

用于保存栏目风格、写作语气、标题规范。

示例：

```text
style_guides/
  news_style.txt
  interview_style.txt
  activity_post_style.txt
  commentary_style.txt
```

推荐字段：

```text
---
style_id: news_style
title: 新闻稿风格规范
applies_to:
  article_types: [news]
  columns: ["*"]
tags:
  - concise
  - neutral
  - factual
---

正文……
```

## 8. risky_phrases/ 目录

用于保存风险表达、禁用表达、容易被误读的词。

示例：

```text
risky_phrases/
  group_conflict_phrases.txt
  bureaucratic_phrases.txt
  title_clickbait_phrases.txt
```

推荐格式：

```text
---
phrase_list_id: group_conflict_phrases
title: 群体对立风险表达
tags:
  - group_conflict
  - wording
---

# 高风险表达
- 某某群体都……
- 所有人都应该……
- 不努力就是……

# 风险解释
这些表达容易把个体问题扩大为群体判断，引发对立。
```

## 9. examples/ 目录

用于保存优秀稿件、优秀标题、优秀修改示例。

示例：

```text
examples/
  good_activity_post.txt
  good_interview_intro.txt
  title_revision_examples.txt
```

代码要求：

```text
examples/ 的检索结果主要给 audience_reviewer、format_reviewer、title_reviewer 使用。
examples/ 不应作为高危风险判定依据，只作为风格和改写参考。
```

## 10. input/ 目录

用于放待审稿件。

支持：

```text
.md
.txt
```

第一版不需要解析 docx、pdf。后续可扩展。

## 11. output/ 目录

每次审稿生成一个 run_id 文件夹：

```text
output/
  20260524_152300_x7a9k2/
    article_snapshot.md
    selector_result.json
    agent_results.json
    report.json
    report.md
    debug.log
```

必须保存 `article_snapshot.md`，因为之后稿件可能被修改，审稿报告需要能对应当时版本。

## 12. .cache/ 目录

用于缓存知识库索引：

```text
.cache/
  corpus_index.jsonl
  keyword_index.json
  embeddings.npy
  file_hashes.json
```

如果不实现 embedding，仍可以保留：

```text
.cache/corpus_index.jsonl
.cache/file_hashes.json
```

实现规则：

```text
每次运行先扫描 txt 文件 hash。
如果 hash 未变化，复用缓存。
如果变化，重新构建索引。
```
