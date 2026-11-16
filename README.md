# 中国钢铁全球政策情报看板

公开看板：https://davidzhu511.github.io/china-steel-policy-watch/

## 处理流程

采集后立即收录，后台补充中文标题与有限摘录；事实核验和业务解读独立处理。中文标题不代表已核验法规或全文。看板分别显示待译标题、可研判条目和证据受阻条目。

| 工作 | 执行方式 | 目标安排（Europe/Berlin） |
| --- | --- | --- |
| 来源采集、去重、历史和初次发布 | GitHub Actions | 07:50、13:50、19:50 |
| 新增英文标题与有限摘录翻译 | 上述发布成功后自动触发CPU翻译 | 有待译内容才启动，缓存固定版本模型与译文 |
| 专业中文编辑、事实核验、业务研判 | ChatGPT已有新闻任务 | 08:30、14:30、20:30 |
| 内容验证、合并和发布 | GitHub Actions | 内容PR检查通过后 |
| 受阻证据复查 | ChatGPT读取retry_items | 每轮最多4条，官方默认3天、其他默认7天 |

以上为目标触发时间，GitHub和Chat任务可能延迟，不能视为到点完成承诺。第三轮也用于接住前两轮延迟到达的数据。空队列快速结束。采集和翻译使用既有GitHub运行环境，不需要购买模型API；Chat任务增加为每日三轮，会增加相应平台使用量。

## 编辑输入与增量输出

首先读取约1KB的 `data/review_manifest.json`；没有可处理、到期复查或待译标题时结束。需要处理时再读取 `data/review_queue.json`，不重复加载完整历史。

队列保持schema v2兼容：items可研判、blocked_items待证据，pending_count为两者之和。retry_items只是blocked_items中到期的至多4条，不能重复计数。队列附带标题译文、原文摘录、相近已核验主条、上次尝试和证据指纹。仅last_seen变化不会改变工作指纹。指标包含中文标题覆盖率和最老可研判条目的等待小时数。

每轮完整分流可处理条目，没有固定5条上限；先翻译标题，再按业务价值核验。配额、关税、贸易救济、原产地和碳政策优先，具有具体业务价值的市场、产能及企业信息也可保留。明确重复或无关内容可据标题作分流，但必须说明核验范围；实质事实、税率、期限和产品范围须有原文支持。

提交一个新的 `config/reviews/YYYYMMDD-HHMM-description.json`，无需重写越来越大的历史配置：

```json
{
  "schema_version": 1,
  "created_at": "2026-11-15T20:30:00+01:00",
  "translations": [],
  "editorial": [],
  "triage": []
}
```

- translations：url、published_date、title_original、title_zh、translated_at。原文摘录译文仅在提供精确source_excerpt时复用。只翻译，不升级核验状态。
- editorial：url、published_date、reviewed_at、title_zh/en、summary_zh/en、impact_zh/en、evidence_url、coverage，另可含分类、重要性、标签和follow_up。
- triage：url、published_date、decision、reason_zh、attempted_at、coverage。duplicate必须有duplicate_of；blocked可指定retry_after或retry_policy=manual。

按文件名时间顺序加载增量，后批次只覆盖同一来源版本。两个旧配置仍兼容。经核验的不同来源日期分别匹配，采集到同URL新版本时保留旧版本证据和已核验内容。禁止将新版本当作旧版本核验完成。

使用editorial/分支创建纯内容PR，自动检查、合并及发布。新批次文件只允许新增；更正放在后续新批次。工程变更使用独立PR。自动合并核对仓库身份、文件范围、CI成功与确切提交SHA，禁止绕过CI。纯内容发布不重复采集，保留generated_at采集时间，另记editorial_updated_at和translation_updated_at。

## 自动翻译与失败处理

采用已固定提交版本并逐文件校验的Helsinki-NLP/opus-mt-en-zh模型，在CPU上翻译；术语与数字须通过完整性检查。机器译文始终标记待核验，不产生正式业务影响结论。非英文内容由编辑补译。翻译独立于采集发布；失败保留原文、记录状态并冷却6小时，避免失败发布形成循环。不配置付费API、不把采集成功当作翻译成功。

官方网站和媒体的证据受阻分别保留，不为清零而伪造事实。失败复查必须更新尝试时间和下一次日期；真实新证据可以提前复查。付费墙等稳定限制可转人工待资料，不能绕过访问控制。

## 来源、历史与维护

监控范围包括中国钢材直接面临的措施，以及针对其他供应国家/地区、影响钢材竞争和贸易流向的措施；不要求原文出现China。钢材反倾销、反补贴、反规避、保障措施、配额关税、原产地及进出口限制均可入队，包括立案、初裁、终裁、复审、延长、撤销和豁免。非钢铁产品措施仍须过滤。

EUR-Lex、DG TRADE、美国Federal Register、GOV.UK和全球钢材贸易救济新闻发现共用产品与措施筛选。第三国措施研判需核对实施方、原产地、产品与排除项、税率及企业差异、阶段和生效/应诉日期，再评估替代采购、竞争报价与贸易转移。明确区分事实与推断，不能将竞争来源被征税等同于中国钢材自动免税或必然受益。

来源在config/sources.json，包括欧盟公众咨询、EUR-Lex、欧委会重点页、美国Federal Register、GOV.UK和RSS。单一来源失败不删除历史或阻断其他来源；零命中不代表完整覆盖。媒体仅保存有限摘录、摘要和链接，不保存全文。默认保留730天历史。

```bash
python -m pip install -e ".[dev]"
python scripts/validate_content.py
ruff check steelwatch tests scripts
pytest
node --check docs/app.js
python -m steelwatch render
```

update执行采集；publish-editorial仅应用内容配置；translate只翻译已有快照；render只生成静态展示。GitHub继续验证实际公开页面的数据校验值，未确认发布时只能报告已提交。运行记录与错误保存在GitHub，用户简报聚焦新事实、影响、行动与来源，不每天重复系统状态。
