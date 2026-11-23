"""WHOOP v2: descriptive measurements and next-sleep workout associations.
Never substitute missing measurements or claim causality.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from statistics import mean
from math import sin
from random import Random

TZ = ZoneInfo('Europe/Berlin')


def local_dt(value, offset=None):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        if offset and len(offset) == 6 and offset[0] in '+-' and offset[3] == ':':
            m = int(offset[1:3]) * 60 + int(offset[4:6])
            return d.astimezone(timezone(timedelta(minutes=m * (1 if offset[0] == '+' else -1))))
        return d.astimezone(TZ)
    except (TypeError, ValueError):
        return None


def local_day(value, offset=None):
    d = local_dt(value, offset)
    return d.date().isoformat() if d else None


def numeric(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) < 1e10:
        return round(float(v), 2)
    return None


def avg(items):
    vals = [v for v in items if isinstance(v, (float, int)) and not isinstance(v, bool)]
    return round(mean(vals), 1) if vals else None


def hours(ms):
    return round(ms / 3600000, 2) if isinstance(ms, (int, float)) else None


def pearson(pairs):
    """Returns a descriptive coefficient only for at least eight actual pairs."""
    if len(pairs) < 8:
        return None
    xs, ys = zip(*pairs)
    mx, my = mean(xs), mean(ys)
    sx = sum((x-mx)**2 for x in xs)
    sy = sum((y-my)**2 for y in ys)
    if sx < 1e-10 or sy < 1e-10:
        return None
    return round(sum((x-mx)*(y-my) for x,y in pairs) / ((sx*sy)**.5), 3)


def _name(raw):
    raw = str(raw or 'Aktivität').replace('_', ' ').strip()
    names = {'golf': 'Golf', 'weightlifting': 'Krafttraining', 'strength trainer':'Krafttraining',
             'running':'Laufen', 'cycling':'Radfahren', 'tennis':'Tennis',
             'walking':'Spazieren', 'sauna':'Sauna', 'hiking/rucking':'Wandern',
             'functional fitness':'Functional Fitness'}
    return names.get(raw.lower(), raw.title())


def transform(collections, days, today=None, workouts_available=True):
    today = today or datetime.now(TZ).date()
    first = today-timedelta(days=days-1)
    base = today-timedelta(days=max(28, days+15))
    byday = {}

    def ensure(day):
        return byday.setdefault(day, dict(date=day, recovery=None, hrv=None, rhr=None,
            sleep_hours=None, deep_hours=None, rem_hours=None, light_hours=None,
            performance=None, efficiency=None, consistency=None, bedtime=None, wake_time=None,
            sleep_need_hours=None, strain=None))

    cycle_days = {}
    for c in collections.get('cycles', []):
        day = local_day(c.get('start'), c.get('timezone_offset'))
        if not day or not base.isoformat() <= day <= today.isoformat():
            continue
        cycle_days[str(c.get('id'))] = day
        if c.get('score_state') == 'SCORED':
            ensure(day)['strain'] = numeric((c.get('score') or {}).get('strain'))

    sleeps = []
    sleep_ids = {}
    for s in collections.get('sleep', []):
        if s.get('nap') or s.get('score_state') != 'SCORED':
            continue
        start_dt = local_dt(s.get('start'), s.get('timezone_offset'))
        end_dt = local_dt(s.get('end'), s.get('timezone_offset'))
        if not end_dt or (start_dt is not None and end_dt <= start_dt):
            continue
        day = end_dt.date().isoformat()
        if not base.isoformat() <= day <= today.isoformat():
            continue
        score = s.get('score') or {}
        st = score.get('stage_summary') or {}
        light, deep, rem = (hours(st.get(k)) for k in ('total_light_sleep_time_milli',
            'total_slow_wave_sleep_time_milli', 'total_rem_sleep_time_milli'))
        dur = round(sum(x or 0 for x in (light, deep, rem)),2) if any(x is not None for x in (light,deep,rem)) else None
        # A sleep can start after midnight; show it as 25:00 for a stable bedtime curve.
        bed = round(start_dt.hour + start_dt.minute/60 + (24 if start_dt.hour < 12 else 0), 2) if start_dt else None
        details = dict(id=str(s.get('id')), day=day, start=start_dt, end=end_dt,
            sleep_hours=dur, deep_hours=deep, rem_hours=rem, light_hours=light,
            performance=numeric(score.get('sleep_performance_percentage')),
            efficiency=numeric(score.get('sleep_efficiency_percentage')),
            consistency=numeric(score.get('sleep_consistency_percentage')),
            bedtime=bed, wake_time=round(end_dt.hour + end_dt.minute/60,2),
            sleep_need_hours=hours((score.get('sleep_needed') or {}).get('baseline_milli')))
        if start_dt: sleeps.append(details)
        sleep_ids[details['id']] = day
        # Prefer the longest scored main sleep if multiple are recorded for a calendar day.
        row = ensure(day)
        if row['sleep_hours'] is None or (dur is not None and dur >= row['sleep_hours']):
            for k in ('sleep_hours','deep_hours','rem_hours','light_hours','performance','efficiency',
                      'consistency','bedtime','wake_time','sleep_need_hours'):
                row[k] = details[k]

    recovery_by_sleep = {}
    for rec in collections.get('recovery', []):
        if rec.get('score_state') != 'SCORED':
            continue
        sleep_id = str(rec.get('sleep_id'))
        day = sleep_ids.get(sleep_id) or cycle_days.get(str(rec.get('cycle_id')))
        if not day or not base.isoformat() <= day <= today.isoformat():
            continue
        score = rec.get('score') or {}
        fields = dict(recovery=numeric(score.get('recovery_score')),
                      hrv=numeric(score.get('hrv_rmssd_milli')),
                      rhr=numeric(score.get('resting_heart_rate')))
        ensure(day).update(fields)
        if sleep_id in sleep_ids:
            recovery_by_sleep[sleep_id] = fields

    workouts = []
    seen = set()
    for w in collections.get('workouts', []):
        start = local_dt(w.get('start'), w.get('timezone_offset'))
        end = local_dt(w.get('end'), w.get('timezone_offset'))
        if not start or not end or end <= start:
            continue
        wid = str(w.get('id') or f'{start.isoformat()}:{end.isoformat()}')
        if wid in seen:
            continue
        seen.add(wid)
        score = w.get('score') or {}
        zone = score.get('zone_durations') or {}
        workouts.append(dict(id=wid, date=start.date().isoformat(),sport=_name(w.get('sport_name')),
            minutes=round((end-start).total_seconds()/60),
            strain=numeric(score.get('strain')),avg_hr=numeric(score.get('average_heart_rate')),
            max_hr=numeric(score.get('max_heart_rate')),
            zones=[round((zone.get(f'zone_{z}_milli') or 0)/60000,1) for z in ('zero','one','two','three','four','five')],
            start=start.isoformat(),end=end.isoformat(), _start=start, _end=end))
    workouts.sort(key=lambda w:w['_end'])

    # Unit of analysis is the NIGHT, not the workout. This prevents double-counting a night
    # after two workouts, and links Recovery via WHOOP's sleep_id (no inferred recovery).
    pairs = []
    if workouts_available:
        # Multiple main-sleep records on one calendar date: use the longest one only.
        distinct_nights = {}
        for sl in sleeps:
            old = distinct_nights.get(sl['day'])
            if old is None or (sl['sleep_hours'] or 0) > (old['sleep_hours'] or 0):
                distinct_nights[sl['day']] = sl
        for sl in sorted(distinct_nights.values(),key=lambda x:x['start']):
            if sl['day'] < first.isoformat() or sl['day'] > today.isoformat():
                continue
            candidates = [w for w in workouts if 0 <= (sl['start']-w['_end']).total_seconds() <= 24*3600]
            last = candidates[-1] if candidates else None
            rec = recovery_by_sleep.get(sl['id'], {})
            pairs.append(dict(date=sl['day'], sport=last['sport'] if last else None,
                workout_count=len(candidates), workout_strain=max((w['strain'] for w in candidates if w['strain'] is not None),default=None),
                total_minutes=sum(w['minutes'] for w in candidates) if candidates else 0,
                hours_before_sleep=round((sl['start']-last['_end']).total_seconds()/3600,1) if last else None,
                sleep_hours=sl['sleep_hours'], deep_hours=sl['deep_hours'],
                recovery=rec.get('recovery'), hrv=rec.get('hrv'),
                performance=sl['performance'], efficiency=sl['efficiency'],
                bedtime=sl['bedtime']))

    rows = [byday.get((base+timedelta(days=i)).isoformat()) or ensure((base+timedelta(days=i)).isoformat())
            for i in range((today-base).days+1)]
    visible = [r for r in rows if r['date']>=first.isoformat()]

    def delta(key):
        latest = [r[key] for r in rows[-7:] if r[key] is not None]
        previous = [r[key] for r in rows[-14:-7] if r[key] is not None]
        return round(mean(latest)-mean(previous),1) if len(latest)>=4 and len(previous)>=4 else None

    fields = ('recovery','hrv','rhr','sleep_hours','strain','performance','efficiency','consistency','bedtime')
    summary = {k:dict(value=avg([r[k] for r in visible]),week_delta=delta(k),count=sum(r[k] is not None for r in visible)) for k in fields}
    trends = []
    for key,name,unit,minimum in [('hrv','HRV','ms',2),('rhr','Ruhepuls','bpm',2),('sleep_hours','Schlafdauer','h',.25),('recovery','Recovery','Punkte',3)]:
        d=delta(key)
        if d is not None and abs(d)>=minimum:
            trends.append(dict(label=name,delta=d,unit=unit,text=f'Ø {name}: {abs(d):g} {unit} '+('höher' if d>0 else 'niedriger')+' als in den 7 Tagen davor.'))
    visible_workouts=[w for w in workouts if first.isoformat()<=w['date']<=today.isoformat()]
    breakdown={}
    for w in visible_workouts:
        a=breakdown.setdefault(w['sport'],{'sport':w['sport'],'sessions':0,'minutes':0,'strain':[]})
        a['sessions']+=1;a['minutes']+=w['minutes']
        if w['strain'] is not None:a['strain'].append(w['strain'])
    activities=sorted([dict(sport=v['sport'],sessions=v['sessions'],minutes=v['minutes'],average_strain=avg(v['strain']))
                     for v in breakdown.values()],key=lambda a:(-a['minutes'],a['sport']))
    clean_workouts=[{k:v for k,v in w.items() if not k.startswith('_')} for w in reversed(visible_workouts)]
    zone_totals=[round(sum(w['zones'][i] for w in visible_workouts),1) for i in range(6)]
    trained=[p for p in pairs if p['workout_count']>0]
    rests=[p for p in pairs if p['workout_count']==0]
    correlations={}
    for k in ('sleep_hours','deep_hours','performance','recovery','hrv'):
        xy=[(p['workout_strain'],p[k]) for p in trained if p['workout_strain'] is not None and p[k] is not None]
        correlations[k]=dict(r=pearson(xy),n=len(xy))
    return dict(days=days,rows=visible,summary=summary,from_=first.isoformat(),to=today.isoformat(),
        stages={k:avg([r[field] for r in visible]) for k,field in [('light','light_hours'),('deep','deep_hours'),('rem','rem_hours')]},
        workouts=clean_workouts[:1000],activities=activities,zones=zone_totals,
        workout_minutes=sum(w['minutes'] for w in visible_workouts),
        workout_count=len(visible_workouts),insights=trends[:4],data_points=summary['recovery']['count'],
        connections=dict(available=workouts_available,pairs=pairs,trained_nights=len(trained),rest_nights=len(rests),correlations=correlations))


def demo_collections(today=None):
    today=today or datetime.now(TZ).date()
    rng=Random(20261122)
    data={'cycles':[],'sleep':[],'recovery':[],'workouts':[]}
    for i in range(410):
        d=today-timedelta(days=i); day=d.isoformat(); prior=(d-timedelta(days=1)).isoformat()
        cid=i+1; sid=f'demo-{i}'
        light=int(max(2.1,rng.gauss(4,.52))*3600000)
        deep=int(max(.6,rng.gauss(1.4,.22))*3600000)
        rem=int(max(.6,rng.gauss(1.5,.3))*3600000)
        data['cycles'].append(dict(id=cid,start=day+'T08:00:00Z',score_state='SCORED',score={'strain':round(max(1,rng.gauss(11,2.8)),1)}))
        data['sleep'].append(dict(id=sid,start=prior+'T22:30:00Z',end=day+'T06:00:00Z',nap=False,score_state='SCORED',
            score={'stage_summary':{'total_light_sleep_time_milli':light,'total_slow_wave_sleep_time_milli':deep,'total_rem_sleep_time_milli':rem},
            'sleep_performance_percentage':round(rng.uniform(67,98)),'sleep_efficiency_percentage':round(rng.uniform(80,98)),
            'sleep_consistency_percentage':round(rng.uniform(65,95))}))
        data['recovery'].append(dict(cycle_id=cid,sleep_id=sid,score_state='SCORED',score={
            'recovery_score':max(17,min(98,round(rng.gauss(72+4*sin(i/17),11)))),
            'hrv_rmssd_milli':max(22,round(rng.gauss(56,6),1)),
            'resting_heart_rate':max(42,round(rng.gauss(55,3)))}))
        if i%3==0:
            data['workouts'].append(dict(id=f'w-{i}',start=prior+'T13:00:00Z',end=prior+'T14:30:00Z',
                sport_name='golf' if i%2 else 'weightlifting',score_state='SCORED',score={
                'strain':round(rng.uniform(6,13),1),'average_heart_rate':round(rng.uniform(99,130)),
                'zone_durations':{'zone_one_milli':900000,'zone_two_milli':1800000,'zone_three_milli':600000}}))
    return data
