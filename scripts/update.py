#!/usr/bin/env python3
"""Fetch public fixtures and produce stable RFC 5545 subscription feeds."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import escape, unescape
import gzip
import json
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
BEIJING = ZoneInfo('Asia/Shanghai')
ROME = ZoneInfo('Europe/Rome')
MILAN = 'https://www.acmilan.com/en/season/active/schedule/all'
LANZHOU = 'https://www.henduoqiu.com/qiudui/170468'
ORIGIN = 'https://ricadre.github.io/football-calendar'
TEAM_NAMES = {'milan': 'AC Milan', 'lanzhou': '兰州陇原竞技', 'all': '米兰 × 陇原｜比赛日历'}
NAMES = {'Milan':'AC Milan','Lazio':'拉齐奥','Benfica':'本菲卡','Lecce':'莱切','Sassuolo':'萨索洛','Salzburg':'萨尔茨堡红牛','Atalanta':'亚特兰大','AFC Bournemouth':'伯恩茅斯','Udinese':'乌迪内斯','Bologna':'博洛尼亚','Inter':'国际米兰','Ferencváros':'费伦茨瓦罗斯','Genoa':'热那亚','Frosinone':'弗罗西诺内','Olympiacos':'奥林匹亚科斯','Cagliari':'卡利亚里','Monza':'蒙扎','Parma':'帕尔马','Sunderland FC':'桑德兰','Napoli':'那不勒斯','Como':'科莫','Fiorentina':'佛罗伦萨','Roma':'罗马','Torino':'都灵','Levski Sofia':'索菲亚列夫斯基','Juventus':'尤文图斯','Ararat-Armenia':'阿拉拉特亚美尼亚','Venezia':'威尼斯'}
COMPETITIONS = {'Serie A':'意甲','UEFA Europa League':'欧联杯','Coppa Italia':'意大利杯','UEFA Champions League':'欧冠','Club Friendlies':'友谊赛'}

def iso(d):
    return d.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00','Z')

def dt(s):
    return datetime.fromisoformat(s.replace('Z','+00:00'))

def plain(s):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', s))).strip()

def fetch(url):
    error = None
    for attempt in range(3):
        try:
            req = Request(url, headers={'User-Agent':'Mozilla/5.0 (compatible; FootballCalendar/1.0)', 'Accept':'text/html', 'Accept-Encoding':'gzip'})
            with urlopen(req, timeout=35) as r:
                raw = r.read(5_000_001)
                if len(raw)>5_000_000: raise ValueError('Source exceeds size limit')
                if raw[:2]==b'\x1f\x8b': raw=gzip.decompress(raw)
                return raw.decode('utf-8')
        except Exception as exc:
            error = exc
            if attempt<2: time.sleep(attempt+1)
    raise RuntimeError(f'Cannot read {url}: {error}')

def parse_milan(html):
    chunks=[]
    for m in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>',html,re.S):
        try:
            value=json.loads(m[1])
            if value[0]==1 and isinstance(value[1],str): chunks.append(value[1])
        except (ValueError,IndexError): pass
    payload=''.join(chunks)
    games={}
    decoder=json.JSONDecoder()
    for m in re.finditer(r'\{"type":"game"',payload):
        try: g,_=decoder.raw_decode(payload[m.start():])
        except ValueError: continue
        if not g.get('datetime') or not g.get('homeTeam') or not g.get('awayTeam'): continue
        if 'milan' not in (g['homeTeam'].get('slug'),g['awayTeam'].get('slug')):continue
        when=dt(g['datetime'])
        status=g.get('status','Fixture')
        tentative=str(g.get('datetimeTBC','')).lower() not in ('','false','none','0')
        venue=g.get('stadiumName') or '场馆待确认'
        if venue in ('Stadio San Siro','San Siro Stadium','Stadio Giuseppe Meazza'): venue='圣西罗球场（San Siro / Giuseppe Meazza）'
        elif venue=='Stadio Olimpico':venue='罗马奥林匹克球场（Stadio Olimpico）'
        games[g['id']]={'id':'milan-'+g['id'],'team':'milan','start':iso(when),'date':when.astimezone(ROME).date().isoformat(), 'tentative':tentative,'home':NAMES.get(g['homeTeam']['name'],g['homeTeam']['name']),'away':NAMES.get(g['awayTeam']['name'],g['awayTeam']['name']),'competition':COMPETITIONS.get(g['competition']['name'],g['competition']['name'])+' · 第'+str(g.get('matchDay','?'))+'轮','venue':venue,'venue_note':'米兰官网赛程列示场馆','venue_source':MILAN,'source':MILAN,'status':status}
    if len(games)<5:raise ValueError('Milan fixture structure changed; refusing empty replacement')
    return list(games.values())

def parse_lanzhou_list(html):
    if not re.search(r'<h1[^>]*>[^<]*兰州陇原竞技',html):raise ValueError('Lanzhou team page does not match')
    results={}
    for li in re.findall(r'<li\b[^>]*>(.*?)</li>',html,re.S):
        if '兰州陇原竞技' not in li:continue
        match=re.search(r'href="(/(?:fenxi|bisai)/(\d+))"[^>]*class="[^"]*group/item',li)
        if not match:continue
        if not re.search(r'>\s*(未开始|推迟|取消|中断|待定)\s*<',li):continue
        names=re.findall(r'<img\b[^>]*\balt="([^"]+)"',li)
        if len(names)!=2:raise ValueError('Cannot identify home and away teams')
        status=re.search(r'>\s*(未开始|推迟|取消|中断|待定)\s*<',li)[1]
        results[match[2]]={'id':'lanzhou-'+match[2],'team':'lanzhou','home':unescape(names[0]),'away':unescape(names[1]),'source':'https://www.henduoqiu.com'+match[1], 'status':{'未开始':'Fixture','推迟':'Postponed','取消':'Cancelled','中断':'Suspended','待定':'Postponed'}[status]}
    return list(results.values())

def parse_lanzhou_detail(game,html,venues):
    # Read the date from this fixture's main article, not tables of historic games.
    head=re.search(r'<article\b[^>]*>(.*?)</h\d>|<article\b[^>]*>(.{0,5000})',html,re.S)
    section=(head[0] if head else html)
    date=re.search(r'(20\d{2}-\d{2}-\d{2})\s+(\d{2}:\d{2})',plain(section))
    if not date:raise ValueError(f'Missing full fixture date: {game["id"]}')
    when=datetime.fromisoformat(date[1]+'T'+date[2]+':00').replace(tzinfo=BEIJING)
    competition=re.search(r'<a\b[^>]*href="/liansai/\d+"[^>]*>(.*?)</a>',section,re.S)
    if not competition:raise ValueError('Missing competition')
    result={**game,'start':iso(when),'date':date[1],'tentative':game['status'] in ('Postponed','Suspended'),'competition':plain(competition[1]),'venue':'场馆待确认','venue_note':'本场场馆尚未核实','venue_source':''}
    ref=venues.get(game['id']) or venues.get(game['home'])
    if ref and date[1]<=ref['valid_until']:
        result.update(venue=ref['name'],venue_note=ref['note'],venue_source=ref['source'])
    # Prefer a fixture-specific venue if the source adds one in structured data.
    for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',html,re.S):
        try: event=json.loads(block)
        except ValueError:continue
        if isinstance(event,dict) and event.get('@type')=='SportsEvent' and isinstance(event.get('location'),dict) and event['location'].get('name'):
            result.update(venue=event['location']['name'],venue_note='赛事页面列示场馆',venue_source=game['source'])
    return result

def get_lanzhou(venues,fixture_dir=None):
    html=(fixture_dir/'lanzhou.html').read_text() if fixture_dir else fetch(LANZHOU)
    games=parse_lanzhou_list(html)
    def one(g):
        p=fixture_dir/(g['id']+'.html') if fixture_dir else None
        body=p.read_text() if p and p.exists() else fetch(g['source'])
        if p and not p.exists():p.write_text(body)
        return parse_lanzhou_detail(g,body,venues)
    with ThreadPoolExecutor(max_workers=4) as pool:return list(pool.map(one,games))

def meaningful(g):
    return {k:v for k,v in g.items() if k not in ('sequence','modified','created')}

def reconcile(previous, fresh, team, now):
    old={g['id']:g for g in previous if g['team']==team}
    new={g['id']:g for g in fresh}
    # Never interpret a partial/changed team page as mass cancellation.
    missing=[g for key,g in old.items() if key not in new and dt(g['start'])>now]
    if len(missing)>max(2,len([g for g in old.values() if dt(g['start'])>now])//2):
        raise ValueError(f'{team}: too many future fixtures disappeared; preserving last good schedule')
    for g in missing:new[g['id']]={**meaningful(g),'status':'NeedsReview'}
    for key,g in new.items():
        prior=old.get(key)
        changed=not prior or meaningful(g)!=meaningful(prior)
        g['sequence']=(prior.get('sequence',0)+(1 if changed else 0)) if prior else 0
        g['modified']=iso(now) if changed else prior['modified']
        g['created']=prior.get('created',prior['modified']) if prior else iso(now)
    # Retain recent past events to keep the calendar stable around matchday.
    return [g for g in new.values() if dt(g['start'])>now-timedelta(days=14)]

def text_escape(s):
    return str(s).replace('\\','\\\\').replace('\r\n','\n').replace('\r','\n').replace('\n','\\n').replace(';','\\;').replace(',','\\,')

def fold(line):
    pieces=[];part='';size=0
    for char in line:
        n=len(char.encode('utf-8'))
        if size+n>75:pieces.append(part);part=' ';size=1
        part+=char;size+=n
    pieces.append(part)
    return '\r\n'.join(pieces)

def stamp(d):return d.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')

def early_alarm(start):
    local=start.astimezone(BEIJING)
    reminder=local.replace(hour=9,minute=0,second=0,microsecond=0)
    if reminder>=local:reminder=(local-timedelta(days=1)).replace(hour=21,minute=0,second=0,microsecond=0)
    return reminder

def build_ics(games,name,feed_url,now):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Ricadre//Football Calendar//ZH-CN','CALSCALE:GREGORIAN','METHOD:PUBLISH','X-WR-CALNAME:'+text_escape(name),'X-WR-TIMEZONE:Asia/Shanghai','X-WR-CALDESC:'+text_escape('AC Milan 与兰州陇原竞技；北京时间；早提醒及开赛前30分钟。场馆核实情况见备注。'),'REFRESH-INTERVAL;VALUE=DURATION:PT6H','X-PUBLISHED-TTL:PT6H','URL:'+feed_url]
    for g in sorted(games,key=lambda x:x['start']):
        start=dt(g['start']);local=start.astimezone(BEIJING)
        tentative=g['tentative'] or g['status'] in ('Postponed','Suspended','NeedsReview')
        cancelled=g['status'].lower() in ('cancelled','canceled')
        label='已取消' if cancelled else ('延期／待重新确认' if g['status'] in ('Postponed','Suspended') else ('赛程待复核' if g['status']=='NeedsReview' else '时间待定' if tentative else ''))
        title=('【'+label+'】' if label else '')+g['home']+' vs '+g['away']+'｜'+g['competition']
        venue=g['venue']+('（本场待确认）' if '本场待确认' in g['venue_note'] else '')
        description='\n'.join([g['home']+'（主） vs '+g['away']+'（客）',g['competition'],'开球：'+('日期／时间待官方确认，当前为暂定比赛日' if tentative else local.strftime('%Y-%m-%d %H:%M')+' 北京时间'),'场馆：'+g['venue'],'场馆说明：'+g['venue_note'],'赛程来源：'+g['source'],('场馆来源：'+g['venue_source']) if g['venue_source'] else '', '日历占用2小时，仅为观赛预留；实际终场时间可能变化。' if not tentative else '时间明确后会更新为定时日程，并启用赛前提醒。'])
        lines+=['BEGIN:VEVENT','UID:'+g['id']+'@football-calendar.ricadre.github.io','DTSTAMP:'+stamp(dt(g['modified'])),'CREATED:'+stamp(dt(g['created'])),'LAST-MODIFIED:'+stamp(dt(g['modified'])),'SEQUENCE:'+str(g['sequence'])]
        if tentative:
            day=datetime.fromisoformat(g['date'])
            lines+=['DTSTART;VALUE=DATE:'+day.strftime('%Y%m%d'),'DTEND;VALUE=DATE:'+(day+timedelta(days=1)).strftime('%Y%m%d')]
        else:lines+=['DTSTART:'+stamp(start),'DTEND:'+stamp(start+timedelta(hours=2))]
        lines+=['SUMMARY:'+text_escape(title),'LOCATION:'+text_escape(venue),'DESCRIPTION:'+text_escape(description),'URL:'+g['source'],'STATUS:'+('CANCELLED' if cancelled else 'TENTATIVE' if tentative else 'CONFIRMED'),'TRANSP:TRANSPARENT','CATEGORIES:'+text_escape(TEAM_NAMES[g['team']])]
        if not tentative and not cancelled:
            triggers=[early_alarm(start).astimezone(UTC),start-timedelta(minutes=30)]
            for trigger in sorted(set(triggers)):
                seconds=int((start-trigger).total_seconds())
                lines+=['BEGIN:VALARM','ACTION:DISPLAY','DESCRIPTION:'+text_escape(title+'\n'+local.strftime('%m月%d日 %H:%M')+' 北京时间\n'+venue),'TRIGGER:-PT'+str(seconds)+'S','END:VALARM']
        lines+=['END:VEVENT']
    lines+=['END:VCALENDAR']
    return ('\r\n'.join(fold(line) for line in lines)+'\r\n').encode('utf-8')

def render_page(data,now):
    upcoming=[g for g in data['games'] if dt(g['start'])>=now and g['status']!='Played']
    rows=[]
    for g in upcoming:
        local=dt(g['start']).astimezone(BEIJING)
        day=g['date'][5:].replace('-','/') if g['tentative'] else local.strftime('%m/%d')
        clock='待定' if g['tentative'] else local.strftime('%H:%M')
        venue=g['venue']+('（本场待确认）' if '本场待确认' in g['venue_note'] else '')
        rows.append(f'<article><div class="date">{day}<strong>{clock}</strong></div><div><small>{escape(g["competition"])}</small><h3>{escape(g["home"])} <span>vs</span> {escape(g["away"])}</h3><p>{escape(venue)}</p></div></article>')
    errors='<p class="notice">部分来源暂时无法更新，保留上次赛程。可在仓库 Actions 查看状态。</p>' if data['errors'] else ''
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="AC Milan 与兰州陇原竞技比赛订阅日历：北京时间、对阵、场馆、赛前提醒。"><title>米兰 × 陇原 · 比赛日历</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f3f5f7;color:#14202b;font:16px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:850px;margin:auto;padding:36px 20px 60px}.eyebrow{color:#b21535;font-size:14px;font-weight:750;letter-spacing:.12em}h1{font-size:48px;letter-spacing:-.05em;margin:12px 0 0;line-height:1.3}h1 span{color:#bc1436}header p{color:#596776;margin:10px 0 24px}.subscribe{background:#14202b;border-top:5px solid #c9193c;color:#fff;border-radius:10px;padding:24px;margin:24px 0}.subscribe p{margin:6px 0 20px;color:#d1d8df}.primary{background:#c6193a;color:#fff;display:inline-flex;text-decoration:none;padding:12px 20px;border-radius:8px;font-weight:650;min-height:48px}a:focus-visible{outline:3px solid #9daff9;outline-offset:3px}.sub-links{display:flex;gap:22px;margin-top:16px;flex-wrap:wrap}.sub-links a{color:#e0e8f0;font-size:14px}.fixtures{background:white;border:1px solid #dfe4e9;border-radius:10px;padding:0 22px}.section-label{display:flex;justify-content:space-between;gap:12px;align-items:center;margin:24px 0 12px}h2{font-size:20px;margin:0}.section-label span{color:#576777;font-size:14px}article{display:grid;grid-template-columns:75px 1fr;gap:16px;padding:20px 0;border-top:1px solid #e2e7ed}article:first-child{border:0}.date{font-size:15px;color:#536579}.date strong{display:block;font-size:24px;color:#18232c;font-variant-numeric:tabular-nums}small{font-size:14px;color:#ad1534}h3{font-size:18px;margin:4px 0;line-height:1.6}h3 span{color:#798896;font-size:14px;font-weight:400}article p{margin:0;font-size:14px;color:#5d6b79}footer{font-size:14px;color:#536170;margin-top:26px}footer a{color:#a91431}code{display:block;overflow-wrap:anywhere;padding:12px;background:white;border:1px solid #dce3ea;border-radius:8px;font:14px/1.6 monospace}.notice{background:#fff0cb;padding:12px;border-radius:8px}ol{padding-left:22px}li{padding:3px 0}@media(max-width:540px){h1{font-size:40px}.section-label{align-items:flex-start;flex-direction:column;gap:3px}.fixtures{padding:0 14px}article{grid-template-columns:61px 1fr;gap:12px}h3{font-size:17px}.primary{width:100%;justify-content:center}}
    </style><main><header><span class="eyebrow">MATCHDAY / 比赛日</span><h1>米兰 <span>×</span> 陇原</h1><p>AC Milan · 兰州陇原竞技</p></header><section class="subscribe"><h2>让日历记住每一个比赛日</h2><p>对阵、开球时间、场馆与赛前提醒。</p><a class="primary" href="webcal://ricadre.github.io/football-calendar/calendars/all.ics">在 iPhone 订阅两队比赛 ↗</a><div class="sub-links"><a href="webcal://ricadre.github.io/football-calendar/calendars/milan.ics">仅 AC Milan</a><a href="webcal://ricadre.github.io/football-calendar/calendars/lanzhou.ics">仅兰州陇原竞技</a></div></section>'''
    page+=errors+f'<div class="section-label"><h2>接下来的 {len(upcoming)} 场比赛</h2><span>北京时间 · UTC+8</span></div><section class="fixtures">'+''.join(rows)+'</section>'
    page+=f'''<footer><h2>订阅与提醒</h2><ol><li>点击上方订阅，或进入 iPhone“日历 → 日历 → 添加日历 → 添加订阅日历”，粘贴下方网址。</li><li>打开此日历的“日程提醒”，并在“设置 → 通知 → 日历”允许通知。</li></ol><code>{ORIGIN}/calendars/all.ics</code><p>默认当天早上 9 点、开赛前 30 分钟提醒；北京时间早上 9 点及之前开球，早提醒安排在前一天 21 点。比赛时间随手机时区显示，备注始终注明北京时间。时间待定的比赛以全天日程呈现，暂不提醒。</p><p>每 6 小时检查公开赛程；iPhone 拉取更新可能延迟。米兰采用俱乐部官网；兰州采用很多球赛程，并交叉核对初始赛程。标注“本场待确认”的场馆是已查到的球队主场参考，尚无本场确认信息。</p><p>最近检查：{now.astimezone(BEIJING).strftime('%Y-%m-%d %H:%M')} 北京时间。</p><p><a href="https://github.com/Ricadre/football-calendar">GitHub 仓库 / 更新状态</a> · <a href="{MILAN}">米兰官方赛程</a> · <a href="{LANZHOU}">兰州赛程</a> · <a href="https://support.apple.com/zh-cn/102301">Apple 订阅说明</a></p><p>非官方球迷日历。</p></footer></main></html>'''
    (ROOT/'index.html').write_text(page)

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path);p.add_argument('--render-only',action='store_true');args=p.parse_args()
    now=datetime.now(UTC);store=ROOT/'data/fixtures.json';previous=json.loads(store.read_text()) if store.exists() else {'games':[],'source_success':{}}
    venues=json.loads((ROOT/'data/venues.json').read_text());data={'games':[],'source_success':previous.get('source_success',{}),'checked_at':iso(now),'errors':{}}
    for team in ('milan','lanzhou'):
        old=[g for g in previous['games'] if g['team']==team]
        try:
            if args.render_only:
                data['games']+=old;continue
            fresh=parse_milan((args.fixtures/'milan.html').read_text() if args.fixtures else fetch(MILAN)) if team=='milan' else get_lanzhou(venues,args.fixtures)
            data['games']+=reconcile(previous['games'],fresh,team,now)
            data['source_success'][team]=iso(now)
        except Exception as exc:
            data['errors'][team]=str(exc);data['games']+=old
            print(str(exc),file=sys.stderr)
    if not data['games']:raise RuntimeError('No verified fixtures available; existing calendars are unchanged')
    data['games'].sort(key=lambda g:g['start'])
    store.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    for team,name in TEAM_NAMES.items():
        games=[g for g in data['games'] if team=='all' or g['team']==team]
        (ROOT/'calendars'/f'{team}.ics').write_bytes(build_ics(games,name,f'{ORIGIN}/calendars/{team}.ics',now))
    render_page(data,now)
    print(json.dumps({'events':len(data['games']),'upcoming':sum(dt(g['start'])>now for g in data['games']),'errors':data['errors']},ensure_ascii=False))
    # Nonzero makes GitHub Actions surface an upstream outage; publishing steps
    # still commit and deploy the preserved last-good fixtures with a status note.
    return 1 if data['errors'] else 0

if __name__=='__main__':sys.exit(main())
