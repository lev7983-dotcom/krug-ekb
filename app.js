/* KRUG source block 1 */
const hero='/krug-hero.png';
document.addEventListener('error',event=>{let image=event.target;if(image instanceof HTMLImageElement&&image.getAttribute('src')!==hero){image.src=hero}},true);
const safeText=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeImageSrc=value=>{let src=String(value||'');return /^data:image\/(?:jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(src)||/^(?:\/|assets\/)[A-Za-z0-9._/-]+\.(?:png|jpe?g|webp)$/i.test(src)?src:hero};
const krugEyeIcon=`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.8"/></svg>`;
let catalogRange='all';
let cars=[
 {name:'Toyota RAV4',price:2890000,year:2021,km:'54 000 км',type:'Продажа',urgent:false,pos:'70% 50%'},
 {name:'Kia K5',price:2470000,year:2020,km:'72 000 км',type:'Обмен',urgent:false,pos:'18% 50%'},
 {name:'Lada Granta',price:690000,year:2019,km:'91 000 км',type:'Срочно',urgent:true,pos:'49% 50%'},
 {name:'Hyundai Solaris',price:1450000,year:2018,km:'86 000 км',type:'Срочно',urgent:true,pos:'48% 50%'},
 {name:'Ford Focus',price:290000,year:2007,km:'181 000 км',type:'Обмен',urgent:false,pos:'23% 50%'},
 {name:'ВАЗ 2114',price:95000,year:2008,km:'210 000 км',type:'Срочно',urgent:true,pos:'48% 50%'}
];
let mode='Все';
const rub=n=>new Intl.NumberFormat('ru-RU').format(n)+' ₽';
function card(c){return `<article class="car" onclick="openCar('${c.name}',${c.price},'${c.pos}')"><div class="car-media"><img src="${hero}" style="object-position:${c.pos}" alt="${c.name}"><span class="badge ${c.urgent?'urgent':''}">${c.urgent?'⚡ Срочно':c.type}</span><button class="heart" onclick="save(event,this)">♡</button></div><div class="car-body"><div class="car-top"><div><h3>${c.name}</h3><div class="meta">${c.year} · ${c.km}</div></div><div class="price">${rub(c.price)}</div></div><div class="tags"><span class="tag">Екатеринбург</span><span class="tag">Проверен VIN</span>${c.type==='Обмен'?'<span class="tag">↔ Рассмотрю обмен</span>':''}</div></div></article>`}
function render(list,target){document.getElementById(target).innerHTML=list.map(card).join('')||'<div class="panel"><h3>Здесь пока пусто</h3><p class="meta">Попробуйте другой диапазон цены.</p></div>'}
function renderAll(){render(cars.slice(0,3),'homeCards');render(cars,'catalogCards');render(cars.filter(c=>c.urgent),'urgentCards')}
queueMicrotask(()=>renderAll());
async function loadCars(){if(location.protocol==='file:')return;try{let r=await fetch('/api/cars');if(!r.ok)throw Error('api');cars=await r.json();renderAll()}catch(e){toast('Сервер недоступен — показаны демо-данные')}}
loadCars();
function go(id){document.querySelectorAll('.screen').forEach(s=>s.classList.toggle('active',s.id===id));document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('active',b.dataset.go===id));scrollTo(0,0)}
document.querySelectorAll('.nav button').forEach(b=>b.onclick=()=>go(b.dataset.go));
function setMode(el,m){document.querySelectorAll('.mode').forEach(x=>x.classList.remove('active'));el.classList.add('active');mode=m;if(m==='Обмен'){go('catalog');render(cars.filter(c=>c.type==='Обмен'),'catalogCards')}}
document.querySelectorAll('#prices .chip').forEach(b=>b.onclick=()=>{document.querySelectorAll('#prices .chip').forEach(x=>x.classList.remove('active'));b.classList.add('active');let r=b.dataset.range, list=cars;if(r!=='all'){if(r==='300+')list=cars.filter(c=>c.price>=300000);else{let[a,z]=r.split('-').map(x=>+x*10000);list=cars.filter(c=>c.price>=a&&c.price<=z)}}render(list,'catalogCards')});
function save(e,b){e.stopPropagation();b.classList.toggle('saved');b.textContent=b.classList.contains('saved')?'♥':'♡';toast(b.classList.contains('saved')?'Добавлено в избранное':'Удалено из избранного')}
async function subscribe(b){if(location.protocol!=='file:')await fetch('/api/subscriptions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user:window.Telegram?.WebApp?.initDataUnsafe?.user?.id||'local-user'})});b.textContent='✓ Вы подписаны';b.closest('.urgent-banner')?.classList.add('subscribed');toast('Уведомления о срочных авто включены')}
function nextStep(n){document.querySelectorAll('.step').forEach(s=>s.classList.toggle('active',+s.dataset.step===n));document.querySelectorAll('.form-progress i').forEach((x,i)=>x.classList.toggle('on',i<n));document.getElementById('stepText').textContent=`Шаг ${n} из 3 · ${['Тип сделки','Автомобиль','Публикация'][n-1]}`;scrollTo(0,0)}
document.querySelectorAll('.type-card').forEach(b=>b.onclick=()=>{document.querySelectorAll('.type-card').forEach(x=>x.classList.remove('active'));b.classList.add('active')});
async function publish(){let active=document.querySelector('.type-card.active').textContent;let data={name:document.getElementById('carName').value,year:+document.getElementById('carYear').value,price:+document.getElementById('carPrice').value,km:(document.getElementById('carKm').value||'0')+' км',description:document.getElementById('carDescription').value,phone:document.getElementById('carPhone').value,type:active.includes('Обмен')?'Обмен':'Продажа',urgent:active.includes('срочно')};if(!data.name||!data.year||!data.price){toast('Заполните марку, год и цену');nextStep(1);return}if(location.protocol!=='file:'){let r=await fetch('/api/cars',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(!r.ok){toast('Не удалось сохранить');return}await loadCars()}else{cars.unshift({...data,pos:'50% 50%'});renderAll()}toast('Объявление опубликовано');setTimeout(()=>go('catalog'),900)}
function toast(t){let x=document.getElementById('toast');x.textContent=t;x.classList.add('show');setTimeout(()=>x.classList.remove('show'),2200)}
function openCar(n,p,pos){document.getElementById('detailName').textContent=n;document.getElementById('detailPrice').textContent=rub(p);document.getElementById('detailImg').src=hero;document.getElementById('detailImg').style.objectPosition=pos;document.getElementById('modal').classList.add('open')}
function closeModal(){document.getElementById('modal').classList.remove('open')}
window.Telegram?.WebApp?.ready();window.Telegram?.WebApp?.expand();

/* KRUG source block 2 */
// KRUG v2: persistent user session, favourites and validated listings.
const krugTgUser=window.Telegram?.WebApp?.initDataUnsafe?.user;
const krugUserId=String(krugTgUser?.id||(location.protocol==='file:'?localStorage.getItem('krug_user'):'')||'anonymous');
if(location.protocol==='file:')localStorage.setItem('krug_user',krugUserId);else localStorage.removeItem('krug_user');
const krugInitData=window.Telegram?.WebApp?.initData||'';
const krugReadRequests=new Map();
const krugSessionRequests=new Map();
const krugFetch=(url,request,timeout=18000)=>{
  if(request.signal)return fetch(url,request);
  let controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);
  return fetch(url,{...request,signal:controller.signal}).finally(()=>clearTimeout(timer));
};
const krugApi=(url,options={})=>{
  let request={...options,headers:{'Content-Type':'application/json','X-Telegram-Init-Data':krugInitData,'X-Krug-User':krugUserId,...options.headers}},method=String(options.method||'GET').toUpperCase();
  let personal=/^\/api\/(?:session|me|subscriptions|favourites|recent|my-cars|exchanges|admin(?:\/|$))/.test(url)||/^\/api\/cars\/\d+\/(?:favourite|report)$/.test(url);
  if(!krugInitData&&location.protocol!=='file:'&&personal)return Promise.resolve(new Response(JSON.stringify({error:'Откройте КРУГ внутри Telegram',code:'telegram_required'}),{status:401,headers:{'Content-Type':'application/json'}}));
  if(method==='POST'&&url==='/api/session'){
    let key=String(options.body||''),cached=krugSessionRequests.get(key),now=Date.now();
    if(!cached||now-cached.created>2000){cached={created:now,promise:krugFetch(url,request)};krugSessionRequests.set(key,cached)}
    return cached.promise.then(response=>{krugReadRequests.clear();return response.clone()});
  }
  if(method!=='GET'){krugReadRequests.clear();return krugFetch(url,request)}
  if(url!=='/api/me')return krugFetch(url,request);
  let cached=krugReadRequests.get(url),now=Date.now();
  if(!cached||now-cached.created>2000){cached={created:now,promise:krugFetch(url,request)};krugReadRequests.set(url,cached)}
  return cached.promise.then(response=>response.clone());
};
function card(c){let safe=String(c.name).replaceAll("'","&#39;");return `<article class="car" onclick="openCarV2(${c.id||0},'${safe}',${c.price},'${c.pos||'50% 50%'}')"><div class="car-media"><img src="${hero}" style="object-position:${c.pos||'50% 50%'}" alt="${c.name}"><span class="badge ${c.urgent?'urgent':''}">${c.urgent?'⚡ Срочно':c.type}</span><button class="heart ${c.favourite?'saved':''}" onclick="saveV2(event,this,${c.id||0})">${c.favourite?'♥':'♡'}</button></div><div class="car-body"><div class="car-top"><div><h3>${c.name}</h3><div class="meta">${c.year} · ${c.km}</div></div><div class="price">${rub(c.price)}</div></div><div class="tags"><span class="tag">Екатеринбург</span><span class="tag">ID ${c.id||'демо'}</span>${c.type==='Обмен'?'<span class="tag">↔ Рассмотрю обмен</span>':''}</div></div></article>`}
async function krugLoadCars(){if(location.protocol==='file:')return;try{let r=await krugApi('/api/cars');if(!r.ok)throw Error('api');cars=await r.json();renderAll();await krugLoadProfile()}catch(e){toast('Не удалось обновить объявления')}}
async function saveV2(e,b,id){e.stopPropagation();if(!id)return;let r=await krugApi(`/api/cars/${id}/favourite`,{method:'POST',body:'{}'}),d=await r.json();if(!r.ok)return toast(d.error||'Ошибка');b.classList.toggle('saved',d.favourite);b.textContent=d.favourite?'♥':'♡';toast(d.favourite?'Добавлено в избранное':'Удалено из избранного');krugLoadProfile()}
let krugOpenedCar=0;
function openCarV2(id,n,p,pos){krugOpenedCar=id;openCar(n,p,pos)}
async function subscribe(b){if(location.protocol!=='file:')await krugApi('/api/subscriptions',{method:'POST',body:'{}'});b.textContent='✓ Вы подписаны';b.closest('.urgent-banner')?.classList.add('subscribed');toast('Подписка на срочные авто включена')}
async function publish(){let active=document.querySelector('.type-card.active').textContent;let data={name:carName.value.trim(),year:+carYear.value,price:+carPrice.value,km:+carKm.value||0,description:carDescription.value.trim(),phone:carPhone.value.trim(),type:active.includes('Обмен')?'Обмен':'Продажа',urgent:active.toLowerCase().includes('срочно')};if(location.protocol==='file:')return toast('Публикация работает внутри Telegram');let r=await krugApi('/api/cars',{method:'POST',body:JSON.stringify(data)}),d=await r.json();if(!r.ok){toast(d.error||'Проверьте данные');return}toast('Объявление опубликовано');document.querySelectorAll('#create input,#create textarea').forEach(x=>x.value='');await krugLoadCars();setTimeout(()=>go('catalog'),700)}
async function krugLoadProfile(){let u=krugTgUser||{first_name:'Пользователь',username:''};await krugApi('/api/session',{method:'POST',body:JSON.stringify({first_name:u.first_name,username:u.username||''})});let r=await krugApi('/api/me'),d=await r.json(),p=document.querySelector('.profile-card');if(!p)return;p.querySelector('.avatar').textContent=(u.first_name||'К')[0]+(u.last_name||'').slice(0,1);p.querySelector('h2').textContent=[u.first_name,u.last_name].filter(Boolean).join(' ');let n=p.querySelectorAll('.stat b');n[0].textContent=d.listings;n[1].textContent=d.favourites;n[2].textContent=d.offers}
krugLoadCars();

/* KRUG source block 3 */
let krugImageData='';
carImage?.addEventListener('change',async()=>{let f=carImage.files[0];if(!f)return;if(f.size>8_000_000){toast('Фото должно быть меньше 8 МБ');carImage.value='';return}let img=new Image(),url=URL.createObjectURL(f);img.onload=()=>{let max=1200,scale=Math.min(1,max/Math.max(img.width,img.height)),canvas=document.createElement('canvas');canvas.width=Math.round(img.width*scale);canvas.height=Math.round(img.height*scale);canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);krugImageData=canvas.toDataURL('image/jpeg',.78);carPreview.src=krugImageData;carPreview.hidden=false;URL.revokeObjectURL(url)};img.src=url});
function card(c){let safe=String(c.name).replaceAll("'","&#39;"),picture=c.image||hero;return `<article class="car" onclick="openCarV3(${c.id||0},'${safe}',${c.price},'${c.pos||'50% 50%'}','${picture}')"><div class="car-media"><img src="${picture}" style="object-position:${c.pos||'50% 50%'}" alt="${c.name}"><span class="badge ${c.urgent?'urgent':''}">${c.urgent?'⚡ Срочно':c.type}</span><button class="heart ${c.favourite?'saved':''}" onclick="saveV2(event,this,${c.id||0})">${c.favourite?'♥':'♡'}</button></div><div class="car-body"><div class="car-top"><div><h3>${c.name}</h3><div class="meta">${c.year} · ${c.km}</div></div><div class="price">${rub(c.price)}</div></div><div class="tags"><span class="tag">Екатеринбург</span><span class="tag">ID ${c.id||'демо'}</span>${c.type==='Обмен'?'<span class="tag">↔ Рассмотрю обмен</span>':''}</div></div></article>`}
function openCarV3(id,n,p,pos,picture){krugOpenedCar=id;openCar(n,p,pos);detailImg.src=picture;let sheet=document.querySelector('.sheet');if(!sheet.querySelector('.exchange-action')){let x=document.createElement('button');x.className='btn back exchange-action';x.textContent='↔ Предложить обмен';x.onclick=offerExchange;sheet.insertBefore(x,sheet.lastElementChild)}}
async function publish(){let active=document.querySelector('.type-card.active').textContent,data={name:carName.value.trim(),year:+carYear.value,price:+carPrice.value,km:+carKm.value||0,description:carDescription.value.trim(),phone:carPhone.value.trim(),type:active.includes('Обмен')?'Обмен':'Продажа',urgent:active.toLowerCase().includes('срочно'),image:krugImageData};if(location.protocol==='file:')return toast('Публикация работает внутри Telegram');let r=await krugApi('/api/cars',{method:'POST',body:JSON.stringify(data)}),d=await r.json();if(!r.ok)return toast(d.error||'Проверьте данные');toast('Объявление опубликовано');document.querySelectorAll('#create input,#create textarea').forEach(x=>x.value='');krugImageData='';carPreview.hidden=true;await krugLoadCars();setTimeout(()=>go('catalog'),700)}
async function showMyCars(){let r=await krugApi('/api/my-cars'),list=await r.json();go('catalog');document.querySelector('#catalog .page-head h1').textContent='Мои объявления';document.getElementById('catalogCards').innerHTML=list.map(c=>`${card(c)}<div class="manage-actions"><button class="btn back" onclick="manageCar(${c.id},'${c.status==='active'?'archive':'activate'}')">${c.status==='active'?'Снять с публикации':'Опубликовать'}</button><button class="btn" style="background:#ffe3dc" onclick="deleteCar(${c.id})">Удалить</button></div>`).join('')||'<div class="panel"><h3>Объявлений пока нет</h3></div>'}
async function manageCar(id,action){let r=await krugApi(`/api/cars/${id}`,{method:'PUT',body:JSON.stringify({action})});if(r.ok){toast('Статус обновлён');showMyCars()}}
async function deleteCar(id){if(!confirm('Удалить объявление?'))return;let r=await krugApi(`/api/cars/${id}`,{method:'DELETE'});if(r.ok){toast('Объявление удалено');showMyCars();krugLoadProfile()}}
async function offerExchange(){let r=await krugApi('/api/my-cars'),mine=(await r.json()).filter(x=>x.status==='active');if(!mine.length){closeModal();go('create');return toast('Сначала разместите свой автомобиль')}let message=prompt(`Предложить ${mine[0].name} в обмен. Добавьте сообщение:`,`Готов обсудить обмен`);if(message===null)return;let res=await krugApi('/api/exchanges',{method:'POST',body:JSON.stringify({target_car_id:krugOpenedCar,offered_car_id:mine[0].id,message})});toast(res.ok?'Предложение обмена отправлено':'Не удалось отправить')}
let profileButtons=document.querySelectorAll('#profile .menu-item');if(profileButtons[0])profileButtons[0].onclick=showMyCars;if(profileButtons[1])profileButtons[1].onclick=async()=>{let r=await krugApi('/api/exchanges'),x=await r.json();toast(x.length?`Предложений обмена: ${x.length}`:'Предложений пока нет')};
queueMicrotask(()=>renderAll());

/* KRUG source block 4 */
// KRUG v4: real counters, persistent subscription controls and complete profile shortcuts.
let krugSubscribed=false;
function paintSubscription(){
  document.querySelectorAll('[onclick="subscribe(this)"]').forEach(b=>{
    b.textContent=krugSubscribed?'✓ Вы подписаны':'🔔 Подписаться';
    b.classList.toggle('subscribed',krugSubscribed);
  });
  document.getElementById('homeSub')?.classList.toggle('subscribed',krugSubscribed);
}
async function loadSubscription(){
  if(location.protocol==='file:')return;
  let r=await krugApi('/api/subscriptions');
  if(r.ok){krugSubscribed=!!(await r.json()).urgent;paintSubscription()}
}
async function subscribe(){
  if(location.protocol==='file:')return toast('Подписка работает внутри Telegram');
  let r=await krugApi('/api/subscriptions',{method:krugSubscribed?'DELETE':'POST',body:krugSubscribed?undefined:'{}'});
  if(!r.ok)return toast('Не удалось изменить подписку');
  krugSubscribed=!krugSubscribed;paintSubscription();await krugLoadProfile();
  toast(krugSubscribed?'Уведомления о срочных авто включены':'Уведомления отключены');
}
async function loadMarketplaceStats(){
  if(location.protocol==='file:')return;
  let r=await krugApi('/api/stats');if(!r.ok)return;let d=await r.json();
  let eyebrow=document.querySelector('#catalog .eyebrow');if(eyebrow)eyebrow.innerHTML=`<span class="dot"></span> ${d.active} объявлений`;
  let urgentCount=document.querySelector('#urgent .count b');if(urgentCount)urgentCount.textContent=d.urgent;
}
async function krugLoadProfile(){
  let u=krugTgUser||{first_name:'Пользователь',username:''};
  await krugApi('/api/session',{method:'POST',body:JSON.stringify({first_name:u.first_name,username:u.username||''})});
  let r=await krugApi('/api/me');if(!r.ok)return;let d=await r.json(),p=document.querySelector('.profile-card');if(!p)return;
  p.querySelector('.avatar').textContent=(u.first_name||'К')[0]+(u.last_name||'').slice(0,1);p.querySelector('h2').textContent=[u.first_name,u.last_name].filter(Boolean).join(' ');
  let n=p.querySelectorAll('.stat b');n[0].textContent=d.listings;n[1].textContent=d.favourites;n[2].textContent=d.subscriptions;
  if(profileButtons[1])profileButtons[1].innerHTML=`Предложения обмена <span>${d.offers} ›</span>`;
}
function showFavourites(){go('catalog');document.querySelector('#catalog .page-head h1').textContent='Избранное';render(cars.filter(c=>c.favourite),'catalogCards')}
if(profileButtons[2])profileButtons[2].onclick=showFavourites;
if(profileButtons[3])profileButtons[3].onclick=()=>go('urgent');
loadSubscription();loadMarketplaceStats();krugLoadProfile();

/* KRUG source block 5 */
// KRUG v6: complete listing details and real seller contact action.
let krugOpenedDetail=null;
async function openCarV3(id,n,p,pos,picture){
  krugOpenedCar=id;openCar(n,p,pos);detailImg.src=picture;
  let sheet=document.querySelector('.sheet');if(!sheet.querySelector('.exchange-action')){let x=document.createElement('button');x.className='btn back exchange-action';x.textContent='↔ Предложить обмен';x.onclick=offerExchange;sheet.insertBefore(x,sheet.lastElementChild)}
  if(!id||location.protocol==='file:')return;
  let r=await krugApi(`/api/cars/${id}`);if(!r.ok)return toast('Не удалось открыть объявление');
  let d=krugOpenedDetail=await r.json();detailName.textContent=d.name;detailPrice.textContent=rub(d.price);detailYear.textContent=d.year;detailKm.textContent=d.km;detailType.textContent=d.type;detailDescription.textContent=d.description||'Описание не указано';
  detailSeller.textContent=d.is_owner?'Это ваше объявление':`${d.seller_name||'Продавец'} · Екатеринбург`;
  sellerContact.textContent=d.is_owner?'Управлять объявлением':(d.seller_username?'Написать в Telegram':d.phone?'Позвонить продавцу':'Запросить контакт');
}
function contactSeller(){
  let d=krugOpenedDetail;if(!d)return toast('Контакт загружается');
  if(d.is_owner){closeModal();return showMyCars()}
  if(d.seller_username){let url=`https://t.me/${d.seller_username.replace(/^@/,'')}`;if(window.Telegram?.WebApp?.openTelegramLink)Telegram.WebApp.openTelegramLink(url);else location.href=url;return}
  if(d.phone){location.href=`tel:${d.phone.replace(/[^+\d]/g,'')}`;return}
  toast('Продавец пока не указал контакт');
}

/* KRUG source block 6 */
// KRUG v7: exchange inbox with accept/reject actions and outgoing statuses.
const exchangeStatus={new:'Новое',accepted:'Принято',rejected:'Отклонено'};
async function showExchanges(){
  let r=await krugApi('/api/exchanges');if(!r.ok)return toast('Не удалось загрузить обмены');let list=await r.json();
  go('catalog');document.querySelector('#catalog .page-head h1').textContent='Предложения обмена';
  document.getElementById('catalogCards').innerHTML=list.map(x=>{
    let incoming=String(x.target_owner_id)===krugUserId, actions=incoming&&x.status==='new'?`<div class="manage-actions"><button class="btn lime" onclick="answerExchange(${x.id},'accept')">Принять</button><button class="btn back" onclick="answerExchange(${x.id},'reject')">Отклонить</button></div>`:'';
    return `<div class="panel"><div class="eyebrow"><span class="dot"></span>${incoming?'Входящее':'Исходящее'} · ${exchangeStatus[x.status]||x.status}</div><h3>${safeText(x.offered_name||'Автомобиль')} ↔ ${safeText(x.target_name)}</h3><p class="meta">${safeText(x.sender_name||'Пользователь')}</p>${x.message?`<p>${safeText(x.message)}</p>`:''}${actions}</div>`
  }).join('')||'<div class="panel"><h3>Предложений пока нет</h3><p class="meta">Они появятся здесь после отправки или получения обмена.</p></div>';
}
async function answerExchange(id,action){let r=await krugApi(`/api/exchanges/${id}`,{method:'PUT',body:JSON.stringify({action})}),d=await r.json();if(!r.ok)return toast(d.error||'Не удалось обновить предложение');toast(action==='accept'?'Обмен принят':'Предложение отклонено');await showExchanges();await krugLoadProfile()}
async function offerExchange(){
  let r=await krugApi('/api/my-cars'),mine=(await r.json()).filter(x=>x.status==='active');if(!mine.length){closeModal();go('create');return toast('Сначала разместите свой автомобиль')}
  let message=prompt(`Предложить ${mine[0].name} в обмен. Добавьте сообщение:`,`Готов обсудить обмен`);if(message===null)return;
  let res=await krugApi('/api/exchanges',{method:'POST',body:JSON.stringify({target_car_id:krugOpenedCar,offered_car_id:mine[0].id,message})}),d=await res.json();toast(res.ok?'Предложение обмена отправлено':d.error||'Не удалось отправить');if(res.ok)closeModal();
}
if(profileButtons[1])profileButtons[1].onclick=showExchanges;

/* KRUG source block 7 */
// KRUG v8: correct price ranges, live search and catalogue sorting.
function applyCatalog(){
  let q=(catalogSearch?.value||'').trim().toLowerCase(),list=cars.filter(c=>String(c.name).toLowerCase().includes(q));
  if(catalogRange!=='all'){
    if(catalogRange==='300+')list=list.filter(c=>c.price>=300000);
    else{let [a,z]=catalogRange.split('-').map(x=>+x*1000);list=list.filter(c=>c.price>=a&&c.price<=z)}
  }
  let sort=catalogSort?.value||'new';list=[...list].sort((a,b)=>sort==='cheap'?a.price-b.price:sort==='expensive'?b.price-a.price:sort==='year'?b.year-a.year:(b.id||0)-(a.id||0));
  render(list,'catalogCards');
}
document.querySelectorAll('#prices .chip').forEach(b=>b.onclick=()=>{document.querySelectorAll('#prices .chip').forEach(x=>x.classList.remove('active'));b.classList.add('active');catalogRange=b.dataset.range;applyCatalog()});
catalogSearch?.addEventListener('input',applyCatalog);catalogSort?.addEventListener('change',applyCatalog);
document.querySelector('#home .icon-btn').onclick=()=>{go('catalog');setTimeout(()=>catalogSearch.focus(),50)};
function renderAll(){render(cars.slice(0,3),'homeCards');applyCatalog();render(cars.filter(c=>c.urgent),'urgentCards')}

/* KRUG source block 8 */
// KRUG v9: dealer accounts and verified company labels.
function card(c){let safe=String(c.name).replaceAll("'","&#39;"),picture=c.image||hero,dealer=c.seller_role==='dealer';return `<article class="car" onclick="openCarV3(${c.id||0},'${safe}',${c.price},'${c.pos||'50% 50%'}','${picture}')"><div class="car-media"><img src="${picture}" style="object-position:${c.pos||'50% 50%'}" alt="${c.name}"><span class="badge ${c.urgent?'urgent':''}">${c.urgent?'⚡ Срочно':c.type}</span><button class="heart ${c.favourite?'saved':''}" onclick="saveV2(event,this,${c.id||0})">${c.favourite?'♥':'♡'}</button></div><div class="car-body"><div class="car-top"><div><h3>${c.name}</h3><div class="meta">${c.year} · ${c.km}</div></div><div class="price">${rub(c.price)}</div></div><div class="tags"><span class="tag">Екатеринбург</span>${dealer?`<span class="tag">✓ Дилер · ${safeText(c.seller_company||'Компания')}</span>`:`<span class="tag">Частник</span>`}${c.type==='Обмен'?'<span class="tag">↔ Рассмотрю обмен</span>':''}</div></div></article>`}
async function showDealerSettings(){
  let r=await krugApi('/api/me'),d=await r.json(),u=d.user||{};go('catalog');document.querySelector('#catalog .page-head h1').textContent='Профиль продавца';
  document.getElementById('catalogCards').innerHTML=`<div class="panel"><div class="eyebrow"><span class="dot"></span>для бизнеса</div><h3>Дилерский профиль</h3><p class="meta">Добавляет отметку дилера и название компании ко всем вашим объявлениям.</p><div class="field"><label>Название компании</label><input id="dealerCompany" maxlength="100" placeholder="Например, Урал Авто" value="${safeText(u.company||'')}"></div><button class="btn lime" onclick="saveDealer('dealer')">${u.role==='dealer'?'Сохранить изменения':'Стать дилером'}</button>${u.role==='dealer'?'<button class="btn back" onclick="saveDealer(\'private\')">Перейти в профиль частника</button>':''}</div>`;
}
async function saveDealer(role){let company=document.getElementById('dealerCompany')?.value.trim()||'';let r=await krugApi('/api/profile',{method:'PUT',body:JSON.stringify({role,company})}),d=await r.json();if(!r.ok)return toast(d.error||'Не удалось сохранить профиль');toast(role==='dealer'?'Профиль дилера сохранён':'Включён профиль частника');await krugLoadCars();await krugLoadProfile();go('profile')}
async function krugLoadProfile(){let u=krugTgUser||{first_name:'Пользователь',username:''};await krugApi('/api/session',{method:'POST',body:JSON.stringify({first_name:u.first_name,username:u.username||''})});let r=await krugApi('/api/me');if(!r.ok)return;let d=await r.json(),p=document.querySelector('.profile-card');if(!p)return;p.querySelector('.avatar').textContent=(u.first_name||'К')[0]+(u.last_name||'').slice(0,1);p.querySelector('h2').textContent=[u.first_name,u.last_name].filter(Boolean).join(' ');p.querySelector('p').textContent=d.user?.role==='dealer'?`Дилер · ${d.user.company||'Компания'} · Екатеринбург`:'Частный продавец · Екатеринбург';let n=p.querySelectorAll('.stat b');n[0].textContent=d.listings;n[1].textContent=d.favourites;n[2].textContent=d.subscriptions;if(profileButtons[1])profileButtons[1].innerHTML=`Предложения обмена <span>${d.offers} ›</span>`}
if(profileButtons[4])profileButtons[4].onclick=showDealerSettings;
queueMicrotask(()=>renderAll());krugLoadProfile();

/* KRUG source block 9 */
// KRUG v10: up to eight compressed photos and a listing gallery.
let krugImagesData=[];carImage.multiple=true;
const photoPreviews=document.createElement('div');photoPreviews.className='photo-previews';carImage.before(photoPreviews);
const detailThumbs=document.createElement('div');detailThumbs.className='detail-thumbs';document.querySelector('.detail-photo').after(detailThumbs);
const compressCarPhoto=file=>new Promise((resolve,reject)=>{let img=new Image(),url=URL.createObjectURL(file);img.onload=()=>{let max=900,scale=Math.min(1,max/Math.max(img.width,img.height)),canvas=document.createElement('canvas');canvas.width=Math.round(img.width*scale);canvas.height=Math.round(img.height*scale);canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);let data=canvas.toDataURL('image/jpeg',.64);URL.revokeObjectURL(url);resolve(data)};img.onerror=()=>{URL.revokeObjectURL(url);reject(new Error('image'))};img.src=url});
function krugRenderPhotoPreviews(){let bytes=krugImagesData.reduce((sum,src)=>sum+Math.ceil(String(src).length*.75),0),size=bytes>=1_000_000?`${(bytes/1_000_000).toFixed(1)} МБ`:`${Math.max(1,Math.round(bytes/1000))} КБ`;photoPreviews.innerHTML=krugImagesData.map((src,i)=>`<div class="photo-preview-item" data-photo-index="${i}"><img src="${safeImageSrc(src)}" alt="Фото ${i+1}" title="Сделать обложкой"><button type="button" data-remove-photo="${i}" aria-label="Удалить фото ${i+1}">×</button>${i===0?'<small>Обложка</small>':''}</div>`).join('')+(krugImagesData.length?`<div class="photo-previews-size">${krugImagesData.length}/8<br>${size}<small>Нажмите фото — сделать обложкой</small></div>`:'')}
carImage.addEventListener('change',async()=>{let available=Math.max(0,8-krugImagesData.length),files=[...carImage.files].slice(0,available);if(!available){carImage.value='';return toast('Уже добавлено 8 фотографий')}if(files.some(f=>f.size>10_000_000))return toast('Каждое фото должно быть меньше 10 МБ');toast('Подготавливаем фотографии…');try{let prepared=await Promise.all(files.map(compressCarPhoto));krugImagesData.push(...prepared);krugImageData=krugImagesData[0]||'';krugThumbnailData=await krugThumbnailFromData(krugImageData);carPreview.hidden=true;carImage.value='';krugRenderPhotoPreviews();toast(`Добавлено фото: ${krugImagesData.length} из 8`)}catch(e){toast('Не удалось обработать фотографию')}});
async function publish(){let active=document.querySelector('.type-card.active').textContent,data={name:carName.value.trim(),year:+carYear.value,price:+carPrice.value,km:+carKm.value||0,description:carDescription.value.trim(),phone:carPhone.value.trim(),type:active.includes('Обмен')?'Обмен':'Продажа',urgent:active.toLowerCase().includes('срочно'),images:krugImagesData};if(location.protocol==='file:')return toast('Публикация работает внутри Telegram');let r=await krugApi('/api/cars',{method:'POST',body:JSON.stringify(data)}),d=await r.json();if(!r.ok)return toast(d.error||'Проверьте данные');toast('Объявление опубликовано');document.querySelectorAll('#create input,#create textarea').forEach(x=>x.value='');krugImageData='';krugImagesData=[];photoPreviews.innerHTML='';carPreview.hidden=true;await krugLoadCars();setTimeout(()=>go('catalog'),700)}
async function openCarV3(id,n,p,pos,picture){krugOpenedCar=id;openCar(n,p,pos);detailImg.src=safeImageSrc(picture);detailThumbs.innerHTML='';let sheet=document.querySelector('.sheet');if(!sheet.querySelector('.exchange-action')){let x=document.createElement('button');x.className='btn back exchange-action';x.textContent='↔ Предложить обмен';x.onclick=offerExchange;sheet.insertBefore(x,sheet.lastElementChild)}if(!id||location.protocol==='file:')return;let r=await krugApi(`/api/cars/${id}`);if(!r.ok)return toast('Не удалось открыть объявление');let d=krugOpenedDetail=await r.json(),pics=(d.images?.length?d.images:[d.image||hero]).map(safeImageSrc);detailImg.src=pics[0];detailThumbs.innerHTML=pics.map((src,i)=>`<img class="${i?'':'active'}" src="${src}" alt="Фото ${i+1}" onclick="selectCarPhoto(this)">`).join('');detailName.textContent=d.name;detailPrice.textContent=rub(d.price);detailYear.textContent=d.year;detailKm.textContent=d.km;detailType.textContent=d.type;detailDescription.textContent=d.description||'Описание не указано';detailSeller.textContent=d.is_owner?'Это ваше объявление':`${d.seller_company||d.seller_name||'Продавец'} · Екатеринбург`;sellerContact.textContent=d.is_owner?'Управлять объявлением':(d.seller_username?'Написать в Telegram':d.phone?'Позвонить продавцу':'Запросить контакт')}
function selectCarPhoto(img){detailImg.src=img.src;detailThumbs.querySelectorAll('img').forEach(x=>x.classList.toggle('active',x===img))}

/* KRUG source block 10 */
// KRUG v11: edit existing listings without losing their identity or photos.
let krugEditingId=0;
async function showMyCars(){let r=await krugApi('/api/my-cars'),list=await r.json();go('catalog');document.querySelector('#catalog .page-head h1').textContent='Мои объявления';document.getElementById('catalogCards').innerHTML=list.map(c=>`${card(c)}<div class="manage-actions"><button class="btn lime" onclick="editCar(${c.id})">Изменить</button><button class="btn back" onclick="manageCar(${c.id},'${c.status==='active'?'archive':'activate'}')">${c.status==='active'?'Снять':'Опубликовать'}</button><button class="btn" style="background:#ffe3dc" onclick="deleteCar(${c.id})">Удалить</button></div>`).join('')||'<div class="panel"><h3>Объявлений пока нет</h3></div>'}
async function editCar(id){let r=await krugApi(`/api/cars/${id}`);if(!r.ok)return toast('Не удалось открыть объявление');let d=await r.json();krugEditingId=id;carName.value=d.name;carYear.value=d.year;carPrice.value=d.price;carKm.value=String(d.km).replace(/\D/g,'');carDescription.value=d.description||'';carPhone.value=d.phone||'';krugImagesData=(d.images||[]).map(safeImageSrc);krugImageData=krugImagesData[0]||'';photoPreviews.innerHTML=krugImagesData.map((src,i)=>`<img src="${src}" alt="Фото ${i+1}">`).join('');document.querySelectorAll('.type-card').forEach(x=>x.classList.toggle('active',d.urgent?x.textContent.toLowerCase().includes('срочно'):d.type==='Обмен'?x.textContent.includes('Обмен'):x.textContent==='Продать'));document.querySelector('#create .page-head h1').textContent='Изменить объявление';document.querySelector('#create .step[data-step="3"] .btn.lime').textContent='Сохранить изменения';go('create');nextStep(1)}
async function publish(){let active=document.querySelector('.type-card.active').textContent,data={action:krugEditingId?'edit':undefined,name:carName.value.trim(),year:+carYear.value,price:+carPrice.value,km:+carKm.value||0,description:carDescription.value.trim(),phone:carPhone.value.trim(),type:active.includes('Обмен')?'Обмен':'Продажа',urgent:active.toLowerCase().includes('срочно'),images:krugImagesData};if(location.protocol==='file:')return toast('Публикация работает внутри Telegram');let editing=krugEditingId,r=await krugApi(editing?`/api/cars/${editing}`:'/api/cars',{method:editing?'PUT':'POST',body:JSON.stringify(data)}),d=await r.json();if(!r.ok)return toast(d.error||'Проверьте данные');toast(editing?'Изменения сохранены':'Объявление опубликовано');document.querySelectorAll('#create input,#create textarea').forEach(x=>x.value='');krugImageData='';krugImagesData=[];krugEditingId=0;photoPreviews.innerHTML='';carPreview.hidden=true;document.querySelector('#create .page-head h1').textContent='Разместить авто';document.querySelector('#create .step[data-step="3"] .btn.lime').textContent='Опубликовать бесплатно';await krugLoadCars();setTimeout(()=>editing?showMyCars():go('catalog'),500)}
if(profileButtons[0])profileButtons[0].onclick=showMyCars;

/* KRUG source block 11 */
// KRUG v12: user reports and automatic safety review.
const reportButton=document.createElement('button');reportButton.className='btn back report-action';reportButton.textContent='⚑ Пожаловаться';reportButton.onclick=reportCar;document.querySelector('.sheet').insertBefore(reportButton,document.querySelector('.sheet .exchange-action')||document.querySelector('.sheet .btn.back'));
async function reportCar(){if(!krugOpenedDetail||krugOpenedDetail.is_owner)return toast('Это ваше объявление');let choice=prompt('Причина жалобы:\n1 — подозрение на мошенничество\n2 — неверные данные\n3 — автомобиль продан\n4 — дубликат\n5 — другое','1');if(choice===null)return;let reasons={1:'fraud',2:'wrong_info',3:'sold',4:'duplicate',5:'other'},reason=reasons[choice];if(!reason)return toast('Введите число от 1 до 5');let details=prompt('Коротко опишите проблему (необязательно)','')||'';let r=await krugApi(`/api/cars/${krugOpenedCar}/report`,{method:'POST',body:JSON.stringify({reason,details})}),d=await r.json();if(!r.ok)return toast(d.error||'Не удалось отправить жалобу');reportButton.disabled=true;reportButton.textContent='✓ Жалоба отправлена';toast(d.under_review?'Объявление отправлено на проверку':'Спасибо, мы проверим объявление')}
const openCarSafe=openCarV3;openCarV3=async function(...args){await openCarSafe(...args);reportButton.hidden=!!krugOpenedDetail?.is_owner;reportButton.disabled=false;reportButton.textContent='⚑ Пожаловаться'};
async function showMyCars(){let r=await krugApi('/api/my-cars'),list=await r.json();go('catalog');document.querySelector('#catalog .page-head h1').textContent='Мои объявления';document.getElementById('catalogCards').innerHTML=list.map(c=>`${card(c)}${c.status==='review'?'<div class="panel" style="margin-top:8px;background:#fff4d8"><b>На проверке</b><div class="meta">Объявление временно скрыто после жалоб. Мы проверим его.</div></div>':''}<div class="manage-actions"><button class="btn lime" onclick="editCar(${c.id})">Изменить</button>${c.status==='review'?'':`<button class="btn back" onclick="manageCar(${c.id},'${c.status==='active'?'archive':'activate'}')">${c.status==='active'?'Снять':'Опубликовать'}</button>`}<button class="btn" style="background:#ffe3dc" onclick="deleteCar(${c.id})">Удалить</button></div>`).join('')||'<div class="panel"><h3>Объявлений пока нет</h3></div>'}
if(profileButtons[0])profileButtons[0].onclick=showMyCars;

/* KRUG source block 12 */
// KRUG v13: safe listing rendering; user text is never interpreted as HTML.
function openCarById(id){let c=cars.find(x=>Number(x.id)===Number(id));if(c)openCarV3(c.id,c.name,c.price,c.pos||'50% 50%',safeImageSrc(c.image||hero))}
function card(c){let name=safeText(c.name),picture=c.image||hero,dealer=c.seller_role==='dealer';return `<article class="car" onclick="openCarById(${Number(c.id)||0})"><div class="car-media"><img src="${picture}" style="object-position:${safeText(c.pos||'50% 50%')}" alt="${name}"><span class="badge ${c.urgent?'urgent':''}">${c.urgent?'⚡ Срочно':safeText(c.type)}</span><button class="heart ${c.favourite?'saved':''}" onclick="saveV2(event,this,${Number(c.id)||0})">${c.favourite?'♥':'♡'}</button></div><div class="car-body"><div class="car-top"><div><h3>${name}</h3><div class="meta">${Number(c.year)||'—'} · ${safeText(c.km)}</div></div><div class="price">${rub(Number(c.price)||0)}</div></div><div class="tags"><span class="tag">Екатеринбург</span>${dealer?`<span class="tag">✓ Дилер · ${safeText(c.seller_company||'Компания')}</span>`:'<span class="tag">Частник</span>'}${c.type==='Обмен'?'<span class="tag">↔ Рассмотрю обмен</span>':''}</div></div></article>`}
queueMicrotask(()=>renderAll());

/* KRUG source block 13 */
// KRUG v14: favourites are loaded from the database, not stale page memory.
async function saveV2(e,b,id){e.stopPropagation();if(!id)return;let r=await krugApi(`/api/cars/${id}/favourite`,{method:'POST',body:'{}'}),d=await r.json();if(!r.ok)return toast(d.error||'Ошибка');let c=cars.find(x=>Number(x.id)===Number(id));if(c)c.favourite=!!d.favourite;b.classList.toggle('saved',d.favourite);b.textContent=d.favourite?'♥':'♡';toast(d.favourite?'Добавлено в избранное':'Удалено из избранного');await krugLoadProfile()}
async function showFavourites(){let r=await krugApi('/api/favourites');if(!r.ok)return toast('Не удалось загрузить избранное');let list=await r.json();go('catalog');document.querySelector('#catalog .page-head h1').textContent='Избранное';document.getElementById('catalogCards').innerHTML=list.map(card).join('')||'<div class="panel"><h3>В избранном пока пусто</h3><p class="meta">Нажмите на сердечко у автомобиля, чтобы сохранить его здесь.</p></div>'}
if(profileButtons[2])profileButtons[2].onclick=showFavourites;

/* KRUG source block 14 */
// KRUG v16: consistent errors, guarded actions and Telegram launch diagnostics.
const krugConnectionNote=document.createElement('div');krugConnectionNote.className='connection-note';krugConnectionNote.hidden=true;document.body.append(krugConnectionNote);
function krugShowConnection(message){krugConnectionNote.textContent=message;krugConnectionNote.hidden=false;setTimeout(()=>krugConnectionNote.hidden=true,5000)}
async function krugJson(url,options={}){
  try{
    let response=await krugApi(url,options),data={};
    try{data=await response.json()}catch(_){data={}}
    if(!response.ok){let message=data.error||(response.status===401?'Откройте КРУГ кнопкой внутри Telegram':'Сервер временно недоступен');let error=new Error(message);error.status=response.status;error.code=data.code||'';throw error}
    return data;
  }catch(error){
    if(error?.name==='AbortError'){let timeoutError=new Error('Сервер долго не отвечает. Проверьте интернет и попробуйте снова.');timeoutError.code='network_timeout';error=timeoutError}
    if(error.status===401)krugShowConnection(error.message);
    throw error;
  }
}
if(location.protocol!=='file:'&&!krugInitData)krugShowConnection('Просмотр доступен. Для избранного и публикации откройте КРУГ внутри Telegram.');
window.addEventListener('offline',()=>krugShowConnection('Нет подключения к интернету. Данные сохранятся после восстановления связи.'));
window.addEventListener('online',()=>{toast('Соединение восстановлено');krugLoadCars()});
async function saveV2(e,b,id){
  e.stopPropagation();if(!id||b.classList.contains('busy'))return;b.classList.add('busy');
  try{let d=await krugJson(`/api/cars/${id}/favourite`,{method:'POST',body:'{}'}),c=cars.find(x=>Number(x.id)===Number(id));if(c)c.favourite=!!d.favourite;b.classList.toggle('saved',d.favourite);b.textContent=d.favourite?'♥':'♡';toast(d.favourite?'Добавлено в избранное':'Удалено из избранного');await krugLoadProfile()}
  catch(error){toast(error.message)}finally{b.classList.remove('busy')}
}
async function showFavourites(){try{let list=await krugJson('/api/favourites');go('catalog');document.querySelector('#catalog .page-head h1').textContent='Избранное';document.getElementById('catalogCards').innerHTML=list.map(card).join('')||'<div class="panel"><h3>В избранном пока пусто</h3><p class="meta">Нажмите на сердечко у автомобиля, чтобы сохранить его здесь.</p></div>'}catch(error){toast(error.message)}}
async function subscribe(b){
  let button=b?.tagName?b:document.querySelector('#urgent [onclick="subscribe(this)"]');if(button?.classList.contains('busy'))return;button?.classList.add('busy');
  try{await krugJson('/api/subscriptions',{method:krugSubscribed?'DELETE':'POST',body:krugSubscribed?undefined:'{}'});krugSubscribed=!krugSubscribed;paintSubscription();await krugLoadProfile();toast(krugSubscribed?'Уведомления о срочных авто включены':'Уведомления отключены')}
  catch(error){toast(error.message)}finally{button?.classList.remove('busy')}
}
if(profileButtons[2])profileButtons[2].onclick=showFavourites;

/* KRUG source block 15 */
// KRUG v17: reliable listing creation, editing and owner controls.
function krugListingData(){
  let active=document.querySelector('.type-card.active')?.textContent||'',year=Number(carYear.value),price=Number(carPrice.value),km=Number(carKm.value||0),phone=carPhone.value.trim();
  if(carName.value.trim().length<2)throw new Error('Укажите марку и модель автомобиля');
  if(!Number.isInteger(year)||year<1950||year>new Date().getFullYear()+1)throw new Error('Проверьте год выпуска');
  if(!Number.isFinite(price)||price<1000)throw new Error('Укажите корректную цену');
  if(!Number.isFinite(km)||km<0)throw new Error('Проверьте пробег');
  if(phone&&phone.replace(/\D/g,'').length<10)throw new Error('Проверьте номер телефона');
  return {action:krugEditingId?'edit':undefined,name:carName.value.trim(),year,price,km,description:carDescription.value.trim(),phone,type:active.includes('Обмен')?'Обмен':'Продажа',urgent:active.toLowerCase().includes('срочно'),images:krugImagesData};
}
function krugResetListingForm(){document.querySelectorAll('#create input:not([type=file]),#create textarea').forEach(x=>x.value='');carImage.value='';krugImageData='';krugImagesData=[];krugEditingId=0;photoPreviews.innerHTML='';carPreview.hidden=true;document.querySelector('#create .page-head h1').textContent='Разместить авто';document.querySelector('#create .step[data-step="3"] .btn.lime').textContent='Опубликовать бесплатно';nextStep(1)}
async function publish(){
  let button=document.querySelector('#create .step[data-step="3"] .btn.lime');if(button.classList.contains('busy'))return;let data;
  try{data=krugListingData()}catch(error){toast(error.message);return}
  if(location.protocol==='file:')return toast('Публикация работает внутри Telegram');let editing=krugEditingId,original=button.textContent;button.classList.add('busy');button.textContent=editing?'Сохраняем…':'Публикуем…';
  try{await krugJson(editing?`/api/cars/${editing}`:'/api/cars',{method:editing?'PUT':'POST',body:JSON.stringify(data)});toast(editing?'Изменения сохранены':'Объявление опубликовано');krugResetListingForm();await krugLoadCars();setTimeout(()=>editing?showMyCars():go('catalog'),450)}
  catch(error){toast(error.message)}finally{button.classList.remove('busy');if(krugEditingId)button.textContent=original}
}
async function showMyCars(){
  try{let list=await krugJson('/api/my-cars');go('catalog');document.querySelector('#catalog .page-head h1').textContent='Мои объявления';document.getElementById('catalogCards').innerHTML=list.map(c=>`${card(c)}${c.status==='review'?'<div class="panel" style="margin-top:8px;background:#fff4d8"><b>На проверке</b><div class="meta">Объявление временно скрыто после жалоб.</div></div>':''}<div class="manage-actions"><button class="btn lime" onclick="editCar(${c.id})">Изменить</button>${c.status==='review'?'':`<button class="btn back" onclick="manageCar(${c.id},'${c.status==='active'?'archive':'activate'}')">${c.status==='active'?'Снять':'Опубликовать'}</button>`}<button class="btn" style="background:#ffe3dc" onclick="deleteCar(${c.id})">Удалить</button></div>`).join('')||'<div class="panel"><h3>Объявлений пока нет</h3></div>'}catch(error){toast(error.message)}}
async function manageCar(id,action){try{await krugJson(`/api/cars/${id}`,{method:'PUT',body:JSON.stringify({action})});toast(action==='archive'?'Объявление снято':'Объявление опубликовано');await showMyCars();await krugLoadCars()}catch(error){toast(error.message)}}
async function deleteCar(id){if(!confirm('Удалить объявление без возможности восстановления?'))return;try{await krugJson(`/api/cars/${id}`,{method:'DELETE'});toast('Объявление удалено');await showMyCars();await krugLoadCars()}catch(error){toast(error.message)}}
async function editCar(id){try{let d=await krugJson(`/api/cars/${id}`);krugEditingId=id;carName.value=d.name;carYear.value=d.year;carPrice.value=d.price;carKm.value=String(d.km).replace(/\D/g,'');carDescription.value=d.description||'';carPhone.value=d.phone||'';krugImagesData=d.images||[];krugImageData=krugImagesData[0]||'';photoPreviews.innerHTML=krugImagesData.map((src,i)=>`<img src="${src}" alt="Фото ${i+1}">`).join('');document.querySelectorAll('.type-card').forEach(x=>x.classList.toggle('active',d.urgent?x.textContent.toLowerCase().includes('срочно'):d.type==='Обмен'?x.textContent.includes('Обмен'):x.textContent==='Продать'));document.querySelector('#create .page-head h1').textContent='Изменить объявление';document.querySelector('#create .step[data-step="3"] .btn.lime').textContent='Сохранить изменения';go('create');nextStep(1)}catch(error){toast(error.message)}}
if(profileButtons[0])profileButtons[0].onclick=showMyCars;

/* KRUG source block 16 */
// KRUG v18: marketplace rules, privacy notice and explicit seller consent.
const krugLegal={
  rules:`<p>КРУГ — информационная площадка объявлений. Мы не являемся продавцом, дилером, платёжным сервисом, представителем стороны или гарантом сделки.</p><h3>Кто может пользоваться</h3><p>Размещая объявление, пользователь подтверждает совершеннолетие и дееспособность, право продать автомобиль либо полномочия действовать от имени владельца.</p><h3>Правила размещения</h3><p>Указывайте достоверные характеристики, цену, фотографии и контакты. Запрещены чужие фотографии, персональные данные третьих лиц без основания, дубликаты, скрытые платежи, мошенничество и объявления о несуществующих автомобилях. Перед фото закройте лица посторонних, документы и лишние номера; публикуйте только материалы, на которые у вас есть права.</p><h3>Безопасная сделка</h3><p>Проверяйте документы, VIN, ограничения и автомобиль до оплаты. Не переводите предоплату незнакомым людям. Встречайтесь в безопасном месте и оформляйте сделку официально.</p><h3>Модерация</h3><p>Объявление может быть скрыто или заблокировано после жалоб либо при нарушении правил. Пользователь отвечает за опубликованные сведения и законность автомобиля; спор по самой сделке разрешается между её сторонами.</p>`,
  privacy:`<p><b>Оператор:</b> <span id="legalOperatorName">будет указан владельцем сервиса до сбора данных</span>.<br><b>Адрес:</b> <span id="legalOperatorAddress">будет указан до запуска</span>.<br><b>Контакт для вопросов и отзыва согласия:</b> <span id="legalOperatorEmail">будет указан до запуска</span>.</p><h3>Какие данные обрабатываются</h3><p>Telegram ID, имя и username; объявления, характеристики и фотографии автомобиля; добровольно введённый телефон; избранное, просмотры, подписки, обмены и жалобы; IP-адрес, User-Agent, время и технический результат запроса в журнале безопасности.</p><h3>Цели и действия</h3><p>Регистрация и работа маркетплейса, публикация объявлений, связь участников, предотвращение злоупотреблений, поддержка и модерация. Данные записываются, систематизируются, хранятся, уточняются, используются, предоставляются в указанном объёме и удаляются.</p><h3>Срок и получатели</h3><p>Данные аккаунта хранятся до его удаления или отзыва согласия; удалённые объявления очищаются через 30 дней, просмотры — через 180 дней, внутренний аудит — через 365 дней, если закон не требует иного. Доступ получают оператор, уполномоченные администраторы и российские поставщики инфраструктуры по договору обработки.</p><h3>Публикация контакта</h3><p>Телефон или Telegram username показываются только после отдельного согласия продавца. Контакты отсутствуют в общей выдаче и доступны только авторизованному пользователю в карточке объявления. Согласие отзывается архивацией/удалением объявления или обращением оператору.</p><h3>Хранение и права</h3><p>Первичный сбор и хранение данных граждан РФ выполняются в базе на территории России; трансграничная передача не выполняется без отдельного законного основания и обязательных уведомлений. Пользователь может запросить сведения, исправление, выгрузку, блокирование или удаление данных, отозвать согласие и удалить аккаунт в профиле.</p>`
};
function openLegal(kind){legalTitle.textContent=kind==='privacy'?'Политика конфиденциальности':'Правила КРУГ';legalBody.innerHTML=krugLegal[kind];legalModal.classList.add('open')}
function closeLegal(){legalModal.classList.remove('open')}
const krugPublishPanel=document.querySelector('#create .step[data-step="3"] .panel');
const krugConsent=document.createElement('label');krugConsent.className='legal-consent';krugConsent.innerHTML=`<input id="legalAccepted" type="checkbox"><span>Я подтверждаю достоверность объявления и принимаю <button type="button" class="legal-link" onclick="event.preventDefault();openLegal('rules')">правила КРУГ</button> и <button type="button" class="legal-link" onclick="event.preventDefault();openLegal('privacy')">политику конфиденциальности</button>.</span>`;krugPublishPanel.append(krugConsent);
legalAccepted.checked=localStorage.getItem('krug_legal_accepted')==='1';legalAccepted.addEventListener('change',()=>localStorage.setItem('krug_legal_accepted',legalAccepted.checked?'1':'0'));
const krugListingDataBeforeLegal=krugListingData;krugListingData=function(){if(!legalAccepted.checked)throw new Error('Подтвердите правила и политику конфиденциальности');return krugListingDataBeforeLegal()};

/* KRUG source block 17 */
// KRUG v19: personal data export and protected account deletion.
const krugProfileMenu=document.querySelector('#profile .menu-list');
const krugDeleteButton=document.createElement('button');krugDeleteButton.className='menu-item';krugDeleteButton.style.color='#b42318';krugDeleteButton.innerHTML='Удалить аккаунт <span>›</span>';krugDeleteButton.onclick=deleteMyAccount;krugProfileMenu.append(krugDeleteButton);
async function exportMyData(){
  try{let data=await krugJson('/api/export'),blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`krug-data-${new Date().toISOString().slice(0,10)}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Копия данных подготовлена')}
  catch(error){toast(error.message)}
}
async function deleteMyAccount(){
  let answer=prompt('Будут удалены аккаунт, объявления, избранное, подписки и предложения обмена. Для подтверждения напишите УДАЛИТЬ','');if(answer!=='УДАЛИТЬ')return answer===null?undefined:toast('Удаление отменено');
  try{await krugJson('/api/account',{method:'DELETE'});['krug_user','krug_legal_accepted','krug_privacy_version','krug_rules_version','krug_listing_draft_v1'].forEach(key=>localStorage.removeItem(key));cars=[];renderAll();go('home');toast('Ваш аккаунт и локальный черновик удалены')}
  catch(error){toast(error.message)}
}

/* KRUG source block 18 */
// KRUG v20: essential automotive specifications.
const krugSpecsHost=document.querySelector('#create .step[data-step="2"] .panel');
const krugSpecs=document.createElement('div');krugSpecs.innerHTML=`<div class="field"><label>Коробка передач</label><select id="carTransmission"><option value="">Выберите</option><option>Автомат</option><option>Механика</option><option>Робот</option><option>Вариатор</option></select></div><div class="field"><label>Тип кузова</label><select id="carBodyType"><option value="">Выберите</option><option>Седан</option><option>Хэтчбек</option><option>Универсал</option><option>Кроссовер</option><option>Внедорожник</option><option>Минивэн</option><option>Купе</option><option>Пикап</option></select></div><div class="field"><label>Привод</label><select id="carDrive"><option value="">Выберите</option><option>Передний</option><option>Задний</option><option>Полный</option></select></div><div class="field"><label>VIN <small>(необязательно)</small></label><input id="carVin" maxlength="17" autocomplete="off" placeholder="17 символов" style="text-transform:uppercase"></div>`;krugSpecsHost.append(krugSpecs);
const krugListingDataBeforeSpecs=krugListingData;krugListingData=function(){let data=krugListingDataBeforeSpecs(),vin=carVin.value.trim().toUpperCase().replace(/[^A-HJ-NPR-Z0-9]/g,'');if(vin&&vin.length!==17)throw new Error('VIN должен содержать 17 символов');return {...data,transmission:carTransmission.value,body_type:carBodyType.value,drive:carDrive.value,vin}};
carVin.addEventListener('input',()=>carVin.value=carVin.value.toUpperCase().replace(/[^A-HJ-NPR-Z0-9]/g,'').slice(0,17));
const krugEditBeforeSpecs=editCar;editCar=async function(id){await krugEditBeforeSpecs(id);if(krugEditingId!==id)return;try{let d=await krugJson(`/api/cars/${id}`);carTransmission.value=d.transmission||'';carBodyType.value=d.body_type||'';carDrive.value=d.drive||'';carVin.value=d.vin||''}catch(_){}}
const krugOpenBeforeSpecs=openCarV3;openCarV3=async function(...args){await krugOpenBeforeSpecs(...args);let d=krugOpenedDetail;if(!d)return;let specs=[d.body_type,d.transmission,d.drive,d.vin?`VIN: ${d.vin}`:''].filter(Boolean);if(specs.length)detailDescription.textContent=`${specs.join(' · ')}\n\n${d.description||'Описание не указано'}`};

/* KRUG source block 19 */
// KRUG v21: filters by vehicle specifications.
const krugFilterBox=document.createElement('div');krugFilterBox.className='auto-filters';krugFilterBox.innerHTML=`<select id="filterTransmission" aria-label="Коробка"><option value="">Любая коробка</option><option>Автомат</option><option>Механика</option><option>Робот</option><option>Вариатор</option></select><select id="filterBody" aria-label="Кузов"><option value="">Любой кузов</option><option>Седан</option><option>Хэтчбек</option><option>Универсал</option><option>Кроссовер</option><option>Внедорожник</option><option>Минивэн</option><option>Купе</option><option>Пикап</option></select><select id="filterDrive" aria-label="Привод"><option value="">Любой привод</option><option>Передний</option><option>Задний</option><option>Полный</option></select><button class="filter-reset" type="button">Сбросить фильтры</button>`;
const krugFilterResult=document.createElement('div');krugFilterResult.className='filter-result';document.querySelector('#catalog .search-panel').after(krugFilterBox,krugFilterResult);
const filterTransmission=document.getElementById('filterTransmission'),filterBody=document.getElementById('filterBody'),filterDrive=document.getElementById('filterDrive');
function applyCatalog(){
  let q=(catalogSearch?.value||'').trim().toLowerCase(),list=cars.filter(c=>String(c.name).toLowerCase().includes(q));
  if(catalogRange!=='all'){if(catalogRange==='300+')list=list.filter(c=>c.price>=300000);else{let[a,z]=catalogRange.split('-').map(x=>+x*1000);list=list.filter(c=>c.price>=a&&c.price<=z)}}
  if(filterTransmission.value)list=list.filter(c=>c.transmission===filterTransmission.value);if(filterBody.value)list=list.filter(c=>c.body_type===filterBody.value);if(filterDrive.value)list=list.filter(c=>c.drive===filterDrive.value);
  let sort=catalogSort?.value||'new';list=[...list].sort((a,b)=>sort==='cheap'?a.price-b.price:sort==='expensive'?b.price-a.price:sort==='year'?b.year-a.year:(b.id||0)-(a.id||0));render(list,'catalogCards');krugFilterResult.textContent=`Найдено автомобилей: ${list.length}`;
}
[filterTransmission,filterBody,filterDrive].forEach(x=>x.addEventListener('change',applyCatalog));
krugFilterBox.querySelector('.filter-reset').onclick=()=>{catalogSearch.value='';catalogRange='all';document.querySelectorAll('#prices .chip').forEach(x=>x.classList.toggle('active',x.dataset.range==='all'));filterTransmission.value='';filterBody.value='';filterDrive.value='';catalogSort.value='new';applyCatalog()};
applyCatalog();

/* KRUG source block 20 */
// KRUG v22: automatic listing drafts survive accidental closes and reconnects.
const KRUG_DRAFT_KEY='krug_listing_draft_v1';
const krugDraftNote=document.createElement('div');krugDraftNote.className='draft-note';krugDraftNote.innerHTML='<span><b>Черновик сохранён</b><small>Данные останутся на этом устройстве</small></span><button type="button">Очистить</button>';document.querySelector('#create .page-head').after(krugDraftNote);
function krugDraftSavedLabel(value){let stamp=value?new Date(value):new Date(),time=Number.isNaN(stamp.getTime())?'':stamp.toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}),label=krugDraftNote.querySelector('span');label.innerHTML=`<b>Черновик сохранён${time?' · '+time:''}</b><small>Без телефона, VIN и фотографий — только на этом устройстве</small>`}
function krugDraftSnapshot(){return {name:carName.value,year:carYear.value,price:carPrice.value,km:carKm.value,description:carDescription.value,transmission:carTransmission.value,body_type:carBodyType.value,drive:carDrive.value,type:[...document.querySelectorAll('.type-card')].findIndex(x=>x.classList.contains('active')),step:Number(document.querySelector('#create .step.active')?.dataset.step)||1,saved_at:new Date().toISOString()}}
function saveKrugDraft(){if(krugEditingId)return;let draft=krugDraftSnapshot(),hasData=Object.entries(draft).some(([k,v])=>!['saved_at','type'].includes(k)&&String(v).trim());if(hasData){localStorage.setItem(KRUG_DRAFT_KEY,JSON.stringify(draft));krugDraftSavedLabel(draft.saved_at);krugDraftNote.classList.add('show')}else{localStorage.removeItem(KRUG_DRAFT_KEY);krugDraftNote.classList.remove('show')}}
function restoreKrugDraft(silent=false){try{let d=JSON.parse(localStorage.getItem(KRUG_DRAFT_KEY)||'null');if(!d)return;delete d.phone;delete d.vin;localStorage.setItem(KRUG_DRAFT_KEY,JSON.stringify(d));carName.value=d.name||'';carYear.value=d.year||'';carPrice.value=d.price||'';carKm.value=d.km||'';carDescription.value=d.description||'';carTransmission.value=d.transmission||'';carBodyType.value=d.body_type||'';carDrive.value=d.drive||'';let types=document.querySelectorAll('.type-card');types.forEach((x,i)=>x.classList.toggle('active',i===Number(d.type||0)));let step=Math.max(1,Math.min(3,Number(d.step)||1));document.querySelectorAll('.step').forEach(section=>section.classList.toggle('active',Number(section.dataset.step)===step));document.querySelectorAll('.form-progress i').forEach((item,index)=>item.classList.toggle('on',index<step));stepText.textContent=`Шаг ${step} из 3 · ${['Тип сделки','Автомобиль','Публикация'][step-1]}`;krugDraftSavedLabel(d.saved_at);krugDraftNote.classList.add('show');if(!silent)toast('Черновик восстановлен')}catch(_){localStorage.removeItem(KRUG_DRAFT_KEY)}}
document.querySelectorAll('#create input:not([type=file]),#create textarea,#create select').forEach(x=>{x.addEventListener('input',saveKrugDraft);x.addEventListener('change',saveKrugDraft)});document.querySelectorAll('.type-card').forEach(x=>x.addEventListener('click',()=>setTimeout(saveKrugDraft)));
krugDraftNote.querySelector('button').onclick=()=>{localStorage.removeItem(KRUG_DRAFT_KEY);krugDraftNote.classList.remove('show');document.querySelectorAll('#create input:not([type=file]),#create textarea').forEach(x=>x.value='');[carTransmission,carBodyType,carDrive].forEach(x=>x.value='');toast('Черновик очищен')};
const krugResetBeforeDraft=krugResetListingForm;krugResetListingForm=function(){localStorage.removeItem(KRUG_DRAFT_KEY);krugDraftNote.classList.remove('show');return krugResetBeforeDraft()};
restoreKrugDraft();

/* KRUG source block 21 */
// KRUG v23: daily unique listing views and seller interest counters.
const krugMyCarsBeforeInsights=showMyCars;showMyCars=async function(){
  try{let list=await krugJson('/api/my-cars');go('catalog');document.querySelector('#catalog .page-head h1').textContent='Мои объявления';document.getElementById('catalogCards').innerHTML=list.map(c=>`${card(c)}<div class="listing-insights"><span>👁 Просмотры: ${Number(c.views)||0}</span><span>♥ В избранном: ${Number(c.favourites_count)||0}</span></div>${c.status==='review'?'<div class="panel" style="margin-top:8px;background:#fff4d8"><b>На проверке</b><div class="meta">Объявление временно скрыто после жалоб.</div></div>':''}<div class="manage-actions"><button class="btn lime" onclick="editCar(${c.id})">Изменить</button>${c.status==='review'?'':`<button class="btn back" onclick="manageCar(${c.id},'${c.status==='active'?'archive':'activate'}')">${c.status==='active'?'Снять':'Опубликовать'}</button>`}<button class="btn" style="background:#ffe3dc" onclick="deleteCar(${c.id})">Удалить</button></div>`).join('')||'<div class="panel"><h3>Объявлений пока нет</h3></div>'}catch(error){toast(error.message)}};
if(profileButtons[0])profileButtons[0].onclick=showMyCars;

/* KRUG source block 22 */
// KRUG v24: shareable listing links and direct card opening.
const krugShareButton=document.createElement('button');krugShareButton.className='btn share-action';krugShareButton.textContent='↗ Поделиться объявлением';krugShareButton.onclick=shareOpenedCar;document.querySelector('.sheet').insertBefore(krugShareButton,document.querySelector('.sheet .btn.back'));
function krugListingUrl(id){let url=new URL(location.href);url.search='';url.hash='';url.searchParams.set('car',String(id));return url.toString()}
async function shareOpenedCar(){
  let d=krugOpenedDetail;if(!d?.id)return toast('Сначала откройте объявление');let url=krugListingUrl(d.id),text=`${d.name} — ${rub(d.price)} · Екатеринбург`;
  try{if(navigator.share){await navigator.share({title:d.name,text,url});return}let telegramUrl=`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;if(window.Telegram?.WebApp?.openTelegramLink)Telegram.WebApp.openTelegramLink(telegramUrl);else{await navigator.clipboard.writeText(`${text}\n${url}`);toast('Ссылка скопирована')}}catch(error){if(error.name!=='AbortError')toast('Не удалось поделиться')}
}
async function openLinkedCar(){let id=Number(new URLSearchParams(location.search).get('car'));if(!id)return;try{if(location.protocol!=='file:')await krugLoadCars();let c=cars.find(x=>Number(x.id)===id);if(!c)return toast('Объявление больше недоступно');go('catalog');await openCarV3(c.id,c.name,c.price,c.pos||'50% 50%',c.image||hero)}catch(_){toast('Не удалось открыть объявление')}}
setTimeout(openLinkedCar,700);

/* KRUG source block 23 */
// KRUG v25: sold status keeps seller history while removing stale listings.
async function showMyCars(){
  try{let list=await krugJson('/api/my-cars');go('catalog');document.querySelector('#catalog .page-head h1').textContent='Мои объявления';document.getElementById('catalogCards').innerHTML=list.map(c=>`${card(c)}${c.status==='sold'?'<div class="sold-label">✓ Автомобиль продан</div>':`<div class="listing-insights"><span>👁 Просмотры: ${Number(c.views)||0}</span><span>♥ В избранном: ${Number(c.favourites_count)||0}</span></div>`}${c.status==='review'?'<div class="panel" style="margin-top:8px;background:#fff4d8"><b>На проверке</b><div class="meta">Объявление временно скрыто после жалоб.</div></div>':''}<div class="manage-actions">${c.status==='sold'?`<button class="btn back" onclick="manageCar(${c.id},'activate')">Вернуть в продажу</button>`:`<button class="btn lime" onclick="editCar(${c.id})">Изменить</button>${c.status==='review'?'':`<button class="btn back" onclick="manageCar(${c.id},'${c.status==='active'?'archive':'activate'}')">${c.status==='active'?'Снять':'Опубликовать'}</button><button class="btn sold-button" onclick="markCarSold(${c.id})">Продано</button>`}`}<button class="btn" style="background:#ffe3dc" onclick="deleteCar(${c.id})">Удалить</button></div>`).join('')||'<div class="panel"><h3>Объявлений пока нет</h3></div>'}catch(error){toast(error.message)}}
async function markCarSold(id){if(!confirm('Отметить автомобиль как проданный? Он исчезнет из каталога.'))return;try{await krugJson(`/api/cars/${id}`,{method:'PUT',body:JSON.stringify({action:'sold'})});toast('Поздравляем с продажей!');await showMyCars();await krugLoadCars()}catch(error){toast(error.message)}}
if(profileButtons[0])profileButtons[0].onclick=showMyCars;

/* KRUG source block 24 */
// KRUG v26: lightweight catalogue thumbnails; full photos load only on detail.
let krugThumbnailData='';
const krugListingDataBeforeThumb=krugListingData;krugListingData=function(){return {...krugListingDataBeforeThumb(),thumbnail:krugThumbnailData}};
const krugEditBeforeThumb=editCar;editCar=async function(id){await krugEditBeforeThumb(id);if(krugEditingId!==id)return;try{let d=await krugJson(`/api/cars/${id}`);krugThumbnailData=d.thumbnail||d.image||''}catch(_){}};
const krugResetBeforeThumb=krugResetListingForm;krugResetListingForm=function(){krugThumbnailData='';return krugResetBeforeThumb()};

/* KRUG source block 25 */
// KRUG v27: price history and visible price drops.
const krugOpenBeforePrice=openCarV3;openCarV3=async function(...args){await krugOpenBeforePrice(...args);let d=krugOpenedDetail;if(!d)return;let old=document.querySelector('.sheet .price-history-ui');old?.remove();if(d.previous_price&&d.previous_price>d.price){let box=document.createElement('div');box.className='price-history-ui';let drop=d.previous_price-d.price;box.innerHTML=`<span class="old-price">${rub(d.previous_price)}</span><span class="price-drop">Цена снижена на ${rub(drop)}</span>`;detailPrice.after(box)}};

/* KRUG source block 26 */
// KRUG v28: consistent favourites in catalogue, saved list and car details.
function card(c){let id=Number(c.id)||0,name=safeText(c.name),picture=c.image||hero,dealer=c.seller_role==='dealer',saved=!!c.favourite;return `<article class="car" data-car-id="${id}" onclick="openCarById(${id})"><div class="car-media"><img src="${picture}" style="object-position:${safeText(c.pos||'50% 50%')}" alt="${name}"><span class="badge ${c.urgent?'urgent':''}">${c.urgent?'⚡ Срочно':safeText(c.type)}</span><button class="heart ${saved?'saved':''}" data-favourite-id="${id}" aria-label="${saved?'Удалить из избранного':'Добавить в избранное'}" onclick="saveV2(event,this,${id})">${saved?'♥':'♡'}</button></div><div class="car-body"><div class="car-top"><div><h3>${name}</h3><div class="meta">${Number(c.year)||'—'} · ${safeText(c.km)}</div></div><div class="price">${rub(Number(c.price)||0)}</div></div><div class="tags"><span class="tag">Екатеринбург</span>${dealer?`<span class="tag">✓ Дилер · ${safeText(c.seller_company||'Компания')}</span>`:'<span class="tag">Частник</span>'}${c.accept_exchange||c.type==='Обмен'?'<span class="tag">↔ Рассмотрю обмен</span>':''}</div></div></article>`}
function paintFavourite(id,state){
  let c=cars.find(x=>Number(x.id)===Number(id));if(c)c.favourite=!!state;
  document.querySelectorAll(`[data-favourite-id="${Number(id)}"]`).forEach(b=>{b.classList.toggle('saved',!!state);b.textContent=state?(b.classList.contains('heart')?'♥':'♥ В избранном'):(b.classList.contains('heart')?'♡':'♡ Добавить в избранное');b.setAttribute('aria-label',state?'Удалить из избранного':'Добавить в избранное')});
}
async function toggleKrugFavourite(id,button){
  if(!id||button?.classList.contains('busy'))return;button?.classList.add('busy');
  try{let d=await krugJson(`/api/cars/${id}/favourite`,{method:'POST',body:'{}'});paintFavourite(id,d.favourite);toast(d.favourite?'Добавлено в избранное':'Удалено из избранного');if(!d.favourite&&document.querySelector('#catalog .page-head h1')?.textContent==='Избранное'){document.querySelector(`#catalogCards .car[data-car-id="${Number(id)}"]`)?.remove();if(!document.querySelector('#catalogCards .car'))document.getElementById('catalogCards').innerHTML='<div class="panel"><h3>В избранном пока пусто</h3><p class="meta">Нажмите на сердечко у автомобиля, чтобы сохранить его здесь.</p></div>'}await krugLoadProfile();return d}
  catch(error){toast(error.message)}finally{button?.classList.remove('busy')}
}
async function saveV2(e,b,id){e?.stopPropagation?.();await toggleKrugFavourite(id,b)}
const krugDetailFavourite=document.createElement('button');krugDetailFavourite.className='btn detail-favourite';krugDetailFavourite.onclick=()=>toggleKrugFavourite(krugOpenedDetail?.id,krugDetailFavourite);document.querySelector('.sheet').insertBefore(krugDetailFavourite,krugShareButton);
const krugOpenBeforeFavourite=openCarV3;openCarV3=async function(...args){await krugOpenBeforeFavourite(...args);let d=krugOpenedDetail;if(!d)return;krugDetailFavourite.dataset.favouriteId=String(d.id);paintFavourite(d.id,!!d.favourite)};

/* KRUG source block 27 */
// KRUG v29: every published listing must have a usable seller contact.
const krugContactHint=document.createElement('div');krugContactHint.className='contact-hint';carPhone.closest('.field').append(krugContactHint);
function paintContactHint(){let username=krugTgUser?.username||'',hasPhone=carPhone.value.replace(/\D/g,'').length>=10;if(username){krugContactHint.className='contact-hint ok';krugContactHint.textContent=`Покупатели смогут написать вам в Telegram: @${username}`}else if(hasPhone){krugContactHint.className='contact-hint ok';krugContactHint.textContent='Телефон будет доступен покупателям в карточке автомобиля'}else{krugContactHint.className='contact-hint';krugContactHint.textContent='Укажите телефон — в вашем Telegram нет публичного username'}}
carPhone.addEventListener('input',paintContactHint);paintContactHint();
const krugListingDataBeforeContact=krugListingData;krugListingData=function(){let data=krugListingDataBeforeContact();if(!data.phone&&!krugTgUser?.username)throw new Error('Укажите телефон для связи с покупателем');return data};
const krugOpenBeforeContact=openCarV3;openCarV3=async function(...args){await krugOpenBeforeContact(...args);let d=krugOpenedDetail;if(!d)return;sellerContact.hidden=!d.is_owner&&!d.seller_username&&!d.phone;if(sellerContact.hidden)toast('У продавца пока нет доступного контакта')};

/* KRUG source block 28 */
// KRUG v30: profile counters only include listings that are actually available.

/* KRUG source block 29 */
// KRUG v31: robust year, price and mileage entry with grouped-number support.
const krugNumericFields=[carYear,carPrice,carKm];
const krugOnlyDigits=value=>String(value??'').replace(/\D/g,'');
const krugNumber=value=>Number(krugOnlyDigits(value)||0);
krugNumericFields.forEach(field=>{field.type='text';field.inputMode='numeric';field.autocomplete='off';field.addEventListener('input',()=>{let digits=krugOnlyDigits(field.value);field.value=field===carYear?digits.slice(0,4):digits.slice(0,9)});field.addEventListener('blur',()=>{let n=krugNumber(field.value);if(n)field.value=field===carYear?String(n):new Intl.NumberFormat('ru-RU').format(n)});field.addEventListener('focus',()=>field.value=krugOnlyDigits(field.value))});
carKm.insertAdjacentHTML('afterend','<small class="number-hint">Можно вводить с пробелами: например, 86 000</small>');
carPrice.insertAdjacentHTML('afterend','<small class="number-hint">Можно вводить с пробелами: например, 1 850 000</small>');
krugListingData=function(){
  let active=document.querySelector('.type-card.active')?.textContent||'',name=carName.value.trim(),year=krugNumber(carYear.value),price=krugNumber(carPrice.value),kmText=String(carKm.value).trim(),km=krugNumber(kmText),phone=carPhone.value.trim(),vin=carVin.value.trim().toUpperCase().replace(/[^A-HJ-NPR-Z0-9]/g,'');
  if(name.length<2)throw new Error('Укажите марку и модель автомобиля');
  if(!year||year<1950||year>new Date().getFullYear()+1)throw new Error('Проверьте год выпуска');
  if(!price||price<1000)throw new Error('Укажите корректную цену');
  if(!kmText)throw new Error('Укажите пробег автомобиля, для нового автомобиля введите 0');
  if(km<0||km>2000000)throw new Error('Проверьте пробег');
  if(phone&&phone.replace(/\D/g,'').length<10)throw new Error('Проверьте номер телефона');
  if(!phone&&!krugTgUser?.username)throw new Error('Укажите телефон для связи с покупателем');
  if(!legalAccepted.checked)throw new Error('Подтвердите правила и политику конфиденциальности');
  if(vin&&vin.length!==17)throw new Error('VIN должен содержать 17 символов');
  return {action:krugEditingId?'edit':undefined,name,year,price,km,description:carDescription.value.trim(),phone,type:active.includes('Обмен')?'Обмен':'Продажа',urgent:active.toLowerCase().includes('срочно'),images:krugImagesData,thumbnail:krugThumbnailData,transmission:carTransmission.value,body_type:carBodyType.value,drive:carDrive.value,vin};
};
const krugNextStepBeforeNumbers=nextStep;nextStep=function(n){
  try{if(n===2){if(carName.value.trim().length<2)throw new Error('Укажите марку и модель');let y=krugNumber(carYear.value),p=krugNumber(carPrice.value);if(!y||y<1950||y>new Date().getFullYear()+1)throw new Error('Проверьте год выпуска');if(!p||p<1000)throw new Error('Укажите корректную цену')}if(n===3&&!String(carKm.value).trim())throw new Error('Укажите пробег, для нового автомобиля введите 0');return krugNextStepBeforeNumbers(n)}catch(error){toast(error.message)}};

/* KRUG source block 30 */
// KRUG v32: remove the obsolete gearbox field that was displayed but never saved.
const krugLegacyGearbox=[...document.querySelectorAll('#create .step[data-step="2"] select')].find(field=>!field.id);
krugLegacyGearbox?.closest('.field')?.remove();

/* KRUG source block 31 */
// KRUG v33: urgent sale and exchange switches now persist as real listing settings.
const krugUrgentSwitch=[...document.querySelectorAll('#create .toggle')].find(row=>row.textContent.includes('Срочная продажа'))?.querySelector('.switch');
const krugExchangeSwitch=[...document.querySelectorAll('#create .toggle')].find(row=>row.textContent.includes('Принимать обмен'))?.querySelector('.switch');
function syncDealSwitches(){let selected=document.querySelector('.type-card.active')?.textContent||'';krugUrgentSwitch?.classList.toggle('on',selected.toLowerCase().includes('срочно'));krugExchangeSwitch?.classList.toggle('on',selected.includes('Обмен'))}
document.querySelectorAll('.type-card').forEach(button=>button.addEventListener('click',()=>setTimeout(syncDealSwitches)));
syncDealSwitches();
const krugListingDataBeforeDealSwitches=krugListingData;krugListingData=function(){let data=krugListingDataBeforeDealSwitches(),urgent=!!krugUrgentSwitch?.classList.contains('on'),accept_exchange=!!krugExchangeSwitch?.classList.contains('on');return {...data,urgent,accept_exchange,type:accept_exchange?'Обмен':'Продажа'}};
const krugEditBeforeDealSwitches=editCar;editCar=async function(id){await krugEditBeforeDealSwitches(id);if(krugEditingId!==id)return;try{let d=await krugJson(`/api/cars/${id}`);krugUrgentSwitch?.classList.toggle('on',!!d.urgent);krugExchangeSwitch?.classList.toggle('on',!!d.accept_exchange||d.type==='Обмен')}catch(_){}};
const krugOpenBeforeDealSwitches=openCarV3;openCarV3=async function(...args){await krugOpenBeforeDealSwitches(...args);let d=krugOpenedDetail;if(d?.accept_exchange)detailType.textContent=d.urgent?'Срочно · обмен':'Обмен возможен'};
setMode=function(el,m){document.querySelectorAll('.mode').forEach(x=>x.classList.remove('active'));el.classList.add('active');mode=m;if(m==='Обмен'){go('catalog');render(cars.filter(c=>c.accept_exchange||c.type==='Обмен'),'catalogCards')}};

/* KRUG source block 32 */
// KRUG v34: draft also remembers urgent-sale and exchange preferences.
const krugDraftSnapshotBeforeDeals=krugDraftSnapshot;
krugDraftSnapshot=function(){return {...krugDraftSnapshotBeforeDeals(),urgent:!!krugUrgentSwitch?.classList.contains('on'),accept_exchange:!!krugExchangeSwitch?.classList.contains('on')}};
function restoreKrugDraftDealSwitches(){
  if(krugEditingId)return;
  try{
    let draft=JSON.parse(localStorage.getItem(KRUG_DRAFT_KEY)||'null');
    if(!draft)return;
    if(typeof draft.urgent==='boolean')krugUrgentSwitch?.classList.toggle('on',draft.urgent);
    if(typeof draft.accept_exchange==='boolean')krugExchangeSwitch?.classList.toggle('on',draft.accept_exchange);
  }catch(_){localStorage.removeItem(KRUG_DRAFT_KEY)}
}
[krugUrgentSwitch,krugExchangeSwitch].filter(Boolean).forEach(button=>button.addEventListener('click',()=>setTimeout(saveKrugDraft)));
restoreKrugDraftDealSwitches();

/* KRUG source block 33 */
// KRUG v35: owner-only moderation queue for reported listings.
const krugAdminButton=document.createElement('button');krugAdminButton.className='menu-item admin-menu';krugAdminButton.innerHTML='Модерация жалоб <span>›</span>';document.querySelector('#profile .menu-list').append(krugAdminButton);
const krugReportReasons={fraud:'Мошенничество',wrong_info:'Неверные данные',sold:'Уже продано',duplicate:'Дубликат',other:'Другая причина'};
async function showModeration(){
  try{let reports=await krugJson('/api/admin/reports');go('catalog');document.querySelector('#catalog .page-head h1').textContent='Модерация';document.getElementById('catalogCards').innerHTML=reports.map(r=>`<div class="panel"><div class="eyebrow"><span class="dot"></span>жалоба №${Number(r.id)}</div><h3>${safeText(r.car_name)}</h3><span class="moderation-reason">${safeText(krugReportReasons[r.reason]||r.reason)}</span>${r.details?`<p>${safeText(r.details)}</p>`:''}<div class="meta">Отправитель: ${safeText(r.reporter_name||'Пользователь')}</div><div class="manage-actions"><button class="btn lime" onclick="moderateReport(${Number(r.id)},'approve')">Вернуть объявление</button><button class="btn sold-button" onclick="moderateReport(${Number(r.id)},'block')">Заблокировать</button></div></div>`).join('')||'<div class="panel"><h3>Новых жалоб нет</h3></div>'}catch(error){toast(error.message)}
}
async function moderateReport(id,action){try{await krugJson(`/api/admin/reports/${id}`,{method:'PUT',body:JSON.stringify({action})});toast(action==='approve'?'Объявление возвращено':'Объявление заблокировано');await showModeration()}catch(error){toast(error.message)}}
krugAdminButton.onclick=showModeration;
const krugLoadProfileBeforeAdmin=krugLoadProfile;krugLoadProfile=async function(){await krugLoadProfileBeforeAdmin();try{let d=await krugJson('/api/me');krugAdminButton.classList.toggle('show',!!d.admin)}catch(_){krugAdminButton.classList.remove('show')}};
krugLoadProfile();

/* KRUG source block 34 */
// KRUG v36: administrators can manage staff; moderators only review reports.
document.addEventListener('error',event=>{let image=event.target;if(image?.tagName==='IMG'&&!image.dataset.fallback){image.dataset.fallback='1';image.src='/krug-hero.png'}},true);
const krugStaffButton=document.createElement('button');krugStaffButton.className='menu-item admin-menu';krugStaffButton.innerHTML='Администраторы и модераторы <span>›</span>';document.querySelector('#profile .menu-list').append(krugStaffButton);
async function showStaff(){
  try{let staff=await krugJson('/api/admin/staff');go('catalog');document.querySelector('#catalog .page-head h1').textContent='Команда КРУГ';document.getElementById('catalogCards').innerHTML=`<div class="panel"><h3>Добавить сотрудника</h3><p class="meta">Человек должен хотя бы один раз открыть бота КРУГ.</p><div class="team-form"><input id="staffIdentifier" placeholder="Telegram ID или @username"><select id="staffRole"><option value="moderator">Модератор</option><option value="admin">Администратор</option></select><button class="btn lime" onclick="addStaff()">Добавить</button></div></div>`+staff.map(s=>`<div class="panel"><h3>${safeText(s.first_name||'Пользователь')}</h3><div class="meta">${s.username?'@'+safeText(s.username):'ID '+safeText(s.user_id)}</div><span class="staff-role">${s.role==='admin'?'Администратор':'Модератор'}</span><div class="manage-actions"><button class="btn back" onclick="removeStaff('${safeText(s.user_id)}')">Снять доступ</button></div></div>`).join('')}catch(error){toast(error.message)}
}
async function addStaff(){try{let identifier=document.getElementById('staffIdentifier').value.trim(),role=document.getElementById('staffRole').value;await krugJson('/api/admin/staff',{method:'POST',body:JSON.stringify({identifier,role})});toast('Доступ сотруднику сохранён');await showStaff()}catch(error){toast(error.message)}}
async function removeStaff(id){if(!confirm('Снять доступ у сотрудника?'))return;try{await krugJson(`/api/admin/staff/${encodeURIComponent(id)}`,{method:'DELETE'});toast('Доступ снят');await showStaff()}catch(error){toast(error.message)}}
krugStaffButton.onclick=showStaff;
const krugLoadProfileBeforeStaff=krugLoadProfile;krugLoadProfile=async function(){await krugLoadProfileBeforeStaff();try{let d=await krugJson('/api/me'),role=d.staff_role||'';krugAdminButton.classList.toggle('show',!!role);krugStaffButton.classList.toggle('show',role==='owner'||role==='admin')}catch(_){krugAdminButton.classList.remove('show');krugStaffButton.classList.remove('show')}};
krugLoadProfile();

/* KRUG source block 35 */
// KRUG v37: paginated catalogue keeps mobile rendering and database reads light.
let krugCatalogOffset=0,krugCatalogHasMore=false,krugCatalogTotal=0;const KRUG_PAGE_SIZE=20;
const krugMoreButton=document.createElement('button');krugMoreButton.className='btn back catalog-more';krugMoreButton.textContent='Показать ещё автомобили';document.querySelector('#catalog .section').after(krugMoreButton);
function paintKrugMore(){let regular=document.querySelector('#catalog .page-head h1')?.textContent==='Автомобили';krugMoreButton.classList.toggle('show',regular&&krugCatalogHasMore);krugFilterResult.textContent=`Загружено ${cars.length} из ${krugCatalogTotal||cars.length}`}
async function loadKrugCarPage(reset=false){
  if(location.protocol==='file:'||krugMoreButton.classList.contains('busy'))return;
  krugMoreButton.classList.add('busy');
  try{let offset=reset?0:krugCatalogOffset,d=await krugJson(`/api/cars?paged=1&limit=${KRUG_PAGE_SIZE}&offset=${offset}`),known=new Set((reset?[]:cars).map(x=>Number(x.id)));cars=reset?d.items:[...cars,...d.items.filter(x=>!known.has(Number(x.id)))];krugCatalogOffset=offset+d.items.length;krugCatalogHasMore=!!d.has_more;krugCatalogTotal=Number(d.total)||cars.length;renderAll();paintKrugMore();await krugLoadProfile()}catch(error){toast(error.message)}finally{krugMoreButton.classList.remove('busy')}
}
krugMoreButton.onclick=()=>loadKrugCarPage(false);
krugLoadCars=async function(){await loadKrugCarPage(true)};
loadKrugCarPage(true);

/* KRUG source block 36 */
// KRUG v38: daily unique public listing views.
const krugDetailViews=document.createElement('div');krugDetailViews.className='detail-views';detailSeller.after(krugDetailViews);
function krugViewsLabel(value){let count=Math.max(0,Number(value)||0);return `${count} ${count%10===1&&count%100!==11?'просмотр':([2,3,4].includes(count%10)&&![12,13,14].includes(count%100)?'просмотра':'просмотров')}`}
function paintCarViews(id,value){let count=Math.max(0,Number(value)||0);document.querySelectorAll(`[data-car-id="${Number(id)}"] .car-interest span`).forEach(x=>x.textContent=krugViewsLabel(count))}
function card(c){let id=Number(c.id)||0,name=safeText(c.name),picture=safeImageSrc(c.image||hero),dealer=c.seller_role==='dealer',saved=!!c.favourite,views=Math.max(0,Number(c.views)||0);return `<article class="car" data-car-id="${id}" onclick="openCarById(${id})"><div class="car-media"><img src="${picture}" style="object-position:${safeText(c.pos||'50% 50%')}" alt="${name}"><span class="badge ${c.urgent?'urgent':''}">${c.urgent?'⚡ Срочно':safeText(c.type)}</span><button class="heart ${saved?'saved':''}" data-favourite-id="${id}" aria-label="${saved?'Удалить из избранного':'Добавить в избранное'}" onclick="saveV2(event,this,${id})">${saved?'♥':'♡'}</button></div><div class="car-body"><div class="car-top"><div><h3>${name}</h3><div class="meta">${Number(c.year)||'—'} · ${safeText(c.km)}</div></div><div class="price">${rub(Number(c.price)||0)}</div></div><div class="tags"><span class="tag">Екатеринбург</span>${dealer?`<span class="tag">✓ Дилер · ${safeText(c.seller_company||'Компания')}</span>`:'<span class="tag">Частник</span>'}${c.accept_exchange||c.type==='Обмен'?'<span class="tag">↔ Рассмотрю обмен</span>':''}</div><div class="car-interest">${krugEyeIcon}<span>${krugViewsLabel(views)}</span></div></div></article>`}
const krugOpenBeforePublicViews=openCarV3;openCarV3=async function(...args){await krugOpenBeforePublicViews(...args);let d=krugOpenedDetail;if(!d){krugDetailViews.textContent='';return}let count=Math.max(0,Number(d.views)||0),c=cars.find(x=>Number(x.id)===Number(d.id));if(c)c.views=count;krugDetailViews.innerHTML=`${krugEyeIcon}<span>${krugViewsLabel(count)}</span>`;paintCarViews(d.id,count)};

/* KRUG source block 37 */
// Selected visual direction: Champagne Graphite.
document.querySelector('#profile .page-head h1').textContent='Профиль';
const krugProfileCard=document.querySelector('#profile .profile-card');
const krugVerified=document.createElement('div');krugVerified.className='profile-verified';krugVerified.innerHTML='<i>✓</i><span>Профиль подтверждён Telegram</span>';
const krugProfileRole=document.createElement('div');krugProfileRole.className='profile-role';krugProfileRole.textContent='Частный продавец';
krugProfileCard.querySelector('.stats').before(krugVerified,krugProfileRole);
const krugProfileStats=krugProfileCard.querySelectorAll('.stat');if(krugProfileStats[2])krugProfileStats[2].lastChild.textContent='просмотры';
const krugGarageCta=document.createElement('button');krugGarageCta.className='profile-garage-cta';krugGarageCta.innerHTML='<b>Мой гараж</b><small>Управляйте автомобилями и объявлениями</small><span>›</span>';krugGarageCta.onclick=showMyCars;krugProfileCard.after(krugGarageCta);
const krugProfileIcons=['▰','⇄','♡','◌','◆','↓','×','!','♟'];document.querySelectorAll('#profile .menu-item').forEach((button,index)=>button.dataset.icon=krugProfileIcons[index]||'•');
const krugLoadProfileBeforeLuxury=krugLoadProfile;krugLoadProfile=async function(){await krugLoadProfileBeforeLuxury();try{let d=await krugJson('/api/me'),p=document.querySelector('.profile-card'),stats=p?.querySelectorAll('.stat b');if(stats?.[2])stats[2].textContent=Number(d.views)||0;krugProfileRole.textContent=d.user?.role==='dealer'?'Проверенный дилер':'Частный продавец'}catch(_){}};
krugLoadProfile();

/* KRUG source block 38 */
// Keep Telegram browser chrome aligned with the selected luxury palette.
try{window.Telegram?.WebApp?.setHeaderColor?.('#101211');window.Telegram?.WebApp?.setBackgroundColor?.('#101211');window.Telegram?.WebApp?.setBottomBarColor?.('#0f1110')}catch(_){}

/* KRUG source block 39 */
// KRUG v41: Russian/Latin brand aliases and typo-friendly catalogue search.
const krugBrandAliases={
  toyota:['toyota','тойота','тайота','тоёта'],ford:['ford','форд'],lada:['lada','лада','ваз','vaz'],
  volkswagen:['volkswagen','фольксваген','фольцваген','vw'],mercedes:['mercedes','мерседес','мерин'],
  bmw:['bmw','бмв'],hyundai:['hyundai','хендай','хундай','хёндай'],kia:['kia','киа'],
  nissan:['nissan','ниссан'],renault:['renault','рено'],chevrolet:['chevrolet','шевроле'],
  skoda:['skoda','шкода'],audi:['audi','ауди'],honda:['honda','хонда'],mazda:['mazda','мазда'],
  mitsubishi:['mitsubishi','митсубиси','мицубиси'],lexus:['lexus','лексус'],subaru:['subaru','субару'],
  peugeot:['peugeot','пежо'],citroen:['citroen','ситроен'],opel:['opel','опель'],volvo:['volvo','вольво'],
  geely:['geely','джили'],haval:['haval','хавал'],chery:['chery','чери'],uaz:['uaz','уаз'],gaz:['gaz','газ']
};
const krugAliasIndex=Object.entries(krugBrandAliases).reduce((index,[brand,names])=>{names.forEach(name=>index[name.replace(/ё/g,'е')]=brand);return index},{});
const krugCyrillicLatin={а:'a',б:'b',в:'v',г:'g',д:'d',е:'e',ж:'zh',з:'z',и:'i',й:'i',к:'k',л:'l',м:'m',н:'n',о:'o',п:'p',р:'r',с:'s',т:'t',у:'u',ф:'f',х:'h',ц:'c',ч:'ch',ш:'sh',щ:'sh',ъ:'',ы:'i',ь:'',э:'e',ю:'yu',я:'ya'};
function krugPhonetic(word){return [...word].map(letter=>krugCyrillicLatin[letter]??letter).join('').replace(/c/g,'k').replace(/q/g,'k').replace(/y/g,'i')}
function krugSearchWords(value){let clean=String(value||'').toLowerCase().replace(/ё/g,'е').replace(/[^a-zа-я0-9]+/g,' ').trim();return clean?clean.split(/\s+/).map(word=>krugAliasIndex[word]||krugPhonetic(word)):[]}
function krugDistance(a,b){let row=[...Array(b.length+1).keys()];for(let i=1;i<=a.length;i++){let next=[i];for(let j=1;j<=b.length;j++)next[j]=Math.min(next[j-1]+1,row[j]+1,row[j-1]+(a[i-1]===b[j-1]?0:1));row=next}return row[b.length]}
function krugMatchesCar(car,query){let wanted=krugSearchWords(query),available=krugSearchWords(`${car.name||''} ${car.brand||''} ${car.model||''}`);return wanted.every(word=>available.some(candidate=>candidate.includes(word)||word.includes(candidate)||(word.length>=4&&candidate.length>=4&&krugDistance(word,candidate)<=1)))}
applyCatalog=function(){
  let q=(catalogSearch?.value||'').trim(),list=cars.filter(c=>krugMatchesCar(c,q));
  if(catalogRange!=='all'){if(catalogRange==='300+')list=list.filter(c=>c.price>=300000);else{let[a,z]=catalogRange.split('-').map(x=>+x*1000);list=list.filter(c=>c.price>=a&&c.price<=z)}}
  if(filterTransmission.value)list=list.filter(c=>c.transmission===filterTransmission.value);if(filterBody.value)list=list.filter(c=>c.body_type===filterBody.value);if(filterDrive.value)list=list.filter(c=>c.drive===filterDrive.value);
  let sort=catalogSort?.value||'new';list=[...list].sort((a,b)=>sort==='cheap'?a.price-b.price:sort==='expensive'?b.price-a.price:sort==='year'?b.year-a.year:(b.id||0)-(a.id||0));render(list,'catalogCards');
  if(!list.length)document.getElementById('catalogCards').innerHTML='<div class="panel search-empty"><h3>Автомобили не найдены</h3><p class="meta">Попробуйте написать марку или модель по-другому либо сбросьте фильтры.</p><button class="btn back" type="button" onclick="document.querySelector(\'.filter-reset\').click()">Сбросить фильтры</button></div>';
  krugFilterResult.textContent=`Найдено автомобилей: ${list.length}`;if(typeof paintKrugMore==='function')paintKrugMore()
};
// Earlier listeners retain the previous function reference, so bind the enhanced search explicitly.
catalogSearch?.addEventListener('input',applyCatalog);catalogSort?.addEventListener('change',applyCatalog);
[filterTransmission,filterBody,filterDrive].forEach(field=>field?.addEventListener('change',applyCatalog));

/* KRUG source block 40 */
// KRUG v43: server-backed recently viewed cars.
const krugRecentButton=document.createElement('button');
krugRecentButton.className='menu-item';krugRecentButton.dataset.icon='◷';krugRecentButton.innerHTML='Недавно просмотренные <span>›</span>';
const krugFavouriteMenu=[...document.querySelectorAll('#profile .menu-item')].find(button=>button.textContent.includes('Избранное'));
if(krugFavouriteMenu)krugFavouriteMenu.insertAdjacentElement('afterend',krugRecentButton);else document.querySelector('#profile .menu-list')?.append(krugRecentButton);
async function showRecentlyViewed(){
  try{let list=await krugJson('/api/recent');go('catalog');document.querySelector('#catalog .page-head h1').textContent='Недавно просмотренные';document.querySelector('#catalog .page-head p').textContent='Автомобили, которые вы открывали';document.getElementById('catalogCards').innerHTML=list.length?list.map(card).join(''):'<div class="panel search-empty"><h3>История пока пустая</h3><p class="meta">Откройте любое объявление — оно появится здесь.</p></div>';krugMoreButton?.classList.remove('show')}
  catch(error){toast(error.message)}
}
krugRecentButton.onclick=showRecentlyViewed;
const krugCatalogNav=document.querySelector('.nav [data-go="catalog"]');
krugCatalogNav?.addEventListener('click',()=>{document.querySelector('#catalog .page-head h1').textContent='Автомобили';document.querySelector('#catalog .page-head p').textContent='Екатеринбург · частники и дилеры';applyCatalog()});

/* KRUG source block 41 */
// KRUG v44: catalogue search, filters and sorting run across the full server catalogue.
const krugClientApplyCatalog=applyCatalog;let krugServerSearchTimer=0,krugServerSearchSeq=0;
function krugServerCatalogueQuery(offset){
  let params=new URLSearchParams({paged:'1',limit:String(KRUG_PAGE_SIZE),offset:String(offset),sort:catalogSort?.value||'new'}),query=krugSearchWords(catalogSearch?.value||'').join(' ');
  if(query)params.set('q',query);if(filterTransmission.value)params.set('transmission',filterTransmission.value);if(filterBody.value)params.set('body',filterBody.value);if(filterDrive.value)params.set('drive',filterDrive.value);
  if(catalogRange!=='all'){if(catalogRange==='300+')params.set('price_min','300000');else{let[a,z]=catalogRange.split('-').map(value=>Number(value)*1000);params.set('price_min',String(a));params.set('price_max',String(z))}}
  return params.toString()
}
loadKrugCarPage=async function(reset=false){
  if(location.protocol==='file:'){krugClientApplyCatalog();return}if(!reset&&krugMoreButton.classList.contains('busy'))return;
  let requestId=++krugServerSearchSeq,offset=reset?0:krugCatalogOffset;krugMoreButton.classList.add('busy');if(reset){krugFilterResult.textContent='Ищем автомобили…';if(!cars.length)document.getElementById('catalogCards').innerHTML='<div class="catalog-skeleton" aria-label="Загружаем автомобили"><i></i><i></i><i></i></div>'}
  try{let d=await krugJson(`/api/cars?${krugServerCatalogueQuery(offset)}`);if(requestId!==krugServerSearchSeq)return;let known=new Set((reset?[]:cars).map(car=>Number(car.id)));cars=reset?d.items:[...cars,...d.items.filter(car=>!known.has(Number(car.id)))];krugCatalogOffset=offset+d.items.length;krugCatalogHasMore=!!d.has_more;krugCatalogTotal=Number(d.total)||0;render(cars,'catalogCards');if(!cars.length)document.getElementById('catalogCards').innerHTML='<div class="panel search-empty"><h3>Автомобили не найдены</h3><p class="meta">Попробуйте изменить запрос или сбросить фильтры.</p><button class="btn back" type="button" onclick="document.querySelector(\'.filter-reset\').click()">Сбросить фильтры</button></div>';paintKrugMore()}
  catch(error){if(requestId===krugServerSearchSeq){krugFilterResult.textContent='Не удалось обновить каталог';if(!cars.length)document.getElementById('catalogCards').innerHTML='<div class="panel catalog-error"><i>↻</i><h3>Не удалось загрузить автомобили</h3><p class="meta">Проверьте интернет. Если бесплатный сервер просыпается, повторите через несколько секунд.</p><button class="btn lime" type="button" onclick="loadKrugCarPage(true)">Попробовать снова</button></div>';toast(error.message)}}finally{if(requestId===krugServerSearchSeq)krugMoreButton.classList.remove('busy')}
};
applyCatalog=function(){clearTimeout(krugServerSearchTimer);krugServerSearchTimer=setTimeout(()=>loadKrugCarPage(true),220)};
catalogSearch?.addEventListener('input',applyCatalog);catalogSort?.addEventListener('change',applyCatalog);[filterTransmission,filterBody,filterDrive].forEach(field=>field?.addEventListener('change',applyCatalog));
setTimeout(()=>loadKrugCarPage(true),0);

/* KRUG source block 42 */
const KRUG_POLICY_VERSION='2026-08-16';
let krugPrivacyReady=localStorage.getItem('krug_privacy_version')===KRUG_POLICY_VERSION&&localStorage.getItem('krug_rules_version')===KRUG_POLICY_VERSION;
const privacyListingAccepted=document.createElement('label');privacyListingAccepted.className='legal-consent';privacyListingAccepted.innerHTML=`<input id="listingPrivacyAccepted" type="checkbox"><span>Я подтверждаю отдельное согласие на обработку данных по <button type="button" class="legal-link" onclick="event.preventDefault();openLegal('privacy')">политике версии ${KRUG_POLICY_VERSION}</button>.</span>`;
const contactPublicAccepted=document.createElement('label');contactPublicAccepted.className='contact-public-consent';contactPublicAccepted.innerHTML='<input id="contactPublicAccepted" type="checkbox"><span><b>Отдельное согласие на распространение контакта.</b><br>Разрешаю оператору КРУГ показывать категории данных «Telegram username» и «номер телефона» кругу авторизованных пользователей, открывших карточку, только для связи по объявлению. В общей выдаче контактов не будет. Согласие действует, пока объявление активно, и отзывается его архивацией/удалением либо обращением оператору из политики.</span>';
krugConsent.querySelector('span').innerHTML='Я подтверждаю достоверность объявления и принимаю <button type="button" class="legal-link" onclick="event.preventDefault();openLegal(\'rules\')">правила КРУГ</button>.';
krugConsent.insertAdjacentElement('afterend',privacyListingAccepted);privacyListingAccepted.insertAdjacentElement('afterend',contactPublicAccepted);
const listingPrivacyInput=privacyListingAccepted.querySelector('input'),contactPublicInput=contactPublicAccepted.querySelector('input');listingPrivacyInput.checked=krugPrivacyReady;
const krugListingDataBeforePrivacy=krugListingData;krugListingData=function(){let data=krugListingDataBeforePrivacy();if(!listingPrivacyInput.checked)throw new Error('Подтвердите отдельное согласие на обработку данных');if(!contactPublicInput.checked)throw new Error('Отдельно разрешите показывать контакт покупателям');return {...data,privacy_consent:true,contact_consent:true,phone_public:!!data.phone,policy_version:KRUG_POLICY_VERSION}};
const krugResetBeforePrivacy=krugResetListingForm;krugResetListingForm=function(){krugResetBeforePrivacy();contactPublicInput.checked=false;listingPrivacyInput.checked=krugPrivacyReady};
const krugEditBeforePrivacy=editCar;editCar=async function(id){await krugEditBeforePrivacy(id);if(krugEditingId!==id)return;try{let d=await krugJson(`/api/cars/${id}`);contactPublicInput.checked=!!d.contact_consent_at&&d.consent_version===KRUG_POLICY_VERSION;listingPrivacyInput.checked=krugPrivacyReady}catch(_){contactPublicInput.checked=false}};
paintContactHint=function(){let username=krugTgUser?.username||'',hasPhone=carPhone.value.replace(/\D/g,'').length>=10;if(username||hasPhone){krugContactHint.className='contact-hint ok';krugContactHint.textContent='Контакт не попадёт в каталог. Он откроется только вошедшему пользователю после вашего отдельного согласия.'}else{krugContactHint.className='contact-hint';krugContactHint.textContent='Укажите телефон — в вашем Telegram нет публичного username'}};paintContactHint();
let krugLegalInfo={};
async function loadKrugLegalInfo(){try{let r=await krugApi('/api/legal',{headers:{'Accept':'application/json'}});krugLegalInfo=await r.json();let name=krugLegalInfo.operator_name||'реквизиты ещё не заполнены',email=krugLegalInfo.operator_email||'контакт ещё не указан',address=krugLegalInfo.operator_address||'адрес ещё не указан';privacyOperatorText.textContent=krugLegalInfo.testing_mode?'КРУГ работает в публичном тестовом режиме. Не публикуйте чужие персональные данные, документы и фотографии без разрешения.':krugLegalInfo.closed_beta?'Вы входите в закрытую тестовую группу КРУГ. Не публикуйте чужие персональные данные и документы.':krugLegalInfo.ready?`Оператор: ${name}. Адрес: ${address}. Контакт: ${email}. Первичное хранение данных в РФ подтверждено.`:'Сбор персональных данных отключён, пока владелец не укажет реквизиты и не подтвердит хранение базы в РФ.';return krugLegalInfo}catch(_){privacyOperatorText.textContent='Не удалось проверить юридические настройки сервиса.';return {ready:false}}}
function paintLegalOperator(){let name=document.getElementById('legalOperatorName'),email=document.getElementById('legalOperatorEmail'),address=document.getElementById('legalOperatorAddress');if(name)name.textContent=krugLegalInfo.operator_name||'не указан';if(email)email.textContent=krugLegalInfo.operator_email||'не указан';if(address)address.textContent=krugLegalInfo.operator_address||'не указан'}
const openLegalBeforeSecurity=openLegal;openLegal=function(kind){openLegalBeforeSecurity(kind);paintLegalOperator()};
async function acceptKrugPrivacy(){if(!privacyPolicyChoice.checked||!privacyRulesChoice.checked){privacyGateStatus.textContent='Нужно отдельно отметить оба пункта.';return}let legal=await loadKrugLegalInfo();if(!legal.ready){privacyGateStatus.textContent='Владелец ещё не завершил обязательную юридическую настройку.';return}privacyAcceptButton.classList.add('busy');try{let u=krugTgUser||{first_name:'Пользователь',username:''};await krugJson('/api/session',{method:'POST',body:JSON.stringify({first_name:u.first_name,username:u.username||'',privacy_consent:true,policy_version:KRUG_POLICY_VERSION,rules_accepted:true,rules_version:KRUG_POLICY_VERSION})});localStorage.setItem('krug_privacy_version',KRUG_POLICY_VERSION);localStorage.setItem('krug_rules_version',KRUG_POLICY_VERSION);krugPrivacyReady=true;listingPrivacyInput.checked=true;privacyGate.classList.remove('open');await krugLoadProfile();toast('Настройки конфиденциальности сохранены')}catch(error){privacyGateStatus.textContent=error.message}finally{privacyAcceptButton.classList.remove('busy')}}
privacyAcceptButton.onclick=acceptKrugPrivacy;privacyBrowseButton.onclick=()=>privacyGate.classList.remove('open');
async function startKrugPrivacy(){if(location.protocol==='file:')return;let legal=await loadKrugLegalInfo();if(!legal.ready){privacyGate.classList.remove('open');krugShowConnection('Каталог доступен. Публикация и личные функции временно отключены до завершения юридической настройки.');return}if(!krugInitData){privacyGate.classList.remove('open');return krugShowConnection('Откройте КРУГ кнопкой внутри Telegram для входа в профиль.')}if(krugPrivacyReady){try{let u=krugTgUser||{first_name:'Пользователь',username:''};await krugJson('/api/session',{method:'POST',body:JSON.stringify({first_name:u.first_name,username:u.username||'',privacy_consent:true,policy_version:KRUG_POLICY_VERSION,rules_accepted:true,rules_version:KRUG_POLICY_VERSION})});return}catch(_){krugPrivacyReady=false;localStorage.removeItem('krug_privacy_version');localStorage.removeItem('krug_rules_version')}}privacyGate.classList.add('open')}
startKrugPrivacy();

/* KRUG source block 43 */
// Saved catalogue search: one editable alert per user for the MVP.
const krugSearchAlert=document.createElement('div');
krugSearchAlert.className='search-alert';
krugSearchAlert.innerHTML='<div><b>Не пропустите подходящий автомобиль</b><small>КРУГ сообщит в Telegram о новом объявлении по выбранным параметрам.</small><span class="search-alert-state"></span></div><div class="search-alert-actions"><button type="button" class="btn search-alert-save">🔔 Подписаться на поиск</button><button type="button" class="search-alert-remove" hidden>Отключить</button></div>';
krugFilterResult.insertAdjacentElement('afterend',krugSearchAlert);
const krugSearchAlertSave=krugSearchAlert.querySelector('.search-alert-save'),krugSearchAlertRemove=krugSearchAlert.querySelector('.search-alert-remove'),krugSearchAlertState=krugSearchAlert.querySelector('.search-alert-state');
let krugSearchSubscription=null;
function krugCurrentSearchFilters(){let filters={q:(catalogSearch?.value||'').trim(),transmission:filterTransmission.value,body_type:filterBody.value,drive:filterDrive.value};if(catalogRange!=='all'){if(catalogRange==='300+')filters.price_min=300000;else{let[from,to]=catalogRange.split('-').map(value=>Number(value)*1000);filters.price_min=from;filters.price_max=to}}return filters}
function krugSearchFilterName(filters){let parts=[];if(filters.q)parts.push(filters.q);if(filters.price_min||filters.price_max){let from=filters.price_min?new Intl.NumberFormat('ru-RU').format(filters.price_min):'0',to=filters.price_max?new Intl.NumberFormat('ru-RU').format(filters.price_max):'выше';parts.push(`${from}–${to} ₽`)}[filters.transmission,filters.body_type,filters.drive].filter(Boolean).forEach(value=>parts.push(value));return parts.join(' · ').slice(0,80)||'Подходящие автомобили'}
function paintKrugSearchAlert(){let active=!!krugSearchSubscription;krugSearchAlert.classList.toggle('active',active);krugSearchAlertSave.textContent=active?'Изменить уведомление':'🔔 Подписаться на поиск';krugSearchAlertRemove.hidden=!active;krugSearchAlertState.textContent=active?`Активно: ${krugSearchSubscription.name}`:'Выберите марку, цену или характеристику выше.'}
async function loadKrugSearchAlert(){if(location.protocol==='file:')return paintKrugSearchAlert();try{let data=await krugJson('/api/subscriptions');krugSearchSubscription=data.search||null;paintKrugSearchAlert()}catch(_){paintKrugSearchAlert()}}
async function saveKrugSearchAlert(){let filters=krugCurrentSearchFilters(),hasFilter=Object.values(filters).some(value=>value!==''&&value!==null&&value!==undefined);if(!hasFilter)return toast('Сначала выберите марку, цену или характеристику');if(location.protocol==='file:')return toast('Подписка включается внутри Telegram');if(krugSearchAlertSave.classList.contains('busy'))return;krugSearchAlertSave.classList.add('busy');try{let name=krugSearchFilterName(filters),data=await krugJson('/api/subscriptions',{method:'POST',body:JSON.stringify({kind:'search',name,filters})});krugSearchSubscription=data.search;paintKrugSearchAlert();toast('Уведомление о новых автомобилях включено')}catch(error){toast(error.message)}finally{krugSearchAlertSave.classList.remove('busy')}}
async function removeKrugSearchAlert(){try{await krugJson('/api/subscriptions?kind=search',{method:'DELETE'});krugSearchSubscription=null;paintKrugSearchAlert();toast('Уведомление о поиске отключено')}catch(error){toast(error.message)}}
krugSearchAlertSave.addEventListener('click',saveKrugSearchAlert);krugSearchAlertRemove.addEventListener('click',removeKrugSearchAlert);krugCatalogNav?.addEventListener('click',loadKrugSearchAlert);paintKrugSearchAlert();

/* KRUG source block 44 */
// Complete vehicle essentials used by buyers when comparing real listings.
const krugEngineFields=document.createElement('div');krugEngineFields.className='engine-fields';
krugEngineFields.innerHTML='<div class="field"><label>Топливо</label><select id="carFuel"><option value="">Выберите</option><option>Бензин</option><option>Дизель</option><option>Гибрид</option><option>Электро</option><option>Газ</option></select></div><div class="engine-row"><div class="field"><label>Объём, л</label><input id="carEngineVolume" inputmode="decimal" placeholder="2.0"></div><div class="field"><label>Мощность, л.с.</label><input id="carEnginePower" inputmode="numeric" placeholder="150"></div></div><div class="engine-row"><div class="field"><label>Цвет</label><input id="carColor" maxlength="30" placeholder="Чёрный"></div><div class="field"><label>Владельцев</label><select id="carOwners"><option value="0">Не указано</option><option value="1">1 владелец</option><option value="2">2 владельца</option><option value="3">3 владельца</option><option value="4">4 и более</option></select></div></div>';
krugSpecsHost.append(krugEngineFields);
const carFuel=document.getElementById('carFuel'),carEngineVolume=document.getElementById('carEngineVolume'),carEnginePower=document.getElementById('carEnginePower'),carColor=document.getElementById('carColor'),carOwners=document.getElementById('carOwners');
carEngineVolume.addEventListener('input',()=>carEngineVolume.value=carEngineVolume.value.replace(/[^0-9,.]/g,'').slice(0,4));carEnginePower.addEventListener('input',()=>carEnginePower.value=carEnginePower.value.replace(/\D/g,'').slice(0,4));
const krugListingDataBeforeEngine=krugListingData;krugListingData=function(){let data=krugListingDataBeforeEngine(),volume=Number(carEngineVolume.value.replace(',','.'))||0,power=Number(carEnginePower.value)||0,owners=Number(carOwners.value)||0;if(volume<0||volume>10)throw new Error('Проверьте объём двигателя');if(power<0||power>3000)throw new Error('Проверьте мощность двигателя');return {...data,fuel:carFuel.value,engine_volume:volume,engine_power:power,color:carColor.value.trim(),owners_count:owners}};
const krugEditBeforeEngine=editCar;editCar=async function(id){await krugEditBeforeEngine(id);if(krugEditingId!==id)return;try{let d=await krugJson(`/api/cars/${id}`);carFuel.value=d.fuel||'';carEngineVolume.value=Number(d.engine_volume)||'';carEnginePower.value=Number(d.engine_power)||'';carColor.value=d.color||'';carOwners.value=String(Math.min(Number(d.owners_count)||0,4))}catch(_){}};
const krugResetBeforeEngine=krugResetListingForm;krugResetListingForm=function(){[carTransmission,carBodyType,carDrive,carFuel].forEach(field=>field.value='');[carEngineVolume,carEnginePower,carColor].forEach(field=>field.value='');carOwners.value='0';return krugResetBeforeEngine()};
const krugDraftSnapshotBeforeEngine=krugDraftSnapshot;krugDraftSnapshot=function(){return {...krugDraftSnapshotBeforeEngine(),fuel:carFuel.value,engine_volume:carEngineVolume.value,engine_power:carEnginePower.value,color:carColor.value,owners_count:carOwners.value}};
[carFuel,carEngineVolume,carEnginePower,carColor,carOwners].forEach(field=>{field.addEventListener('input',saveKrugDraft);field.addEventListener('change',saveKrugDraft)});
try{let draft=JSON.parse(localStorage.getItem(KRUG_DRAFT_KEY)||'null');if(draft){carFuel.value=draft.fuel||'';carEngineVolume.value=draft.engine_volume||'';carEnginePower.value=draft.engine_power||'';carColor.value=draft.color||'';carOwners.value=String(draft.owners_count||0)}}catch(_){}
const krugExtendedSpecs=document.createElement('div');krugExtendedSpecs.className='extended-specs';document.querySelector('.detail-specs').after(krugExtendedSpecs);
const krugOpenBeforeEngine=openCarV3;openCarV3=async function(...args){await krugOpenBeforeEngine(...args);let d=krugOpenedDetail;if(!d)return;let values=[d.fuel,d.engine_volume?`${Number(d.engine_volume).toLocaleString('ru-RU')} л`:'',d.engine_power?`${Number(d.engine_power)} л.с.`:'',d.color,d.owners_count?`${Number(d.owners_count)} вл.`:''].filter(Boolean);krugExtendedSpecs.innerHTML=values.map(value=>`<span>${safeText(value)}</span>`).join('')};
const filterFuel=document.createElement('select');filterFuel.id='filterFuel';filterFuel.setAttribute('aria-label','Топливо');filterFuel.innerHTML='<option value="">Любое топливо</option><option>Бензин</option><option>Дизель</option><option>Гибрид</option><option>Электро</option><option>Газ</option>';krugFilterBox.insertBefore(filterFuel,krugFilterBox.querySelector('.filter-reset'));filterFuel.addEventListener('change',applyCatalog);
const krugServerCatalogueQueryBeforeFuel=krugServerCatalogueQuery;krugServerCatalogueQuery=function(offset){let params=new URLSearchParams(krugServerCatalogueQueryBeforeFuel(offset));if(filterFuel.value)params.set('fuel',filterFuel.value);return params.toString()};
const krugCurrentSearchFiltersBeforeFuel=krugCurrentSearchFilters;krugCurrentSearchFilters=function(){return {...krugCurrentSearchFiltersBeforeFuel(),fuel:filterFuel.value}};
const krugSearchFilterNameBeforeFuel=krugSearchFilterName;krugSearchFilterName=function(filters){let label=krugSearchFilterNameBeforeFuel(filters);return filters.fuel&&!label.includes(filters.fuel)?`${label} · ${filters.fuel}`.slice(0,80):label};
const krugFilterResetBeforeFuel=krugFilterBox.querySelector('.filter-reset').onclick;krugFilterBox.querySelector('.filter-reset').onclick=()=>{filterFuel.value='';krugFilterResetBeforeFuel()};

/* KRUG source block 45 */
// Buyer comparison for up to three cars, kept locally on the user's device.
const KRUG_COMPARE_KEY='krug_compare_v1';
let krugCompareIds=[];try{krugCompareIds=JSON.parse(localStorage.getItem(KRUG_COMPARE_KEY)||'[]').map(Number).filter(id=>id>0).slice(0,3)}catch(_){localStorage.removeItem(KRUG_COMPARE_KEY)}
const krugCompareBar=document.createElement('div');krugCompareBar.className='compare-bar';krugCompareBar.innerHTML='<span><b class="compare-count">0</b> в сравнении</span><button type="button">Сравнить</button>';document.querySelector('.app').append(krugCompareBar);
const krugCompareModal=document.createElement('div');krugCompareModal.className='modal compare-modal';krugCompareModal.innerHTML='<div class="sheet compare-sheet"><div class="grab"></div><div class="compare-head"><div><span class="eyebrow"><span class="dot"></span> выбор покупателя</span><h2>Сравнение автомобилей</h2></div><button type="button" class="icon-btn compare-close">×</button></div><div class="compare-content"></div></div>';document.body.append(krugCompareModal);
const krugCompareContent=krugCompareModal.querySelector('.compare-content');
function saveKrugCompare(){localStorage.setItem(KRUG_COMPARE_KEY,JSON.stringify(krugCompareIds));paintKrugCompare()}
function paintKrugCompare(){krugCompareBar.classList.toggle('show',krugCompareIds.length>0);krugCompareBar.querySelector('.compare-count').textContent=krugCompareIds.length;document.querySelectorAll('[data-compare-id]').forEach(button=>button.classList.toggle('selected',krugCompareIds.includes(Number(button.dataset.compareId))))}
function toggleKrugCompare(event,id){event?.stopPropagation?.();id=Number(id);if(!id)return toast('Сравнение доступно для опубликованных объявлений');let index=krugCompareIds.indexOf(id);if(index>=0)krugCompareIds.splice(index,1);else{if(krugCompareIds.length>=3)return toast('Можно сравнить не больше трёх автомобилей');krugCompareIds.push(id)}saveKrugCompare();toast(index>=0?'Убрано из сравнения':'Добавлено к сравнению')}
const krugCardBeforeCompare=card;card=function(c){let html=krugCardBeforeCompare(c),id=Number(c.id)||0,selected=krugCompareIds.includes(id);return html.replace('<div class="car-interest">',`<button type="button" class="compare-add ${selected?'selected':''}" data-compare-id="${id}" onclick="toggleKrugCompare(event,${id})">${selected?'✓ В сравнении':'＋ Сравнить'}</button><div class="car-interest">`)};
function krugCompareValue(car,key){if(key==='price')return rub(Number(car.price)||0);if(key==='engine')return car.engine_volume?`${Number(car.engine_volume).toLocaleString('ru-RU')} л`:'—';if(key==='power')return car.engine_power?`${Number(car.engine_power)} л.с.`:'—';if(key==='owners')return car.owners_count?String(car.owners_count):'—';if(key==='views')return String(Number(car.views)||0);return safeText(car[key]||'—')}
async function openKrugCompare(){if(!krugCompareIds.length)return;krugCompareBar.querySelector('button').classList.add('busy');try{let compared=[];for(let id of krugCompareIds){let summary=cars.find(car=>Number(car.id)===id);if(location.protocol==='file:'){if(summary)compared.push(summary);continue}try{compared.push(await krugJson(`/api/cars/${id}`))}catch(_){}}krugCompareIds=compared.map(car=>Number(car.id)).filter(Boolean);saveKrugCompare();if(!compared.length)return toast('Выбранные объявления больше недоступны');let rows=[['Цена','price'],['Год','year'],['Пробег','km'],['Кузов','body_type'],['Коробка','transmission'],['Привод','drive'],['Топливо','fuel'],['Объём','engine'],['Мощность','power'],['Цвет','color'],['Владельцев','owners'],['Просмотры','views']];krugCompareContent.innerHTML=`<div class="compare-cars">${compared.map(car=>`<div class="compare-car"><img src="${safeImageSrc(car.image||car.thumbnail||hero)}" alt="${safeText(car.name)}"><b>${safeText(car.name)}</b><button type="button" onclick="toggleKrugCompare(event,${Number(car.id)});openKrugCompare()">Убрать</button></div>`).join('')}</div><div class="compare-table">${rows.map(([label,key])=>`<div class="compare-row"><b>${label}</b>${compared.map(car=>`<span>${krugCompareValue(car,key)}</span>`).join('')}</div>`).join('')}</div>`;krugCompareModal.classList.add('open')}finally{krugCompareBar.querySelector('button').classList.remove('busy')}}
function closeKrugCompare(){krugCompareModal.classList.remove('open')}
krugCompareBar.querySelector('button').addEventListener('click',openKrugCompare);krugCompareModal.querySelector('.compare-close').addEventListener('click',closeKrugCompare);krugCompareModal.addEventListener('click',event=>{if(event.target===krugCompareModal)closeKrugCompare()});paintKrugCompare();renderAll();

/* KRUG source block 46 */
// Full exchange flow: choose a car, write a message, track and cancel offers.
const krugExchangeCompose=document.createElement('div');krugExchangeCompose.className='modal exchange-compose';
krugExchangeCompose.innerHTML='<div class="sheet exchange-compose-sheet"><div class="grab"></div><div class="compare-head"><div><span class="eyebrow"><span class="dot"></span> предложение обмена</span><h2>Что предложить?</h2></div><button type="button" class="icon-btn exchange-compose-close">×</button></div><div class="exchange-target"></div><div class="field"><label>Вариант предложения</label><select id="exchangeOfferedCar"></select></div><div class="exchange-custom-fields"><div class="field"><label>Ваше предложение</label><textarea id="exchangeOfferText" maxlength="500" placeholder="Например: мотоцикл, техника, услуги или другой вариант"></textarea><small class="exchange-offer-count">0 / 500</small></div></div><div class="field"><label>Доплата, ₽ <span class="optional">необязательно</span></label><input id="exchangeCashAmount" type="number" min="0" max="100000000" inputmode="numeric" placeholder="0"></div><div class="field"><label>Комментарий продавцу</label><textarea id="exchangeMessage" maxlength="500" placeholder="Расскажите подробнее об условиях"></textarea><small class="exchange-message-count">0 / 500</small></div><button type="button" class="btn lime exchange-send">Отправить предложение</button></div>';document.body.append(krugExchangeCompose);
const exchangeOfferedCar=document.getElementById('exchangeOfferedCar'),exchangeOfferText=document.getElementById('exchangeOfferText'),exchangeCashAmount=document.getElementById('exchangeCashAmount'),exchangeMessage=document.getElementById('exchangeMessage'),krugExchangeTarget=krugExchangeCompose.querySelector('.exchange-target'),krugExchangeSend=krugExchangeCompose.querySelector('.exchange-send'),krugExchangeCustomFields=krugExchangeCompose.querySelector('.exchange-custom-fields');
function closeKrugExchangeCompose(){krugExchangeCompose.classList.remove('open')}
exchangeMessage.addEventListener('input',()=>krugExchangeCompose.querySelector('.exchange-message-count').textContent=`${exchangeMessage.value.length} / 500`);exchangeOfferText.addEventListener('input',()=>krugExchangeCompose.querySelector('.exchange-offer-count').textContent=`${exchangeOfferText.value.length} / 500`);exchangeOfferedCar.addEventListener('change',()=>krugExchangeCustomFields.classList.toggle('hidden',Number(exchangeOfferedCar.value)>0));krugExchangeCompose.querySelector('.exchange-compose-close').addEventListener('click',closeKrugExchangeCompose);krugExchangeCompose.addEventListener('click',event=>{if(event.target===krugExchangeCompose)closeKrugExchangeCompose()});
offerExchange=async function(){try{if(!krugOpenedDetail?.accept_exchange)return toast('Продавец не принимает обмен');let mine=(await krugJson('/api/my-cars')).filter(car=>car.status==='active'&&Number(car.id)!==Number(krugOpenedCar));exchangeOfferedCar.innerHTML='<option value="0">Другое предложение — без автомобиля</option>'+mine.map(car=>`<option value="${Number(car.id)}">Мой автомобиль: ${safeText(car.name)} · ${rub(Number(car.price)||0)}</option>`).join('');exchangeOfferText.value='';exchangeCashAmount.value='';exchangeMessage.value='';exchangeOfferText.dispatchEvent(new Event('input'));exchangeMessage.dispatchEvent(new Event('input'));exchangeOfferedCar.dispatchEvent(new Event('change'));krugExchangeTarget.innerHTML=`<small>Предлагаете обмен на</small><b>${safeText(krugOpenedDetail.name)}</b><span>${rub(Number(krugOpenedDetail.price)||0)}</span>`;closeModal();krugExchangeCompose.classList.add('open')}catch(error){toast(error.message)}};
async function sendKrugExchange(){if(krugExchangeSend.classList.contains('busy'))return;let offeredCarId=Number(exchangeOfferedCar.value)||0,offerText=exchangeOfferText.value.trim(),cashAmount=Number(exchangeCashAmount.value)||0;if(!offeredCarId&&offerText.length<3)return toast('Опишите, что вы предлагаете');if(cashAmount<0||cashAmount>100000000)return toast('Проверьте размер доплаты');krugExchangeSend.classList.add('busy');try{await krugJson('/api/exchanges',{method:'POST',body:JSON.stringify({target_car_id:Number(krugOpenedCar),offered_car_id:offeredCarId||null,offer_text:offerText,cash_amount:cashAmount,message:exchangeMessage.value.trim()})});closeKrugExchangeCompose();toast('Предложение отправлено продавцу');await krugLoadProfile()}catch(error){toast(error.message)}finally{krugExchangeSend.classList.remove('busy')}}
krugExchangeSend.addEventListener('click',sendKrugExchange);
function krugExchangeCard(item,incoming){let offeredImage=safeImageSrc(item.offered_image||hero),targetImage=safeImageSrc(item.target_image||hero),actions='',customOffer=!item.offered_car_id;if(item.status==='new')actions=incoming?`<div class="manage-actions"><button class="btn lime" onclick="answerExchange(${Number(item.id)},'accept')">Принять</button><button class="btn back" onclick="answerExchange(${Number(item.id)},'reject')">Отклонить</button></div>`:`<button class="exchange-cancel" onclick="cancelKrugExchange(${Number(item.id)})">Отменить предложение</button>`;let offered=customOffer?`<div class="exchange-custom-offer"><span>✦</span><b>Другое предложение</b><small>${safeText(item.offer_text||'Условия не указаны')}</small></div>`:`<div><img src="${offeredImage}" alt="${safeText(item.offered_name)}"><b>${safeText(item.offered_name||'Автомобиль')}</b><small>${item.offered_price?rub(Number(item.offered_price)):''}</small></div>`;return `<article class="exchange-card"><div class="exchange-direction"><span>${incoming?'Входящее':'Исходящее'}</span><b class="exchange-status ${safeText(item.status)}">${safeText(exchangeStatus[item.status]||item.status)}</b></div><div class="exchange-cars">${offered}<i>⇄</i><div><img src="${targetImage}" alt="${safeText(item.target_name)}"><b>${safeText(item.target_name)}</b><small>${item.target_price?rub(Number(item.target_price)):''}</small></div></div>${Number(item.cash_amount)>0?`<div class="exchange-cash">Доплата: <b>${rub(Number(item.cash_amount))}</b></div>`:''}${item.message?`<p>${safeText(item.message)}</p>`:''}${actions}</article>`}
showExchanges=async function(){try{let list=await krugJson('/api/exchanges'),incoming=list.filter(item=>String(item.target_owner_id)===krugUserId),outgoing=list.filter(item=>String(item.target_owner_id)!==krugUserId);go('catalog');document.querySelector('#catalog .page-head h1').textContent='Предложения обмена';document.querySelector('#catalog .page-head p').textContent='Входящие и отправленные предложения';document.getElementById('catalogCards').innerHTML=`<div class="exchange-group"><h3>Входящие <span>${incoming.length}</span></h3>${incoming.map(item=>krugExchangeCard(item,true)).join('')||'<div class="panel"><p class="meta">Новых входящих предложений нет.</p></div>'}</div><div class="exchange-group"><h3>Исходящие <span>${outgoing.length}</span></h3>${outgoing.map(item=>krugExchangeCard(item,false)).join('')||'<div class="panel"><p class="meta">Вы пока ничего не предлагали.</p></div>'}</div>`;krugMoreButton?.classList.remove('show')}catch(error){if(error.code==='legal_setup_required')return showKrugExchangeSetup();toast(error.message)}};
async function cancelKrugExchange(id){if(!confirm('Отменить предложение обмена?'))return;try{await krugJson(`/api/exchanges/${id}`,{method:'DELETE'});toast('Предложение отменено');await showExchanges();await krugLoadProfile()}catch(error){toast(error.message)}}
if(profileButtons[1])profileButtons[1].onclick=showExchanges;
const krugOpenBeforeExchangeUi=openCarV3;openCarV3=async function(...args){await krugOpenBeforeExchangeUi(...args);let button=document.querySelector('.sheet .exchange-action'),detail=krugOpenedDetail;if(button)button.hidden=!detail||detail.is_owner||!detail.accept_exchange};

/* KRUG source block 47 */
// Reliable profile identity and bounded listing publication on slow mobile connections.
const KRUG_PENDING_PUBLISH='krug_pending_publish_v1';
const krugPublishStatus=document.createElement('div');krugPublishStatus.className='publish-status';krugPublishStatus.setAttribute('role','status');krugPublishStatus.setAttribute('aria-live','polite');document.querySelector('#create .step[data-step="3"] .btn.lime')?.after(krugPublishStatus);
function krugPublishIdentity(data){
  let fingerprint=JSON.stringify([data.name,data.year,data.price,data.km,data.phone||'',(data.images||[]).length]);
  try{let saved=JSON.parse(localStorage.getItem(KRUG_PENDING_PUBLISH)||'null');if(saved?.fingerprint===fingerprint&&/^[A-Za-z0-9_-]{16,80}$/.test(saved.key))return saved.key}catch(_){}
  let key=(crypto.randomUUID?.()||`${Date.now()}-${Math.random().toString(36).slice(2)}`).replace(/[^A-Za-z0-9_-]/g,'');localStorage.setItem(KRUG_PENDING_PUBLISH,JSON.stringify({fingerprint,key}));return key
}
krugLoadProfile=async function(){
  try{
    let p=document.querySelector('.profile-card');if(!p)return;
    if(!krugInitData&&location.protocol!=='file:'){p.querySelector('h2').textContent='Гостевой просмотр';p.querySelector('.avatar').textContent='К';p.querySelector('p').textContent='Откройте КРУГ внутри Telegram для входа';p.querySelectorAll('.stat b').forEach(value=>value.textContent='0');return}
    let telegramName=[krugTgUser?.first_name,krugTgUser?.last_name].filter(Boolean).join(' ').trim(),initialName=telegramName||'Пользователь КРУГ';p.querySelector('h2').textContent=initialName;p.querySelector('.avatar').textContent=initialName.split(/\s+/).slice(0,2).map(part=>part[0]).join('').toUpperCase();
    let d=await krugJson('/api/me'),storedName=String(d.user?.first_name||'').trim(),name=telegramName||storedName||initialName;
    p.querySelector('h2').textContent=name;p.querySelector('.avatar').textContent=name.split(/\s+/).slice(0,2).map(part=>part[0]).join('').toUpperCase();
    p.querySelector('p').textContent=d.user?.role==='dealer'?`Дилер · ${d.user.company||'Компания'} · Екатеринбург`:'Частный продавец · Екатеринбург';
    let stats=p.querySelectorAll('.stat b');if(stats[0])stats[0].textContent=Number(d.listings)||0;if(stats[1])stats[1].textContent=Number(d.favourites)||0;if(stats[2])stats[2].textContent=Number(d.views)||0;
    krugProfileRole.textContent=d.user?.role==='dealer'?'Проверенный дилер':'Частный продавец';
    if(profileButtons[1])profileButtons[1].innerHTML=`Предложения обмена <span>${Number(d.offers)||0} ›</span>`;
    let role=d.staff_role||'',pending=Number(d.moderation_pending)||0;krugAdminButton.classList.toggle('show',!!role);krugAdminButton.innerHTML=`Модерация жалоб <span>${pending?`${pending} новых`:'›'}</span>`;krugStaffButton.classList.toggle('show',role==='owner'||role==='admin');
  }catch(error){console.warn('Profile refresh failed',error?.message||error)}
};
publish=async function(){
  let button=document.querySelector('#create .step[data-step="3"] .btn.lime');if(!button||button.classList.contains('busy'))return;let data;
  try{data=krugListingData()}catch(error){toast(error.message);return}
  if(location.protocol==='file:')return toast('Публикация работает внутри Telegram');
  if(navigator.onLine===false){krugPublishStatus.textContent='Нет подключения к интернету. Данные формы сохранены — попробуйте снова после подключения.';return toast('Нет подключения к интернету')}
  if(!krugEditingId)data.publish_key=krugPublishIdentity(data);
  let editing=krugEditingId,defaultLabel=editing?'Сохранить изменения':'Опубликовать бесплатно',controller=new AbortController(),seconds=0,timer=setTimeout(()=>controller.abort(),35000),ticker=setInterval(()=>{seconds+=1;krugPublishStatus.textContent=seconds<8?'Защищённо передаём данные…':seconds<20?'Загружаем фотографии — это может занять немного времени…':'Соединение медленное, продолжаем попытку…'},1000);
  button.classList.add('busy');button.textContent=editing?'Сохраняем…':'Публикуем…';
  krugPublishStatus.className='publish-status working';krugPublishStatus.textContent=editing?'Сохраняем изменения…':'Проверяем и публикуем объявление…';
  try{
    await krugJson(editing?`/api/cars/${editing}`:'/api/cars',{method:editing?'PUT':'POST',body:JSON.stringify(data),signal:controller.signal});
    if(!editing)localStorage.removeItem(KRUG_PENDING_PUBLISH);krugPublishStatus.className='publish-status success';krugPublishStatus.textContent=editing?'✓ Изменения сохранены':'✓ Объявление опубликовано';toast(editing?'Изменения сохранены':'Объявление опубликовано');krugResetListingForm();go('catalog');
    setTimeout(()=>{editing?showMyCars():krugLoadCars()},50);
  }catch(error){let message=error?.name==='AbortError'?'Сервер долго не отвечает. Форма сохранена — проверьте «Мои объявления» и попробуйте снова.':error.message;krugPublishStatus.className='publish-status error';krugPublishStatus.textContent=message;toast(message)}
  finally{clearTimeout(timer);clearInterval(ticker);button.classList.remove('busy');button.textContent=defaultLabel}
};
krugLoadProfile();

const krugLegalSetupBanner=document.createElement('div');krugLegalSetupBanner.className='legal-setup-banner';krugLegalSetupBanner.innerHTML='<b>Каталог работает в режиме просмотра</b><span>Личные функции откроются после завершения настройки оператора и российского хранения данных.</span>';document.querySelector('#home .hero')?.after(krugLegalSetupBanner);
loadKrugLegalInfo().then(info=>{krugLegalSetupBanner.classList.toggle('show',!info.ready||info.testing_mode);if(info.testing_mode){krugLegalSetupBanner.querySelector('b').textContent='КРУГ открыт для публичного тестирования';krugLegalSetupBanner.querySelector('span').textContent='Основные функции доступны всем пользователям Telegram. Юридическая и инфраструктурная подготовка продолжается.'}});

/* KRUG source block 52 */
// Launch-readiness details: explain safe browse mode without exposing credentials.
krugLegalSetupBanner.setAttribute('role','button');
krugLegalSetupBanner.setAttribute('tabindex','0');
krugLegalSetupBanner.setAttribute('aria-label','Показать готовность запуска');
krugLegalSetupBanner.insertAdjacentHTML('beforeend','<em>Посмотреть, что осталось настроить →</em>');
const krugReadinessModal=document.createElement('div');
krugReadinessModal.className='modal readiness-modal';
krugReadinessModal.innerHTML='<div class="sheet readiness-sheet"><div class="grab"></div><div class="compare-head"><div><span class="eyebrow"><span class="dot"></span> центр запуска</span><h2>Готовность КРУГ</h2></div><button type="button" class="icon-btn readiness-close" aria-label="Закрыть">×</button></div><p class="readiness-intro">Каталог уже доступен. Для публикации объявлений и других личных функций необходимо выполнить обязательные настройки.</p><div class="readiness-list"></div><div class="readiness-note">Токен Telegram и пароль базы здесь никогда не показываются.</div></div>';
document.body.append(krugReadinessModal);
function krugReadinessRow(done,title,text){return `<div class="readiness-row ${done?'done':'pending'}"><i>${done?'✓':'!'}</i><div><b>${safeText(title)}</b><span>${safeText(text)}</span></div></div>`}
async function openKrugReadiness(){
  let list=krugReadinessModal.querySelector('.readiness-list');
  list.innerHTML=krugReadinessRow(false,'Проверяем настройки','Получаем безопасный статус сервера…');
  krugReadinessModal.classList.add('open');
  try{
    let info=await loadKrugLegalInfo(),operatorReady=!!info.operator_configured||!!(info.operator_name&&info.operator_email&&info.operator_address),storageReady=!!info.data_residency_rf;
    list.innerHTML=krugReadinessRow(operatorReady,'Реквизиты оператора',operatorReady?'Название, адрес и контакт заполнены.':'Нужно указать настоящее имя/название оператора, адрес и электронную почту.')+krugReadinessRow(storageReady,'Хранение персональных данных в РФ',storageReady?'Российское размещение подтверждено.':'Нужно подключить базу на территории России и только затем подтвердить размещение.')+krugReadinessRow(!!info.ready,'Личные функции',info.ready?'Публикация, избранное, обмены и профиль доступны.':'Включатся автоматически после выполнения двух пунктов выше.');
  }catch(_){list.innerHTML=krugReadinessRow(false,'Сервер не ответил','Повторите проверку немного позже.')}
}
function closeKrugReadiness(){krugReadinessModal.classList.remove('open')}
krugLegalSetupBanner.addEventListener('click',openKrugReadiness);
krugLegalSetupBanner.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();openKrugReadiness()}});
krugReadinessModal.querySelector('.readiness-close').addEventListener('click',closeKrugReadiness);
krugReadinessModal.addEventListener('click',event=>{if(event.target===krugReadinessModal)closeKrugReadiness()});

/* KRUG source block 53 */
// Personal sections stay understandable while legally required production settings are incomplete.
function showKrugPersonalUnavailable(title){
  go('catalog');
  document.querySelector('#catalog .page-head h1').textContent=title;
  document.querySelector('#catalog .page-head p').textContent='Личный раздел КРУГ';
  document.getElementById('catalogCards').innerHTML='<div class="panel personal-unavailable"><i>◇</i><h3>Раздел скоро станет доступен</h3><p>Функция уже готова. Сейчас завершается обязательная настройка оператора и хранения персональных данных в России.</p><button type="button" class="btn back" onclick="openKrugReadiness()">Посмотреть готовность</button><button type="button" class="personal-catalog-link" onclick="go(\'catalog\');krugLoadCars()">Вернуться к автомобилям</button></div>';
  krugMoreButton?.classList.remove('show');
}
function showKrugExchangeSetup(){showKrugPersonalUnavailable('Предложения обмена')}
async function krugPersonalReady(){try{return !!(await loadKrugLegalInfo()).ready}catch(_){return false}}
const krugShowMyCarsWhenReady=showMyCars;
showMyCars=async function(){if(!await krugPersonalReady())return showKrugPersonalUnavailable('Мои объявления');return krugShowMyCarsWhenReady()};
const krugShowFavouritesWhenReady=showFavourites;
showFavourites=async function(){if(!await krugPersonalReady())return showKrugPersonalUnavailable('Избранное');return krugShowFavouritesWhenReady()};
const krugShowRecentWhenReady=showRecentlyViewed;
showRecentlyViewed=async function(){if(!await krugPersonalReady())return showKrugPersonalUnavailable('Недавно просмотренные');return krugShowRecentWhenReady()};
const krugShowExchangesWhenReady=showExchanges;
showExchanges=async function(){if(!await krugPersonalReady())return showKrugExchangeSetup();return krugShowExchangesWhenReady()};
const krugSaveFavouriteWhenReady=saveV2;
saveV2=async function(event,button,id){event?.preventDefault?.();event?.stopPropagation?.();if(!await krugPersonalReady()){showKrugPersonalUnavailable('Избранное');return}return krugSaveFavouriteWhenReady(event,button,id)};
const krugOfferExchangeWhenReady=offerExchange;
offerExchange=async function(){if(!await krugPersonalReady()){closeModal();return showKrugExchangeSetup()}return krugOfferExchangeWhenReady()};
const krugSubscribeWhenReady=subscribe;
subscribe=async function(button){if(!await krugPersonalReady()){openKrugReadiness();return}return krugSubscribeWhenReady(button)};
if(profileButtons[0])profileButtons[0].onclick=showMyCars;
if(profileButtons[1])profileButtons[1].onclick=showExchanges;
if(profileButtons[2])profileButtons[2].onclick=showFavourites;
krugRecentButton.onclick=showRecentlyViewed;
krugGarageCta.onclick=showMyCars;

/* KRUG source block 54 */
// Telegram-native listing links open KRUG and the exact vehicle in one tap.
const KRUG_BOT_USERNAME='Krug_ekb_bot';
function krugTelegramListingUrl(id){return `https://t.me/${KRUG_BOT_USERNAME}?startapp=car_${Number(id)}`}
function krugLinkedCarId(){
  let query=new URLSearchParams(location.search),raw=window.Telegram?.WebApp?.initDataUnsafe?.start_param||query.get('tgWebAppStartParam')||query.get('startapp')||'';
  let match=String(raw).match(/^car_(\d{1,12})$/);return Number(match?.[1]||query.get('car'))||0
}
krugListingUrl=function(id){return krugTelegramListingUrl(id)};
shareOpenedCar=async function(){
  let detail=krugOpenedDetail;if(!detail?.id)return toast('Сначала откройте объявление');
  let url=krugTelegramListingUrl(detail.id),text=`${detail.name} — ${rub(detail.price)} · Екатеринбург`;
  try{
    let telegramShare=`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
    if(window.Telegram?.WebApp?.openTelegramLink){Telegram.WebApp.openTelegramLink(telegramShare);return}
    if(navigator.share){await navigator.share({title:detail.name,text,url});return}
    await navigator.clipboard.writeText(`${text}\n${url}`);toast('Ссылка на объявление скопирована');
  }catch(error){if(error.name!=='AbortError')toast('Не удалось поделиться')}
};
async function openKrugTelegramListing(){
  let id=krugLinkedCarId();if(!id||window.krugDeepLinkOpened===id)return;window.krugDeepLinkOpened=id;
  try{
    let detail=location.protocol==='file:'?cars.find(car=>Number(car.id)===id):await krugJson(`/api/cars/${id}`);
    if(!detail)throw new Error('Объявление больше недоступно');
    let known=cars.find(car=>Number(car.id)===id);if(!known)cars.unshift(detail);
    go('catalog');await openCarV3(detail.id,detail.name,detail.price,detail.pos||'50% 50%',safeImageSrc(detail.image||detail.thumbnail||hero));
  }catch(error){window.krugDeepLinkOpened=0;toast(error.message||'Не удалось открыть объявление')}
}
setTimeout(openKrugTelegramListing,850);

/* KRUG source block 55 */
// Local buyer checklist: practical deal safety without collecting personal data.
const KRUG_BUYER_CHECKLIST='krug_buyer_checklist_v1';
const krugChecklistItems=[
  ['vin','Сверить VIN','Сравните VIN на кузове, в ПТС и СТС.'],
  ['limits','Проверить ограничения','Проверьте залог, розыск, регистрационные ограничения и историю ДТП.'],
  ['owner','Проверить продавца','Сверьте паспорт продавца с ПТС и правом распоряжаться автомобилем.'],
  ['service','Провести диагностику','Осмотрите автомобиль на независимом сервисе до оплаты.'],
  ['drive','Выполнить тест-драйв','Проверьте двигатель, коробку, тормоза, подвеску и электронику.'],
  ['contract','Оформить сделку безопасно','Заполните договор, акт передачи и не переводите предоплату незнакомому человеку.']
];
let krugChecklistCar=0;
const krugChecklistButton=document.createElement('button');krugChecklistButton.className='btn checklist-action';krugChecklistButton.textContent='✓ Проверка перед покупкой';document.querySelector('.sheet').insertBefore(krugChecklistButton,krugDetailFavourite);
const krugChecklistModal=document.createElement('div');krugChecklistModal.className='modal checklist-modal';krugChecklistModal.innerHTML='<div class="sheet checklist-sheet"><div class="grab"></div><div class="compare-head"><div><span class="eyebrow"><span class="dot"></span> безопасная покупка</span><h2>Проверьте автомобиль</h2></div><button type="button" class="icon-btn checklist-close" aria-label="Закрыть">×</button></div><p class="checklist-caption"></p><div class="checklist-progress"><i></i><span></span></div><div class="checklist-items"></div><button type="button" class="checklist-reset">Сбросить отметки</button></div>';document.body.append(krugChecklistModal);
function krugChecklistState(){try{return JSON.parse(localStorage.getItem(KRUG_BUYER_CHECKLIST)||'{}')}catch(_){return {}}}
function saveKrugChecklistState(state){localStorage.setItem(KRUG_BUYER_CHECKLIST,JSON.stringify(state))}
function paintKrugChecklist(){
  let all=krugChecklistState(),done=new Set(Array.isArray(all[krugChecklistCar])?all[krugChecklistCar]:[]),count=done.size;
  krugChecklistModal.querySelector('.checklist-caption').textContent=`${krugOpenedDetail?.name||'Автомобиль'} · ваш личный список`;
  krugChecklistModal.querySelector('.checklist-progress i').style.width=`${Math.round(count/krugChecklistItems.length*100)}%`;
  krugChecklistModal.querySelector('.checklist-progress span').textContent=`Выполнено ${count} из ${krugChecklistItems.length}`;
  krugChecklistModal.querySelector('.checklist-items').innerHTML=krugChecklistItems.map(([key,title,text])=>`<button type="button" class="checklist-item ${done.has(key)?'done':''}" data-check-key="${key}"><i>${done.has(key)?'✓':''}</i><span><b>${title}</b><small>${text}</small></span></button>`).join('');
}
function openKrugChecklist(){if(!krugOpenedDetail?.id)return toast('Сначала откройте объявление');krugChecklistCar=Number(krugOpenedDetail.id);paintKrugChecklist();krugChecklistModal.classList.add('open')}
function closeKrugChecklist(){krugChecklistModal.classList.remove('open')}
krugChecklistButton.addEventListener('click',openKrugChecklist);
krugChecklistModal.querySelector('.checklist-close').addEventListener('click',closeKrugChecklist);
krugChecklistModal.addEventListener('click',event=>{if(event.target===krugChecklistModal)closeKrugChecklist()});
krugChecklistModal.querySelector('.checklist-items').addEventListener('click',event=>{let button=event.target.closest('[data-check-key]');if(!button)return;let all=krugChecklistState(),items=new Set(Array.isArray(all[krugChecklistCar])?all[krugChecklistCar]:[]),key=button.dataset.checkKey;items.has(key)?items.delete(key):items.add(key);all[krugChecklistCar]=[...items];saveKrugChecklistState(all);paintKrugChecklist()});
krugChecklistModal.querySelector('.checklist-reset').addEventListener('click',()=>{let all=krugChecklistState();delete all[krugChecklistCar];saveKrugChecklistState(all);paintKrugChecklist()});

/* KRUG source block 56 */
// Live listing-quality assistant encourages complete, trustworthy adverts.
const krugQuality=document.createElement('div');krugQuality.className='listing-quality';krugQuality.innerHTML='<div class="quality-head"><span><b>Качество объявления</b><small>Заполните карточку — покупателю будет проще принять решение</small></span><strong>0%</strong></div><div class="quality-track"><i></i></div><p></p>';document.querySelector('#create .page-head')?.after(krugQuality);
function krugListingQuality(){
  let checks=[
    [carName.value.trim().length>=2,12,'Укажите марку и модель'],
    [Number(carYear.value)>=1950,8,'Добавьте год выпуска'],
    [Number(carPrice.value)>=1000,8,'Укажите цену'],
    [Number(carKm.value)>=0&&carKm.value!=='',6,'Укажите пробег'],
    [krugImagesData.length>0,18,'Добавьте хотя бы одну фотографию'],
    [carDescription.value.trim().length>=80,12,'Добавьте подробное описание от 80 символов'],
    [!!carTransmission.value,6,'Выберите коробку передач'],
    [!!carBodyType.value,6,'Выберите тип кузова'],
    [!!carDrive.value,5,'Укажите привод'],
    [!!carFuel.value,5,'Укажите тип топлива'],
    [Number(carEnginePower.value)>0,5,'Добавьте мощность двигателя'],
    [!!carColor.value.trim(),5,'Укажите цвет'],
    [Number(carOwners.value)>0,4,'Укажите количество владельцев']
  ];
  let score=checks.reduce((sum,[done,weight])=>sum+(done?weight:0),0),missing=checks.find(([done])=>!done)?.[2]||'Объявление отлично заполнено';return {score,missing}
}
function paintKrugListingQuality(){let {score,missing}=krugListingQuality();krugQuality.querySelector('strong').textContent=`${score}%`;krugQuality.querySelector('.quality-track i').style.width=`${score}%`;krugQuality.querySelector('p').textContent=score===100?'✓ Объявление готово привлекать покупателей':`Следующий шаг: ${missing}`;krugQuality.classList.toggle('complete',score===100)}
document.querySelectorAll('#create input,#create textarea,#create select').forEach(field=>{field.addEventListener('input',paintKrugListingQuality);field.addEventListener('change',paintKrugListingQuality)});
new MutationObserver(paintKrugListingQuality).observe(photoPreviews,{childList:true,subtree:true});
const krugNextStepBeforeQuality=nextStep;nextStep=function(step){let result=krugNextStepBeforeQuality(step);paintKrugListingQuality();return result};
paintKrugListingQuality();

/* KRUG source block 57 */
// Native report flow: clear reasons, optional comment and no browser prompt dialogs.
const krugReportOptions=[
  ['fraud','Подозрение на мошенничество','Просят предоплату, скрывают документы или вводят в заблуждение'],
  ['wrong_info','Неверные данные','Цена, характеристики, фотографии или описание не соответствуют автомобилю'],
  ['sold','Автомобиль уже продан','Объявление больше не актуально'],
  ['duplicate','Повторное объявление','Этот автомобиль опубликован несколько раз'],
  ['other','Другая причина','Опишите проблему в комментарии']
];
const krugReportModal=document.createElement('div');krugReportModal.className='modal report-modal';krugReportModal.innerHTML=`<div class="sheet report-sheet"><div class="grab"></div><div class="compare-head"><div><span class="eyebrow"><span class="dot"></span> помощь модерации</span><h2>Что не так с объявлением?</h2></div><button type="button" class="icon-btn report-close" aria-label="Закрыть">×</button></div><p class="report-caption">Жалоба не показывается продавцу. Модератор проверит объявление.</p><div class="report-reasons">${krugReportOptions.map(([key,title,text],index)=>`<label class="report-reason"><input type="radio" name="krug-report-reason" value="${key}" ${index===0?'checked':''}><i></i><span><b>${title}</b><small>${text}</small></span></label>`).join('')}</div><label class="field report-details"><span>Комментарий <small>необязательно</small></span><textarea maxlength="500" placeholder="Коротко опишите, что заметили"></textarea><em>0 / 500</em></label><button type="button" class="btn lime report-submit">Отправить жалобу</button></div>`;document.body.append(krugReportModal);
function closeKrugReport(){krugReportModal.classList.remove('open')}
function openKrugReport(){if(!krugOpenedDetail||krugOpenedDetail.is_owner)return toast('Это ваше объявление');krugReportModal.querySelector('textarea').value='';krugReportModal.querySelector('.report-details em').textContent='0 / 500';krugReportModal.querySelector('input[value="fraud"]').checked=true;krugReportModal.querySelector('.report-submit').disabled=false;krugReportModal.querySelector('.report-submit').textContent='Отправить жалобу';krugReportModal.classList.add('open')}
async function submitKrugReport(){
  let submit=krugReportModal.querySelector('.report-submit'),reason=krugReportModal.querySelector('input[name="krug-report-reason"]:checked')?.value,details=krugReportModal.querySelector('textarea').value.trim();
  if(!reason)return toast('Выберите причину');submit.disabled=true;submit.textContent='Отправляем…';
  try{let r=await krugApi(`/api/cars/${krugOpenedCar}/report`,{method:'POST',body:JSON.stringify({reason,details})}),d=await r.json();if(!r.ok)throw new Error(d.error||'Не удалось отправить жалобу');reportButton.disabled=true;reportButton.textContent='✓ Жалоба отправлена';closeKrugReport();toast(d.under_review?'Объявление отправлено на проверку':'Спасибо, мы проверим объявление')}
  catch(error){submit.disabled=false;submit.textContent='Отправить жалобу';toast(error.message)}
}
reportButton.onclick=openKrugReport;
krugReportModal.querySelector('.report-close').addEventListener('click',closeKrugReport);
krugReportModal.addEventListener('click',event=>{if(event.target===krugReportModal)closeKrugReport()});
krugReportModal.querySelector('textarea').addEventListener('input',event=>{krugReportModal.querySelector('.report-details em').textContent=`${event.target.value.length} / 500`});
krugReportModal.querySelector('.report-submit').addEventListener('click',submitKrugReport);

/* KRUG source block 58 */
// Account deletion uses an explicit in-app confirmation instead of a browser prompt.
const krugDeleteModal=document.createElement('div');krugDeleteModal.className='modal delete-account-modal';krugDeleteModal.innerHTML='<div class="sheet delete-account-sheet"><div class="grab"></div><div class="compare-head"><div><span class="eyebrow"><span class="dot"></span> управление профилем</span><h2>Удалить аккаунт?</h2></div><button type="button" class="icon-btn delete-account-close" aria-label="Закрыть">×</button></div><p>Будут удалены профиль, объявления, избранное, подписки и предложения обмена. Отменить это действие будет нельзя.</p><label class="field"><span>Для подтверждения напишите <b>УДАЛИТЬ</b></span><input autocomplete="off" maxlength="7" placeholder="УДАЛИТЬ"></label><div class="delete-account-actions"><button type="button" class="btn delete-account-confirm" disabled>Удалить навсегда</button><button type="button" class="btn back delete-account-cancel">Отмена</button></div></div>';document.body.append(krugDeleteModal);
function closeKrugDelete(){krugDeleteModal.classList.remove('open')}
deleteAccount=function(){let input=krugDeleteModal.querySelector('input');input.value='';krugDeleteModal.querySelector('.delete-account-confirm').disabled=true;krugDeleteModal.classList.add('open');setTimeout(()=>input.focus(),120)};
krugDeleteModal.querySelector('input').addEventListener('input',event=>{krugDeleteModal.querySelector('.delete-account-confirm').disabled=event.target.value.trim().toUpperCase()!=='УДАЛИТЬ'});
krugDeleteModal.querySelector('.delete-account-close').addEventListener('click',closeKrugDelete);krugDeleteModal.querySelector('.delete-account-cancel').addEventListener('click',closeKrugDelete);krugDeleteModal.addEventListener('click',event=>{if(event.target===krugDeleteModal)closeKrugDelete()});
krugDeleteModal.querySelector('.delete-account-confirm').addEventListener('click',async event=>{let button=event.currentTarget;button.disabled=true;button.textContent='Удаляем…';try{let response=await krugApi('/api/account',{method:'DELETE'}),data=await response.json();if(!response.ok)throw new Error(data.error||'Не удалось удалить аккаунт');['krug_user','krug_legal_accepted','krug_privacy_version','krug_rules_version','krug_listing_draft_v1',KRUG_BUYER_CHECKLIST].forEach(key=>localStorage.removeItem(key));closeKrugDelete();toast('Аккаунт удалён');setTimeout(()=>location.reload(),900)}catch(error){button.disabled=false;button.textContent='Удалить навсегда';toast(error.message)}});

/* KRUG source block 59 */
// One consistent confirmation sheet for reversible management actions.
let krugConfirmAction=null;
const krugConfirmModal=document.createElement('div');krugConfirmModal.className='modal confirm-modal';krugConfirmModal.innerHTML='<div class="sheet confirm-sheet"><div class="grab"></div><div class="confirm-symbol">!</div><h2></h2><p></p><div class="confirm-actions"><button type="button" class="btn confirm-yes"></button><button type="button" class="btn back confirm-no">Отмена</button></div></div>';document.body.append(krugConfirmModal);
function closeKrugConfirm(){krugConfirmModal.classList.remove('open');krugConfirmAction=null}
function askKrugConfirm({title,text,action='Продолжить',danger=false,onConfirm}){krugConfirmModal.querySelector('h2').textContent=title;krugConfirmModal.querySelector('p').textContent=text;let yes=krugConfirmModal.querySelector('.confirm-yes');yes.textContent=action;yes.classList.toggle('danger',danger);yes.disabled=false;krugConfirmAction=onConfirm;krugConfirmModal.classList.add('open')}
krugConfirmModal.querySelector('.confirm-no').addEventListener('click',closeKrugConfirm);krugConfirmModal.addEventListener('click',event=>{if(event.target===krugConfirmModal)closeKrugConfirm()});
krugConfirmModal.querySelector('.confirm-yes').addEventListener('click',async event=>{if(!krugConfirmAction)return;let button=event.currentTarget,run=krugConfirmAction;button.disabled=true;button.textContent='Подождите…';try{await run();closeKrugConfirm()}catch(error){button.disabled=false;button.textContent='Повторить';toast(error.message||'Не удалось выполнить действие')}});
deleteCar=function(id){askKrugConfirm({title:'Удалить объявление?',text:'Оно исчезнет из каталога и восстановить его будет нельзя.',action:'Удалить объявление',danger:true,onConfirm:async()=>{await krugJson(`/api/cars/${id}`,{method:'DELETE'});toast('Объявление удалено');await showMyCars();await krugLoadCars()}})};
removeStaff=function(id){askKrugConfirm({title:'Снять доступ?',text:'Сотрудник больше не сможет модерировать объявления и жалобы.',action:'Снять доступ',danger:true,onConfirm:async()=>{await krugJson(`/api/admin/staff/${encodeURIComponent(id)}`,{method:'DELETE'});toast('Доступ снят');await showStaff()}})};
cancelKrugExchange=function(id){askKrugConfirm({title:'Отменить предложение?',text:'Получатель больше не сможет принять это предложение обмена.',action:'Отменить предложение',danger:true,onConfirm:async()=>{await krugJson(`/api/exchanges/${id}`,{method:'DELETE'});toast('Предложение отменено');await showExchanges();await krugLoadProfile()}})};
markCarSold=function(id){askKrugConfirm({title:'Автомобиль продан?',text:'Объявление исчезнет из общего каталога. Позже его можно будет вернуть в продажу из раздела «Мои объявления».',action:'Да, автомобиль продан',onConfirm:async()=>{await krugJson(`/api/cars/${id}`,{method:'PUT',body:JSON.stringify({action:'sold'})});toast('Поздравляем с продажей!');await showMyCars();await krugLoadCars()}})};
document.addEventListener('keydown',event=>{if(event.key!=='Escape')return;if(krugConfirmModal.classList.contains('open'))closeKrugConfirm();else if(krugDeleteModal.classList.contains('open'))closeKrugDelete();else if(krugReportModal.classList.contains('open'))closeKrugReport()});

/* KRUG source block 48 */
// Mobile photo manager: compact payload, visible size and removal before publishing.
function krugThumbnailFromData(src){return new Promise(resolve=>{if(!src)return resolve('');let img=new Image();img.onload=()=>{let max=420,scale=Math.min(1,max/Math.max(img.width,img.height)),canvas=document.createElement('canvas');canvas.width=Math.round(img.width*scale);canvas.height=Math.round(img.height*scale);canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);resolve(canvas.toDataURL('image/jpeg',.6))};img.onerror=()=>resolve('');img.src=src})}
photoPreviews.addEventListener('click',async event=>{let button=event.target.closest('[data-remove-photo]'),item=event.target.closest('[data-photo-index]'),index=Number(button?.dataset.removePhoto??item?.dataset.photoIndex);if(!Number.isInteger(index)||index<0||index>=krugImagesData.length)return;if(button){krugImagesData.splice(index,1);toast('Фотография удалена')}else if(index>0){let [cover]=krugImagesData.splice(index,1);krugImagesData.unshift(cover);toast('Обложка изменена')}else return;krugImageData=krugImagesData[0]||'';krugThumbnailData=await krugThumbnailFromData(krugImageData);krugRenderPhotoPreviews();carImage.value=''});
const krugEditBeforePhotoManager=editCar;editCar=async function(id){await krugEditBeforePhotoManager(id);if(krugEditingId===id)krugRenderPhotoPreviews()};

/* KRUG source block 60 */
// Public web preview never impersonates a demo Telegram user.
if(!krugInitData&&location.protocol!=='file:'){
  let profile=document.querySelector('#profile .profile-card'),stats=profile?.querySelectorAll('.stat b');
  if(profile){profile.querySelector('.avatar').textContent='К';profile.querySelector('h2').textContent='Гостевой просмотр';profile.querySelector('p').textContent='Откройте КРУГ внутри Telegram для входа';}
  stats?.forEach(value=>value.textContent='0');
  if(krugVerified)krugVerified.innerHTML='<i>↗</i><span>Вход выполняется безопасно через Telegram</span>';
  if(krugProfileRole)krugProfileRole.textContent='Публичный каталог';
}
window.addEventListener('pageshow',()=>setTimeout(()=>{if(!krugEditingId){restoreKrugDraft(true);restoreKrugDraftDealSwitches();paintKrugListingQuality()}},0),{once:true});
document.querySelector('#create').addEventListener('focusin',event=>event.target.closest('.field')?.classList.add('typing'));
document.querySelector('#create').addEventListener('focusout',event=>event.target.closest('.field')?.classList.remove('typing'));
