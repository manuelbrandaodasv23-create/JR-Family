const $ = (id) => document.getElementById(id);
const state = { token: sessionStorage.getItem('jr_admin_token') || '' };

function api(path, options={}) {
  const headers = {'Content-Type':'application/json', ...(options.headers||{})};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  return fetch(path, {...options, headers}).then(async r => {
    const data = await r.json().catch(()=>({}));
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    return data;
  });
}

function fmt(v){ if(!v) return '—'; const d=new Date(v); return Number.isNaN(d.getTime())?String(v):d.toLocaleString('pt-BR'); }
function esc(v){ return String(v??'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function pill(v, bad=false){ return `<span class="pill ${bad?'bad':''}">${esc(v)}</span>`; }

async function login(email,password){
  const data = await api('/admin/auth/login',{method:'POST',body:JSON.stringify({email,password})});
  state.token=data.access_token;
  sessionStorage.setItem('jr_admin_token',state.token);
  const me=await api('/me');
  if(!me.is_admin) throw new Error('Esta conta não possui permissão administrativa.');
}

function renderSummary(s){
  $('privacyBanner').textContent=s.privacy_note || 'Administração técnica.';
  const metrics=[['Usuários',s.users],['Famílias',s.families],['Dispositivos',s.devices],['Online 30 min',s.devices_online_30m],['Alertas 24h',s.alerts_24h],['SOS abertos',s.sos_open]];
  $('cards').innerHTML=metrics.map(([label,value])=>`<article class="metric glass"><span>${esc(label)}</span><strong>${esc(value)}</strong></article>`).join('');
}

async function loadDashboard(){
  const [summary,devices,alerts,users,audit]=await Promise.all([
    api('/admin/summary'),api('/admin/devices?limit=200'),api('/admin/alerts?limit=200'),api('/admin/users?limit=200'),api('/admin/audit?limit=200')
  ]);
  renderSummary(summary);
  $('deviceCount').textContent=`${devices.items.length} registros`;
  $('devicesBody').innerHTML=devices.items.map(d=>`<tr><td>${esc(d.device_name)}</td><td>${pill(d.platform)}</td><td>${esc(d.app_version||'—')}</td><td>${d.battery_percent==null?'—':esc(d.battery_percent)+'%'}</td><td>${pill(d.permission_location,d.permission_location!=='authorized')}</td><td>${pill(d.permission_background,!['authorized','requested'].includes(d.permission_background))}</td><td>${fmt(d.last_seen_at)}</td><td>${d.push_registered?pill('registrado'):pill('sem token',true)}</td></tr>`).join('');
  $('alertCount').textContent=`${alerts.items.length} registros`;
  $('alertsBody').innerHTML=alerts.items.map(a=>`<tr><td>${pill(a.kind,a.kind==='sos')}</td><td>${esc(a.title)}</td><td>${esc(a.family_id)}</td><td>${fmt(a.created_at)}</td></tr>`).join('');
  $('userCount').textContent=`${users.items.length} registros`;
  $('usersBody').innerHTML=users.items.map(u=>`<tr><td>${esc(u.name)}</td><td>${esc(u.email)}</td><td>${u.is_admin?pill('sim'):pill('não')}</td><td>${fmt(u.created_at)}</td><td><button data-action="block" data-id="${esc(u.id)}" data-blocked="${u.is_blocked}">${u.is_blocked?'Desbloquear':'Bloquear'}</button><button data-action="revoke" data-id="${esc(u.id)}">Encerrar sessões</button></td></tr>`).join('');
  $('auditCount').textContent=`${audit.items.length} registros`;
  $('auditBody').innerHTML=audit.items.map(a=>`<tr><td>${esc(a.action)}</td><td>${esc(a.entity)}</td><td>${esc(a.entity_id||'—')}</td><td>${fmt(a.created_at)}</td></tr>`).join('');
}

async function showDashboard(){
  $('loginView').classList.add('hidden');
  $('dashboardView').classList.remove('hidden');
  try { await loadDashboard(); }
  catch(e){
    if(String(e.message).includes('403') || String(e.message).toLowerCase().includes('admin')) logout();
    else alert(e.message);
  }
}
async function logout(){try { await api('/auth/logout',{method:'POST'}); } catch (_) {} state.token='';sessionStorage.removeItem('jr_admin_token');$('dashboardView').classList.add('hidden');$('loginView').classList.remove('hidden');}

$('loginForm').addEventListener('submit',async e=>{e.preventDefault();$('loginError').textContent='';try{await login($('email').value.trim(),$('password').value);await showDashboard();}catch(err){state.token='';sessionStorage.removeItem('jr_admin_token');$('loginError').textContent=err.message;}});
$('refreshBtn').addEventListener('click',()=>loadDashboard().catch(e=>alert(e.message)));
$('logoutBtn').addEventListener('click',logout);
if(state.token) showDashboard();

$('userSearch').addEventListener('input', e => {
  const query=e.target.value.toLowerCase();
  for (const row of $('usersBody').rows) row.hidden=!row.textContent.toLowerCase().includes(query);
});
$('usersBody').addEventListener('click',async e=>{
  const button=e.target.closest('button[data-action]'); if(!button) return;
  if(!confirm('Confirmar esta ação administrativa?')) return;
  try {
    if(button.dataset.action==='revoke') await api(`/admin/users/${button.dataset.id}/revoke-sessions`,{method:'POST'});
    else await api(`/admin/users/${button.dataset.id}/blocked`,{method:'PATCH',body:JSON.stringify({blocked:button.dataset.blocked!=='true'})});
    await loadDashboard();
  } catch(error) {alert(error.message);}
});

for(const [id,path] of [['sessionsBtn','/admin/sessions'],['notificationsBtn','/admin/notifications'],['versionsBtn','/admin/app-versions']]) {
  $(id).addEventListener('click',async()=>{try{$('technicalResult').textContent=JSON.stringify(await api(path),null,2);}catch(e){alert(e.message);}});
}
$('versionForm').addEventListener('submit',async e=>{
  e.preventDefault();
  try {await api('/admin/app-versions',{method:'POST',body:JSON.stringify({platform:$('versionPlatform').value,version:$('versionName').value,build_number:Number($('versionBuild').value),required:$('versionRequired').checked})});$('technicalResult').textContent='Versão registrada.';}
  catch(error){alert(error.message);}
});
