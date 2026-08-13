"""KRUG marketplace API: users, listings, favourites, subscriptions and exchanges."""
import hashlib, hmac, json, os, re, sqlite3, threading, time
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlparse
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get("KRUG_DB_PATH",ROOT/"krug.db"))
DATABASE_URL=os.environ.get("DATABASE_URL","")
BOT_TOKEN=(os.environ.get("BOT_TOKEN") or os.environ.get("KRUG_BOT_TOKEN") or "").strip()
PUBLIC_URL=os.environ.get("PUBLIC_URL","https://krug-ekb.onrender.com/index.html")
WEBHOOK_SECRET=hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32] if BOT_TOKEN else ""
NOW=lambda: datetime.now(timezone.utc)
RATE_BUCKETS={}; RATE_LOCK=threading.Lock()

def rate_allowed(key,limit,window):
    now=time.time()
    with RATE_LOCK:
        recent=[x for x in RATE_BUCKETS.get(key,[]) if now-x<window]
        if len(recent)>=limit: return False
        recent.append(now); RATE_BUCKETS[key]=recent
        return True

class PGCursor:
    def __init__(self,cursor,lastrowid=None): self.cursor=cursor; self.lastrowid=lastrowid
    def fetchone(self): return self.cursor.fetchone()
    def fetchall(self): return self.cursor.fetchall()
    @property
    def rowcount(self): return self.cursor.rowcount

class PGConnection:
    def __init__(self):
        import psycopg
        from psycopg.rows import dict_row
        self.db=psycopg.connect(DATABASE_URL,row_factory=dict_row)
    def execute(self,sql,params=()):
        sql=sql.replace("?","%s")
        if sql.startswith("INSERT OR IGNORE INTO subscriptions"):
            sql=sql.replace("INSERT OR IGNORE","INSERT",1)+" ON CONFLICT(telegram_user,kind) DO NOTHING"
        wants_id=sql.lstrip().startswith("INSERT INTO cars(") and "RETURNING" not in sql
        cur=self.db.execute(sql+(" RETURNING id" if wants_id else ""),params)
        last=cur.fetchone()["id"] if wants_id else None
        return PGCursor(cur,last)
    def executemany(self,sql,rows):
        cur=self.db.cursor(); cur.executemany(sql.replace("?","%s"),rows); return cur
    def executescript(self,sql):
        for statement in sql.split(";"):
            if statement.strip(): self.db.execute(statement)
    def __enter__(self): return self
    def __exit__(self,typ,val,tb):
        self.db.commit() if typ is None else self.db.rollback(); self.db.close()

def connect():
    if DATABASE_URL: return PGConnection()
    db=sqlite3.connect(DB); db.row_factory=sqlite3.Row; db.execute("PRAGMA foreign_keys=ON"); return db

def add_column(db,table,column,definition):
    if DATABASE_URL:
        db.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}"); return
    if column not in {r[1] for r in db.execute(f"PRAGMA table_info({table})")}:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

def init_db():
    DB.parent.mkdir(parents=True,exist_ok=True)
    with connect() as db:
        car_id="BIGSERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY"
        generic_id="BIGSERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY"
        ref_id="BIGINT" if DATABASE_URL else "INTEGER"
        db.executescript(f"""
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, first_name TEXT NOT NULL, username TEXT DEFAULT '', role TEXT NOT NULL DEFAULT 'private', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cars(id {car_id}, name TEXT NOT NULL, price INTEGER NOT NULL, year INTEGER NOT NULL, km TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'Продажа', urgent INTEGER NOT NULL DEFAULT 0, pos TEXT NOT NULL DEFAULT '50% 50%', description TEXT DEFAULT '', phone TEXT DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS favourites(user_id TEXT NOT NULL, car_id {ref_id} NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(user_id,car_id), FOREIGN KEY(car_id) REFERENCES cars(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS subscriptions(id {generic_id}, telegram_user TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'urgent', created_at TEXT NOT NULL, UNIQUE(telegram_user,kind));
        CREATE TABLE IF NOT EXISTS exchanges(id {generic_id}, from_user TEXT NOT NULL, target_car_id {ref_id} NOT NULL, offered_car_id {ref_id}, message TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL, FOREIGN KEY(target_car_id) REFERENCES cars(id) ON DELETE CASCADE, FOREIGN KEY(offered_car_id) REFERENCES cars(id) ON DELETE SET NULL);
        CREATE TABLE IF NOT EXISTS reports(id {generic_id}, reporter_id TEXT NOT NULL, car_id {ref_id} NOT NULL, reason TEXT NOT NULL, details TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL, UNIQUE(reporter_id,car_id), FOREIGN KEY(car_id) REFERENCES cars(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS car_views(viewer_id TEXT NOT NULL, car_id {ref_id} NOT NULL, view_day TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(viewer_id,car_id,view_day), FOREIGN KEY(car_id) REFERENCES cars(id) ON DELETE CASCADE);
        """)
        add_column(db,"cars","owner_id","TEXT NOT NULL DEFAULT 'demo'")
        add_column(db,"cars","status","TEXT NOT NULL DEFAULT 'active'")
        add_column(db,"cars","urgent_until","TEXT DEFAULT NULL")
        add_column(db,"cars","updated_at","TEXT DEFAULT NULL")
        add_column(db,"cars","image","TEXT DEFAULT ''")
        add_column(db,"cars","images","TEXT DEFAULT '[]'")
        add_column(db,"cars","transmission","TEXT DEFAULT ''")
        add_column(db,"cars","body_type","TEXT DEFAULT ''")
        add_column(db,"cars","drive","TEXT DEFAULT ''")
        add_column(db,"cars","vin","TEXT DEFAULT ''")
        add_column(db,"users","company","TEXT DEFAULT ''")
        count_row=db.execute("SELECT COUNT(*) AS count FROM cars").fetchone()
        if not (count_row["count"] if DATABASE_URL else count_row[0]):
            seed=[("Toyota RAV4",2890000,2021,"54 000 км","Продажа",0,"70% 50%"),("Kia K5",2470000,2020,"72 000 км","Обмен",0,"18% 50%"),("Lada Granta",690000,2019,"91 000 км","Срочно",1,"49% 50%"),("Hyundai Solaris",1450000,2018,"86 000 км","Срочно",1,"48% 50%"),("Ford Focus",290000,2007,"181 000 км","Обмен",0,"23% 50%"),("ВАЗ 2114",95000,2008,"210 000 км","Срочно",1,"48% 50%")]
            now=NOW().isoformat(); urgent=(NOW()+timedelta(hours=24)).isoformat()
            db.executemany("INSERT INTO cars(name,price,year,km,type,urgent,pos,created_at,updated_at,urgent_until) VALUES(?,?,?,?,?,?,?,?,?,?)",[(*x,now,now,urgent if x[5] else None) for x in seed])

def validate_telegram_init_data(raw,max_age=86400):
    """Return the verified Telegram user, or None when initData is invalid/expired."""
    if not BOT_TOKEN or not raw: return None
    try:
        fields=dict(parse_qsl(raw,keep_blank_values=True)); received=fields.pop("hash","")
        if not received: return None
        check="\n".join(f"{key}={fields[key]}" for key in sorted(fields))
        secret=hmac.new(b"WebAppData",BOT_TOKEN.encode("utf-8"),hashlib.sha256).digest()
        calculated=hmac.new(secret,check.encode("utf-8"),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated,received): return None
        auth_date=int(fields.get("auth_date","0"))
        if auth_date<=0 or abs(int(time.time())-auth_date)>max_age: return None
        user=json.loads(fields.get("user","{}"))
        return user if isinstance(user,dict) and user.get("id") else None
    except (ValueError,TypeError,json.JSONDecodeError): return None

def auth_context(headers,data=None,query=None):
    tg_user=validate_telegram_init_data(headers.get("X-Telegram-Init-Data", ""))
    if tg_user: return str(tg_user["id"]),True,tg_user
    return user_id(headers,data,query),not BOT_TOKEN,None

def user_id(headers,data=None,query=None):
    value=headers.get("X-Krug-User") or (data or {}).get("user") or (query or {}).get("user",["local-user"])[0]
    return re.sub(r"[^a-zA-Z0-9_-]","",str(value))[:80] or "local-user"

def car_dict(row,faved=False):
    d=dict(row); until=d.get("urgent_until")
    if d.get("urgent") and until:
        try:
            if datetime.fromisoformat(until)<NOW(): d["urgent"]=0; d["type"]="Продажа"
        except ValueError: pass
    try: d["images"]=json.loads(d.get("images") or "[]")
    except (TypeError,json.JSONDecodeError): d["images"]=[]
    if not d["images"] and d.get("image"): d["images"]=[d["image"]]
    d["favourite"]=bool(faved); return d

def notify_urgent(car_id,name,price):
    """Send urgent-listing alerts in the background when a Telegram token is configured."""
    if not BOT_TOKEN: return
    try:
        with connect() as db: rows=db.execute("SELECT telegram_user FROM subscriptions WHERE kind='urgent'").fetchall()
        subscribers=[str(r["telegram_user"] if DATABASE_URL else r[0]) for r in rows]
        text=f"⚡ Срочное авто в Екатеринбурге\n\n{name}\n{price:,} ₽".replace(","," ")+"\n\nОткройте КРУГ, чтобы посмотреть объявление."
        for chat_id in subscribers:
            if not chat_id.isdigit(): continue
            payload=json.dumps({"chat_id":chat_id,"text":text,"reply_markup":{"inline_keyboard":[[{"text":"Открыть КРУГ","web_app":{"url":PUBLIC_URL}}]]}},ensure_ascii=False).encode("utf-8")
            try: urlopen(Request(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",data=payload,headers={"Content-Type":"application/json"}),timeout=8).read()
            except Exception as exc: print(f"Telegram alert failed for {chat_id}: {exc}")
    except Exception as exc: print(f"Telegram alerts unavailable: {exc}")

def telegram_call(method,payload):
    raw=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    return json.load(urlopen(Request(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",data=raw,headers={"Content-Type":"application/json"}),timeout=12))

def notify_exchange_user(chat_id,text):
    if not BOT_TOKEN or not str(chat_id).isdigit(): return
    try: telegram_call("sendMessage",{"chat_id":str(chat_id),"text":text,"reply_markup":{"inline_keyboard":[[{"text":"Открыть КРУГ","web_app":{"url":PUBLIC_URL}}]]}})
    except Exception as exc: print(f"Exchange notification failed for {chat_id}: {exc}")

def telegram_welcome(update):
    message=update.get("message") or {}; text=str(message.get("text") or "")
    if not text.startswith("/start"): return
    chat_id=(message.get("chat") or {}).get("id"); first=(message.get("from") or {}).get("first_name") or ""
    if not chat_id: return
    greeting=f"Добро пожаловать в КРУГ, {first}!" if first else "Добро пожаловать в КРУГ!"
    telegram_call("sendMessage",{"chat_id":chat_id,"text":greeting+"\n\nАвтомобили Екатеринбурга: покупка, продажа, обмен и срочные объявления.","reply_markup":{"inline_keyboard":[[{"text":"Открыть КРУГ","web_app":{"url":PUBLIC_URL}}]]}})

def setup_telegram_webhook():
    if not BOT_TOKEN: return
    try:
        base=PUBLIC_URL.split("/index.html",1)[0].rstrip("/")
        webhook=f"{base}/api/telegram/{WEBHOOK_SECRET}"
        telegram_call("setWebhook",{"url":webhook,"allowed_updates":["message"]})
        telegram_call("setChatMenuButton",{"menu_button":{"type":"web_app","text":"Открыть КРУГ","web_app":{"url":PUBLIC_URL}}})
        telegram_call("setMyCommands",{"commands":[{"command":"start","description":"Открыть КРУГ"}]})
        print("Telegram webhook configured")
    except Exception as exc: print(f"Telegram webhook unavailable: {exc}")

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
    def send_json(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False).encode("utf-8"); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.send_header("X-Content-Type-Options","nosniff"); self.send_header("Referrer-Policy","no-referrer"); self.send_header("Permissions-Policy","camera=(), microphone=(), geolocation=()"); self.end_headers(); self.wfile.write(raw)
    def end_headers(self):
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("X-Frame-Options","SAMEORIGIN")
        super().end_headers()
    def read_json(self):
        n=int(self.headers.get("Content-Length","0"))
        if n>12_000_000: raise ValueError("Слишком большой запрос")
        return json.loads(self.rfile.read(n) or b"{}")
    def require_auth(self,authenticated):
        if authenticated: return True
        self.send_json({"error":"Откройте КРУГ через Telegram, чтобы выполнить это действие"},401); return False
    def do_GET(self):
        parsed=urlparse(self.path); path=parsed.path; query=parse_qs(parsed.query); uid,authenticated,_=auth_context(self.headers,query=query)
        if path=="/api/health": return self.send_json({"ok":True,"service":"krug","version":7,"database":"postgres" if DATABASE_URL else "sqlite","notifications":bool(BOT_TOKEN),"telegram_auth":bool(BOT_TOKEN)})
        if path=="/api/cars":
            with connect() as db:
                rows=db.execute("""SELECT c.*,u.role AS seller_role,u.company AS seller_company,
                    EXISTS(SELECT 1 FROM favourites f WHERE f.car_id=c.id AND f.user_id=?) AS faved
                    FROM cars c LEFT JOIN users u ON u.id=c.owner_id
                    WHERE c.status='active' ORDER BY c.urgent DESC,c.id DESC""",(uid,)).fetchall()
            return self.send_json([car_dict(r,r["faved"]) for r in rows])
        detail=re.fullmatch(r"/api/cars/(\d+)",path)
        if detail:
            with connect() as db:
                row=db.execute("""SELECT c.*,u.first_name AS seller_name,u.username AS seller_username,u.role AS seller_role,u.company AS seller_company,
                    EXISTS(SELECT 1 FROM favourites f WHERE f.car_id=c.id AND f.user_id=?) AS faved
                    FROM cars c LEFT JOIN users u ON u.id=c.owner_id
                    WHERE c.id=? AND (c.status='active' OR c.owner_id=?)""",(uid,int(detail.group(1)),uid)).fetchone()
            if not row: return self.send_json({"error":"Объявление не найдено"},404)
            with connect() as db:
                if row["owner_id"]!=uid:
                    try: db.execute("INSERT INTO car_views(viewer_id,car_id,view_day,created_at) VALUES(?,?,?,?) ON CONFLICT(viewer_id,car_id,view_day) DO NOTHING",(uid,int(detail.group(1)),NOW().date().isoformat(),NOW().isoformat()))
                    except sqlite3.IntegrityError: pass
                vr=db.execute("SELECT COUNT(*) AS count FROM car_views WHERE car_id=?",(int(detail.group(1)),)).fetchone(); favr=db.execute("SELECT COUNT(*) AS count FROM favourites WHERE car_id=?",(int(detail.group(1)),)).fetchone()
            data=car_dict(row,row["faved"]); data["is_owner"]=data.get("owner_id")==uid; data["views"]=vr["count"] if DATABASE_URL else vr[0]; data["favourites_count"]=favr["count"] if DATABASE_URL else favr[0]
            return self.send_json(data)
        if path=="/api/stats":
            with connect() as db:
                ur=db.execute("SELECT COUNT(*) AS count FROM cars WHERE status='active' AND urgent=1 AND (urgent_until IS NULL OR urgent_until>?)",(NOW().isoformat(),)).fetchone()
                ar=db.execute("SELECT COUNT(*) AS count FROM cars WHERE status='active'").fetchone()
            return self.send_json({"urgent":ur["count"] if DATABASE_URL else ur[0],"active":ar["count"] if DATABASE_URL else ar[0]})
        if path=="/api/subscriptions":
            if not self.require_auth(authenticated): return
            with connect() as db: row=db.execute("SELECT 1 FROM subscriptions WHERE telegram_user=? AND kind='urgent'",(uid,)).fetchone()
            return self.send_json({"urgent":bool(row)})
        if path=="/api/favourites":
            if not self.require_auth(authenticated): return
            with connect() as db:
                rows=db.execute("""SELECT c.*,u.role AS seller_role,u.company AS seller_company,1 AS faved
                    FROM favourites f JOIN cars c ON c.id=f.car_id LEFT JOIN users u ON u.id=c.owner_id
                    WHERE f.user_id=? AND c.status='active' ORDER BY f.created_at DESC""",(uid,)).fetchall()
            return self.send_json([car_dict(r,True) for r in rows])
        if path=="/api/me":
            if not self.require_auth(authenticated): return
            with connect() as db:
                u=db.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); lr=db.execute("SELECT COUNT(*) AS count FROM cars WHERE owner_id=? AND status='active'",(uid,)).fetchone(); fr=db.execute("SELECT COUNT(*) AS count FROM favourites WHERE user_id=?",(uid,)).fetchone(); er=db.execute("SELECT COUNT(*) AS count FROM exchanges e JOIN cars c ON c.id=e.target_car_id WHERE c.owner_id=? AND e.status='new'",(uid,)).fetchone(); sr=db.execute("SELECT COUNT(*) AS count FROM subscriptions WHERE telegram_user=?",(uid,)).fetchone(); listings=lr["count"] if DATABASE_URL else lr[0]; favs=fr["count"] if DATABASE_URL else fr[0]; offers=er["count"] if DATABASE_URL else er[0]; subscriptions=sr["count"] if DATABASE_URL else sr[0]
            return self.send_json({"user":dict(u) if u else None,"listings":listings,"favourites":favs,"offers":offers,"subscriptions":subscriptions})
        if path=="/api/my-cars":
            if not self.require_auth(authenticated): return
            with connect() as db: rows=db.execute("""SELECT c.*, (SELECT COUNT(*) FROM reports r WHERE r.car_id=c.id) AS report_count,
                (SELECT COUNT(*) FROM car_views v WHERE v.car_id=c.id) AS views,
                (SELECT COUNT(*) FROM favourites f WHERE f.car_id=c.id) AS favourites_count
                FROM cars c WHERE c.owner_id=? AND c.status<>'deleted' ORDER BY c.id DESC""",(uid,)).fetchall()
            return self.send_json([car_dict(r) for r in rows])
        if path=="/api/exchanges":
            if not self.require_auth(authenticated): return
            with connect() as db:
                rows=db.execute("""SELECT e.*, target.name AS target_name, target.owner_id AS target_owner_id,
                    offered.name AS offered_name, sender.first_name AS sender_name, sender.username AS sender_username
                    FROM exchanges e JOIN cars target ON target.id=e.target_car_id
                    LEFT JOIN cars offered ON offered.id=e.offered_car_id
                    LEFT JOIN users sender ON sender.id=e.from_user
                    WHERE e.from_user=? OR target.owner_id=? ORDER BY e.id DESC""",(uid,uid)).fetchall()
            return self.send_json([dict(r) for r in rows])
        if path=="/api/export":
            if not self.require_auth(authenticated): return
            with connect() as db:
                user=db.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
                cars_rows=db.execute("SELECT * FROM cars WHERE owner_id=? AND status<>'deleted' ORDER BY id",(uid,)).fetchall()
                favourites=db.execute("SELECT car_id,created_at FROM favourites WHERE user_id=? ORDER BY created_at",(uid,)).fetchall()
                subscriptions=db.execute("SELECT kind,created_at FROM subscriptions WHERE telegram_user=? ORDER BY created_at",(uid,)).fetchall()
                exchanges=db.execute("SELECT * FROM exchanges WHERE from_user=? OR EXISTS(SELECT 1 FROM cars WHERE cars.id=exchanges.target_car_id AND cars.owner_id=?) ORDER BY id",(uid,uid)).fetchall()
            return self.send_json({"exported_at":NOW().isoformat(),"user":dict(user) if user else None,"cars":[car_dict(r) for r in cars_rows],"favourites":[dict(r) for r in favourites],"subscriptions":[dict(r) for r in subscriptions],"exchanges":[dict(r) for r in exchanges]})
        if path.endswith((".py",".db",".sqlite",".yaml",".yml",".txt")) or path.startswith("/.git"):
            return self.send_json({"error":"Not found"},404)
        return super().do_GET()
    def do_POST(self):
        try:
            path=urlparse(self.path).path; data=self.read_json(); now=NOW().isoformat()
            if BOT_TOKEN and path==f"/api/telegram/{WEBHOOK_SECRET}":
                threading.Thread(target=telegram_welcome,args=(data,),daemon=True).start()
                return self.send_json({"ok":True})
            uid,authenticated,tg_user=auth_context(self.headers,data=data)
            if not self.require_auth(authenticated): return
            if path=="/api/session":
                first=str(data.get("first_name") or "Пользователь")[:80]; username=str(data.get("username") or "")[:80]
                with connect() as db: db.execute("INSERT INTO users(id,first_name,username,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET first_name=excluded.first_name,username=excluded.username,updated_at=excluded.updated_at",(uid,first,username,now,now))
                return self.send_json({"ok":True,"user":uid})
            if path=="/api/cars":
                if not rate_allowed((uid,"create"),10,3600): return self.send_json({"error":"Слишком много объявлений. Попробуйте позже"},429)
                name=str(data.get("name","")).strip(); price=int(data.get("price") or 0); year=int(data.get("year") or 0); km=int(str(data.get("km","0")).replace(" км","").replace(" ","") or 0)
                if len(name)<2 or price<1000 or not 1950<=year<=NOW().year+1 or km<0: return self.send_json({"error":"Проверьте марку, цену, год и пробег"},400)
                urgent=bool(data.get("urgent")); deal="Срочно" if urgent else ("Обмен" if data.get("type")=="Обмен" else "Продажа"); until=(NOW()+timedelta(hours=24)).isoformat() if urgent else None
                phone=str(data.get("phone","")).strip()
                if phone and len(re.sub(r"\D","",phone))<10: return self.send_json({"error":"Проверьте номер телефона"},400)
                images=data.get("images") if isinstance(data.get("images"),list) else ([data.get("image")] if data.get("image") else [])
                images=[str(x) for x in images[:8] if x]
                if any(not x.startswith("data:image/") for x in images) or sum(map(len,images))>9_000_000: return self.send_json({"error":"Фотографии слишком большие"},400)
                image=images[0] if images else ""; images_json=json.dumps(images,ensure_ascii=False)
                transmission=str(data.get("transmission") or "")[:30]; body_type=str(data.get("body_type") or "")[:30]; drive=str(data.get("drive") or "")[:30]; vin=re.sub(r"[^A-HJ-NPR-Z0-9]","",str(data.get("vin") or "").upper())[:17]
                if vin and len(vin)!=17: return self.send_json({"error":"VIN должен содержать 17 символов"},400)
                with connect() as db:
                    cur=db.execute("INSERT INTO cars(name,price,year,km,type,urgent,description,phone,owner_id,created_at,updated_at,urgent_until,image,images,transmission,body_type,drive,vin) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(name[:80],price,year,f"{km:,}".replace(","," ")+" км",deal,int(urgent),str(data.get("description", ""))[:2000],phone[:40],uid,now,now,until,image,images_json,transmission,body_type,drive,vin)); cid=cur.lastrowid
                if urgent: threading.Thread(target=notify_urgent,args=(cid,name[:80],price),daemon=True).start()
                return self.send_json({"ok":True,"id":cid},201)
            m=re.fullmatch(r"/api/cars/(\d+)/favourite",path)
            if m:
                cid=int(m.group(1))
                with connect() as db:
                    exists=db.execute("SELECT 1 FROM favourites WHERE user_id=? AND car_id=?",(uid,cid)).fetchone()
                    if exists: db.execute("DELETE FROM favourites WHERE user_id=? AND car_id=?",(uid,cid)); state=False
                    else: db.execute("INSERT INTO favourites(user_id,car_id,created_at) VALUES(?,?,?)",(uid,cid,now)); state=True
                return self.send_json({"ok":True,"favourite":state})
            if path=="/api/subscriptions":
                with connect() as db: db.execute("INSERT OR IGNORE INTO subscriptions(telegram_user,kind,created_at) VALUES(?,?,?)",(uid,"urgent",now))
                return self.send_json({"ok":True})
            report=re.fullmatch(r"/api/cars/(\d+)/report",path)
            if report:
                cid=int(report.group(1)); reason=str(data.get("reason") or "other")[:40]; details=str(data.get("details") or "").strip()[:500]
                if not rate_allowed((uid,"report"),15,3600): return self.send_json({"error":"Слишком много жалоб. Попробуйте позже"},429)
                allowed={"fraud","wrong_info","sold","duplicate","other"}
                if reason not in allowed: return self.send_json({"error":"Выберите причину жалобы"},400)
                with connect() as db:
                    car=db.execute("SELECT owner_id,status FROM cars WHERE id=?",(cid,)).fetchone()
                    if not car or (car["status"] if DATABASE_URL else car[1])!="active": return self.send_json({"error":"Объявление недоступно"},404)
                    if (car["owner_id"] if DATABASE_URL else car[0])==uid: return self.send_json({"error":"Нельзя пожаловаться на своё объявление"},400)
                    try: db.execute("INSERT INTO reports(reporter_id,car_id,reason,details,created_at) VALUES(?,?,?,?,?)",(uid,cid,reason,details,now))
                    except Exception:
                        return self.send_json({"error":"Вы уже отправляли жалобу"},409)
                    count=db.execute("SELECT COUNT(*) AS count FROM reports WHERE car_id=? AND status='new'",(cid,)).fetchone(); total=count["count"] if DATABASE_URL else count[0]
                    if total>=3: db.execute("UPDATE cars SET status='review',updated_at=? WHERE id=? AND status='active'",(now,cid))
                return self.send_json({"ok":True,"under_review":total>=3},201)
            if path=="/api/exchanges":
                target=int(data.get("target_car_id") or 0); offered=int(data.get("offered_car_id") or 0) or None
                with connect() as db:
                    target_row=db.execute("SELECT owner_id,name FROM cars WHERE id=? AND status='active'",(target,)).fetchone()
                    if not target_row: return self.send_json({"error":"Объявление не найдено"},404)
                    target_owner=target_row["owner_id"] if DATABASE_URL else target_row[0]
                    if target_owner==uid: return self.send_json({"error":"Нельзя предложить обмен самому себе"},400)
                    offered_row=db.execute("SELECT name FROM cars WHERE id=? AND owner_id=? AND status='active'",(offered,uid)).fetchone() if offered else None
                    if not offered_row: return self.send_json({"error":"Выберите своё активное объявление"},400)
                    if db.execute("SELECT 1 FROM exchanges WHERE from_user=? AND target_car_id=? AND status='new'",(uid,target)).fetchone(): return self.send_json({"error":"Предложение уже отправлено"},409)
                    db.execute("INSERT INTO exchanges(from_user,target_car_id,offered_car_id,message,created_at) VALUES(?,?,?,?,?)",(uid,target,offered,str(data.get("message", ""))[:500],now))
                target_name=target_row["name"] if DATABASE_URL else target_row[1]; offered_name=offered_row["name"] if DATABASE_URL else offered_row[0]
                threading.Thread(target=notify_exchange_user,args=(target_owner,f"🔄 Новое предложение обмена\n\nВам предлагают {offered_name} в обмен на {target_name}.\n\nОткройте КРУГ, чтобы посмотреть предложение."),daemon=True).start()
                return self.send_json({"ok":True},201)
            return self.send_json({"error":"Маршрут не найден"},404)
        except (ValueError,TypeError,json.JSONDecodeError,sqlite3.IntegrityError) as e: return self.send_json({"error":str(e)},400)
    def do_DELETE(self):
        path=urlparse(self.path).path; uid,authenticated,_=auth_context(self.headers)
        if not self.require_auth(authenticated): return
        if path=="/api/account":
            with connect() as db:
                owned=db.execute("SELECT id FROM cars WHERE owner_id=?",(uid,)).fetchall(); car_ids=[int(r["id"] if DATABASE_URL else r[0]) for r in owned]
                db.execute("DELETE FROM favourites WHERE user_id=?",(uid,)); db.execute("DELETE FROM subscriptions WHERE telegram_user=?",(uid,)); db.execute("DELETE FROM reports WHERE reporter_id=?",(uid,)); db.execute("DELETE FROM exchanges WHERE from_user=?",(uid,))
                for cid in car_ids: db.execute("DELETE FROM cars WHERE id=?",(cid,))
                db.execute("DELETE FROM users WHERE id=?",(uid,))
            return self.send_json({"ok":True,"deleted":True})
        if path=="/api/subscriptions":
            with connect() as db: db.execute("DELETE FROM subscriptions WHERE telegram_user=? AND kind='urgent'",(uid,))
            return self.send_json({"ok":True,"urgent":False})
        m=re.fullmatch(r"/api/cars/(\d+)",path)
        if not m: return self.send_json({"error":"Маршрут не найден"},404)
        with connect() as db:
            cur=db.execute("UPDATE cars SET status='deleted',updated_at=? WHERE id=? AND owner_id=?",(NOW().isoformat(),int(m.group(1)),uid))
        return self.send_json({"ok":bool(cur.rowcount)},200 if cur.rowcount else 403)
    def do_PUT(self):
        try:
            path=urlparse(self.path).path; data=self.read_json(); uid,authenticated,_=auth_context(self.headers,data=data)
            if not self.require_auth(authenticated): return
            if path=="/api/profile":
                role="dealer" if data.get("role")=="dealer" else "private"; company=str(data.get("company") or "").strip()[:100]
                if role=="dealer" and len(company)<2: return self.send_json({"error":"Укажите название компании"},400)
                with connect() as db: cur=db.execute("UPDATE users SET role=?,company=?,updated_at=? WHERE id=?",(role,company,NOW().isoformat(),uid))
                return self.send_json({"ok":bool(cur.rowcount),"role":role,"company":company},200 if cur.rowcount else 404)
            exchange=re.fullmatch(r"/api/exchanges/(\d+)",path)
            if exchange:
                status={"accept":"accepted","reject":"rejected"}.get(data.get("action"))
                if not status: return self.send_json({"error":"Неизвестное действие"},400)
                with connect() as db:
                    exchange_row=db.execute("""SELECT e.from_user,target.name AS target_name,offered.name AS offered_name
                        FROM exchanges e JOIN cars target ON target.id=e.target_car_id LEFT JOIN cars offered ON offered.id=e.offered_car_id
                        WHERE e.id=? AND target.owner_id=? AND e.status='new'""",(int(exchange.group(1)),uid)).fetchone()
                    cur=db.execute("""UPDATE exchanges SET status=? WHERE id=? AND status='new'
                        AND EXISTS(SELECT 1 FROM cars WHERE cars.id=exchanges.target_car_id AND cars.owner_id=?)""",(status,int(exchange.group(1)),uid))
                if cur.rowcount and exchange_row:
                    sender=exchange_row["from_user"] if DATABASE_URL else exchange_row[0]; target_name=exchange_row["target_name"] if DATABASE_URL else exchange_row[1]
                    result="принято ✅" if status=="accepted" else "отклонено"
                    threading.Thread(target=notify_exchange_user,args=(sender,f"🔄 Ваше предложение обмена на {target_name} {result}.\n\nОткройте КРУГ, чтобы посмотреть подробности."),daemon=True).start()
                return self.send_json({"ok":bool(cur.rowcount),"status":status},200 if cur.rowcount else 403)
            m=re.fullmatch(r"/api/cars/(\d+)",path)
            if not m: return self.send_json({"error":"Маршрут не найден"},404)
            if data.get("action")=="edit":
                name=str(data.get("name","")).strip(); price=int(data.get("price") or 0); year=int(data.get("year") or 0); km=int(data.get("km") or 0)
                if len(name)<2 or price<1000 or not 1950<=year<=NOW().year+1 or km<0: return self.send_json({"error":"Проверьте марку, цену, год и пробег"},400)
                urgent=bool(data.get("urgent")); deal="Срочно" if urgent else ("Обмен" if data.get("type")=="Обмен" else "Продажа"); until=(NOW()+timedelta(hours=24)).isoformat() if urgent else None
                phone=str(data.get("phone","")).strip(); images=data.get("images") if isinstance(data.get("images"),list) else []
                images=[str(x) for x in images[:8] if x]
                if phone and len(re.sub(r"\D","",phone))<10: return self.send_json({"error":"Проверьте номер телефона"},400)
                if any(not x.startswith("data:image/") for x in images) or sum(map(len,images))>9_000_000: return self.send_json({"error":"Фотографии слишком большие"},400)
                image=images[0] if images else ""; images_json=json.dumps(images,ensure_ascii=False); transmission=str(data.get("transmission") or "")[:30]; body_type=str(data.get("body_type") or "")[:30]; drive=str(data.get("drive") or "")[:30]; vin=re.sub(r"[^A-HJ-NPR-Z0-9]","",str(data.get("vin") or "").upper())[:17]
                if vin and len(vin)!=17: return self.send_json({"error":"VIN должен содержать 17 символов"},400)
                with connect() as db: cur=db.execute("""UPDATE cars SET name=?,price=?,year=?,km=?,type=?,urgent=?,description=?,phone=?,updated_at=?,urgent_until=?,image=?,images=?,transmission=?,body_type=?,drive=?,vin=? WHERE id=? AND owner_id=? AND status<>'deleted'""",(name[:80],price,year,f"{km:,}".replace(","," ")+" км",deal,int(urgent),str(data.get("description", ""))[:2000],phone[:40],NOW().isoformat(),until,image,images_json,transmission,body_type,drive,vin,int(m.group(1)),uid))
                return self.send_json({"ok":bool(cur.rowcount)},200 if cur.rowcount else 403)
            status={"archive":"archived","activate":"active","sold":"sold"}.get(data.get("action"))
            if not status: return self.send_json({"error":"Неизвестное действие"},400)
            with connect() as db: cur=db.execute("UPDATE cars SET status=?,updated_at=? WHERE id=? AND owner_id=? AND status IN ('active','archived','sold')",(status,NOW().isoformat(),int(m.group(1)),uid))
            return self.send_json({"ok":bool(cur.rowcount),"status":status},200 if cur.rowcount else 403)
        except (ValueError,json.JSONDecodeError) as e: return self.send_json({"error":str(e)},400)

if __name__=="__main__":
    port=int(os.environ.get("PORT","4173")); init_db(); threading.Thread(target=setup_telegram_webhook,daemon=True).start(); print(f"KRUG on {port}"); ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
