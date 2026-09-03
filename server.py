"""KRUG marketplace API: users, listings, favourites, subscriptions and exchanges."""
import base64, binascii, hashlib, hmac, io, json, os, re, sqlite3, threading, time, warnings
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlparse
from urllib.request import Request, urlopen

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:  # The server remains readable locally, but uploads fail closed.
    Image=ImageOps=UnidentifiedImageError=None

ROOT=Path(__file__).resolve().parent
PROCESS_STARTED_AT=time.time()
DEPLOY_COMMIT=(os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("GIT_COMMIT") or "").strip()[:8]
DB=Path(os.environ.get("KRUG_DB_PATH",ROOT/"krug.db"))
DATABASE_URL=os.environ.get("DATABASE_URL","")
BOT_TOKEN=(os.environ.get("BOT_TOKEN") or os.environ.get("KRUG_BOT_TOKEN") or "").strip()
PUBLIC_URL=os.environ.get("PUBLIC_URL","https://krug-ekb.onrender.com/index.html")
APP_RELEASE="v138"
ADMIN_IDS={x.strip() for x in os.environ.get("ADMIN_TELEGRAM_IDS","").split(",") if x.strip()}
TESTER_IDS=ADMIN_IDS|{x.strip() for x in os.environ.get("KRUG_TESTER_TELEGRAM_IDS","").split(",") if x.strip()}
ALLOW_DEV_AUTH=os.environ.get("KRUG_ALLOW_DEV_AUTH","")=="1" and not BOT_TOKEN
INIT_DATA_MAX_AGE=max(300,min(int(os.environ.get("TELEGRAM_INIT_MAX_AGE","3600")),86400))
POLICY_VERSION=os.environ.get("PRIVACY_POLICY_VERSION","2026-08-16").strip()
RULES_VERSION=os.environ.get("TERMS_VERSION","2026-08-16").strip()
OPERATOR_NAME=os.environ.get("LEGAL_OPERATOR_NAME","").strip()
OPERATOR_EMAIL=os.environ.get("LEGAL_OPERATOR_EMAIL","").strip()
OPERATOR_ADDRESS=os.environ.get("LEGAL_OPERATOR_ADDRESS","").strip()
DATA_RESIDENCY_CONFIRMED=os.environ.get("DATA_RESIDENCY_RF_CONFIRMED","")=="1"
LEGAL_READY=ALLOW_DEV_AUTH or bool(OPERATOR_NAME and OPERATOR_EMAIL and OPERATOR_ADDRESS and DATA_RESIDENCY_CONFIRMED)
OPEN_BETA=os.environ.get("KRUG_OPEN_BETA","1")=="1" and not LEGAL_READY
PRODUCTION=os.environ.get("KRUG_ENV","").strip().lower()=="production" or bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))
WEBHOOK_SECRET=(os.environ.get("TELEGRAM_WEBHOOK_SECRET") or (hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32] if BOT_TOKEN else "")).strip()
TELEGRAM_STATUS={"configured":bool(BOT_TOKEN),"api_ok":False,"webhook_ok":False,"bot_username":"","error":"token_missing" if not BOT_TOKEN else "starting","updates_received":0,"last_update_at":"","welcome_sent":0,"last_delivery_error":"","notifications_sent":0,"notifications_failed":0,"last_notification_error":"","last_notification_at":""}
PUBLIC_ORIGIN=f"{urlparse(PUBLIC_URL).scheme}://{urlparse(PUBLIC_URL).netloc}" if urlparse(PUBLIC_URL).netloc else ""
ALLOWED_ORIGINS={PUBLIC_ORIGIN,*[x.strip().rstrip("/") for x in os.environ.get("ALLOWED_ORIGINS","").split(",") if x.strip()]}
NOW=lambda: datetime.now(timezone.utc)
RATE_BUCKETS={}; RATE_LOCK=threading.Lock()
ALLOWED_IMAGE_TYPES={"image/jpeg":(b"\xff\xd8\xff",),"image/png":(b"\x89PNG\r\n\x1a\n",),"image/webp":(b"RIFF",)}
if Image: Image.MAX_IMAGE_PIXELS=20_000_000

def is_admin(user_id): return str(user_id) in ADMIN_IDS

def staff_role(user_id):
    if is_admin(user_id): return "owner"
    try:
        with connect() as db: row=db.execute("SELECT role FROM staff_roles WHERE user_id=?",(str(user_id),)).fetchone()
        return (row["role"] if DATABASE_URL else row[0]) if row else ""
    except Exception: return ""

def can_moderate(user_id): return staff_role(user_id) in {"owner","admin","moderator"}
def can_manage_staff(user_id): return staff_role(user_id) in {"owner","admin"}

def rate_allowed(key,limit,window):
    now=time.time()
    with RATE_LOCK:
        if len(RATE_BUCKETS)>10000:
            for old_key in list(RATE_BUCKETS)[:2000]: RATE_BUCKETS.pop(old_key,None)
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
        self.db=psycopg.connect(DATABASE_URL,row_factory=dict_row,connect_timeout=5,options="-c statement_timeout=8000 -c idle_in_transaction_session_timeout=10000")
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
        CREATE TABLE IF NOT EXISTS price_history(id {generic_id}, car_id {ref_id} NOT NULL, old_price INTEGER NOT NULL, new_price INTEGER NOT NULL, changed_at TEXT NOT NULL, FOREIGN KEY(car_id) REFERENCES cars(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS staff_roles(user_id TEXT PRIMARY KEY, role TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS audit_log(id {generic_id}, actor_id TEXT NOT NULL, action TEXT NOT NULL, target TEXT DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS import_drafts(id {generic_id}, user_id TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'telegram', source_url TEXT DEFAULT '', original_text TEXT DEFAULT '', parsed_json TEXT NOT NULL DEFAULT '{{}}', status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS partner_sources(id {generic_id}, owner_id TEXT NOT NULL, platform TEXT NOT NULL, source_ref TEXT NOT NULL, title TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(platform,source_ref));
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
        add_column(db,"cars","fuel","TEXT DEFAULT ''")
        add_column(db,"cars","engine_volume","REAL NOT NULL DEFAULT 0")
        add_column(db,"cars","engine_power","INTEGER NOT NULL DEFAULT 0")
        add_column(db,"cars","color","TEXT DEFAULT ''")
        add_column(db,"cars","owners_count","INTEGER NOT NULL DEFAULT 0")
        add_column(db,"cars","vin","TEXT DEFAULT ''")
        add_column(db,"cars","thumbnail","TEXT DEFAULT ''")
        add_column(db,"cars","accept_exchange","INTEGER NOT NULL DEFAULT 0")
        add_column(db,"cars","search_key","TEXT DEFAULT ''")
        add_column(db,"cars","phone_public","INTEGER NOT NULL DEFAULT 0")
        add_column(db,"cars","contact_consent_at","TEXT DEFAULT NULL")
        add_column(db,"cars","consent_version","TEXT DEFAULT ''")
        add_column(db,"subscriptions","filters","TEXT DEFAULT '{}'")
        add_column(db,"subscriptions","name","TEXT DEFAULT ''")
        add_column(db,"exchanges","offer_text","TEXT DEFAULT ''")
        add_column(db,"exchanges","cash_amount","INTEGER NOT NULL DEFAULT 0")
        add_column(db,"cars","publish_key","TEXT DEFAULT NULL")
        db.execute("CREATE INDEX IF NOT EXISTS idx_cars_status_urgent_id ON cars(status,urgent,id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_cars_owner_status ON cars(owner_id,status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_favourites_user_created ON favourites(user_id,created_at)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_car_views_viewer_created ON car_views(viewer_id,created_at)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_cars_owner_publish_key ON cars(owner_id,publish_key) WHERE publish_key IS NOT NULL")
        db.execute("CREATE INDEX IF NOT EXISTS idx_reports_car_status ON reports(car_id,status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_cars_search_key ON cars(search_key)")
        db.execute("UPDATE cars SET accept_exchange=1 WHERE type='Обмен' AND accept_exchange=0")
        for row in db.execute("SELECT id,name FROM cars WHERE search_key IS NULL OR search_key='' ").fetchall():
            db.execute("UPDATE cars SET search_key=? WHERE id=?",(normalize_search(row["name"] if DATABASE_URL else row[1]),row["id"] if DATABASE_URL else row[0]))
        add_column(db,"users","company","TEXT DEFAULT ''")
        add_column(db,"users","dealer_verified","INTEGER NOT NULL DEFAULT 0")
        add_column(db,"users","privacy_consent_version","TEXT DEFAULT ''")
        add_column(db,"users","privacy_consent_at","TEXT DEFAULT NULL")
        add_column(db,"users","rules_version","TEXT DEFAULT ''")
        add_column(db,"users","rules_accepted_at","TEXT DEFAULT NULL")
        add_column(db,"partner_sources","secret_hash","TEXT DEFAULT ''")
        add_column(db,"partner_sources","confirmation_code","TEXT DEFAULT ''")
        add_column(db,"import_drafts","import_key","TEXT DEFAULT NULL")
        add_column(db,"import_drafts","published_car_id","INTEGER DEFAULT NULL")
        db.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_import_drafts_user_created ON import_drafts(user_id,created_at)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_partner_sources_owner ON partner_sources(owner_id,status)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_import_drafts_key ON import_drafts(import_key) WHERE import_key IS NOT NULL")
        count_row=db.execute("SELECT COUNT(*) AS count FROM cars").fetchone()
        if not (count_row["count"] if DATABASE_URL else count_row[0]):
            seed=[("Toyota RAV4",2890000,2021,"54 000 км","Продажа",0,"70% 50%"),("Kia K5",2470000,2020,"72 000 км","Обмен",0,"18% 50%"),("Lada Granta",690000,2019,"91 000 км","Срочно",1,"49% 50%"),("Hyundai Solaris",1450000,2018,"86 000 км","Срочно",1,"48% 50%"),("Ford Focus",290000,2007,"181 000 км","Обмен",0,"23% 50%"),("ВАЗ 2114",95000,2008,"210 000 км","Срочно",1,"48% 50%")]
            now=NOW().isoformat(); urgent=(NOW()+timedelta(hours=24)).isoformat()
            db.executemany("INSERT INTO cars(name,price,year,km,type,urgent,pos,created_at,updated_at,urgent_until,search_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)",[(*x,now,now,urgent if x[5] else None,normalize_search(x[0])) for x in seed])

def validate_telegram_init_data(raw,max_age=INIT_DATA_MAX_AGE):
    """Return the verified Telegram user, or None when initData is invalid/expired."""
    if not BOT_TOKEN or not raw or len(raw)>8192: return None
    try:
        fields=dict(parse_qsl(raw,keep_blank_values=True)); received=fields.pop("hash","")
        if not received: return None
        check="\n".join(f"{key}={fields[key]}" for key in sorted(fields))
        secret=hmac.new(b"WebAppData",BOT_TOKEN.encode("utf-8"),hashlib.sha256).digest()
        calculated=hmac.new(secret,check.encode("utf-8"),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated,received): return None
        auth_date=int(fields.get("auth_date","0"))
        age=int(time.time())-auth_date
        if auth_date<=0 or age < -60 or age>max_age: return None
        user=json.loads(fields.get("user","{}"))
        return user if isinstance(user,dict) and user.get("id") else None
    except (ValueError,TypeError,json.JSONDecodeError): return None

def auth_context(headers,data=None,query=None):
    tg_user=validate_telegram_init_data(headers.get("X-Telegram-Init-Data", ""))
    if tg_user: return str(tg_user["id"]),True,tg_user
    if ALLOW_DEV_AUTH: return user_id(headers,data,query),True,None
    return "anonymous",False,None

def user_id(headers,data=None,query=None):
    value=headers.get("X-Krug-User") or (data or {}).get("user") or (query or {}).get("user",["dev-user"])[0]
    return re.sub(r"[^a-zA-Z0-9_-]","",str(value))[:80] or "dev-user"

SEARCH_ALIASES={
    "тойота":"toyota","тайота":"toyota","тоёта":"toyota","форд":"ford","лада":"lada","ваз":"lada","vaz":"lada",
    "фольксваген":"volkswagen","фольцваген":"volkswagen","vw":"volkswagen","мерседес":"mercedes","мерин":"mercedes",
    "бмв":"bmw","хендай":"hyundai","хундай":"hyundai","хёндай":"hyundai","киа":"kia","ниссан":"nissan",
    "рено":"renault","шевроле":"chevrolet","шкода":"skoda","ауди":"audi","хонда":"honda","мазда":"mazda",
    "митсубиси":"mitsubishi","мицубиси":"mitsubishi","лексус":"lexus","субару":"subaru","пежо":"peugeot",
    "ситроен":"citroen","опель":"opel","вольво":"volvo","джили":"geely","хавал":"haval","чери":"chery","уаз":"uaz","газ":"gaz"
}
CYRILLIC_LATIN=dict(zip("абвгдежзийклмнопрстуфхцчшщъыьэюя",("a","b","v","g","d","e","zh","z","i","i","k","l","m","n","o","p","r","s","t","u","f","h","c","ch","sh","sh","","i","","e","yu","ya")))
def normalize_search(value):
    words=re.sub(r"[^a-zа-я0-9]+"," ",str(value or "").lower().replace("ё","е")).split(); result=[]
    for word in words:
        if word in SEARCH_ALIASES:
            result.append(SEARCH_ALIASES[word].replace("c","k").replace("q","k").replace("y","i")); continue
        result.append("".join(CYRILLIC_LATIN.get(letter,letter) for letter in word).replace("c","k").replace("q","k").replace("y","i"))
    return " ".join(result)

def clean_text(value,limit):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]","",str(value or "")).strip()[:limit]

def vehicle_specs(data):
    allowed_fuels={"","Бензин","Дизель","Гибрид","Электро","Газ"}
    fuel=str(data.get("fuel") or "")
    if fuel not in allowed_fuels: raise ValueError("Проверьте тип топлива")
    try:
        engine_volume=round(float(str(data.get("engine_volume") or "0").replace(",",".")),1)
        engine_power=int(data.get("engine_power") or 0)
        owners_count=int(data.get("owners_count") or 0)
    except (TypeError,ValueError): raise ValueError("Проверьте характеристики двигателя и владельцев")
    if not 0<=engine_volume<=10 or not 0<=engine_power<=3000 or not 0<=owners_count<=20: raise ValueError("Проверьте характеристики двигателя и владельцев")
    return fuel,engine_volume,engine_power,clean_text(data.get("color"),30),owners_count

def normalize_phone(value):
    digits=re.sub(r"\D","",str(value or ""))
    if not digits: return ""
    if len(digits)==10 and digits.startswith("9"): digits="7"+digits
    if len(digits)==11 and digits.startswith("8"): digits="7"+digits[1:]
    if len(digits)!=11 or not digits.startswith("7"): raise ValueError("Укажите российский номер в формате +7")
    return "+"+digits

def validated_image(value,max_bytes=2_000_000,max_dimension=2400):
    if not isinstance(value,str): raise ValueError("Некорректная фотография")
    match=re.fullmatch(r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\r\n]+)",value)
    if not match: raise ValueError("Разрешены только JPEG, PNG и WebP")
    try: raw=base64.b64decode(match.group(2),validate=True)
    except (ValueError,binascii.Error): raise ValueError("Повреждённая фотография")
    if not raw or len(raw)>max_bytes: raise ValueError("Одна фотография должна быть не больше 2 МБ")
    mime=match.group(1); signatures=ALLOWED_IMAGE_TYPES[mime]
    if not any(raw.startswith(signature) for signature in signatures): raise ValueError("Тип фотографии не совпадает с содержимым")
    if mime=="image/webp" and raw[8:12]!=b"WEBP": raise ValueError("Повреждённая WebP-фотография")
    if not Image: raise ValueError("Безопасная обработка фотографий не установлена на сервере")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error",Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as probe:
                probe.verify()
            with Image.open(io.BytesIO(raw)) as source:
                source.seek(0)
                if source.width<1 or source.height<1 or source.width*source.height>20_000_000:
                    raise ValueError("Слишком большое разрешение фотографии")
                image=ImageOps.exif_transpose(source)
                image.thumbnail((max_dimension,max_dimension),Image.Resampling.LANCZOS)
                has_alpha=image.mode in {"RGBA","LA"} or (image.mode=="P" and "transparency" in image.info)
                image=image.convert("RGBA" if has_alpha else "RGB")
                output=io.BytesIO(); image.save(output,"WEBP",quality=86,method=4)
        sanitized=output.getvalue()
    except (UnidentifiedImageError,OSError,SyntaxError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise ValueError("Повреждённая или опасная фотография")
    if not sanitized or len(sanitized)>max_bytes:
        raise ValueError("Фотография слишком большая после безопасной обработки")
    return "data:image/webp;base64,"+base64.b64encode(sanitized).decode("ascii")

def validated_images(values,max_count=8,max_total=8_000_000):
    values=list(values or [])
    if len(values)>max_count: raise ValueError(f"Можно загрузить не больше {max_count} фотографий")
    result=[]; total=0
    for value in values:
        checked=validated_image(value); total+=len(checked)
        if total>max_total: raise ValueError("Общий размер фотографий слишком большой")
        result.append(checked)
    return result

def backfill_missing_thumbnails(limit=25):
    """Repair legacy listings gradually without delaying startup indefinitely."""
    repaired=0
    try:
        with connect() as db:
            rows=db.execute("SELECT id,image FROM cars WHERE COALESCE(thumbnail,'')='' AND COALESCE(image,'')<>'' ORDER BY id DESC LIMIT ?",(int(limit),)).fetchall()
            for row in rows:
                car_id=row["id"] if DATABASE_URL else row[0]; source=row["image"] if DATABASE_URL else row[1]
                try: thumbnail=validated_image(source,250_000,480)
                except ValueError: continue
                db.execute("UPDATE cars SET thumbnail=? WHERE id=? AND COALESCE(thumbnail,'')=''",(thumbnail,car_id)); repaired+=1
    except Exception as exc: print(f"Thumbnail backfill failed: {type(exc).__name__}")
    if repaired: print(f"Thumbnail backfill repaired: {repaired}")
    return repaired

def start_thumbnail_backfill(batch_size=25):
    """Repair every legacy thumbnail in small background batches."""
    def worker():
        while True:
            repaired=backfill_missing_thumbnails(batch_size)
            if repaired<batch_size: return
            time.sleep(1)
    threading.Thread(target=worker,name="thumbnail-backfill",daemon=True).start()

def has_current_consent(user_id):
    try:
        with connect() as db: row=db.execute("SELECT privacy_consent_version,privacy_consent_at,rules_version,rules_accepted_at FROM users WHERE id=?",(str(user_id),)).fetchone()
        if not row: return False
        version=row["privacy_consent_version"] if DATABASE_URL else row[0]; accepted=row["privacy_consent_at"] if DATABASE_URL else row[1]; rules_version=row["rules_version"] if DATABASE_URL else row[2]; rules_at=row["rules_accepted_at"] if DATABASE_URL else row[3]
        return bool(accepted and version==POLICY_VERSION and rules_at and rules_version==RULES_VERSION)
    except Exception: return False

def personal_ready(user_id):
    """Allow production after legal setup and a closed beta for explicitly known users only."""
    return bool(LEGAL_READY or OPEN_BETA or str(user_id) in TESTER_IDS or has_current_consent(user_id))

def record_audit(actor_id,action,target=""):
    try:
        with connect() as db: db.execute("INSERT INTO audit_log(actor_id,action,target,created_at) VALUES(?,?,?,?)",(str(actor_id),str(action)[:80],str(target)[:160],NOW().isoformat()))
    except Exception as exc: print(f"Audit write failed: {type(exc).__name__}")

def request_origin_allowed(headers):
    origin=str(headers.get("Origin") or "").rstrip("/")
    if not origin: return ALLOW_DEV_AUTH
    if ALLOW_DEV_AUTH and re.fullmatch(r"http://(?:127\.0\.0\.1|localhost)(?::\d{1,5})?",origin): return True
    return origin in ALLOWED_ORIGINS

def public_car_summary(row,faved=False):
    source=car_dict(row,faved)
    allowed=("id","name","price","year","km","type","urgent","urgent_until","pos","created_at","updated_at","image","thumbnail","transmission","body_type","drive","fuel","engine_volume","engine_power","color","owners_count","accept_exchange","seller_role","seller_company","views","favourite")
    result={key:source.get(key) for key in allowed if key in source}
    result["image"]=source.get("thumbnail") or ""
    result.pop("thumbnail",None)
    return result

def masked_vin(value):
    value=str(value or "")
    return value[:3]+"*"*10+value[-4:] if len(value)==17 else ""

def car_detail_payload(row,faved,user_id,authenticated):
    allowed=personal_ready(user_id); data=car_dict(row,faved); owner=str(data.get("owner_id"))==str(user_id); consent=bool(data.get("contact_consent_at")); viewer_allowed=allowed and authenticated and has_current_consent(user_id)
    data["is_owner"]=owner
    contact_allowed=allowed and (owner or (viewer_allowed and consent))
    data["phone"]=data.get("phone","") if contact_allowed and (owner or data.get("phone_public")) else ""
    data["seller_username"]=data.get("seller_username","") if contact_allowed else ""
    data["seller_name"]=data.get("seller_name","") if contact_allowed else ""
    if not (owner and allowed): data["vin"]=masked_vin(data.get("vin"))
    for key in ("owner_id","search_key","contact_consent_at","consent_version","phone_public"):
        if not (owner and allowed): data.pop(key,None)
    return data

def purge_expired_data():
    try:
        deleted_before=(NOW()-timedelta(days=30)).isoformat(); views_before=(NOW()-timedelta(days=180)).isoformat(); audit_before=(NOW()-timedelta(days=365)).isoformat(); imports_before=(NOW()-timedelta(days=7)).isoformat()
        with connect() as db:
            db.execute("DELETE FROM cars WHERE status='deleted' AND COALESCE(updated_at,created_at)<?",(deleted_before,))
            db.execute("DELETE FROM car_views WHERE created_at<?",(views_before,))
            db.execute("DELETE FROM audit_log WHERE created_at<?",(audit_before,))
            db.execute("DELETE FROM import_drafts WHERE created_at<?",(imports_before,))
    except Exception as exc: print(f"Retention cleanup failed: {type(exc).__name__}")

def retention_loop():
    while True:
        time.sleep(6*60*60)
        purge_expired_data()

def car_dict(row,faved=False):
    d=dict(row); until=d.get("urgent_until")
    d.pop("publish_key",None)
    if d.get("urgent") and until:
        try:
            if datetime.fromisoformat(until)<NOW(): d["urgent"]=0; d["type"]="Продажа"
        except ValueError: pass
    try: d["images"]=json.loads(d.get("images") or "[]")
    except (TypeError,json.JSONDecodeError): d["images"]=[]
    if not d["images"] and d.get("image"): d["images"]=[d["image"]]
    d["favourite"]=bool(faved); return d

def web_app_url(car_id=None,import_id=None):
    separator="&" if "?" in PUBLIC_URL else "?"
    url=f"{PUBLIC_URL}{separator}app={APP_RELEASE}"
    if car_id: return f"{url}&car={int(car_id)}"
    return f"{url}&import={int(import_id)}" if import_id else url

def parse_imported_listing(text):
    """Extract only obvious vehicle fields; the user must verify every value."""
    value=clean_text(text,5000); lines=[line.strip(" •\t-") for line in value.splitlines() if line.strip()]
    year_match=re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)",value)
    km_match=re.search(r"(?<!\d)(\d[\d\s.]{0,10})\s*(?:км|km)\b",value,re.I)
    price_match=re.search(r"(?<!\d)(\d[\d\s.,]{0,14})\s*(?:(млн|тыс|т)\.?\s*(?:₽|руб(?:лей|ля|ль)?\.?|р\.?)?|(?:₽|руб(?:лей|ля|ль)?\.?|р\.))",value,re.I)
    if not price_match: price_match=re.search(r"\bцена\s*[:\-]?\s*(\d[\d\s.,]{2,14})\s*(млн|тыс)?",value,re.I)
    phone_match=re.search(r"(?:\+7|8)[\s()\-]*\d{3}[\s()\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}",value)
    source_match=re.search(r"https?://(?:www\.)?(?:vk\.com|t\.me)/[^\s]+",value,re.I)
    def number(match): return int(re.sub(r"\D","",match.group(1))) if match else 0
    def price_number(match):
        if not match: return 0
        raw=match.group(1).replace(" ","").replace(",","."); suffix=(match.group(2) or "").lower()
        try: amount=float(raw)
        except ValueError: return 0
        if suffix=="млн": amount*=1_000_000
        elif suffix in {"тыс","т"}: amount*=1_000
        return int(amount)
    brand_words=r"toyota|тойота|lada|лада|ваз|ford|форд|kia|киа|hyundai|хендай|bmw|бмв|mercedes|мерседес|renault|рено|nissan|ниссан|volkswagen|фольксваген|audi|ауди|skoda|шкода|chevrolet|шевроле|mazda|мазда|mitsubishi|мицубиси|subaru|субару|lexus|лексус|honda|хонда|geely|джили|chery|чери|haval|хавал|exeed|эксид|omoda|омода|moskvich|москвич|уаз|gaz|газ"
    title=next((line for line in lines if re.search(rf"\b(?:{brand_words})\b",line,re.I)),next((line for line in lines if not line.lower().startswith(("http://","https://"))),""))
    phone=""
    if phone_match:
        try: phone=normalize_phone(phone_match.group(0))
        except ValueError: pass
    return {"name":clean_text(title,80),"year":number(year_match),"price":price_number(price_match),"km":number(km_match),"phone":phone,"description":value,"source_url":clean_text(source_match.group(0),500) if source_match else ""}

def looks_like_vehicle_listing(text):
    value=str(text or "").lower()
    has_price=bool(re.search(r"\d[\d\s.,]{2,14}\s*(?:₽|руб|р\.|т\.?\s*р\.?|тыс|млн)|\bцена\b",value))
    has_year=bool(re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)",value))
    has_km=bool(re.search(r"\d[\d\s.]{0,10}\s*(?:км|km)\b|\bпробег\b",value))
    has_vehicle=bool(re.search(r"\b(?:авто|автомобиль|машина|продам|обмен|toyota|тойота|lada|лада|ваз|ford|форд|kia|киа|hyundai|хендай|bmw|бмв|mercedes|мерседес|renault|рено|nissan|ниссан|volkswagen|фольксваген|audi|ауди|skoda|шкода|chevrolet|шевроле|mazda|мазда|mitsubishi|мицубиси|subaru|субару|lexus|лексус|honda|хонда|geely|джили|chery|чери|haval|хавал|exeed|эксид|omoda|омода|moskvich|москвич|уаз|gaz|газ)\b",value))
    return has_price and (has_year or has_km or has_vehicle)

def import_quality(parsed):
    checks=(("name",bool(str(parsed.get("name") or "").strip())),("year",int(parsed.get("year") or 0)>=1950),("price",int(parsed.get("price") or 0)>=1000),("km",bool(re.search(r"\b(?:км|km|пробег)\b",str(parsed.get("description") or ""),re.I))),("photo",bool(parsed.get("images"))))
    missing=[name for name,ready in checks if not ready]
    return {"quality":int(round(100*(len(checks)-len(missing))/len(checks))),"missing":missing}

def import_source_title(db,source_type,import_key):
    """Resolve an approved source name without exposing callback secrets."""
    platform="telegram" if source_type=="telegram_group" else "vk" if source_type=="vk_group" else ""
    match=re.match(r"^(?:telegram|vk):([^:]+):",str(import_key or ""))
    if not platform or not match: return ""
    row=db.execute("SELECT title FROM partner_sources WHERE platform=? AND source_ref=?",(platform,match.group(1))).fetchone()
    return clean_text((row["title"] if DATABASE_URL else row[0]) if row else "",120)

def telegram_photo_data(message):
    photos=message.get("photo") if isinstance(message.get("photo"),list) else []
    if not photos or not BOT_TOKEN: return []
    file_id=str((photos[-1] or {}).get("file_id") or "")
    if not file_id: return []
    info=telegram_call("getFile",{"file_id":file_id}).get("result") or {}; file_path=str(info.get("file_path") or "")
    if not re.fullmatch(r"[A-Za-z0-9_./-]{1,300}",file_path): return []
    with urlopen(Request(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"),timeout=12) as response: raw=response.read(3_000_001)
    if len(raw)>3_000_000: raise ValueError("Фотография из Telegram слишком большая")
    return [validated_image("data:image/jpeg;base64,"+base64.b64encode(raw).decode("ascii"),2_000_000,1600)]

def vk_photo_data(post):
    """Download one photo URL supplied by a signed official VK callback event."""
    attachments=post.get("attachments") if isinstance(post.get("attachments"),list) else []
    candidates=[]
    for attachment in attachments:
        photo=(attachment or {}).get("photo") if isinstance(attachment,dict) else None
        for size in (photo or {}).get("sizes",[]) if isinstance(photo,dict) else []:
            url=str((size or {}).get("url") or ""); parsed=urlparse(url); host=(parsed.hostname or "").lower()
            if parsed.scheme=="https" and any(host==suffix or host.endswith("."+suffix) for suffix in ("userapi.com","vkuserphoto.ru")):
                candidates.append((int((size or {}).get("width") or 0)*int((size or {}).get("height") or 0),url))
    if not candidates: return []
    url=max(candidates,key=lambda item:item[0])[1]
    with urlopen(Request(url,headers={"User-Agent":"KRUG/1.0"}),timeout=12) as response: raw=response.read(2_000_001)
    if not raw or len(raw)>2_000_000: return []
    mime="image/jpeg" if raw.startswith((b"\xff\xd8\xff",b"\xff\xd8")) else "image/png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else "image/webp" if raw.startswith(b"RIFF") and raw[8:12]==b"WEBP" else ""
    return [validated_image(f"data:{mime};base64,"+base64.b64encode(raw).decode("ascii"),2_000_000,1600)] if mime else []

def import_draft_exists(import_key):
    if not import_key: return False
    with connect() as db: return bool(db.execute("SELECT 1 FROM import_drafts WHERE import_key=?",(import_key,)).fetchone())

def create_import_draft(user_id,source_type,text,source_url="",import_key="",images=None):
    """Create a private, user-bound draft. Imported content is never auto-published."""
    parsed=parse_imported_listing(text); now=NOW().isoformat(); parsed["images"]=list(images or [])[:1]
    safe_key=clean_text(import_key,240) or None
    params=(str(user_id),source_type,clean_text(source_url or parsed.get("source_url"),500),clean_text(text,5000),json.dumps(parsed,ensure_ascii=False),now,safe_key)
    with connect() as db:
        if safe_key:
            existing=db.execute("SELECT id FROM import_drafts WHERE import_key=?",(safe_key,)).fetchone()
            if existing: return int(existing["id"] if DATABASE_URL else existing[0]),False
        if DATABASE_URL:
            row=db.execute("INSERT INTO import_drafts(user_id,source_type,source_url,original_text,parsed_json,created_at,import_key) VALUES(?,?,?,?,?,?,?) RETURNING id",params).fetchone(); draft_id=int(row["id"])
            db.execute("DELETE FROM import_drafts WHERE id IN (SELECT id FROM import_drafts WHERE user_id=? AND status='draft' ORDER BY id DESC OFFSET 100)",(str(user_id),))
            return draft_id,True
        draft_id=int(db.execute("INSERT INTO import_drafts(user_id,source_type,source_url,original_text,parsed_json,created_at,import_key) VALUES(?,?,?,?,?,?,?)",params).lastrowid)
        db.execute("DELETE FROM import_drafts WHERE id IN (SELECT id FROM import_drafts WHERE user_id=? AND status='draft' ORDER BY id DESC LIMIT -1 OFFSET 100)",(str(user_id),))
        return draft_id,True

def telegram_import_listing(update):
    message=update.get("message") or {}; text=str(message.get("text") or message.get("caption") or "")
    chat=message.get("chat") or {}; sender=message.get("from") or {}; chat_id=chat.get("id"); user_id=sender.get("id")
    if not text or text.startswith("/") or not chat_id: return
    if chat.get("type")!="private":
        try:
            with connect() as db: source=db.execute("SELECT owner_id FROM partner_sources WHERE platform='telegram' AND source_ref=? AND status='active'",(str(chat_id),)).fetchone()
            if not source: return
            if not looks_like_vehicle_listing(text): return
            if not rate_allowed(("telegram_import",str(chat_id)),60,3600): return
            owner_id=str(source["owner_id"] if DATABASE_URL else source[0]); import_key=f"telegram:{chat_id}:{int(message.get('message_id') or 0)}"
            if import_draft_exists(import_key): return
            photos=telegram_photo_data(message); draft_id,created=create_import_draft(owner_id,"telegram_group",text,import_key=import_key,images=photos)
            if not created: return
            notify_import_user(owner_id,"Новый черновик из партнёрской Telegram-группы подготовлен. Проверьте данные перед публикацией.",draft_id)
        except Exception as exc: print(f"Partner Telegram import failed: {type(exc).__name__}")
        return
    if str(chat_id)!=str(user_id): return
    forwarded=bool(message.get("forward_origin") or message.get("forward_from_chat") or message.get("forward_date"))
    source_type="vk" if re.search(r"https?://(?:www\.)?vk\.com/",text,re.I) else "telegram"
    if not forwarded and source_type!="vk": return
    try:
        normalized=re.sub(r"\s+"," ",text.strip().lower()).encode("utf-8"); content_hash=hashlib.sha256(normalized).hexdigest()[:32]
        import_key=f"private:{user_id}:{source_type}:{content_hash}"
        if import_draft_exists(import_key):
            telegram_call("sendMessage",{"chat_id":str(chat_id),"text":"Этот пост уже сохранён в ваших черновиках."}); return
        photos=telegram_photo_data(message); draft_id,created=create_import_draft(user_id,source_type,text,import_key=import_key,images=photos)
        if not created: return
        label="поста ВК" if source_type=="vk" else "пересланного сообщения"
        notify_import_user(str(chat_id),f"Черновик из {label} подготовлен. Проверьте марку, год, пробег, цену и контакт перед публикацией.",draft_id)
    except Exception as exc: print(f"Telegram import failed: {type(exc).__name__}")

def telegram_connect_source(update):
    message=update.get("message") or {}; text=str(message.get("text") or "").split("@",1)[0].strip()
    chat=message.get("chat") or {}; sender=message.get("from") or {}; chat_id=chat.get("id"); user_id=sender.get("id")
    if text!="/krug_source" or chat.get("type") not in {"group","supergroup"} or not chat_id or not user_id: return
    try:
        membership=telegram_call("getChatMember",{"chat_id":str(chat_id),"user_id":str(user_id)}).get("result") or {}
        if membership.get("status") not in {"creator","administrator"}:
            telegram_call("sendMessage",{"chat_id":str(chat_id),"text":"Подключить источник может только администратор этой группы."}); return
        if not has_current_consent(str(user_id)):
            telegram_call("sendMessage",{"chat_id":str(chat_id),"text":"Сначала откройте КРУГ в личном чате и примите правила, затем повторите /krug_source."}); return
        now=NOW().isoformat(); title=clean_text(chat.get("title") or "Telegram-группа",120)
        with connect() as db:
            params=(str(user_id),"telegram",str(chat_id),title,"active",now,now)
            db.execute("INSERT INTO partner_sources(owner_id,platform,source_ref,title,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(platform,source_ref) DO UPDATE SET owner_id=excluded.owner_id,title=excluded.title,status='active',updated_at=excluded.updated_at",params)
        record_audit(str(user_id),"telegram_source_connected",str(chat_id))
        telegram_call("sendMessage",{"chat_id":str(chat_id),"text":"✅ Группа подключена к КРУГ. Новые автомобильные публикации будут приходить администратору как черновики и не появятся в каталоге без ручной проверки."})
    except Exception as exc: print(f"Telegram source connect failed: {type(exc).__name__}")

def record_notification_delivery(ok,error=""):
    key="notifications_sent" if ok else "notifications_failed"
    TELEGRAM_STATUS[key]=int(TELEGRAM_STATUS.get(key) or 0)+1
    TELEGRAM_STATUS["last_notification_at"]=NOW().isoformat()
    TELEGRAM_STATUS["last_notification_error"]="" if ok else clean_text(error,80)

def notify_urgent(car_id,name,price):
    """Send urgent-listing alerts in the background when a Telegram token is configured."""
    if not BOT_TOKEN: return
    try:
        with connect() as db: rows=db.execute("SELECT telegram_user FROM subscriptions WHERE kind='urgent'").fetchall()
        subscribers=[str(r["telegram_user"] if DATABASE_URL else r[0]) for r in rows]
        text=f"⚡ Срочное авто в Екатеринбурге\n\n{name}\n{price:,} ₽".replace(","," ")+"\n\nОткройте КРУГ, чтобы посмотреть объявление."
        for chat_id in subscribers:
            if not chat_id.isdigit(): continue
            payload=json.dumps({"chat_id":chat_id,"text":text,"reply_markup":{"inline_keyboard":[[{"text":"Открыть автомобиль","web_app":{"url":web_app_url(car_id)}}]]}},ensure_ascii=False).encode("utf-8")
            try: urlopen(Request(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",data=payload,headers={"Content-Type":"application/json"}),timeout=8).read(); record_notification_delivery(True)
            except Exception as exc: record_notification_delivery(False,type(exc).__name__); print(f"Telegram alert failed: {type(exc).__name__}")
    except Exception as exc: print(f"Telegram alerts unavailable: {type(exc).__name__}")

def telegram_call(method,payload):
    raw=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    return json.load(urlopen(Request(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",data=raw,headers={"Content-Type":"application/json"}),timeout=12))

def notify_exchange_user(chat_id,text,car_id=None):
    if not BOT_TOKEN or not str(chat_id).isdigit(): return
    try:
        result=telegram_call("sendMessage",{"chat_id":str(chat_id),"text":text,"reply_markup":{"inline_keyboard":[[{"text":"Открыть КРУГ","web_app":{"url":web_app_url(car_id)}}]]}})
        record_notification_delivery(bool(result.get("ok")),"telegram_rejected" if not result.get("ok") else "")
    except Exception as exc: record_notification_delivery(False,type(exc).__name__); print(f"Exchange notification failed: {type(exc).__name__}")

def notify_import_user(chat_id,text,draft_id):
    if not BOT_TOKEN or not str(chat_id).isdigit(): return
    try:
        result=telegram_call("sendMessage",{"chat_id":str(chat_id),"text":text,"reply_markup":{"inline_keyboard":[[{"text":"Проверить черновик","web_app":{"url":web_app_url(import_id=draft_id)}}]]}})
        record_notification_delivery(bool(result.get("ok")),"telegram_rejected" if not result.get("ok") else "")
    except Exception as exc: record_notification_delivery(False,type(exc).__name__); print(f"Import notification failed: {type(exc).__name__}")

def notify_price_drop(car_id,name,old_price,new_price):
    if not BOT_TOKEN: return
    try:
        with connect() as db: rows=db.execute("SELECT user_id FROM favourites WHERE car_id=?",(car_id,)).fetchall()
        drop=old_price-new_price; text=f"📉 Снижение цены в избранном\n\n{name}\nБыло: {old_price:,} ₽\nСтало: {new_price:,} ₽\nВыгода: {drop:,} ₽".replace(","," ")
        for row in rows: notify_exchange_user(row["user_id"] if DATABASE_URL else row[0],text,car_id)
    except Exception as exc: print(f"Price drop notifications failed: {type(exc).__name__}")

def search_subscription_matches(filters,car):
    query=normalize_search(filters.get("q") or "")
    if query and any(token not in normalize_search(car.get("name") or "") for token in query.split()): return False
    try:
        if filters.get("price_min") is not None and int(car.get("price") or 0)<int(filters["price_min"]): return False
        if filters.get("price_max") is not None and int(car.get("price") or 0)>int(filters["price_max"]): return False
    except (TypeError,ValueError): return False
    for key in ("transmission","body_type","drive","fuel"):
        if filters.get(key) and str(car.get(key) or "")!=str(filters[key]): return False
    return True

def notify_saved_searches(owner_id,car):
    if not BOT_TOKEN: return
    try:
        with connect() as db: rows=db.execute("SELECT telegram_user,filters,name FROM subscriptions WHERE kind='search'").fetchall()
        for row in rows:
            chat_id=str(row["telegram_user"] if DATABASE_URL else row[0])
            if chat_id==str(owner_id) or not chat_id.isdigit(): continue
            try: filters=json.loads((row["filters"] if DATABASE_URL else row[1]) or "{}")
            except (TypeError,json.JSONDecodeError): continue
            if not search_subscription_matches(filters,car): continue
            title=(row["name"] if DATABASE_URL else row[2]) or "Ваш поиск"
            text=f"🔔 Новое авто по подписке «{title}»\n\n{car['name']}\n{int(car['price']):,} ₽".replace(","," ")+"\n\nОткройте КРУГ, чтобы посмотреть объявление."
            notify_exchange_user(chat_id,text,car.get("id"))
    except Exception as exc: print(f"Saved search notifications failed: {type(exc).__name__}")

def telegram_welcome(update):
    message=update.get("message") or {}; text=str(message.get("text") or "")
    if not text.startswith("/start"): return
    chat_id=(message.get("chat") or {}).get("id"); first=(message.get("from") or {}).get("first_name") or ""
    if not chat_id: return
    greeting=f"Добро пожаловать в КРУГ, {first}!" if first else "Добро пожаловать в КРУГ!"
    try:
        result=telegram_call("sendMessage",{"chat_id":chat_id,"text":greeting+"\n\nАвтомобили Екатеринбурга: покупка, продажа, обмен и срочные объявления.","reply_markup":{"inline_keyboard":[[{"text":"Открыть КРУГ","web_app":{"url":web_app_url()}}]]}})
        if result.get("ok"): TELEGRAM_STATUS["welcome_sent"]=int(TELEGRAM_STATUS.get("welcome_sent") or 0)+1; TELEGRAM_STATUS["last_delivery_error"]=""
    except Exception as exc:
        code=getattr(exc,"code",None); TELEGRAM_STATUS["last_delivery_error"]=f"telegram_http_{code}" if code else type(exc).__name__; print(f"Telegram welcome failed: {type(exc).__name__}")

def setup_telegram_webhook():
    if not BOT_TOKEN: return
    try:
        base=PUBLIC_URL.split("/index.html",1)[0].rstrip("/")
        webhook=f"{base}/api/telegram/webhook"
        identity=telegram_call("getMe",{})
        TELEGRAM_STATUS.update({"api_ok":bool(identity.get("ok")),"bot_username":str((identity.get("result") or {}).get("username") or ""),"error":""})
        telegram_call("setWebhook",{"url":webhook,"secret_token":WEBHOOK_SECRET,"allowed_updates":["message"]})
        telegram_call("setChatMenuButton",{"menu_button":{"type":"web_app","text":"Открыть КРУГ","web_app":{"url":web_app_url()}}})
        telegram_call("setMyCommands",{"commands":[{"command":"start","description":"Открыть КРУГ"}]})
        info=telegram_call("getWebhookInfo",{}).get("result") or {}
        TELEGRAM_STATUS.update({"webhook_ok":str(info.get("url") or "")==webhook,"pending_updates":min(int(info.get("pending_update_count") or 0),9999),"last_error":clean_text(info.get("last_error_message") or "",120)})
        print("Telegram webhook configured")
    except Exception as exc:
        code=getattr(exc,"code",None); TELEGRAM_STATUS.update({"api_ok":False,"webhook_ok":False,"error":f"telegram_http_{code}" if code else type(exc).__name__})
        print(f"Telegram webhook unavailable: {type(exc).__name__}")

class Handler(SimpleHTTPRequestHandler):
    server_version="KRUG"
    sys_version=""

    def version_string(self):
        return self.server_version
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
    def setup(self):
        super().setup(); self.connection.settimeout(20)
    def log_message(self,format,*args):
        safe_args=tuple(re.sub(r"/api/telegram/[^ ?\"]+","/api/telegram/[redacted]",arg) if isinstance(arg,str) else arg for arg in args)
        super().log_message(format,*safe_args)
    def client_key(self):
        forwarded=str(self.headers.get("X-Forwarded-For") or "").split(",",1)[0].strip()
        return re.sub(r"[^0-9a-fA-F:._-]","",forwarded or self.client_address[0])[:80] or "unknown"
    def send_json(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False).encode("utf-8"); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def send_empty(self,status):
        self.send_response(status); self.send_header("Content-Length","0"); self.send_header("Cache-Control","no-store"); self.end_headers()
    def send_text(self,value,status=200):
        raw=str(value).encode("utf-8"); self.send_response(status); self.send_header("Content-Type","text/plain; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def end_headers(self):
        parsed_static=urlparse(self.path); static_path=parsed_static.path.lower(); static_query=parse_qs(parsed_static.query)
        versioned_asset=static_path.endswith((".js",".css")) and bool(re.fullmatch(r"\d{1,8}",str(static_query.get("v",[""])[0])))
        if versioned_asset:
            self.send_header("Cache-Control","public, max-age=31536000, immutable")
        elif static_path.endswith((".png",".jpg",".jpeg",".webp",".ico",".svg")):
            self.send_header("Cache-Control","public, max-age=604800")
        elif static_path.endswith((".html",".js",".css")) or static_path in {"/",""}:
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma","no-cache")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Strict-Transport-Security","max-age=31536000; includeSubDomains")
        self.send_header("Permissions-Policy","camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        self.send_header("Cross-Origin-Opener-Policy","same-origin-allow-popups")
        self.send_header("Content-Security-Policy","default-src 'self'; base-uri 'none'; object-src 'none'; form-action 'self'; script-src 'self' https://telegram.org; script-src-attr 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'self' https://web.telegram.org https://*.telegram.org")
        super().end_headers()
    def read_json(self):
        if "application/json" not in str(self.headers.get("Content-Type") or "").lower(): raise ValueError("Ожидается JSON")
        n=int(self.headers.get("Content-Length","0"))
        if n<0 or n>10_000_000: raise ValueError("Слишком большой запрос")
        body=self.rfile.read(n)
        if len(body)!=n: raise ValueError("Запрос передан не полностью")
        data=json.loads(body or b"{}")
        if not isinstance(data,dict): raise ValueError("Ожидается JSON-объект")
        return data
    def require_auth(self,authenticated):
        if authenticated: return True
        self.send_json({"error":"Откройте КРУГ через Telegram, чтобы выполнить это действие"},401); return False
    def require_consent(self,user_id):
        if not personal_ready(user_id):
            self.send_json({"error":"Обработка персональных данных временно отключена до завершения юридической настройки","code":"legal_setup_required"},503); return False
        if has_current_consent(user_id): return True
        self.send_json({"error":"Сначала примите актуальную политику обработки данных","code":"privacy_consent_required","policy_version":POLICY_VERSION},428); return False
    def require_origin(self):
        if request_origin_allowed(self.headers): return True
        self.send_json({"error":"Недопустимый источник запроса"},403); return False
    def require_rate(self,scope,limit,window,user_id=""):
        identity="user:"+str(user_id)[:80] if str(user_id).strip() else "ip:"+self.client_key()
        if rate_allowed((identity,scope),limit,window): return True
        self.send_json({"error":"Слишком много запросов. Попробуйте позже"},429); return False
    def safe_static(self,path):
        if path in {"/","/index.html","/favicon.ico","/favicon.svg"}: return True
        clean=Path(path.lstrip("/"))
        if any(part.startswith(".") or part in {"render-deploy","__pycache__","work","tmp"} for part in clean.parts): return False
        return clean.suffix.lower() in {".png",".jpg",".jpeg",".webp",".ico",".css",".js"}
    def valid_request_target(self):
        if len(self.path)<=4096: return True
        self.send_json({"error":"Слишком длинный адрес запроса"},414); return False
    def do_HEAD(self):
        if not self.valid_request_target() or not self.require_rate("head",120,60): return
        path=urlparse(self.path).path
        if path.startswith("/api/"): return self.send_empty(405)
        if not self.safe_static(path): return self.send_empty(404)
        return super().do_HEAD()
    def do_OPTIONS(self):
        return self.send_empty(405)
    def do_GET(self):
        if not self.valid_request_target(): return
        parsed=urlparse(self.path); path=parsed.path; query=parse_qs(parsed.query); uid,authenticated,_=auth_context(self.headers,query=query)
        if not self.require_rate("get",300,60,uid if authenticated else ""): return
        if path=="/api/health": return self.send_json({"ok":True,"service":"krug","version":91,"release":APP_RELEASE,"commit":DEPLOY_COMMIT,"uptime_seconds":max(0,int(time.time()-PROCESS_STARTED_AT)),"production":PRODUCTION,"personal_actions":bool(LEGAL_READY or OPEN_BETA),"testing_mode":OPEN_BETA,"closed_beta":bool(TESTER_IDS and not OPEN_BETA),"telegram":dict(TELEGRAM_STATUS)})
        if path=="/api/legal":
            beta=bool(authenticated and personal_ready(uid) and not LEGAL_READY)
            return self.send_json({"operator_name":OPERATOR_NAME,"operator_email":OPERATOR_EMAIL,"operator_address":OPERATOR_ADDRESS,"operator_configured":bool(OPERATOR_NAME and OPERATOR_EMAIL and OPERATOR_ADDRESS),"policy_version":POLICY_VERSION,"rules_version":RULES_VERSION,"ready":bool(LEGAL_READY or OPEN_BETA or beta),"testing_mode":bool(OPEN_BETA),"closed_beta":bool(beta and not OPEN_BETA),"data_residency_rf":DATA_RESIDENCY_CONFIRMED})
        if path=="/api/cars":
            paged=query.get("paged",[""])[0]=="1"
            try: limit=max(1,min(int(query.get("limit",["20"])[0]),50)) if paged else None; offset=max(0,min(int(query.get("offset",["0"])[0]),1_000_000)) if paged else 0
            except ValueError: return self.send_json({"error":"Некорректная пагинация"},400)
            conditions=["c.status='active'"]; filter_params=[]
            if PRODUCTION: conditions.append("c.owner_id IS NOT NULL AND c.owner_id<>'demo'")
            for token in normalize_search(query.get("q",[""])[0]).split(): conditions.append("c.search_key LIKE ?"); filter_params.append(f"%{token}%")
            for key,column in (("transmission","c.transmission"),("body","c.body_type"),("drive","c.drive"),("fuel","c.fuel")):
                value=str(query.get(key,[""])[0])[:30]
                if value: conditions.append(f"{column}=?"); filter_params.append(value)
            try:
                minimum=max(0,int(query.get("price_min",["0"])[0] or 0)); maximum=max(0,int(query.get("price_max",["0"])[0] or 0))
            except ValueError: minimum=maximum=0
            if minimum: conditions.append("c.price>=?"); filter_params.append(minimum)
            if maximum: conditions.append("c.price<=?"); filter_params.append(maximum)
            where=" AND ".join(conditions); sort=query.get("sort",["new"])[0]
            order={"cheap":"c.price ASC,c.id DESC","expensive":"c.price DESC,c.id DESC","year":"c.year DESC,c.id DESC"}.get(sort,"c.urgent DESC,c.id DESC")
            with connect() as db:
                total_row=db.execute(f"SELECT COUNT(*) AS count FROM cars c WHERE {where}",tuple(filter_params)).fetchone() if paged else None
                sql="""SELECT c.*,CASE WHEN u.role='dealer' AND u.dealer_verified=1 THEN 'dealer' ELSE 'private' END AS seller_role,CASE WHEN u.role='dealer' AND u.dealer_verified=1 THEN u.company ELSE '' END AS seller_company,
                    (SELECT COUNT(*) FROM car_views v WHERE v.car_id=c.id) AS views,
                    EXISTS(SELECT 1 FROM favourites f WHERE f.car_id=c.id AND f.user_id=?) AS faved
                    FROM cars c LEFT JOIN users u ON u.id=c.owner_id
                    WHERE """+where+" ORDER BY "+order
                params=[uid,*filter_params]
                if paged: sql+=" LIMIT ? OFFSET ?"; params.extend([limit,offset])
                rows=db.execute(sql,tuple(params)).fetchall()
            summaries=[]
            for row in rows:
                summaries.append(public_car_summary(row,row["faved"]))
            if paged:
                total=int(total_row["count"] if DATABASE_URL else total_row[0])
                return self.send_json({"items":summaries,"total":total,"offset":offset,"limit":limit,"has_more":offset+len(summaries)<total})
            return self.send_json(summaries)
        detail=re.fullmatch(r"/api/cars/(\d+)",path)
        if detail:
            moderation_access=bool(authenticated and can_moderate(uid))
            with connect() as db:
                row=db.execute("""SELECT c.*,u.first_name AS seller_name,u.username AS seller_username,CASE WHEN u.role='dealer' AND u.dealer_verified=1 THEN 'dealer' ELSE 'private' END AS seller_role,CASE WHEN u.role='dealer' AND u.dealer_verified=1 THEN u.company ELSE '' END AS seller_company,
                    EXISTS(SELECT 1 FROM favourites f WHERE f.car_id=c.id AND f.user_id=?) AS faved
                    FROM cars c LEFT JOIN users u ON u.id=c.owner_id
                    WHERE c.id=? AND (c.status='active' OR c.owner_id=? OR (?=1 AND c.status='review'))""",(uid,int(detail.group(1)),uid,int(moderation_access))).fetchone()
            if PRODUCTION and row and str(row["owner_id"] or "").strip() in {"", "demo"}: row=None
            if not row: return self.send_json({"error":"Объявление не найдено"},404)
            with connect() as db:
                if authenticated and has_current_consent(uid) and str(row["owner_id"])!=str(uid):
                    try: db.execute("INSERT INTO car_views(viewer_id,car_id,view_day,created_at) VALUES(?,?,?,?) ON CONFLICT(viewer_id,car_id,view_day) DO UPDATE SET created_at=excluded.created_at",(uid,int(detail.group(1)),NOW().date().isoformat(),NOW().isoformat()))
                    except sqlite3.IntegrityError: pass
                vr=db.execute("SELECT COUNT(*) AS count FROM car_views WHERE car_id=?",(int(detail.group(1)),)).fetchone(); favr=db.execute("SELECT COUNT(*) AS count FROM favourites WHERE car_id=?",(int(detail.group(1)),)).fetchone()
                phr=db.execute("SELECT old_price,new_price,changed_at FROM price_history WHERE car_id=? ORDER BY id DESC LIMIT 1",(int(detail.group(1)),)).fetchone()
            data=car_detail_payload(row,row["faved"],uid,authenticated); data["views"]=vr["count"] if DATABASE_URL else vr[0]; data["favourites_count"]=favr["count"] if DATABASE_URL else favr[0]; data["previous_price"]=int(phr["old_price"] if DATABASE_URL else phr[0]) if phr and int(phr["old_price"] if DATABASE_URL else phr[0])>data["price"] else None
            return self.send_json(data)
        if path=="/api/stats":
            production_scope=" AND owner_id IS NOT NULL AND owner_id<>'demo'" if PRODUCTION else ""
            with connect() as db:
                ur=db.execute("SELECT COUNT(*) AS count FROM cars WHERE status='active' AND urgent=1 AND (urgent_until IS NULL OR urgent_until>?)"+production_scope,(NOW().isoformat(),)).fetchone()
                ar=db.execute("SELECT COUNT(*) AS count FROM cars WHERE status='active'"+production_scope).fetchone()
            return self.send_json({"urgent":ur["count"] if DATABASE_URL else ur[0],"active":ar["count"] if DATABASE_URL else ar[0]})
        personal={"/api/subscriptions","/api/favourites","/api/recent","/api/me","/api/imports","/api/admin/staff","/api/admin/reports","/api/admin/partner-sources","/api/my-cars","/api/exchanges"}
        if path in personal or path.startswith("/api/admin/"):
            if not self.require_auth(authenticated) or not self.require_consent(uid): return
        if path=="/api/export" and not self.require_auth(authenticated): return
        if path=="/api/subscriptions":
            if not self.require_auth(authenticated): return
            with connect() as db:
                urgent_row=db.execute("SELECT 1 FROM subscriptions WHERE telegram_user=? AND kind='urgent'",(uid,)).fetchone()
                search_row=db.execute("SELECT filters,name FROM subscriptions WHERE telegram_user=? AND kind='search'",(uid,)).fetchone()
            search=None
            if search_row:
                try: filters=json.loads((search_row["filters"] if DATABASE_URL else search_row[0]) or "{}")
                except (TypeError,json.JSONDecodeError): filters={}
                search={"filters":filters,"name":search_row["name"] if DATABASE_URL else search_row[1]}
            return self.send_json({"urgent":bool(urgent_row),"search":search})
        if path=="/api/favourites":
            if not self.require_auth(authenticated): return
            with connect() as db:
                rows=db.execute("""SELECT c.*,CASE WHEN u.role='dealer' AND u.dealer_verified=1 THEN 'dealer' ELSE 'private' END AS seller_role,CASE WHEN u.role='dealer' AND u.dealer_verified=1 THEN u.company ELSE '' END AS seller_company,
                    (SELECT COUNT(*) FROM car_views v WHERE v.car_id=c.id) AS views,1 AS faved
                    FROM favourites f JOIN cars c ON c.id=f.car_id LEFT JOIN users u ON u.id=c.owner_id
                    WHERE f.user_id=? AND c.status='active' ORDER BY f.created_at DESC""",(uid,)).fetchall()
            return self.send_json([public_car_summary(r,True) for r in rows])
        if path=="/api/recent":
            if not self.require_auth(authenticated): return
            with connect() as db:
                rows=db.execute("""SELECT c.*,CASE WHEN u.role='dealer' AND u.dealer_verified=1 THEN 'dealer' ELSE 'private' END AS seller_role,CASE WHEN u.role='dealer' AND u.dealer_verified=1 THEN u.company ELSE '' END AS seller_company,
                    (SELECT COUNT(*) FROM car_views all_views WHERE all_views.car_id=c.id) AS views,
                    EXISTS(SELECT 1 FROM favourites f WHERE f.car_id=c.id AND f.user_id=?) AS faved,
                    MAX(v.created_at) AS viewed_at
                    FROM car_views v JOIN cars c ON c.id=v.car_id LEFT JOIN users u ON u.id=c.owner_id
                    WHERE v.viewer_id=? AND c.status='active'
                    GROUP BY c.id,u.role,u.company ORDER BY viewed_at DESC LIMIT 20""",(uid,uid)).fetchall()
            return self.send_json([public_car_summary(r,r["faved"]) for r in rows])
        if path=="/api/imports":
            if not self.require_auth(authenticated): return
            if not self.require_consent(uid): return
            with connect() as db:
                rows=db.execute("SELECT id,source_type,source_url,parsed_json,created_at,import_key FROM import_drafts WHERE user_id=? AND status='draft' ORDER BY id DESC LIMIT 100",(uid,)).fetchall()
                result=[]
                for row in rows:
                    try: parsed=json.loads(row["parsed_json"] if DATABASE_URL else row[3])
                    except (TypeError,json.JSONDecodeError): parsed={}
                    source_type=row["source_type"] if DATABASE_URL else row[1]; import_key=row["import_key"] if DATABASE_URL else row[5]
                    quality=import_quality(parsed)
                    result.append({"id":int(row["id"] if DATABASE_URL else row[0]),"source_type":source_type,"source_title":import_source_title(db,source_type,import_key),"source_url":row["source_url"] if DATABASE_URL else row[2],"name":clean_text(parsed.get("name") or "Черновик объявления",80),"year":int(parsed.get("year") or 0),"price":int(parsed.get("price") or 0),"has_photo":bool(parsed.get("images")),"quality":quality["quality"],"missing":quality["missing"],"created_at":row["created_at"] if DATABASE_URL else row[4]})
            return self.send_json(result)
        if path=="/api/me":
            if not self.require_auth(authenticated): return
            with connect() as db:
                u=db.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); lr=db.execute("SELECT COUNT(*) AS count FROM cars WHERE owner_id=? AND status='active'",(uid,)).fetchone(); fr=db.execute("SELECT COUNT(*) AS count FROM favourites f JOIN cars c ON c.id=f.car_id WHERE f.user_id=? AND c.status='active'",(uid,)).fetchone(); er=db.execute("SELECT COUNT(*) AS count FROM exchanges e JOIN cars c ON c.id=e.target_car_id WHERE c.owner_id=? AND e.status='new'",(uid,)).fetchone(); sr=db.execute("SELECT COUNT(*) AS count FROM subscriptions WHERE telegram_user=?",(uid,)).fetchone(); vr=db.execute("SELECT COUNT(*) AS count FROM car_views v JOIN cars c ON c.id=v.car_id WHERE c.owner_id=? AND c.status<>'deleted'",(uid,)).fetchone(); ir=db.execute("SELECT COUNT(*) AS count FROM import_drafts WHERE user_id=? AND status='draft'",(uid,)).fetchone(); listings=lr["count"] if DATABASE_URL else lr[0]; favs=fr["count"] if DATABASE_URL else fr[0]; offers=er["count"] if DATABASE_URL else er[0]; subscriptions=sr["count"] if DATABASE_URL else sr[0]; views=vr["count"] if DATABASE_URL else vr[0]; imports=ir["count"] if DATABASE_URL else ir[0]
            role=staff_role(uid); moderation_pending=0
            if role in {"owner","admin","moderator"}:
                with connect() as db:
                    pending_row=db.execute("SELECT COUNT(*) AS count FROM reports WHERE status='new'").fetchone()
                    moderation_pending=pending_row["count"] if DATABASE_URL else pending_row[0]
            return self.send_json({"user":dict(u) if u else None,"listings":listings,"favourites":favs,"offers":offers,"subscriptions":subscriptions,"views":views,"imports":imports,"admin":role in {"owner","admin"},"staff_role":role,"moderation_pending":moderation_pending})
        if path=="/api/admin/staff":
            if not self.require_auth(authenticated): return
            if not can_manage_staff(uid): return self.send_json({"error":"Доступ только для администратора"},403)
            with connect() as db:
                rows=db.execute("""SELECT s.user_id,s.role,s.created_at,u.first_name,u.username
                    FROM staff_roles s JOIN users u ON u.id=s.user_id ORDER BY s.created_at DESC""").fetchall()
            return self.send_json([dict(r) for r in rows])
        if path=="/api/admin/partner-sources":
            if not self.require_auth(authenticated): return
            if not can_manage_staff(uid): return self.send_json({"error":"Доступ только для администратора"},403)
            result=[]
            with connect() as db:
                rows=db.execute("SELECT id,platform,source_ref,title,status,created_at,updated_at FROM partner_sources ORDER BY id DESC").fetchall()
                for row in rows:
                    item=dict(row); prefix=("telegram:" if item["platform"]=="telegram" else "vk:")+str(item["source_ref"])+":"
                    stats=db.execute("SELECT COUNT(*) AS count,MAX(created_at) AS last_import_at FROM import_drafts WHERE import_key LIKE ?",(prefix+"%",)).fetchone()
                    item["draft_count"]=int(stats["count"] if DATABASE_URL else stats[0]); item["last_import_at"]=stats["last_import_at"] if DATABASE_URL else stats[1]; result.append(item)
            return self.send_json(result)
        if path=="/api/admin/reports":
            if not self.require_auth(authenticated): return
            if not can_moderate(uid): return self.send_json({"error":"Доступ только для модератора"},403)
            with connect() as db:
                rows=db.execute("""SELECT r.*,c.name AS car_name,c.status AS car_status,c.owner_id,
                    c.price AS car_price,c.year AS car_year,c.km AS car_km,
                    CASE WHEN COALESCE(c.thumbnail,'')<>'' THEN c.thumbnail ELSE c.image END AS car_image,
                    u.first_name AS reporter_name FROM reports r JOIN cars c ON c.id=r.car_id
                    LEFT JOIN users u ON u.id=r.reporter_id WHERE r.status='new' ORDER BY r.id DESC""").fetchall()
            return self.send_json([dict(r) for r in rows])
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
                    target.price AS target_price,target.year AS target_year,target.thumbnail AS target_image,
                    offered.name AS offered_name,offered.price AS offered_price,offered.year AS offered_year,offered.thumbnail AS offered_image,
                    sender.first_name AS sender_name, sender.username AS sender_username
                    FROM exchanges e JOIN cars target ON target.id=e.target_car_id
                    LEFT JOIN cars offered ON offered.id=e.offered_car_id
                    LEFT JOIN users sender ON sender.id=e.from_user
                    WHERE e.from_user=? OR target.owner_id=? ORDER BY e.id DESC""",(uid,uid)).fetchall()
            return self.send_json([dict(r) for r in rows])
        imported=re.fullmatch(r"/api/imports/(\d+)",path)
        if imported:
            if not self.require_auth(authenticated): return
            if not self.require_consent(uid): return
            with connect() as db:
                row=db.execute("SELECT id,source_type,source_url,parsed_json,created_at,import_key FROM import_drafts WHERE id=? AND user_id=? AND status='draft'",(int(imported.group(1)),uid)).fetchone()
                source_title=import_source_title(db,row["source_type"] if DATABASE_URL else row[1],row["import_key"] if DATABASE_URL else row[5]) if row else ""
            if not row: return self.send_json({"error":"Черновик не найден или уже истёк"},404)
            payload=dict(row); payload.pop("import_key",None); parsed=json.loads(payload.pop("parsed_json") or "{}"); payload.update(parsed); payload.update(import_quality(parsed)); payload["source_title"]=source_title
            return self.send_json(payload)
        if path=="/api/export":
            if not self.require_auth(authenticated): return
            with connect() as db:
                user=db.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
                cars_rows=db.execute("SELECT * FROM cars WHERE owner_id=? AND status<>'deleted' ORDER BY id",(uid,)).fetchall()
                favourites=db.execute("SELECT car_id,created_at FROM favourites WHERE user_id=? ORDER BY created_at",(uid,)).fetchall()
                subscriptions=db.execute("SELECT kind,filters,name,created_at FROM subscriptions WHERE telegram_user=? ORDER BY created_at",(uid,)).fetchall()
                exchanges=db.execute("SELECT * FROM exchanges WHERE from_user=? OR EXISTS(SELECT 1 FROM cars WHERE cars.id=exchanges.target_car_id AND cars.owner_id=?) ORDER BY id",(uid,uid)).fetchall()
                reports=db.execute("SELECT car_id,reason,details,status,created_at FROM reports WHERE reporter_id=? ORDER BY id",(uid,)).fetchall()
                views=db.execute("SELECT car_id,view_day,created_at FROM car_views WHERE viewer_id=? ORDER BY created_at",(uid,)).fetchall()
                staff=db.execute("SELECT role,created_by,created_at FROM staff_roles WHERE user_id=?",(uid,)).fetchone()
                audit=db.execute("SELECT action,target,created_at FROM audit_log WHERE actor_id=? ORDER BY id",(uid,)).fetchall()
            return self.send_json({"exported_at":NOW().isoformat(),"user":dict(user) if user else None,"cars":[car_dict(r) for r in cars_rows],"favourites":[dict(r) for r in favourites],"subscriptions":[dict(r) for r in subscriptions],"exchanges":[dict(r) for r in exchanges],"reports":[dict(r) for r in reports],"views":[dict(r) for r in views],"staff":dict(staff) if staff else None,"audit":[dict(r) for r in audit]})
        if not self.safe_static(path): return self.send_json({"error":"Not found"},404)
        return super().do_GET()
    def do_POST(self):
        try:
            if not self.valid_request_target() or not self.require_rate("post_ip",600,60): return
            path=urlparse(self.path).path; is_webhook=bool(BOT_TOKEN and path=="/api/telegram/webhook"); is_vk_callback=path=="/api/vk/callback"
            if not is_webhook and not is_vk_callback and not self.require_origin(): return
            data=self.read_json(); now=NOW().isoformat()
            if is_webhook:
                supplied=str(self.headers.get("X-Telegram-Bot-Api-Secret-Token") or "")
                if not supplied or not hmac.compare_digest(supplied,WEBHOOK_SECRET): return self.send_json({"error":"Not found"},404)
                TELEGRAM_STATUS["updates_received"]=int(TELEGRAM_STATUS.get("updates_received") or 0)+1; TELEGRAM_STATUS["last_update_at"]=NOW().isoformat()
                threading.Thread(target=telegram_welcome,args=(data,),daemon=True).start()
                threading.Thread(target=telegram_connect_source,args=(data,),daemon=True).start()
                threading.Thread(target=telegram_import_listing,args=(data,),daemon=True).start()
                return self.send_json({"ok":True})
            if is_vk_callback:
                group_id=str(data.get("group_id") or ""); supplied=str(data.get("secret") or "")
                with connect() as db: source=db.execute("SELECT owner_id,secret_hash,confirmation_code FROM partner_sources WHERE platform='vk' AND source_ref=? AND status='active'",(group_id,)).fetchone()
                if not source or not supplied: return self.send_json({"error":"Not found"},404)
                owner_id=str(source["owner_id"] if DATABASE_URL else source[0]); secret_hash=str(source["secret_hash"] if DATABASE_URL else source[1]); confirmation=str(source["confirmation_code"] if DATABASE_URL else source[2])
                if not secret_hash or not hmac.compare_digest(hashlib.sha256(supplied.encode("utf-8")).hexdigest(),secret_hash): return self.send_json({"error":"Not found"},404)
                event_type=str(data.get("type") or "")
                if event_type=="confirmation": return self.send_text(confirmation)
                if event_type=="wall_post_new":
                    obj=data.get("object") if isinstance(data.get("object"),dict) else {}; post=obj.get("post") if isinstance(obj.get("post"),dict) else obj
                    text=str(post.get("text") or ""); post_id=int(post.get("id") or 0)
                    if text and looks_like_vehicle_listing(text) and rate_allowed(("vk_import",str(group_id)),60,3600):
                        source_url=f"https://vk.com/wall-{group_id}_{post_id}" if post_id else f"https://vk.com/club{group_id}"
                        try: photos=vk_photo_data(post)
                        except Exception: photos=[]
                        draft_id,created=create_import_draft(owner_id,"vk_group",text,source_url,f"vk:{group_id}:{post_id}",photos)
                        if not created: return self.send_text("ok")
                        threading.Thread(target=notify_import_user,args=(owner_id,"Новый черновик из партнёрского сообщества VK подготовлен. Проверьте данные перед публикацией.",draft_id),daemon=True).start()
                        record_audit(owner_id,"vk_import_draft",draft_id)
                return self.send_text("ok")
            uid,authenticated,tg_user=auth_context(self.headers,data=data)
            if not self.require_auth(authenticated): return
            if not self.require_rate("post",120,60,uid): return
            if path=="/api/session":
                if not personal_ready(uid): return self.send_json({"error":"Сбор персональных данных доступен только закрытой тестовой группе до завершения юридической настройки","code":"legal_setup_required"},503)
                already=has_current_consent(uid)
                if not already:
                    if data.get("privacy_consent") is not True or str(data.get("policy_version") or "")!=POLICY_VERSION:
                        return self.send_json({"error":"Нужно отдельное согласие на обработку персональных данных","code":"privacy_consent_required","policy_version":POLICY_VERSION},428)
                    if data.get("rules_accepted") is not True or str(data.get("rules_version") or "")!=RULES_VERSION:
                        return self.send_json({"error":"Нужно отдельно принять актуальные правила КРУГ","code":"rules_acceptance_required","rules_version":RULES_VERSION},428)
                first=clean_text((tg_user or data).get("first_name") or "Пользователь",80); username=clean_text((tg_user or data).get("username") or "",80).lstrip("@")
                if username and not re.fullmatch(r"[A-Za-z0-9_]{5,32}",username): username=""
                with connect() as db:
                    previous=db.execute("SELECT privacy_consent_at,rules_accepted_at FROM users WHERE id=?",(uid,)).fetchone(); consent_at=(previous["privacy_consent_at"] if DATABASE_URL else previous[0]) if previous and already else now; rules_at=(previous["rules_accepted_at"] if DATABASE_URL else previous[1]) if previous and already else now
                    if username: db.execute("UPDATE users SET username='' WHERE id<>? AND LOWER(username)=LOWER(?)",(uid,username))
                    db.execute("INSERT INTO users(id,first_name,username,privacy_consent_version,privacy_consent_at,rules_version,rules_accepted_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET first_name=excluded.first_name,username=excluded.username,privacy_consent_version=excluded.privacy_consent_version,privacy_consent_at=excluded.privacy_consent_at,rules_version=excluded.rules_version,rules_accepted_at=excluded.rules_accepted_at,updated_at=excluded.updated_at",(uid,first,username,POLICY_VERSION,consent_at,RULES_VERSION,rules_at,now,now))
                if not already:
                    record_audit(uid,"privacy_consent",POLICY_VERSION)
                    record_audit(uid,"rules_accepted",RULES_VERSION)
                return self.send_json({"ok":True,"user":uid,"policy_version":POLICY_VERSION,"rules_version":RULES_VERSION})
            if not self.require_consent(uid): return
            if path=="/api/admin/staff":
                if not can_manage_staff(uid): return self.send_json({"error":"Доступ только для администратора"},403)
                identifier=str(data.get("identifier") or "").strip().lstrip("@"); role=str(data.get("role") or "")
                if role not in {"admin","moderator"}: return self.send_json({"error":"Выберите роль"},400)
                if not re.fullmatch(r"(?:\d{5,20}|[A-Za-z0-9_]{5,32})",identifier): return self.send_json({"error":"Укажите корректный Telegram ID или username"},400)
                with connect() as db:
                    target=db.execute("SELECT id,first_name,username FROM users WHERE id=? OR LOWER(username)=LOWER(?)",(identifier,identifier)).fetchone()
                    if not target: return self.send_json({"error":"Пользователь сначала должен открыть бота КРУГ"},404)
                    target_id=str(target["id"] if DATABASE_URL else target[0])
                    if target_id in ADMIN_IDS: return self.send_json({"error":"Владелец уже имеет полный доступ"},409)
                    db.execute("""INSERT INTO staff_roles(user_id,role,created_by,created_at) VALUES(?,?,?,?)
                        ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,created_by=excluded.created_by,created_at=excluded.created_at""",(target_id,role,uid,now))
                record_audit(uid,"staff_granted",f"{target_id}:{role}")
                return self.send_json({"ok":True,"user_id":target_id,"role":role},201)
            if path=="/api/admin/partner-sources":
                if not can_manage_staff(uid): return self.send_json({"error":"Доступ только для администратора"},403)
                platform=str(data.get("platform") or "").strip().lower(); source_ref=clean_text(data.get("source_ref"),120); title=clean_text(data.get("title"),120); callback_secret=str(data.get("callback_secret") or ""); confirmation_code=clean_text(data.get("confirmation_code"),120)
                if platform not in {"telegram","vk"}: return self.send_json({"error":"Выберите Telegram или VK"},400)
                if platform=="telegram" and not re.fullmatch(r"-100\d{6,20}",source_ref): return self.send_json({"error":"Укажите ID Telegram-группы вида -100..."},400)
                if platform=="vk" and not re.fullmatch(r"\d{1,20}",source_ref): return self.send_json({"error":"Укажите числовой ID сообщества VK"},400)
                if platform=="vk" and (not 8<=len(callback_secret)<=100 or not 3<=len(confirmation_code)<=120): return self.send_json({"error":"Для VK укажите секрет и строку подтверждения Callback API"},400)
                with connect() as db:
                    params=(uid,platform,source_ref,title or ("Telegram-группа" if platform=="telegram" else "Сообщество VK"),"active",hashlib.sha256(callback_secret.encode("utf-8")).hexdigest() if callback_secret else "",confirmation_code if platform=="vk" else "",now,now)
                    if DATABASE_URL: row=db.execute("INSERT INTO partner_sources(owner_id,platform,source_ref,title,status,secret_hash,confirmation_code,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(platform,source_ref) DO UPDATE SET owner_id=excluded.owner_id,title=excluded.title,status='active',secret_hash=excluded.secret_hash,confirmation_code=excluded.confirmation_code,updated_at=excluded.updated_at RETURNING id",params).fetchone(); source_id=int(row["id"])
                    else:
                        db.execute("INSERT INTO partner_sources(owner_id,platform,source_ref,title,status,secret_hash,confirmation_code,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(platform,source_ref) DO UPDATE SET owner_id=excluded.owner_id,title=excluded.title,status='active',secret_hash=excluded.secret_hash,confirmation_code=excluded.confirmation_code,updated_at=excluded.updated_at",params)
                        row=db.execute("SELECT id FROM partner_sources WHERE platform=? AND source_ref=?",(platform,source_ref)).fetchone(); source_id=int(row[0])
                record_audit(uid,"partner_source_saved",f"{platform}:{source_ref}")
                return self.send_json({"ok":True,"id":source_id,"platform":platform,"status":"active"},201)
            source_enable=re.fullmatch(r"/api/admin/partner-sources/(\d+)/enable",path)
            if source_enable:
                if not can_manage_staff(uid): return self.send_json({"error":"Доступ только для администратора"},403)
                with connect() as db: cur=db.execute("UPDATE partner_sources SET status='active',updated_at=? WHERE id=? AND status='disabled'",(now,int(source_enable.group(1))))
                if not cur.rowcount: return self.send_json({"error":"Источник не найден или уже включён"},404)
                record_audit(uid,"partner_source_enabled",source_enable.group(1))
                return self.send_json({"ok":True,"status":"active"})
            if path=="/api/cars":
                if not rate_allowed((uid,"create"),10,3600): return self.send_json({"error":"Слишком много объявлений. Попробуйте позже"},429)
                name=clean_text(data.get("name"),80); price=int(data.get("price") or 0); year=int(data.get("year") or 0); km=int(str(data.get("km","0")).replace(" км","").replace(" ","") or 0)
                if len(name)<2 or price<1000 or not 1950<=year<=NOW().year+1 or km<0: return self.send_json({"error":"Проверьте марку, цену, год и пробег"},400)
                publish_key=str(data.get("publish_key") or "").strip()
                if publish_key and not re.fullmatch(r"[A-Za-z0-9_-]{16,80}",publish_key): return self.send_json({"error":"Некорректный идентификатор публикации"},400)
                try: import_id=int(data.get("import_id") or 0)
                except (TypeError,ValueError): return self.send_json({"error":"Некорректный черновик"},400)
                if import_id<0: return self.send_json({"error":"Некорректный черновик"},400)
                if import_id:
                    with connect() as db: imported_draft=db.execute("SELECT status,published_car_id FROM import_drafts WHERE id=? AND user_id=?",(import_id,uid)).fetchone()
                    if not imported_draft: return self.send_json({"error":"Черновик не найден"},404)
                if publish_key:
                    with connect() as db:
                        existing=db.execute("SELECT id FROM cars WHERE owner_id=? AND publish_key=?",(uid,publish_key)).fetchone()
                        if existing and import_id:
                            existing_id=existing["id"] if DATABASE_URL else existing[0]
                            draft_status=imported_draft["status"] if DATABASE_URL else imported_draft[0]; draft_car=imported_draft["published_car_id"] if DATABASE_URL else imported_draft[1]
                            if draft_status=='draft': db.execute("UPDATE import_drafts SET status='published',published_car_id=? WHERE id=? AND user_id=?",(existing_id,import_id,uid))
                            elif draft_status!='published' or int(draft_car or 0)!=int(existing_id): return self.send_json({"error":"Черновик уже использован"},409)
                    if existing: return self.send_json({"ok":True,"id":existing["id"] if DATABASE_URL else existing[0],"duplicate":True},200)
                if import_id:
                    draft_status=imported_draft["status"] if DATABASE_URL else imported_draft[0]
                    if draft_status!='draft': return self.send_json({"error":"Черновик уже опубликован"},409)
                urgent=bool(data.get("urgent")); deal="Срочно" if urgent else ("Обмен" if data.get("type")=="Обмен" else "Продажа"); until=(NOW()+timedelta(hours=24)).isoformat() if urgent else None
                accept_exchange=int(bool(data.get("accept_exchange") or data.get("type")=="Обмен"))
                phone=normalize_phone(data.get("phone")); phone_public=int(bool(phone) and data.get("phone_public") is True)
                if phone and not phone_public: return self.send_json({"error":"Для публикации телефона нужно отдельное разрешение"},400)
                with connect() as db: contact_user=db.execute("SELECT username FROM users WHERE id=?",(uid,)).fetchone()
                contact_username=(str(tg_user.get("username") or "") if tg_user else "") or (str(contact_user["username"] if DATABASE_URL else contact_user[0]) if contact_user else "")
                if not phone and not contact_username: return self.send_json({"error":"Укажите телефон: в вашем Telegram нет публичного username"},400)
                if data.get("contact_consent") is not True or str(data.get("policy_version") or "")!=POLICY_VERSION: return self.send_json({"error":"Отдельно разрешите показывать контакт покупателям"},400)
                images=data.get("images") if isinstance(data.get("images"),list) else ([data.get("image")] if data.get("image") else [])
                images=validated_images([x for x in images if x])
                image=images[0] if images else ""; images_json=json.dumps(images,ensure_ascii=False); thumbnail=str(data.get("thumbnail") or "")
                if thumbnail or image: thumbnail=validated_image(thumbnail or image,250_000,480)
                transmission=str(data.get("transmission") or "")[:30]; body_type=str(data.get("body_type") or "")[:30]; drive=str(data.get("drive") or "")[:30]; vin=re.sub(r"[^A-HJ-NPR-Z0-9]","",str(data.get("vin") or "").upper())[:17]
                fuel,engine_volume,engine_power,color,owners_count=vehicle_specs(data)
                if vin and len(vin)!=17: return self.send_json({"error":"VIN должен содержать 17 символов"},400)
                with connect() as db:
                    cur=db.execute("INSERT INTO cars(name,price,year,km,type,urgent,description,phone,phone_public,contact_consent_at,consent_version,owner_id,created_at,updated_at,urgent_until,image,images,transmission,body_type,drive,fuel,engine_volume,engine_power,color,owners_count,vin,thumbnail,accept_exchange,publish_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(name,price,year,f"{km:,}".replace(","," ")+" км",deal,int(urgent),clean_text(data.get("description"),2000),phone,phone_public,now,POLICY_VERSION,uid,now,now,until,image,images_json,transmission,body_type,drive,fuel,engine_volume,engine_power,color,owners_count,vin,thumbnail,accept_exchange,publish_key or None)); cid=cur.lastrowid
                    db.execute("UPDATE cars SET search_key=? WHERE id=?",(normalize_search(name),cid))
                    if import_id: db.execute("UPDATE import_drafts SET status='published',published_car_id=? WHERE id=? AND user_id=? AND status='draft'",(cid,import_id,uid))
                record_audit(uid,"listing_created",cid)
                if urgent: threading.Thread(target=notify_urgent,args=(cid,name[:80],price),daemon=True).start()
                threading.Thread(target=notify_saved_searches,args=(uid,{"id":cid,"name":name[:80],"price":price,"transmission":transmission,"body_type":body_type,"drive":drive,"fuel":fuel}),daemon=True).start()
                return self.send_json({"ok":True,"id":cid},201)
            m=re.fullmatch(r"/api/cars/(\d+)/favourite",path)
            if m:
                cid=int(m.group(1))
                with connect() as db:
                    car=db.execute("SELECT status FROM cars WHERE id=?",(cid,)).fetchone()
                    if not car: return self.send_json({"error":"Объявление не найдено"},404)
                    exists=db.execute("SELECT 1 FROM favourites WHERE user_id=? AND car_id=?",(uid,cid)).fetchone()
                    if exists: db.execute("DELETE FROM favourites WHERE user_id=? AND car_id=?",(uid,cid)); state=False
                    else:
                        status=car["status"] if DATABASE_URL else car[0]
                        if status!="active": return self.send_json({"error":"Объявление больше не активно"},409)
                        db.execute("INSERT INTO favourites(user_id,car_id,created_at) VALUES(?,?,?)",(uid,cid,now)); state=True
                return self.send_json({"ok":True,"favourite":state})
            if path=="/api/subscriptions":
                kind=str(data.get("kind") or "urgent")
                if kind=="urgent":
                    with connect() as db: db.execute("INSERT OR IGNORE INTO subscriptions(telegram_user,kind,created_at) VALUES(?,?,?)",(uid,"urgent",now))
                    return self.send_json({"ok":True,"urgent":True})
                if kind!="search": return self.send_json({"error":"Неизвестный тип подписки"},400)
                raw=data.get("filters") if isinstance(data.get("filters"),dict) else {}
                allowed_values={"transmission":{"Автомат","Механика","Робот","Вариатор"},"body_type":{"Седан","Хэтчбек","Универсал","Кроссовер","Внедорожник","Минивэн","Купе","Пикап"},"drive":{"Передний","Задний","Полный"},"fuel":{"Бензин","Дизель","Гибрид","Электро","Газ"}}
                filters={"q":clean_text(raw.get("q"),80)}
                for key,values in allowed_values.items():
                    value=str(raw.get(key) or ""); filters[key]=value if value in values else ""
                for key in ("price_min","price_max"):
                    value=raw.get(key)
                    if value not in (None,""):
                        try: filters[key]=max(0,min(int(value),100_000_000))
                        except (TypeError,ValueError): return self.send_json({"error":"Некорректная цена подписки"},400)
                if filters.get("price_min",0)>filters.get("price_max",100_000_000): return self.send_json({"error":"Минимальная цена выше максимальной"},400)
                if not any(value not in ("",None,0) for value in filters.values()): return self.send_json({"error":"Сначала задайте хотя бы один параметр поиска"},400)
                label=clean_text(data.get("name"),80) or "Подходящие автомобили"
                with connect() as db:
                    db.execute("DELETE FROM subscriptions WHERE telegram_user=? AND kind='search'",(uid,))
                    db.execute("INSERT INTO subscriptions(telegram_user,kind,created_at,filters,name) VALUES(?,?,?,?,?)",(uid,"search",now,json.dumps(filters,ensure_ascii=False),label))
                return self.send_json({"ok":True,"search":{"filters":filters,"name":label}})
            report=re.fullmatch(r"/api/cars/(\d+)/report",path)
            if report:
                cid=int(report.group(1)); reason=str(data.get("reason") or "other")[:40]; details=clean_text(data.get("details"),500)
                review_owner=None
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
                    if total>=3:
                        moved=db.execute("UPDATE cars SET status='review',updated_at=? WHERE id=? AND status='active'",(now,cid))
                        if moved.rowcount: review_owner=car["owner_id"] if DATABASE_URL else car[0]
                if review_owner:
                    threading.Thread(target=notify_exchange_user,args=(review_owner,"⚠️ Объявление временно отправлено на проверку после нескольких жалоб. Оно скрыто из каталога, но доступно в разделе «Мои объявления».",cid),daemon=True).start()
                return self.send_json({"ok":True,"under_review":total>=3},201)
            if path=="/api/exchanges":
                target=int(data.get("target_car_id") or 0); offered=int(data.get("offered_car_id") or 0) or None; offer_text=clean_text(data.get("offer_text"),500); cash_amount=int(data.get("cash_amount") or 0)
                if cash_amount<0 or cash_amount>100_000_000: return self.send_json({"error":"Проверьте сумму доплаты"},400)
                if not offered and len(offer_text)<3: return self.send_json({"error":"Опишите ваше предложение"},400)
                with connect() as db:
                    target_row=db.execute("SELECT owner_id,name,accept_exchange FROM cars WHERE id=? AND status='active'",(target,)).fetchone()
                    if not target_row: return self.send_json({"error":"Объявление не найдено"},404)
                    target_owner=target_row["owner_id"] if DATABASE_URL else target_row[0]
                    accepts=target_row["accept_exchange"] if DATABASE_URL else target_row[2]
                    if not accepts: return self.send_json({"error":"Продавец не принимает предложения обмена"},409)
                    if target_owner==uid: return self.send_json({"error":"Нельзя предложить обмен самому себе"},400)
                    offered_row=db.execute("SELECT name FROM cars WHERE id=? AND owner_id=? AND status='active'",(offered,uid)).fetchone() if offered else None
                    if offered and not offered_row: return self.send_json({"error":"Выберите своё активное объявление"},400)
                    if db.execute("SELECT 1 FROM exchanges WHERE from_user=? AND target_car_id=? AND status='new'",(uid,target)).fetchone(): return self.send_json({"error":"Предложение уже отправлено"},409)
                    db.execute("INSERT INTO exchanges(from_user,target_car_id,offered_car_id,message,offer_text,cash_amount,created_at) VALUES(?,?,?,?,?,?,?)",(uid,target,offered,clean_text(data.get("message"),500),offer_text,cash_amount,now))
                target_name=target_row["name"] if DATABASE_URL else target_row[1]; offered_name=(offered_row["name"] if DATABASE_URL else offered_row[0]) if offered_row else offer_text
                extra=f"\nДоплата: {cash_amount:,} ₽".replace(","," ") if cash_amount else ""
                threading.Thread(target=notify_exchange_user,args=(target_owner,f"🔄 Новое предложение\n\nВам предлагают: {offered_name}\nЗа автомобиль: {target_name}{extra}\n\nОткройте КРУГ, чтобы посмотреть предложение.",target),daemon=True).start()
                return self.send_json({"ok":True},201)
            return self.send_json({"error":"Маршрут не найден"},404)
        except (ValueError,json.JSONDecodeError) as exc: return self.send_json({"error":clean_text(exc,180) or "Проверьте данные"},400)
        except (TypeError,sqlite3.IntegrityError): return self.send_json({"error":"Запрос содержит некорректные данные"},400)
        except Exception as exc:
            print(f"POST failed: {type(exc).__name__}")
            return self.send_json({"error":"Внутренняя ошибка. Попробуйте позже"},500)
    def do_DELETE(self):
        if not self.valid_request_target() or not self.require_rate("delete_ip",200,60) or not self.require_origin(): return
        path=urlparse(self.path).path; uid,authenticated,_=auth_context(self.headers)
        if not self.require_auth(authenticated): return
        if not self.require_rate("delete",40,60,uid): return
        if path=="/api/account":
            deleted_actor="deleted:"+hashlib.sha256((WEBHOOK_SECRET+":"+uid).encode("utf-8")).hexdigest()[:20]
            with connect() as db:
                owned=db.execute("SELECT id FROM cars WHERE owner_id=?",(uid,)).fetchall(); car_ids=[int(r["id"] if DATABASE_URL else r[0]) for r in owned]
                db.execute("DELETE FROM favourites WHERE user_id=?",(uid,)); db.execute("DELETE FROM subscriptions WHERE telegram_user=?",(uid,)); db.execute("DELETE FROM reports WHERE reporter_id=?",(uid,)); db.execute("DELETE FROM exchanges WHERE from_user=?",(uid,)); db.execute("DELETE FROM car_views WHERE viewer_id=?",(uid,)); db.execute("DELETE FROM staff_roles WHERE user_id=?",(uid,)); db.execute("DELETE FROM import_drafts WHERE user_id=?",(uid,))
                db.execute("UPDATE staff_roles SET created_by=? WHERE created_by=?",(deleted_actor,uid))
                db.execute("UPDATE audit_log SET actor_id=? WHERE actor_id=?",(deleted_actor,uid))
                db.execute("UPDATE audit_log SET target='' WHERE target=? OR target LIKE ?",(uid,uid+":%"))
                for cid in car_ids: db.execute("DELETE FROM cars WHERE id=?",(cid,))
                db.execute("DELETE FROM users WHERE id=?",(uid,))
            record_audit(deleted_actor,"account_deleted")
            return self.send_json({"ok":True,"deleted":True})
        if not self.require_consent(uid): return
        imported=re.fullmatch(r"/api/imports/(\d+)",path)
        if imported:
            with connect() as db: cur=db.execute("DELETE FROM import_drafts WHERE id=? AND user_id=? AND status='draft'",(int(imported.group(1)),uid))
            return self.send_json({"ok":bool(cur.rowcount)},200 if cur.rowcount else 404)
        source=re.fullmatch(r"/api/admin/partner-sources/(\d+)",path)
        if source:
            if not can_manage_staff(uid): return self.send_json({"error":"Доступ только для администратора"},403)
            with connect() as db: cur=db.execute("UPDATE partner_sources SET status='disabled',updated_at=? WHERE id=? AND status<>'disabled'",(NOW().isoformat(),int(source.group(1))))
            if cur.rowcount: record_audit(uid,"partner_source_disabled",source.group(1))
            return self.send_json({"ok":bool(cur.rowcount)},200 if cur.rowcount else 404)
        exchange=re.fullmatch(r"/api/exchanges/(\d+)",path)
        if exchange:
            with connect() as db: cur=db.execute("DELETE FROM exchanges WHERE id=? AND from_user=? AND status='new'",(int(exchange.group(1)),uid))
            if cur.rowcount: record_audit(uid,"exchange_cancelled",exchange.group(1))
            return self.send_json({"ok":bool(cur.rowcount)},200 if cur.rowcount else 403)
        if path=="/api/subscriptions":
            kind=parse_qs(urlparse(self.path).query).get("kind",["urgent"])[0]
            if kind not in {"urgent","search"}: return self.send_json({"error":"Неизвестный тип подписки"},400)
            with connect() as db: db.execute("DELETE FROM subscriptions WHERE telegram_user=? AND kind=?",(uid,kind))
            return self.send_json({"ok":True,kind:False})
        staff=re.fullmatch(r"/api/admin/staff/([^/]+)",path)
        if staff:
            if not can_manage_staff(uid): return self.send_json({"error":"Доступ только для администратора"},403)
            target=staff.group(1)
            if target in ADMIN_IDS: return self.send_json({"error":"Нельзя удалить владельца"},400)
            with connect() as db: cur=db.execute("DELETE FROM staff_roles WHERE user_id=?",(target,))
            if cur.rowcount: record_audit(uid,"staff_removed",target)
            return self.send_json({"ok":bool(cur.rowcount)},200 if cur.rowcount else 404)
        m=re.fullmatch(r"/api/cars/(\d+)",path)
        if not m: return self.send_json({"error":"Маршрут не найден"},404)
        with connect() as db:
            cur=db.execute("UPDATE cars SET status='deleted',updated_at=? WHERE id=? AND owner_id=?",(NOW().isoformat(),int(m.group(1)),uid))
        if cur.rowcount: record_audit(uid,"listing_deleted",m.group(1))
        return self.send_json({"ok":bool(cur.rowcount)},200 if cur.rowcount else 403)
    def do_PUT(self):
        try:
            if not self.valid_request_target() or not self.require_rate("put_ip",400,60) or not self.require_origin(): return
            path=urlparse(self.path).path; data=self.read_json(); uid,authenticated,_=auth_context(self.headers,data=data)
            if not self.require_auth(authenticated): return
            if not self.require_rate("put",80,60,uid): return
            if not self.require_consent(uid): return
            moderation=re.fullmatch(r"/api/admin/reports/(\d+)",path)
            if moderation:
                if not can_moderate(uid): return self.send_json({"error":"Доступ только для модератора"},403)
                action=data.get("action")
                if action not in {"approve","block"}: return self.send_json({"error":"Неизвестное решение"},400)
                report_id=int(moderation.group(1)); new_car_status="active" if action=="approve" else "blocked"; owner=None; car_name=""
                with connect() as db:
                    row=db.execute("""SELECT r.car_id,c.owner_id,c.name FROM reports r JOIN cars c ON c.id=r.car_id
                        WHERE r.id=? AND r.status='new'""",(report_id,)).fetchone()
                    if not row: return self.send_json({"error":"Жалоба уже рассмотрена"},404)
                    car_id=row["car_id"] if DATABASE_URL else row[0]; owner=row["owner_id"] if DATABASE_URL else row[1]; car_name=row["name"] if DATABASE_URL else row[2]
                    db.execute("UPDATE cars SET status=?,updated_at=? WHERE id=?",(new_car_status,NOW().isoformat(),car_id))
                    db.execute("UPDATE reports SET status=? WHERE car_id=? AND status='new'",("approved" if action=="approve" else "blocked",car_id))
                result="возвращено в каталог" if action=="approve" else "заблокировано"
                record_audit(uid,"moderation_"+action,car_id)
                threading.Thread(target=notify_exchange_user,args=(owner,f"Решение модерации: объявление «{car_name}» {result}.",car_id),daemon=True).start()
                return self.send_json({"ok":True,"action":action,"car_status":new_car_status})
            if path=="/api/profile":
                role="dealer_pending" if data.get("role")=="dealer" else "private"; company=clean_text(data.get("company"),100)
                if role=="dealer_pending" and len(company)<2: return self.send_json({"error":"Укажите название компании"},400)
                with connect() as db: cur=db.execute("UPDATE users SET role=?,company=?,dealer_verified=0,updated_at=? WHERE id=?",(role,company,NOW().isoformat(),uid))
                return self.send_json({"ok":bool(cur.rowcount),"role":role,"company":company},200 if cur.rowcount else 404)
            exchange=re.fullmatch(r"/api/exchanges/(\d+)",path)
            if exchange:
                status={"accept":"accepted","reject":"rejected"}.get(data.get("action"))
                if not status: return self.send_json({"error":"Неизвестное действие"},400)
                with connect() as db:
                    exchange_row=db.execute("""SELECT e.from_user,e.target_car_id,target.name AS target_name,offered.name AS offered_name
                        FROM exchanges e JOIN cars target ON target.id=e.target_car_id LEFT JOIN cars offered ON offered.id=e.offered_car_id
                        WHERE e.id=? AND target.owner_id=? AND e.status='new'""",(int(exchange.group(1)),uid)).fetchone()
                    cur=db.execute("""UPDATE exchanges SET status=? WHERE id=? AND status='new'
                        AND EXISTS(SELECT 1 FROM cars WHERE cars.id=exchanges.target_car_id AND cars.owner_id=?)""",(status,int(exchange.group(1)),uid))
                if cur.rowcount and exchange_row:
                    sender=exchange_row["from_user"] if DATABASE_URL else exchange_row[0]; target_id=exchange_row["target_car_id"] if DATABASE_URL else exchange_row[1]; target_name=exchange_row["target_name"] if DATABASE_URL else exchange_row[2]
                    result="принято ✅" if status=="accepted" else "отклонено"
                    threading.Thread(target=notify_exchange_user,args=(sender,f"🔄 Ваше предложение обмена на {target_name} {result}.\n\nОткройте КРУГ, чтобы посмотреть подробности.",target_id),daemon=True).start()
                return self.send_json({"ok":bool(cur.rowcount),"status":status},200 if cur.rowcount else 403)
            m=re.fullmatch(r"/api/cars/(\d+)",path)
            if not m: return self.send_json({"error":"Маршрут не найден"},404)
            if data.get("action")=="edit":
                name=clean_text(data.get("name"),80); price=int(data.get("price") or 0); year=int(data.get("year") or 0); km=int(data.get("km") or 0)
                if len(name)<2 or price<1000 or not 1950<=year<=NOW().year+1 or km<0: return self.send_json({"error":"Проверьте марку, цену, год и пробег"},400)
                urgent=bool(data.get("urgent")); deal="Срочно" if urgent else ("Обмен" if data.get("type")=="Обмен" else "Продажа"); until=(NOW()+timedelta(hours=24)).isoformat() if urgent else None
                accept_exchange=int(bool(data.get("accept_exchange") or data.get("type")=="Обмен"))
                phone=normalize_phone(data.get("phone")); phone_public=int(bool(phone) and data.get("phone_public") is True); images=data.get("images") if isinstance(data.get("images"),list) else []
                if phone and not phone_public: return self.send_json({"error":"Для публикации телефона нужно отдельное разрешение"},400)
                with connect() as db: contact_user=db.execute("SELECT username FROM users WHERE id=?",(uid,)).fetchone()
                contact_username=str(contact_user["username"] if DATABASE_URL else contact_user[0]) if contact_user else ""
                if not phone and not contact_username: return self.send_json({"error":"Укажите телефон: в вашем Telegram нет публичного username"},400)
                if data.get("contact_consent") is not True or str(data.get("policy_version") or "")!=POLICY_VERSION: return self.send_json({"error":"Отдельно разрешите показывать контакт покупателям"},400)
                images=validated_images([x for x in images if x])
                image=images[0] if images else ""; images_json=json.dumps(images,ensure_ascii=False); thumbnail=str(data.get("thumbnail") or ""); transmission=str(data.get("transmission") or "")[:30]; body_type=str(data.get("body_type") or "")[:30]; drive=str(data.get("drive") or "")[:30]; vin=re.sub(r"[^A-HJ-NPR-Z0-9]","",str(data.get("vin") or "").upper())[:17]
                fuel,engine_volume,engine_power,color,owners_count=vehicle_specs(data)
                if thumbnail or image: thumbnail=validated_image(thumbnail or image,250_000,480)
                if vin and len(vin)!=17: return self.send_json({"error":"VIN должен содержать 17 символов"},400)
                cid=int(m.group(1)); old_price=None
                with connect() as db:
                    old=db.execute("SELECT price FROM cars WHERE id=? AND owner_id=? AND status<>'deleted'",(cid,uid)).fetchone(); old_price=int(old["price"] if DATABASE_URL else old[0]) if old else None
                    cur=db.execute("""UPDATE cars SET name=?,price=?,year=?,km=?,type=?,urgent=?,description=?,phone=?,phone_public=?,contact_consent_at=?,consent_version=?,updated_at=?,urgent_until=?,image=?,images=?,transmission=?,body_type=?,drive=?,fuel=?,engine_volume=?,engine_power=?,color=?,owners_count=?,vin=?,thumbnail=?,accept_exchange=? WHERE id=? AND owner_id=? AND status<>'deleted'""",(name,price,year,f"{km:,}".replace(","," ")+" км",deal,int(urgent),clean_text(data.get("description"),2000),phone,phone_public,NOW().isoformat(),POLICY_VERSION,NOW().isoformat(),until,image,images_json,transmission,body_type,drive,fuel,engine_volume,engine_power,color,owners_count,vin,thumbnail,accept_exchange,cid,uid))
                    if cur.rowcount: db.execute("UPDATE cars SET search_key=? WHERE id=?",(normalize_search(name),cid))
                    if cur.rowcount and old_price is not None and old_price!=price: db.execute("INSERT INTO price_history(car_id,old_price,new_price,changed_at) VALUES(?,?,?,?)",(cid,old_price,price,NOW().isoformat()))
                if cur.rowcount and old_price is not None and price<old_price: threading.Thread(target=notify_price_drop,args=(cid,name[:80],old_price,price),daemon=True).start()
                if cur.rowcount: record_audit(uid,"listing_edited",cid)
                return self.send_json({"ok":bool(cur.rowcount)},200 if cur.rowcount else 403)
            status={"archive":"archived","activate":"active","sold":"sold"}.get(data.get("action"))
            if not status: return self.send_json({"error":"Неизвестное действие"},400)
            with connect() as db: cur=db.execute("UPDATE cars SET status=?,updated_at=? WHERE id=? AND owner_id=? AND status IN ('active','archived','sold')",(status,NOW().isoformat(),int(m.group(1)),uid))
            if cur.rowcount: record_audit(uid,"listing_status",f"{m.group(1)}:{status}")
            return self.send_json({"ok":bool(cur.rowcount),"status":status},200 if cur.rowcount else 403)
        except (ValueError,json.JSONDecodeError) as exc: return self.send_json({"error":clean_text(exc,180) or "Проверьте данные"},400)
        except Exception as exc:
            print(f"PUT failed: {type(exc).__name__}")
            return self.send_json({"error":"Внутренняя ошибка. Попробуйте позже"},500)

class SecureHTTPServer(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=128

if __name__=="__main__":
    port=int(os.environ.get("PORT","4173")); init_db(); start_thumbnail_backfill(); purge_expired_data()
    if not BOT_TOKEN and not ALLOW_DEV_AUTH: print("WARNING: Telegram token is missing; all personal actions are disabled")
    if not LEGAL_READY: print("WARNING: legal operator details or confirmed Russian data residency are missing; new consent cannot be collected")
    threading.Thread(target=retention_loop,daemon=True).start(); threading.Thread(target=setup_telegram_webhook,daemon=True).start(); print(f"KRUG on {port}"); SecureHTTPServer(("0.0.0.0",port),Handler).serve_forever()
