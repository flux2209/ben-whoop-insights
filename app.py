"""WHOOP Insights: FastAPI, OAuth 2.0, WHOOP Developer v2, protected cookies."""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet,InvalidToken
from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse,JSONResponse,RedirectResponse,Response
from fastapi.staticfiles import StaticFiles
from analytics import TZ,transform,demo_collections

ROOT=Path(__file__).resolve().parent
HOST='https://api.prod.whoop.com'
AUTH=HOST+'/oauth/oauth2/auth';TOKEN=HOST+'/oauth/oauth2/token';API=HOST+'/developer/v2'
SCOPES='read:recovery read:cycles read:sleep read:workout offline'
CLIENT_ID=os.getenv('WHOOP_CLIENT_ID','').strip();CLIENT_SECRET=os.getenv('WHOOP_CLIENT_SECRET','').strip();PUBLIC_URL=os.getenv('PUBLIC_BASE_URL','').rstrip('/')
SECRET=os.getenv('APP_SECRET') or secrets.token_urlsafe(48)
CIPHER=Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET.encode()).digest()))
COOKIE='whoop_private';STATE='whoop_state';CACHE={};LOCK=asyncio.Lock()
logging.getLogger('uvicorn.access').disabled = True  # OAuth callback URLs can include short-lived authorization codes.
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
app.mount('/static',StaticFiles(directory=str(ROOT/'static')),name='static')

def base(req):return PUBLIC_URL or str(req.base_url).rstrip('/')
def redirect_uri(req):return base(req)+'/auth/callback'
def secure(req):return base(req).startswith('https://')
def seal(obj):return CIPHER.encrypt(json.dumps(obj,separators=(',',':')).encode()).decode()
def unseal(data):
    try:
        value=json.loads(CIPHER.decrypt(data.encode(),ttl=60*86400))
        return value if value.get('access_token') else None
    except (AttributeError,ValueError,InvalidToken,TypeError):return None

def save_cookie(resp,data,req):resp.set_cookie(COOKIE,seal(data),max_age=60*86400,secure=secure(req),httponly=True,samesite='lax',path='/')
def token_obj(data):return dict(access_token=data['access_token'],refresh_token=data.get('refresh_token'),expires_at=time.time()+int(data.get('expires_in',3600)))

@app.middleware('http')
async def security(request,call_next):
    result=await call_next(request)
    for key,value in {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"}.items():result.headers[key]=value
    if secure(request):result.headers['Strict-Transport-Security']='max-age=31536000'
    return result

@app.get('/')
async def home():return HTMLResponse((ROOT/'templates/index.html').read_text(encoding='utf-8'))
@app.get('/health')
async def health():return {'status':'ok'}
@app.get('/api/status')
async def status(req:Request):return {'connected':bool(unseal(req.cookies.get(COOKIE))),'configured':bool(CLIENT_ID and CLIENT_SECRET),'callback_url':redirect_uri(req)}
@app.get('/auth/login')
async def login(req:Request):
    if not (CLIENT_ID and CLIENT_SECRET):return RedirectResponse('/?setup=1',status_code=303)
    state=secrets.token_urlsafe(6) # WHOOP developer documentation specifies exactly 8 characters.
    args={'client_id':CLIENT_ID,'response_type':'code','redirect_uri':redirect_uri(req),'scope':SCOPES,'state':state}
    resp=RedirectResponse(AUTH+'?'+urlencode(args),status_code=302)
    resp.set_cookie(STATE,state,max_age=600,secure=secure(req),httponly=True,samesite='lax',path='/')
    return resp

async def token_request(params):
    async with httpx.AsyncClient(timeout=20) as client:
        response=await client.post(TOKEN,data=params,headers={'Accept':'application/json'})
        response.raise_for_status()
        return response.json()

@app.get('/auth/callback')
async def callback(req:Request):
    state=req.query_params.get('state');expected=req.cookies.get(STATE);code=req.query_params.get('code')
    if not (state and expected and code and hmac.compare_digest(state,expected)):
        return RedirectResponse('/?error=state',status_code=303)
    try:
        result=await token_request({'grant_type':'authorization_code','code':code,'redirect_uri':redirect_uri(req),'client_id':CLIENT_ID,'client_secret':CLIENT_SECRET})
        resp=RedirectResponse('/',status_code=303);save_cookie(resp,token_obj(result),req)
    except (httpx.HTTPError,KeyError,ValueError):resp=RedirectResponse('/?error=oauth',status_code=303)
    resp.delete_cookie(STATE,path='/');return resp

async def refresh(old):
    if not old.get('refresh_token'):raise PermissionError('WHOOP bitte erneut verbinden.')
    result=await token_request({'grant_type':'refresh_token','refresh_token':old['refresh_token'],'client_id':CLIENT_ID,'client_secret':CLIENT_SECRET,'scope':'offline'})
    return token_obj(result)

async def collect(client,path,access,start):
    records=[];next_token=None
    for page in range(65):
        params={'start':start,'limit':25}
        if next_token:params['nextToken']=next_token
        for tries in range(3):
            r=await client.get(API+path,params=params,headers={'Authorization':'Bearer '+access,'Accept':'application/json'})
            if r.status_code==429 and tries<2:
                try:delay=min(8,max(1,int(r.headers.get('Retry-After','2'))))
                except ValueError:delay=2
                await asyncio.sleep(delay);continue
            r.raise_for_status();break
        content=r.json();records.extend(content.get('records') or []);next_token=content.get('next_token')
        if not next_token:return records
    raise ValueError('Zu viele Datenseiten')

async def fetch_data(access,days):
    since=(datetime.now(timezone.utc)-timedelta(days=max(29,days+16))).isoformat(timespec='seconds')
    fields=[('cycles','/cycle'),('sleep','/activity/sleep'),('recovery','/recovery'),('workouts','/activity/workout')]
    async with httpx.AsyncClient(timeout=25) as client:
        result=await asyncio.gather(*(collect(client,path,access,since) for _,path in fields),return_exceptions=True)
    data={};warnings=[]
    for (name,_),r in zip(fields,result):
        if isinstance(r,Exception):
            if isinstance(r,httpx.HTTPStatusError) and r.response.status_code==401:raise PermissionError('WHOOP-Sitzung abgelaufen. Bitte erneut verbinden.')
            data[name]=[]
            if isinstance(r,httpx.HTTPStatusError):
                code=r.response.status_code
                logging.warning('WHOOP %s collection returned HTTP %s',name,code)
                if code==429: warnings.append(name+' wegen WHOOP-Abfragelimit vorübergehend nicht verfügbar (HTTP 429)')
                elif code==403: warnings.append(name+' von WHOOP abgewiesen (HTTP 403)')
                else: warnings.append(name+' gerade nicht verfügbar (HTTP '+str(code)+')')
            else:
                logging.warning('WHOOP %s collection failed with %s',name,type(r).__name__)
                warnings.append(name+' gerade nicht verfügbar (Verbindungsfehler)')
        else:data[name]=r
    if len(warnings)==len(fields):raise ConnectionError('Keine Datenabrufe möglich')
    return data,warnings,not any('workouts ' in item for item in warnings)

@app.get('/api/dashboard')
async def dashboard(req:Request):
    try:days=int(req.query_params.get('days','30'))
    except ValueError:return JSONResponse({'error':'Ungültiger Zeitraum'},status_code=400)
    if days not in (7,30,90,365):return JSONResponse({'error':'Ungültiger Zeitraum'},status_code=400)
    if req.query_params.get('demo')=='1':
        result=transform(demo_collections(),days);result['from']=result.pop('from_');return {**result,'demo':True,'warnings':[]}
    session=unseal(req.cookies.get(COOKIE))
    if not session:return JSONResponse({'error':'WHOOP noch nicht verbunden','unauthorized':True},status_code=401)
    rotated=False
    if session.get('expires_at',0)<time.time()+90:
        try:session=await refresh(session);rotated=True
        except (httpx.HTTPError,ValueError,PermissionError,KeyError):return JSONResponse({'error':'Bitte WHOOP erneut verbinden','unauthorized':True},status_code=401)
    key=(hashlib.sha256(session['access_token'].encode()).hexdigest(),days)
    async with LOCK:
        hit=CACHE.get(key)
        if req.query_params.get('force')!='1' and hit and time.monotonic()-hit[0]<300:
            resp=JSONResponse(hit[1]);
            if rotated:save_cookie(resp,session,req)
            return resp
    try:
        data,warnings,workouts_available=await fetch_data(session['access_token'],days)
        result=transform(data,days,workouts_available=workouts_available);result['from']=result.pop('from_')
        result.update(demo=False,warnings=warnings,refreshed_at=datetime.now(TZ).isoformat(timespec='minutes'))
    except PermissionError as exc:return JSONResponse({'error':str(exc),'unauthorized':True},status_code=401)
    except (httpx.HTTPError,ValueError,ConnectionError):return JSONResponse({'error':'WHOOP antwortet aktuell nicht. Bitte später aktualisieren.'},status_code=502)
    async with LOCK:
        if len(CACHE)>80:CACHE.clear()
        CACHE[key]=(time.monotonic(),result)
    resp=JSONResponse(result)
    if rotated:save_cookie(resp,session,req)
    return resp

@app.post('/auth/disconnect')
async def disconnect(req:Request):
    origin=req.headers.get('origin')
    if origin and origin.rstrip('/')!=base(req):return JSONResponse({'error':'Ungültige Herkunft'},status_code=403)
    session=unseal(req.cookies.get(COOKIE))
    if session:
        try:
            async with httpx.AsyncClient(timeout=6) as client:await client.delete(API+'/user/access',headers={'Authorization':'Bearer '+session['access_token']})
        except httpx.HTTPError:pass
    resp=JSONResponse({'ok':True});resp.delete_cookie(COOKIE,path='/');return resp
