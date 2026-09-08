import copy
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
        html='<article><a href="/liansai/1544">中乙第1轮</a><span>2027-03-22 15:00</span></article>'
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

if __name__=='__main__':unittest.main()
