"""比赛日历配置。修改后推送，GitHub Actions 自动重新生成并发布。"""

# 提醒按这个时区计算；日历事件仍用 UTC 保存，iPhone 按设备时区显示。
USER_TIMEZONE = "Asia/Shanghai"
MORNING_REMINDER = "09:00"       # 设为 None 可关闭早提醒
PREVIOUS_EVENING_REMINDER = "21:00"  # 早于早提醒开球时，改到前一晚；None 可关闭
KICKOFF_REMINDER_MINUTES = [30]  # 可设置多个正整数，如 [60, 30]
MATCH_DURATION_MINUTES = 120
PAST_DAYS_KEEP = 14
REFRESH_HOURS = 6              # 改抓取频率时，需同步修改 workflow 的 cron

FOLLOWED_TEAMS = {"milan": "AC米兰", "lanzhou": "兰州陇原竞技"}
CALENDAR_NAMES = {"milan": "AC米兰", "lanzhou": "兰州陇原竞技", "all": "AC米兰 × 陇原｜比赛日历"}
EXTRA_TIMEZONES = {"milan": ["Europe/Rome"], "lanzhou": []}
TIMEZONE_LABELS = {"Asia/Shanghai": "北京时间", "Europe/Rome": "意大利时间", "America/Los_Angeles": "洛杉矶时间", "America/New_York": "纽约时间"}
SHOW_HOME_AWAY = True

SOURCES = {
    "milan": "https://www.acmilan.com/en/season/active/schedule/all",
    "lanzhou": "https://www.henduoqiu.com/qiudui/170468",
}
# 仅核对 AC米兰已确定的开球时间。不会覆盖官网，也不会用于补齐待定时间。
MILAN_CROSSCHECK_URL = "https://pub.fotmob.com/prod/pub/api/v2/calendar/team/8564.ics"
SITE_ORIGIN = "https://ricadre.github.io/football-calendar"

# 修改事件生成逻辑时递增；时区、名称、提醒配置变化则自动检测。
PRESENTATION_VERSION = 2

# 英文别名只用于识别来源，展示使用中文值。
TEAM_ALIASES = {'Milan': 'AC米兰',
 'Lazio': '拉齐奥',
 'Benfica': '本菲卡',
 'Lecce': '莱切',
 'Sassuolo': '萨索洛',
 'Salzburg': '萨尔茨堡红牛',
 'Atalanta': '亚特兰大',
 'AFC Bournemouth': '伯恩茅斯',
 'Udinese': '乌迪内斯',
 'Bologna': '博洛尼亚',
 'Inter': '国际米兰',
 'Ferencváros': '费伦茨瓦罗斯',
 'Genoa': '热那亚',
 'Frosinone': '弗罗西诺内',
 'Olympiacos': '奥林匹亚科斯',
 'Cagliari': '卡利亚里',
 'Monza': '蒙扎',
 'Parma': '帕尔马',
 'Sunderland FC': '桑德兰',
 'Napoli': '那不勒斯',
 'Como': '科莫',
 'Fiorentina': '佛罗伦萨',
 'Roma': '罗马',
 'Torino': '都灵',
 'Levski Sofia': '索菲亚列夫斯基',
 'Juventus': '尤文图斯',
 'Ararat-Armenia': '阿拉拉特亚美尼亚',
 'Venezia': '威尼斯',
 'AC Milan': 'AC米兰',
 'AC米兰': 'AC米兰',
 'S.S. Lazio': '拉齐奥',
 'AS Roma': '罗马',
 'FC Genoa': '热那亚',
 'US Sassuolo': '萨索洛',
 'AC Monza': '蒙扎',
 'RB Salzburg': '萨尔茨堡红牛',
 'Bournemouth': '伯恩茅斯',
 'Ferencvaros': '费伦茨瓦罗斯',
 'Ferencvarosi': '费伦茨瓦罗斯',
 'Olympiakos Piraeus': '奥林匹亚科斯',
 'Sunderland': '桑德兰',
 'PFC Levski Sofia': '索菲亚列夫斯基',
 'FC Ararat-Armenia': '阿拉拉特亚美尼亚',
 'Rizhao Yuqi': '兰州陇原竞技',
 'Lanzhou Longyuan Athletic': '兰州陇原竞技',
 'Lanzhou Longyuan': '兰州陇原竞技',
 '兰州陇原竞技天佑德': '兰州陇原竞技'}

COMPETITIONS = {'Serie A': '意甲',
 'UEFA Europa League': '欧联杯',
 'Coppa Italia': '意大利杯',
 'UEFA Champions League': '欧冠',
 'Club Friendlies': '友谊赛'}
