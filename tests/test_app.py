import os
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pytest
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analytics import demo_collections, transform, local_day
import app as service


def test_whoop_schema_transformation():
    records = {
        'cycles': [{'id':42,'start':'2026-11-21T07:00:00Z','timezone_offset':'+01:00','score_state':'SCORED','score':{'strain':12.4}}],
        'sleep':[{'id':'s-1','end':'2026-11-21T06:00:00Z','timezone_offset':'+01:00','score_state':'SCORED','nap':False,'score': {'stage_summary':{'total_light_sleep_time_milli':14400000,'total_slow_wave_sleep_time_milli':5400000,'total_rem_sleep_time_milli':7200000},'sleep_performance_percentage':90,'sleep_efficiency_percentage':93}}],
        'recovery':[{'cycle_id':42,'sleep_id':'s-1','score_state':'SCORED','score':{'recovery_score':71,'resting_heart_rate':54,'hrv_rmssd_milli':63.7}}],
        'workouts':[{'start':'2026-11-21T13:00:00Z','end':'2026-11-21T14:30:00Z','sport_name':'golf','score':{'strain':9.4,'average_heart_rate':112}}]
    }
    result = transform(records,7,today=date(2026,11,22))
    d = next(r for r in result['rows'] if r['date']=='2026-11-21')
    assert (d['recovery'],d['hrv'],d['rhr'],d['sleep_hours'],d['strain']) == (71.0,63.7,54.0,7.5,12.4)
    assert result['workouts'][0]['minutes']==90


def test_missing_scores_not_invented():
    records={'cycles':[{'id':1,'start':'2026-11-21T06:00:00Z','score_state':'PENDING_SCORE'}],
             'sleep':[],'recovery':[],'workouts':[]}
    result=transform(records,7,today=date(2026,11,22))
    assert result['summary']['recovery']['value'] is None
    assert result['summary']['recovery']['week_delta'] is None
    assert all(r['recovery'] is None for r in result['rows'])


def test_demo_has_no_real_data():
    result=transform(demo_collections(today=date(2026,11,22)),30,today=date(2026,11,22))
    assert len(result['rows'])==30
    assert result['data_points']>=27
    assert result['summary']['recovery']['count']>=27
    assert result['stages']['deep']>0


def test_timezones():
    assert local_day('2026-11-21T23:30:00Z','+01:00')=='2026-11-22'
    assert local_day('2026-11-21T23:30:00Z','-05:00')=='2026-11-21'


@pytest.mark.asyncio
async def test_demo_route_works_without_oauth():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app),base_url='http://testserver') as client:
        res=await client.get('/api/dashboard?days=30&demo=1')
        assert res.status_code==200, res.text
        assert res.json()['demo'] is True
        assert res.headers['Cache-Control']=='no-store'
        assert res.headers['X-Frame-Options']=='DENY'


@pytest.mark.asyncio
async def test_live_data_requires_oauth():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app),base_url='http://testserver') as client:
        res=await client.get('/api/dashboard?days=30')
        assert res.status_code==401
        assert res.json()['unauthorized'] is True


@pytest.mark.asyncio
async def test_oauth_state_and_scopes(monkeypatch):
    monkeypatch.setattr(service,'CLIENT_ID','fake-id')
    monkeypatch.setattr(service,'CLIENT_SECRET','fake-secret')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app),base_url='https://dashboard.example') as client:
        res=await client.get('/auth/login',follow_redirects=False)
        assert res.status_code==302
        url=urlparse(res.headers['location'])
        query=parse_qs(url.query)
        assert len(query['state'][0])==8
        assert 'offline' in query['scope'][0]
        assert query['redirect_uri'][0]=='https://dashboard.example/auth/callback'
        assert 'Secure' in res.headers['set-cookie']
