# 米兰 × 陇原 · iPhone 比赛订阅日历

AC Milan 男足一线队与兰州陇原竞技的非官方球迷日历。比赛日程包含对阵双方、开球时间、赛事、场馆和提醒。

**[打开订阅页面](https://ricadre.github.io/football-calendar/)**

| 日历 | 订阅网址 |
| --- | --- |
| 两队合并 | https://ricadre.github.io/football-calendar/calendars/all.ics |
| AC Milan | https://ricadre.github.io/football-calendar/calendars/milan.ics |
| 兰州陇原竞技 | https://ricadre.github.io/football-calendar/calendars/lanzhou.ics |

备用合并地址：<https://raw.githubusercontent.com/Ricadre/football-calendar/main/calendars/all.ics>

在 iPhone「日历 → 日历 → 添加日历 → 添加订阅日历」粘贴网址。iOS 26 轻点「查找」，较早版本轻点「订阅」。打开此日历的「日程提醒」，并在「设置 → 通知 → 日历」允许通知。使用订阅才能获取改期等更新；下载文件导入只是一份快照。参见 [Apple 官方说明](https://support.apple.com/zh-cn/102301)。

## 时间与提醒

- 默认北京时间当天 09:00 与开赛前 30 分钟各提醒一次。
- 北京时间 09:00 及之前的比赛，早提醒改为前一天 21:00，避免在开球后提醒。
- 日程以 UTC 保存，会按设备时区显示；备注始终写明北京时间。意大利夏令时由 IANA Europe/Rome 转换。
- 官方尚未确定时间的比赛以「时间待定」全天日程展示，不把占位时间误认为开球时间，不触发提醒。
- 每场预留 2 小时，仅供观赛安排，实际结束时间可能不同。
- 赛事 UID 保持固定，改期更新原事件；内容变化递增 SEQUENCE。取消比赛保留 CANCELLED 状态并移除提醒。

## 来源与当前覆盖

- 米兰：[AC Milan 男足官网赛程](https://www.acmilan.com/en/season/active/schedule/all)，包含官网已列出的联赛、杯赛和欧战。
- 兰州：[很多球球队赛程](https://www.henduoqiu.com/qiudui/170468)，逐场读取完整日期；初始 2026 决赛阶段赛程交叉核对 [乐彩网](https://m.17500.cn/zq/data-team/course-70468-0-0)、[温州晚报](https://www.66wz.com/wendu/system/2026/09/04/105834039.shtml)。
- 米兰场馆以官方赛程为准。兰州来源缺少逐场场馆，`data/venues.json` 记录经过查找的球队主场参考及证据；日历明确显示「本场待确认」。这类场馆不会被表述成该场已确认场馆。后续如果赛事页面提供 SportsEvent 场馆，会优先采用。特定场馆变更可按比赛 ID 更新映射。
- 初始核实时间：2026-09-08；后续赛程 52 场，其中米兰 44 场、兰州 8 场。未公布的后续杯赛、下赛季赛程在来源发布后才能加入。
- `data/fixtures.json` 记录每个来源的最后成功读取时间、失败原因和稳定事件版本。

## 自动更新

GitHub Actions 每 6 小时检查一次（UTC 每日 00:17、06:17、12:17、18:17），也可以手动运行。GitHub 调度和 iPhone 刷新可能延迟，不能保证即时同步。日历请求的建议刷新周期为 6 小时。

更新失败时保留该队上次成功赛程，页面展示状态，工作流返回失败便于排查；成功来源仍可更新。赛程大批消失时拒绝覆盖，避免误删。最近 14 天的已完赛事件保留，较早比赛逐步移除。

GitHub 对长时间没有仓库活动的公开仓库可能停用定时工作流；正常检查会写入来源更新时间并提交。可在 Actions 查看运行状态。参见 [GitHub 调度说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## 本地维护

Python 3.10+，仅用标准库，无 API key。

```sh
python -m unittest discover -s scripts -p 'test_*.py' -v
python scripts/update.py
```

修改 `scripts/update.py` 可调整提醒规则；修改 `data/venues.json` 可补充逐场已确认场馆。公开仓库只保存公开比赛资料与生成程序。
