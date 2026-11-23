"""WHOOP v2 data mapping. Missing and unscored measurements stay NULL."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from statistics import mean
from math import sin
from random import Random

TZ=ZoneInfo('Europe/Berlin')

def local_day(value,offset=None):
    if not value:return None
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        if offset and len(offset)==6 and offset[0] in '+-':
            h,m=int(offset[1:3]),int(offset[4:6]);minutes=(h*60+m)*(1 if offset[0]=='+' else -1)
            return d.astimezone(__import__('datetime').timezone(timedelta(minutes=minutes))).date().isoformat()
        return d.astimezone(TZ).date().isoformat()
    except (TypeError, ValueError):return None

def numeric(n):
    if isinstance(n,(int,float)) and not isinstance(n,bool) and abs(n)<1e10:return round(float(n),2)
    return None

def avg(items):
    vals=[i for i in items if isinstance(i,(float,int))]
    return round(mean(vals),1) if vals else None

def hours(milli):
    return round(milli/3600000,2) if isinstance(milli,(float,int)) else None

def transform(collections,days,today=None):
    today=today or datetime.now(TZ).date();first=today-timedelta(days=days-1);base=today-timedelta(days=max(28,days+14))
    byday={}
    def ensure(day):
        return byday.setdefault(day,dict(date=day,recovery=None,hrv=None,rhr=None,sleep_hours=None,deep_hours=None,rem_hours=None,light_hours=None,performance=None,efficiency=None,strain=None))
    cdays={}; sdays={}
    for c in collections.get('cycles',[]):
        day=local_day(c.get('start'),c.get('timezone_offset'))
        if not day or day<base.isoformat() or day>today.isoformat():continue
        cdays[str(c.get('id'))]=day
        if c.get('score_state')=='SCORED':ensure(day)['strain']=numeric((c.get('score') or {}).get('strain'))
    for s in collections.get('sleep',[]):
        day=local_day(s.get('end'),s.get('timezone_offset'))
        if not day or day<base.isoformat() or day>today.isoformat():continue
        sdays[str(s.get('id'))]=day
        if s.get('nap') or s.get('score_state')!='SCORED':continue
        score=s.get('score') or {};stages=score.get('stage_summary') or {}
        light=hours(stages.get('total_light_sleep_time_milli'))
        deep=hours(stages.get('total_slow_wave_sleep_time_milli'))
        rem=hours(stages.get('total_rem_sleep_time_milli'))
        if any(v is not None for v in (light,deep,rem)):
            row=ensure(day);row.update(light_hours=light,deep_hours=deep,rem_hours=rem,sleep_hours=round(sum(x or 0 for x in (light,deep,rem)),2),performance=numeric(score.get('sleep_performance_percentage')),efficiency=numeric(score.get('sleep_efficiency_percentage')))
    for r in collections.get('recovery',[]):
        day=sdays.get(str(r.get('sleep_id'))) or cdays.get(str(r.get('cycle_id')))
        if not day or r.get('score_state')!='SCORED':continue
        score=r.get('score') or {};ensure(day).update(recovery=numeric(score.get('recovery_score')),hrv=numeric(score.get('hrv_rmssd_milli')),rhr=numeric(score.get('resting_heart_rate')))
    workouts=[]
    for w in collections.get('workouts',[]):
        day=local_day(w.get('start'),w.get('timezone_offset'))
        if not day or day<first.isoformat() or day>today.isoformat():continue
        mins=None
        try:
            a=datetime.fromisoformat(w['start'].replace('Z','+00:00'));b=datetime.fromisoformat(w['end'].replace('Z','+00:00'));mins=round((b-a).total_seconds()/60)
        except (TypeError,ValueError,KeyError):pass
        score=w.get('score') or {}
        workouts.append(dict(date=day,sport=(w.get('sport_name') or 'Aktivität').replace('_',' ').title(),minutes=mins,strain=numeric(score.get('strain')),avg_hr=numeric(score.get('average_heart_rate'))))
    workouts.sort(key=lambda r:r['date'],reverse=True)
    rows=[byday.get((base+timedelta(days=i)).isoformat()) or ensure((base+timedelta(days=i)).isoformat()) for i in range((today-base).days+1)]
    visible=[r for r in rows if r['date']>=first.isoformat()]
    def delta(key):
        a=[r[key] for r in rows[-7:] if r[key] is not None];b=[r[key] for r in rows[-14:-7] if r[key] is not None]
        return round(mean(a)-mean(b),1) if len(a)>=4 and len(b)>=4 else None
    keys=('recovery','hrv','rhr','sleep_hours','strain')
    summary={k:dict(value=avg([r[k] for r in visible]),week_delta=delta(k),count=sum(r[k] is not None for r in visible)) for k in keys}
    insights=[]
    for key,name,unit,threshold in [('hrv','HRV','ms',2),('rhr','Ruhepuls','bpm',2),('sleep_hours','Schlaf','h',.25),('recovery','Recovery','%',2)]:
        change=delta(key)
        if change is not None and abs(change)>=threshold:
            insights.append(dict(label=name,delta=change,unit=unit,text=f'Ø {name} in den letzten 7 Tagen: {abs(change):g} {unit} '+('höher' if change>0 else 'niedriger')+' als in den 7 Tagen davor.'))
    return dict(days=days,rows=visible,summary=summary,from_=first.isoformat(),to=today.isoformat(),stages={key:avg([r[field] for r in visible]) for key,field in [('light','light_hours'),('deep','deep_hours'),('rem','rem_hours')]},workouts=workouts[:15],insights=insights[:3],data_points=summary['recovery']['count'])

def demo_collections(today=None):
    today=today or datetime.now(TZ).date();rng=Random(20261122)
    data={'cycles':[],'sleep':[],'recovery':[],'workouts':[]}
    for i in range(410):
        day=(today-timedelta(days=i)).isoformat();cid=i+1;sid=f'demo-{i}';phase=sin(i/17)
        light=int(max(2.1,rng.gauss(4,.52))*3600000);deep=int(max(.6,rng.gauss(1.4,.22))*3600000);rem=int(max(.6,rng.gauss(1.5,.3))*3600000)
        data['cycles'].append(dict(id=cid,start=day+'T08:00:00Z',score_state='SCORED',score={'strain':round(max(1,rng.gauss(11,2.8)),1)}))
        data['sleep'].append(dict(id=sid,end=day+'T06:00:00Z',nap=False,score_state='SCORED',score={'stage_summary':{'total_light_sleep_time_milli':light,'total_slow_wave_sleep_time_milli':deep,'total_rem_sleep_time_milli':rem},'sleep_performance_percentage':round(rng.uniform(67,98))}))
        data['recovery'].append(dict(cycle_id=cid,sleep_id=sid,score_state='SCORED',score={'recovery_score':max(17,min(98,round(rng.gauss(72+4*phase,11)))),'hrv_rmssd_milli':max(22,round(rng.gauss(56+2*phase,6),1)),'resting_heart_rate':max(42,round(rng.gauss(55,3)))}))
        if i%3==0:data['workouts'].append(dict(start=day+'T13:00:00Z',end=day+'T14:30:00Z',sport_name='golf' if i%2 else 'weightlifting',score={'strain':round(rng.uniform(6,13),1),'average_heart_rate':round(rng.uniform(99,130))}))
    return data
