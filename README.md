# 中国钢铁全球政策情报看板

公开看板：https://davidzhu511.github.io/china-steel-policy-watch/

## 分工

**GitHub 自动收集与发布；ChatGPT 翻译、核验与解读。**

GitHub Actions 独立采集官方来源和新闻索引、去重、保存原始链接与有限摘录、生成待分析队列、测试和发布。日常采集不调用付费模型，也不下载离线翻译模型。

ChatGPT 读取队列，优先处理重要新增与临期政策，每轮最多5条。读取原文后提供中文标题、核心事实、对中国钢材出口的影响与下一步动作。仅有标题或不足的证据不能支持税率、期限、产品范围或法规状态结论。

有新成果时，ChatGPT 按原始 URL + 来源日期增量修改 `config/editorial.json` 或 `config/triage.json`，提交一个 `editorial/` 前缀的纯内容 PR。GitHub 自动执行测试、检查文件范围与提交版本、合并和发布；ChatGPT 不负责轮询 CI、等待部署、重复采集或修理流水线。提交成功不等于上线成功，简报可写“解读已提交，网页自动发布处理中”。

## 自动采集与内容发布

采集目标为每天 **07:50、13:50（Europe/Berlin）**。冬夏令时 UTC 候选时段中不适用的时段会正常跳过；这不是采集失败或部署失败。GitHub 调度可能延迟，目标时间不是到点完成承诺。ChatGPT 按最新可用资料分析，注明资料日期，不把当天未刷新一律报错。

- 定时运行及默认手动运行：采集、应用已核验解读、生成并发布。
- 纯编辑提交，以及自动合并后的 `mode=editorial`：只应用解读并发布已有数据，不再次访问采集来源。
- 内容发布保留 `generated_at` 采集时间，单列 `editorial_updated_at`，不会用编辑时间冒充新采集。
- GitHub 继续执行部署与公网数据一致性验证。正常跳过、等待运行或未完成的验证不能称为部署失败。

## ChatGPT 的输入与输出

优先读取 `data/review_queue.json`，避免反复读取完整历史：

- `schema_version=2`：`items` 只包含可分析条目；`blocked_items` 保存证据受阻条目。
- `actionable_count` 是本轮可处理数，`blocked_count` 是暂缓数；`pending_count` 为两者之和。因此可处理列表为空但待处理总数大于0并非错误。
- 受阻条目保持未核验，只有新来源版本、新证据或用户要求时重查，不每天反复访问同一受阻页面。
- 完整历史仍在 `data/items.json`；网页和 RSS 不会把暂缓内容冒充已核验结论。

简报只提供值得关注的新事实、业务影响、下一步动作及来源链接；必要时附内容 PR。没有实质新内容时静默，不输出每日运行状态表或重复故障报告。基础设施故障由 GitHub 记录；只有持续影响业务或需要用户处理时才提醒。

## 来源与范围

来源配置在 `config/sources.json`。当前包括欧盟公众咨询、EUR-Lex、欧委会重点页面、美国 Federal Register、GOV.UK、官方及 Google News RSS。GDELT 保留为停用的备用来源。

追踪与中国钢铁相关的法规、贸易救济、配额关税、原产地、碳政策、市场和企业信息。单一来源失败不应删除历史或阻断其他来源。成功但零命中不代表完整覆盖，也不自动表示失败；来源状态保留错误、最后成功与最后收录时间。

## 内容版本与准确性

`config/editorial.json` 保存经核验的双语解读。`published_date` 精确匹配被核验版本；来源误用观察日期时才使用 `match_published_date`，并保留真实文件日期。证据链接与核验范围分别写入 `evidence_url`、`coverage`。

`config/triage.json` 中 `duplicate` 合并到已核验主条目，`excluded` 排除无关内容，`blocked` 保存证据不足原因。新来源日期不沿用旧版本的处理结论。不得把暂缓条目算作完成。

这是信息发现和辅助研判工具，正式政策结论必须有主管机关原文支持。媒体内容仅保存有限摘录、摘要和链接，不存储新闻全文。

## 开发与维护

```bash
python -m pip install -e ".[dev]"
ruff check steelwatch tests scripts
pytest
python -m steelwatch render
```

`render` 只生成静态展示；`publish-editorial` 应用当前内容配置，不采集；`update` 执行采集。需要现有采集快照才能单独发布解读。

代码和工作流修改使用独立 PR；只有同仓库、确切 CI 通过、最新提交未变化且仅修改两份内容配置的 `editorial/` PR 可以自动合并。不得绕过检查、伪造采集时间或用空提交触发发布。测试、合并、部署及公网验证均由 GitHub 完成。

历史保留默认730天。核心目录：`config/` 配置，`steelwatch/` 程序，`data/` 历史和队列，`docs/` 看板，`tests/` 测试，`.github/workflows/` 自动运行。
