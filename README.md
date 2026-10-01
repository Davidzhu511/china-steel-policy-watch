# 中国钢铁全球政策情报看板

每天自动采集与中国钢铁有关的法规、贸易救济、配额/关税、原产地、碳政策、市场和企业新闻，提供来源核对后的中英文重点解读，并可选接入自动摘要，并通过 GitHub Pages 发布静态看板。每条情报都保留官方或原始网页链接。

## 看板包含什么

- **正式法规优先**：EUR-Lex 的 L 系列法规和 C 系列公告分别采集，不把新闻和法律文件混为一类。
- **政策前置预警**：接入欧委会 Have Your Say 官方接口，追踪钢铁与 CBAM 倡议，并显示征求意见状态和截止日期。
- **重点市场官方来源**：欧盟公众咨询与官方公报、美国 Federal Register、GOV.UK。
- **多源新闻发现**：DG CLIMA / DG TRADE 官方 RSS、DG TAXUD / CLIMA / TRADE 页面直采、Google News 中英文索引。GDELT 已默认停用，保留为可选备用。
- **双视图与归档**：默认按发布时间显示最新动态；重点关注含重大、高优先级及待跟进节点。支持 CBAM、EU ETS / UK ETS、关税与贸易救济、钢企与市场主题，以及时间范围、首次收录排序。
- **中英文研判**：经原文核对的重点解读保存在 `config/editorial.json`，仅适用指定日期的来源版本。每日离线英译中模型为未解读条目翻译标题及原文摘录，明确标注“机器译文 · 待研判”；不据此声称业务影响或法规状态已经核实。
- **个性化外观**：内置黑金、深海蓝、翡翠绿、赤铜棕、紫晶夜和象牙浅色六套配色，语言与主题偏好保存在浏览器本地。
- **历史与去重**：近似标题和规范化 URL 去重；历史情报默认保留 730 天。
- **健康隔离**：单个来源失败不会中断其他来源，也不会删除已有历史数据。
- **静态发布**：采集与 GitHub Pages 发布不依赖付费模型服务。GitHub Models 已于 2026-07-30 退役（[官方说明](https://docs.github.com/en/github-models)），不再调用旧接口或传递 `GITHUB_TOKEN` 给模型端点。英文原文机器译文由 GitHub Actions 在本机运行的 [OPUS 英译中模型](https://huggingface.co/Helsinki-NLP/opus-mt-en-zh) 生成；自动业务影响研判仍需另行配置模型服务。

## 自动更新时间

工作流每天按德国杜塞尔多夫时间 **07:50** 运行。GitHub cron 只接受 UTC，因此配置了 05:50 和 06:50 两个候选时点，再依据 `Europe/Berlin` 当天的夏令时偏移只放行其中一次，保证冬夏时间切换后仍是当地 07:50。

GitHub 的定时任务在平台繁忙时可能延迟数分钟；这不改变应运行的当地日期和时段。

## 首次部署

1. 把项目推送到公开仓库 `Davidzhu511/china-steel-policy-watch`，默认分支使用 `main`。
2. 打开仓库 **Settings → Actions → General → Workflow permissions**，选择 **Read and write permissions**。
3. 打开 **Settings → Pages → Build and deployment**，将 Source 设为 **GitHub Actions**。
4. 进入 **Actions → 每日更新并部署看板 → Run workflow**，手动执行首轮更新。
5. 成功后访问 `https://davidzhu511.github.io/china-steel-policy-watch/`。

## 本地运行

```bash
python -m pip install -e ".[dev]"
pytest
python -m steelwatch render
python -m http.server 8000 --directory docs
```

浏览器打开 `http://localhost:8000`。无模型凭据时 `python -m steelwatch update` 仍完整收录新信息。若要在本地生成机器译文，先安装 CPU 版 PyTorch 与 `pip install -e '.[translation]'`，再运行 `python scripts/prepare_translation.py` 下载并核验固定版本的公开模型（约 312 MB 权重）；译文保留原文供核对。GitHub Actions 自动准备并缓存模型；失败时只显示原文，不中断新闻更新。

可选自动解读：在仓库 Actions Variables 中配置 `STEELWATCH_MODEL_ENDPOINT`（受信任服务的完整 HTTPS chat/completions URL）和 `STEELWATCH_MODEL`（模型名）；在 Actions Secrets 中配置 `STEELWATCH_MODEL_API_KEY`。端点需兼容 Chat Completions 的 JSON 输出。不要把 API key 写进代码或来源配置。未配置时默认禁用，不承诺自动翻译完成。

每轮默认最多收录 120 条候选记录，最多 12 条参与可选模型解读。模型失败不会阻止其余记录入库；历史记录不会因为离开 RSS 窗口或单次来源故障被删除。
每轮最多补充 100 条机器译文，设有 180 秒上限。术语与数字保护失败时保留原文并在下轮重试。官方贸易救济与 CBAM 执行标题会按可解释的关键词进入“重点关注”，属于待核对线索，不代表正式认定。

## ChatGPT 定时研判与发布核验

采集工作流继续负责发现和保留原文；ChatGPT 任务读取仓库与官方来源后，把版本限定的双语研判写入 `config/editorial.json`。这是外部任务，不能用 `analysis_status=available` 冒充仓库内模型 API 已配置。未核验条目仍保留待处理状态。

每次内容更新应通过分支和 PR，经 CI 校验后合并，再确认部署和线上数据。原文同 URL 的新版必须重新核验；`reviewed_at` 不能替代发布或采集日期。DG TRADE 咨询列表可独立于 Have Your Say 接口采集，保存当前 OPEN/CLOSED 状态及带时区的截止日期；USTR 钢铁公告也是直采来源。

如果合并后没有新的发布运行，而连接工具没有 workflow_dispatch，可通过已授权的 GitHub 重跑作业功能启动现有 update 作业。该工作流明确检出 main，因此会处理当前内容。先检查该运行的构建包：旧工作流未使用独立名称时，选择构建包列表为空的历史运行（例如旧包已到期的 push 运行），并确认其调度门允许执行；不要重跑仍有同名 Pages 包的旧运行，否则部署会因多个同名包失败。若没有合适运行，应报告发布阻塞，不能宣称网站已更新。

新工作流为每个运行/尝试使用独立的 Pages 包名称，并将实际 update 作业的名称作为输出传给 deploy，支持只重试部署作业时仍选择正确的构建包。最终必须读取线上 `data/items.json` 和 `data/status.json`，核对实际发布日期、研判内容与待处理数量；主分支已有内容并不等同于线上已发布。

## 配置来源和关键词

所有配置在 [`config/sources.json`](config/sources.json)：

- `sources.*.enabled`：启停某个来源；
- `lookback_days`：每次回看天数；
- `queries`：官方搜索或 GDELT 查询；
- `sources.ec_have_your_say.match_terms`：欧委会倡议的钢铁领域匹配词；
- `keywords.china`：中国钢企和中国主体词；
- `keywords.materials`：钢铁产品、原料和加工品；
- `keywords.global_steel_policy`：即使标题未直接写 China，仍会影响中国出口的普遍性钢铁政策；
- `keywords.universal_policy`：无需同时出现 China 或 steel 也应纳入的跨品类制度（包括 CBAM、EU ETS、UK ETS）；
- `official_domains`：把新闻索引中的政府/国际组织域名升级为官方来源。

建议先扩充配置再改程序。新增查询应保持“主体词 + 钢铁词 + 措施词”的组合，避免抓入体育、影视或泛金属噪声。

## 数据流

1. 并行抓取官方来源及中英文 RSS；每个页面/订阅源独立报告异常。
2. 根据标题、来源和关键词筛选，规范 URL 并去重。
3. 收录原始记录；自动解读为可选独立步骤，失败时保留待解读记录。
4. 应用经原文核对的版本限定解读，再生成看板 JSON 与 RSS。

来源状态列出抓取命中数量；`analysis_status` 单独报告自动解读是否可用。来源请求成功但无命中显示为零，部分渠道失败显示部分异常。转载的相同标题保留同题来源链接。

## 目录

```text
config/sources.json       来源、查询与关键词
steelwatch/               采集、去重、翻译和生成逻辑
data/                     可追溯历史数据与运行状态
docs/                     GitHub Pages 静态看板
tests/                    离线单元测试
.github/workflows/        每日更新、部署和 CI
```

## 准确性边界

程序是“发现和初筛工具”，不是法律数据库替代品。模型不得补造税率、期限或产品范围，摘录不足时应明确提示；但业务决策前仍必须打开原文，核对税号、产品描述、原产地、生产商税率、适用期和后续修订。

媒体内容只保存短摘要或短摘录和原始链接，不保存新闻全文。正式法规以发布机关文本为准。

## 常见问题

**Actions 显示 `Resource not accessible by integration`**

检查仓库 Actions 的 Workflow permissions 是否允许读写，并确认工作流含有 `contents: write` 和 `pages: write`。

**Pages 部署失败**

先在 Settings → Pages 把 Source 设为 GitHub Actions，然后重新运行工作流。

**某一来源显示异常**

历史情报仍会保留。可打开 `data/status.json` 查看来源错误；网站改版时只需修复对应 collector。

## 许可与声明

代码采用 MIT License。机器翻译与摘要仅供业务筛查，不构成法律意见；正式要求以原文及主管机关解释为准。
