import copy
import json
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
import update as cal

class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,9,8,tzinfo=timezone.utc)
        self.g={'id':'milan-test','team':'milan','start':'2026-09-12T16:00:00Z','date':'2026-09-12','tentative':False,'home':'拉齐奥','away':'AC Milan','competition':'意甲 · 第4轮','venue':'罗马奥林匹克球场','venue_note':'官网场馆','venue_source':cal.MILAN,'source':cal.MILAN,'status':'Fixture','sequence':0,'created':cal.iso(self.now),'modified':cal.iso(self.now)}
    def test_early_reminder_precedes_midnight_kickoff(self):
        kickoff=cal.dt(self.g['start'])
        early=cal.early_alarm(kickoff)
        self.assertEqual(early.isoformat(),'2026-09-12T21:00:00+08:00')
        self.assertLess(early,kickoff)
        self.assertEqual((kickoff-early).total_seconds(),10800)
    def test_afternoon_reminder_is_same_day_nine(self):
        kickoff=cal.dt('2026-09-13T08:00:00Z')
        self.assertEqual(cal.early_alarm(kickoff).isoformat(),'2026-09-13T09:00:00+08:00')
    def test_reschedule_keeps_uid_and_increments_sequence_once(self):
        changed=copy.deepcopy(self.g);changed['start']='2026-09-13T18:45:00Z'
        first=cal.reconcile([self.g],[changed],'milan',self.now+timedelta(hours=6))[0]
        self.assertEqual(first['id'],self.g['id']);self.assertEqual(first['sequence'],1)
        again=cal.reconcile([first],[cal.meaningful(changed)],'milan',self.now+timedelta(hours=12))[0]
        self.assertEqual(again['sequence'],1);self.assertEqual(again['modified'],first['modified'])
    def test_tentative_dates_are_all_day_without_false_kickoffs(self):
        self.g.update(tentative=True,start='2026-12-05T23:00:00Z',date='2026-12-06')
        body=cal.build_ics([self.g],'测试','https://example.com/all.ics',self.now).decode()
        self.assertIn('DTSTART;VALUE=DATE:20261206',body)
        self.assertNotIn('BEGIN:VALARM',body);self.assertIn('STATUS:TENTATIVE',body)
    def test_cancelled_match_has_no_alarm(self):
        self.g['status']='Cancelled'
        body=cal.build_ics([self.g],'测试','https://example.com/all.ics',self.now).decode()
        self.assertIn('STATUS:CANCELLED',body);self.assertNotIn('BEGIN:VALARM',body)
    def test_utf8_folding_and_text_escaping(self):
        self.g['venue']='玫瑰体育场,'*30+'\n测试;\\'
        data=cal.build_ics([self.g],'测试','https://example.com/all.ics',self.now)
        for line in data.split(b'\r\n'):self.assertLessEqual(len(line),75);line.decode('utf-8')
        unfolded=data.decode().replace('\r\n ','')
        self.assertIn('玫瑰体育场\\,',unfolded);self.assertIn('\\n测试\\;\\\\',unfolded)
    def test_chinese_listing_does_not_assume_current_year(self):
        html='<article><a href="/liansai/1544">中乙第1轮</a><span>2027-03-22 15:00</span><img alt="兰州陇原竞技"><div>未开始</div><img alt="北京理工"><h1>比赛</h1></article>'
        game={'id':'lanzhou-test','team':'lanzhou','home':'兰州陇原竞技','away':'北京理工','source':cal.LANZHOU,'status':'Fixture'}
        result=cal.parse_lanzhou_detail(game,html,{})
        self.assertEqual(result['start'],'2027-03-22T07:00:00Z')
        self.assertEqual(result['venue'],'场馆待确认')
    def test_mass_disappearance_rejects_replacement(self):
        old=[dict(self.g,id=f'milan-{i}') for i in range(8)]
        with self.assertRaises(ValueError):cal.reconcile(old,[],'milan',self.now)
    def test_italian_winter_tbc_date_uses_rome(self):
        self.assertEqual(cal.dt('2026-12-05T23:00:00Z').astimezone(cal.ROME).date().isoformat(),'2026-12-06')

    def test_chinese_name_and_home_away_preserve_original_uid(self):
        migrated=cal.reconcile([self.g],[self.g],'milan',self.now)[0]
        self.assertEqual(migrated['away'],'AC米兰')
        self.assertEqual(migrated['id'],self.g['id'])
        body=cal.build_ics([migrated],'测试','https://example.com/all.ics',self.now).decode().replace('\r\n ','')
        self.assertIn('【客场】拉齐奥 vs AC米兰',body)
        self.assertIn('主客：AC米兰客场',body)
        self.assertIn('UID:milan-test@football-calendar.ricadre.github.io',body)
        self.assertNotIn('AC Milan',body)
        self.assertEqual(cal.home_away(dict(migrated,home='AC米兰',away='本菲卡')),'主场')

    def test_dual_timezone_tracks_summer_and_winter(self):
        summer='\n'.join(cal.kickoff_lines(self.g))
        self.assertIn('开球（北京时间）：2026-09-13 00:00',summer)
        self.assertIn('开球（意大利时间）：2026-09-12 18:00',summer)
        winter='\n'.join(cal.kickoff_lines(dict(self.g,start='2026-12-10T20:00:00Z')))
        self.assertIn('开球（北京时间）：2026-12-11 04:00',winter)
        self.assertIn('开球（意大利时间）：2026-12-10 21:00',winter)
        pending='\n'.join(cal.kickoff_lines(dict(self.g,tentative=True)))
        self.assertNotIn('00:00',pending)

    def test_reminder_only_change_updates_version_once(self):
        first=cal.reconcile([], [self.g], 'milan', self.now)[0]
        with patch.object(cal.C,'KICKOFF_REMINDER_MINUTES',[60]):
            second=cal.reconcile([first],[first],'milan',self.now+timedelta(hours=6))[0]
            self.assertEqual(second['sequence'],first['sequence']+1)
            self.assertNotEqual(second['modified'],first['modified'])
            body=cal.build_ics([second],'测试','https://example.com/all.ics',self.now).decode()
            self.assertIn('TRIGGER:-PT3600S',body)
            third=cal.reconcile([second],[second],'milan',self.now+timedelta(hours=12))[0]
            self.assertEqual(third['sequence'],second['sequence'])
            self.assertEqual(third['modified'],second['modified'])

    def test_configured_timezone_and_optional_reminders(self):
        with patch.object(cal.C,'USER_TIMEZONE','America/Los_Angeles'):
            self.assertEqual(cal.early_alarm(cal.dt('2026-09-13T08:00:00Z')).isoformat(),'2026-09-12T21:00:00-07:00')
        with patch.object(cal.C,'MORNING_REMINDER',None):
            self.assertEqual(cal.alarm_triggers(cal.dt(self.g['start'])),[cal.dt(self.g['start'])-timedelta(minutes=30)])
        with patch.object(cal.C,'KICKOFF_REMINDER_MINUTES',[0]):
            with self.assertRaises(ValueError):cal.validate_settings()

    def test_crosscheck_parses_real_emoji_and_competition_suffix(self):
        raw='BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:sample\r\nDTSTART:20260912T160000Z\r\nSUMMARY:⚽️ RB Salzburg - AC Milan [EL]\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
        parsed=cal.parse_crosscheck_feed(raw)
        self.assertEqual((parsed[0]['home'],parsed[0]['away']),('萨尔茨堡红牛','AC米兰'))
        self.assertEqual(cal.chinese_name('S.S. Lazio'),'拉齐奥')
        self.assertEqual(cal.chinese_name('Ferencváros'),'费伦茨瓦罗斯')

    def test_crosscheck_never_changes_official_times(self):
        known=copy.deepcopy(self.g)
        pending=dict(self.g,id='milan-pending',home='AC米兰',away='帕尔马',tentative=True,start='2026-12-05T23:00:00Z')
        games=[known,pending];before=copy.deepcopy(games)
        ref=[{'home':'拉齐奥','away':'AC米兰','start':'2026-09-13T18:45:00Z','status':'','source':'https://example.com/reference'}, {'home':'AC米兰','away':'帕尔马','start':'2026-12-06T20:00:00Z','status':'','source':'https://example.com/reference'}]
        report=cal.compare_milan_fixtures(games,ref,self.now)
        self.assertEqual(report['compared'],1)
        self.assertEqual(report['official_time_pending'],1)
        self.assertEqual(len(report['differences']),1)
        self.assertEqual(games,before)

class MatchdayRegressionTests(unittest.TestCase):
    setUp=CalendarTests.setUp

    def lanzhou_game(self, **changes):
        return dict(self.g, **{'id':'lanzhou-14640192','team':'lanzhou','home':'广州蒲公英','away':'兰州陇原竞技','start':'2026-09-13T08:00:00Z','date':'2026-09-13','source':'https://www.henduoqiu.com/bisai/14640192',**changes})

    def detail(self, status='已结束', home=1, away=2):
        return f'''<article><a href="/liansai/1544">中乙保级组第23轮</a><span>2026-09-13 16:00</span>
        <img alt="广州蒲公英"><span>排名5</span><div>{status}</div>
        <div><span>{home}</span><span>-</span><span>{away}</span></div><span>半场0-0</span><span>角球9-2</span>
        <img alt="兰州陇原竞技"><h1>广州蒲公英 VS 兰州陇原竞技</h1>
        <table><tr><td>2025-09-14 16:00</td><td>9-9</td></tr></table></article>'''

    def listing(self, status='已结束'):
        return f'''<h1>兰州陇原竞技</h1><li><span>09/13 16:00</span><span>{status}</span>
        <a href="/bisai/14640192" class="anything group/item"><img alt="广州蒲公英"><span>1</span><span>-</span><span>2</span><img alt="兰州陇原竞技"></a></li>'''

    def test_listing_discovers_finished_live_and_unknown_states(self):
        for label,status in [('已结束','Played'),('下半场','Live'),('90+3&#39;','Live'),('新状态','Unknown')]:
            with self.subTest(label=label):
                games=cal.parse_lanzhou_list(self.listing(label))
                self.assertEqual(len(games),1)
                self.assertEqual(games[0]['status'],status)

    def test_detail_updates_stale_list_state_and_reads_only_header_score(self):
        g=cal.parse_lanzhou_detail(self.lanzhou_game(status='NeedsReview'),self.detail(),{})
        self.assertEqual((g['status'],g['home_score'],g['away_score']),('Played',1,2))
        self.assertEqual(g['start'],'2026-09-13T08:00:00Z')
        self.assertFalse(g['tentative'])
        self.assertEqual(cal.parse_lanzhou_detail(self.lanzhou_game(),self.detail('已结束',0,0),{})['home_score'],0)
        upcoming=cal.parse_lanzhou_detail(self.lanzhou_game(),self.detail('未开始',0,0),{})
        self.assertNotIn('home_score',upcoming)
        self.assertEqual(cal.parse_lanzhou_detail(self.lanzhou_game(),self.detail('未开始'),{})['status'],'Fixture')

    def test_wrong_teams_and_missing_final_score_fail_safely(self):
        for body in [self.detail().replace('广州蒲公英','其他球队'),self.detail(home='?')]:
            with self.assertRaises(ValueError):cal.parse_lanzhou_detail(self.lanzhou_game(),body,{})

    def test_known_match_is_polled_when_absent_from_team_page(self):
        old=self.lanzhou_game()
        with patch.object(cal,'parse_lanzhou_list',return_value=[]),patch.object(cal,'fetch',side_effect=lambda url:self.detail() if '/bisai/' in url else 'list') as fetch:
            games,errors=cal.get_lanzhou({},previous=[old],now=self.now)
        self.assertFalse(errors)
        self.assertEqual(games[0]['status'],'Played')
        self.assertIn(unittest.mock.call(old['source']),fetch.call_args_list)

    def test_one_failed_detail_does_not_block_other_results(self):
        old=self.lanzhou_game(id='lanzhou-2')
        def fetch(url):
            if url==cal.LANZHOU:return self.listing()
            if url.endswith('/2'):raise RuntimeError('temporary failure')
            return self.detail()
        with patch.object(cal,'fetch',side_effect=fetch):
            games,errors=cal.get_lanzhou({},previous=[old],now=cal.dt('2026-09-14T00:00:00Z'))
        self.assertEqual(len(errors),1)
        self.assertEqual(len(games),2)
        kept=next(g for g in games if g['id']==old['id'])
        self.assertEqual(kept['start'],old['start'])
        self.assertFalse(kept['tentative'])
        self.assertEqual(next(g for g in games if g['id']!=old['id'])['away_score'],2)

    def test_missing_fixture_keeps_timed_event_and_past_result(self):
        old=cal.reconcile([],[self.g],'milan',self.now)[0]
        missing=cal.reconcile([old],[],'milan',self.now)[0]
        body=cal.build_ics([missing],'测试','https://example.com',self.now).decode()
        self.assertIn('DTSTART:20260912T160000Z',body)
        self.assertIn('BEGIN:VALARM',body)
        self.assertNotIn('时间待定',body)
        finished=dict(old,status='Played',home_score=0,away_score=0)
        retained=cal.reconcile([finished],[],'milan',cal.dt('2026-09-14T00:00:00Z'))
        self.assertEqual(cal.score_text(retained[0]),'0–0')
        self.assertEqual(cal.reconcile([finished],[],'milan',cal.dt('2026-10-14T00:00:00Z')),[])

    def test_completed_and_corrected_score_update_same_uid_only_once(self):
        from icalendar import Calendar
        old=cal.reconcile([],[self.lanzhou_game()],'lanzhou',self.now)[0]
        final=cal.parse_lanzhou_detail(old,self.detail(),{})
        updated=cal.reconcile([old],[final],'lanzhou',self.now+timedelta(days=6))[0]
        corrected=cal.reconcile([updated],[dict(final,away_score=3)],'lanzhou',self.now+timedelta(days=7))[0]
        again=cal.reconcile([corrected],[dict(final,away_score=3)],'lanzhou',self.now+timedelta(days=8))[0]
        self.assertEqual([g['sequence'] for g in [old,updated,corrected,again]],[0,1,2,2])
        self.assertEqual(again['modified'],corrected['modified'])
        event=Calendar.from_ical(cal.build_ics([updated],'测试','https://example.com',self.now)).walk('VEVENT')[0]
        self.assertEqual(str(event['UID']),old['id']+'@football-calendar.ricadre.github.io')
        self.assertIn('【已结束】【客场】广州蒲公英 1–2 兰州陇原竞技',str(event['SUMMARY']))
        self.assertIn('终场比分',str(event['DESCRIPTION']))
        self.assertEqual(event.decoded('DTSTART'),cal.dt(old['start']))
        self.assertEqual(event.walk('VALARM'),[])

    def test_final_result_does_not_regress_to_cached_upcoming_data(self):
        old=dict(self.g,status='Played',home_score=2,away_score=2)
        updated=cal.reconcile([old],[self.g],'milan',self.now)[0]
        self.assertEqual((updated['status'],cal.score_text(updated)),('Played','2–2'))

    def test_milan_official_final_zero_and_placeholder_scores(self):
        games=[]
        for i,status in enumerate(['Played','Played','Fixture','Playing','Played']):
            games.append({'type':'game','id':str(i),'datetime':self.g['start'],'status':status,'datetimeTBC':'','competition':{'name':'Serie A'},'homeTeam':{'name':'Milan','slug':'milan','score':0},'awayTeam':{'name':'Lazio','slug':'lazio','score':i}})
        html='<script>self.__next_f.push('+json.dumps([1,json.dumps(games,separators=(',',':'))])+')</script>'
        parsed=cal.parse_milan(html)
        self.assertEqual(cal.score_text(parsed[0]),'0–0')
        self.assertEqual(cal.score_text(parsed[1]),'0–1')
        self.assertNotIn('home_score',parsed[2])
        self.assertEqual(parsed[3]['status'],'Live')

if __name__=='__main__':unittest.main()
