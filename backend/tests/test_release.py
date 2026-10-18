from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import User, Location, now
from app.maintenance import purge_old_locations
client = TestClient(app)

def account():
    email = uuid4().hex+"@example.com"
    r=client.post('/auth/register',json={'name':'Pessoa','email':email,'password':'test-password-123'})
    assert r.status_code==200, r.text
    return r.json(), email

def header(tokens): return {'Authorization':'Bearer '+tokens['access_token']}

def family_device():
    t,e=account(); h=header(t)
    f=client.post('/families',headers=h,json={'name':'Família'}).json()
    d=client.post(f"/families/{f['id']}/devices",headers=h,json={'member_id':f['member_id'],'platform':'android','device_name':'Test'}).json()['id']
    client.patch(f"/families/{f['id']}/devices/{d}/permissions",headers=h,json={'location':'authorized','background':'authorized','sharing_enabled':True})
    return h,f,d

def test_rotation_logout_and_replay():
    t,_=account()
    r=client.post('/auth/refresh',json={'refresh_token':t['refresh_token']})
    assert r.status_code==200
    assert client.get('/me',headers=header(t)).status_code==401
    assert client.post('/auth/refresh',json={'refresh_token':t['refresh_token']}).status_code==401
    new=r.json()
    assert client.post('/auth/logout',headers=header(new)).status_code==200
    assert client.get('/me',headers=header(new)).status_code==401

def test_admin_scope_block_and_revoke():
    t,email=account()
    with SessionLocal() as db:
        db.query(User).filter_by(email=email).first().is_admin=True;db.commit()
    assert client.get('/admin/summary',headers=header(t)).status_code==403
    admin=client.post('/admin/auth/login',json={'email':email,'password':'test-password-123'}).json()
    assert client.get('/admin/summary',headers=header(admin)).status_code==200
    target,mail=account(); uid=client.get('/me',headers=header(target)).json()['id']
    assert client.patch(f'/admin/users/{uid}/blocked',headers=header(admin),json={'blocked':True}).status_code==200
    assert client.get('/me',headers=header(target)).status_code==401
    assert client.post('/auth/login',json={'email':mail,'password':'test-password-123'}).status_code==401

@pytest.mark.parametrize('suffix',['','/alerts','/geofences'])
def test_idor_family_reads(suffix):
    h,f,d=family_device(); outsider,_=account()
    assert client.get(f"/families/{f['id']}"+suffix,headers=header(outsider)).status_code==403

@pytest.mark.parametrize('action',['history','push','permissions','upload','sos'])
def test_idor_device_actions(action):
    h,f,d=family_device(); outsider,_=account(); h=header(outsider)
    if action=='history': r=client.get(f"/families/{f['id']}/members/{f['member_id']}/locations",headers=h)
    elif action=='push': r=client.patch(f'/devices/{d}/push-token',headers=h,json={'push_token':'abc'})
    elif action=='permissions': r=client.patch(f"/families/{f['id']}/devices/{d}/permissions",headers=h,json={'location':'authorized','background':'authorized','sharing_enabled':True})
    elif action=='upload': r=client.post(f'/devices/{d}/locations',headers=h,json={'latitude':0,'longitude':0})
    else: r=client.post(f"/families/{f['id']}/members/{f['member_id']}/sos",headers=h,json={})
    assert r.status_code==403

def test_invite_single_use_and_dependent_permissions():
    h,f,d=family_device()
    code=client.post(f"/families/{f['id']}/invites",headers=h,json={}).json()['code']
    dependent,_=account(); dh=header(dependent)
    joined=client.post('/invites/join',headers=dh,json={'code':code,'display_name':'Filho'})
    assert joined.status_code==200
    other,_=account()
    assert client.post('/invites/join',headers=header(other),json={'code':code,'display_name':'Outro'}).status_code==400
    assert client.post(f"/families/{f['id']}/geofences",headers=dh,json={'name':'Casa','latitude':0,'longitude':0}).status_code==403
    assert client.post(f"/families/{f['id']}/devices",headers=h,json={'member_id':joined.json()['member_id'],'platform':'android','device_name':'Fake'}).status_code==403

def test_geofence_sos_history_and_retention():
    h,f,d=family_device(); base=f"/families/{f['id']}"
    assert client.post(base+'/geofences',headers=h,json={'name':'Casa','latitude':0,'longitude':0,'radius_m':100}).status_code==200
    for lat in [0,1,0]:
        r=client.post(f'/devices/{d}/locations',headers=h,json={'latitude':lat,'longitude':0,'battery_percent':10})
        assert r.status_code==200,r.text
    kinds=[a['kind'] for a in client.get(base+'/alerts',headers=h).json()['items']]
    assert kinds.count('battery_low')==1
    assert 'geofence_exit' in kinds and 'geofence_enter' in kinds
    assert client.post(base+f"/members/{f['member_id']}/sos",headers=h,json={'latitude':0,'longitude':0}).status_code==200
    history=client.get(base+f"/members/{f['member_id']}/locations",headers=h).json()['items']
    assert len(history)==3 and history[0]['captured_at'].endswith('+00:00')
    with SessionLocal() as db:
        db.add(Location(device_id=d,latitude=0,longitude=0,captured_at=now()-timedelta(days=40)));db.commit()
        assert purge_old_locations(db)==1;db.commit()

def test_sharing_off_future_and_invalid_coordinates():
    h,f,d=family_device()
    assert client.post(f'/devices/{d}/locations',headers=h,json={'latitude':99,'longitude':0}).status_code==422
    assert client.post(f'/devices/{d}/locations',headers=h,json={'latitude':0,'longitude':0,'captured_at':(now()+timedelta(days=1)).isoformat()}).status_code==422
    client.patch(f"/families/{f['id']}/devices/{d}/permissions",headers=h,json={'location':'denied','background':'off','sharing_enabled':False})
    assert client.post(f'/devices/{d}/locations',headers=h,json={'latitude':0,'longitude':0}).status_code==409

def test_delete_owner_family_then_account_cascades():
    h,f,d=family_device()
    assert client.delete('/me',headers=h).status_code==409
    assert client.delete(f"/families/{f['id']}",headers=h).status_code==200
    assert client.delete('/me',headers=h).status_code==200
    assert client.get('/me',headers=h).status_code==401

def test_bruteforce_and_mass_assignment():
    assert client.post('/auth/register',json={'name':'Admin','email':'admin@example.com','password':'test-password-123','is_admin':True}).status_code==422
    for _ in range(20):
        assert client.post('/auth/login',json={'email':'x@example.com','password':'wrong'}).status_code==401
    assert client.post('/auth/login',json={'email':'x@example.com','password':'wrong'}).status_code==429


def test_offline_and_recovery_alerts_and_disabled_push():
    from app.models import Device, NotificationLog
    from app.maintenance import check_unavailable
    from app.push import notify_guardians
    h,f,d=family_device()
    with SessionLocal() as db:
        device=db.get(Device,d);device.last_seen_at=now()-timedelta(hours=1);device.push_token='test-token-not-a-real-fcm-token';db.commit()
        check_unavailable(db);db.commit()
        assert db.get(Device,d).offline_notified is True
        assert notify_guardians(db,f['id'],title='Test',body='Test')==0
        db.commit()
        assert db.query(NotificationLog).filter_by(status='skipped').count()>=1
    assert client.post(f'/devices/{d}/locations',headers=h,json={'latitude':0,'longitude':0}).status_code==200
    with SessionLocal() as db: assert db.get(Device,d).offline_notified is False

def test_old_location_does_not_trigger_present_geofence_alert():
    h,f,d=family_device();base=f"/families/{f['id']}"
    client.post(base+'/geofences',headers=h,json={'name':'Casa','latitude':0,'longitude':0,'radius_m':100})
    client.post(f'/devices/{d}/locations',headers=h,json={'latitude':0,'longitude':0})
    r=client.post(f'/devices/{d}/locations',headers=h,json={'latitude':1,'longitude':0,'captured_at':(now()-timedelta(hours=1)).isoformat()})
    assert r.status_code==200 and r.json()['alerts']==0

def test_custom_history_range_and_admin_private_metadata():
    h,f,d=family_device()
    assert client.get(f"/families/{f['id']}/members/{f['member_id']}/locations",headers=h,
                      params={'start':'2020-01-01T00:00:00Z','end':'2026-10-16T00:00:00Z'}).status_code==422
    assert client.get('/admin/users',headers=h).status_code==403
