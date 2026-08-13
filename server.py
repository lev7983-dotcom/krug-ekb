"""KRUG marketplace API: users, listings, favourites, subscriptions and exchanges."""
import json, os, re, sqlite3
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get("KRUG_DB_PATH",ROOT/"krug.db"))
DATABASE_URL=os.environ.get("DATABASE_URL","")
NOW=lambda: datetime.now(timezone.utc)

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
        """)
        add_column(db,"cars","owner_id","TEXT NOT NULL DEFAULT 'demo'")
        add_column(db,"cars","status","TEXT NOT NULL DEFAULT 'active'")
        add_column(db,"cars","urgent_until","TEXT DEFAULT NULL")
        add_column(db,"cars","updated_at","TEXT DEFAULT NULL")
        add_column(db,"cars","image","TEXT DEFAULT ''")
        count_row=db.execute("SELECT COUNT(*) AS count FROM cars").fetchone()
        if not (count_row["count"] if DATABASE_URL else count_row[0]):
            seed=[("Toyota RAV4",2890000,2021,"54 000 км","Продажа",0,"70% 50%"),("Kia K5",2470000,2020,"72 000 км","Обмен",0,"18% 50%"),("Lada Granta",690000,2019,"91 000 км","Срочно",1,"49% 50%"),("Hyundai Solaris",1450000,2018,"86 000 км","Срочно",1,"48% 50%"),("Ford Focus",290000,2007,"181 000 км","Обмен",0,"23% 50%"),("ВАЗ 2114",95000,2008,"210 000 км","Срочно",1,"48% 50%")]
            now=NOW().isoformat(); urgent=(NOW()+timedelta(hours=24)).isoformat()
            db.executemany("INSERT INTO cars(name,price,year,km,type,urgent,pos,created_at,updated_at,urgent_until) VALUES(?,?,?,?,?,?,?,?,?,?)",[(*x,now,now,urgent if x[5] else None) for x in seed])

def user_id(headers,data=None,query=None):
    value=headers.get("X-Krug-User") or (data or {}).get("user") or (query or {}).get("user",["local-user"])[0]
    return re.sub(r"[^a-zA-Z0-9_-]","",str(value))[:80] or "local-user"

def car_dict(row,faved=False):
    d=dict(row); until=d.get("urgent_until")
    if d.get("urgent") and until:
        try:
            if datetime.fromisoformat(until)<NOW(): d["urgent"]=0; d["type"]="Продажа"
        except ValueError: pass
    d["favourite"]=bool(faved); return d

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
    def send_json(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False).encode("utf-8"); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def read_json(self):
        n=int(self.headers.get("Content-Length","0"))
        if n>4_000_000: raise ValueError("Слишком большой запрос")
        return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        parsed=urlparse(self.path); path=parsed.path; query=parse_qs(parsed.query); uid=user_id(self.headers,query=query)
        if path=="/api/health": return self.send_json({"ok":True,"service":"krug","version":2})
        if path=="/api/cars":
            with connect() as db:
                rows=db.execute("SELECT c.*, EXISTS(SELECT 1 FROM favourites f WHERE f.car_id=c.id AND f.user_id=?) AS faved FROM cars c WHERE c.status='active' ORDER BY c.urgent DESC,c.id DESC",(uid,)).fetchall()
            return self.send_json([car_dict(r,r["faved"]) for r in rows])
        if path=="/api/me":
            with connect() as db:
                u=db.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); lr=db.execute("SELECT COUNT(*) AS count FROM cars WHERE owner_id=? AND status='active'",(uid,)).fetchone(); fr=db.execute("SELECT COUNT(*) AS count FROM favourites WHERE user_id=?",(uid,)).fetchone(); er=db.execute("SELECT COUNT(*) AS count FROM exchanges e JOIN cars c ON c.id=e.target_car_id WHERE c.owner_id=? AND e.status='new'",(uid,)).fetchone(); listings=lr["count"] if DATABASE_URL else lr[0]; favs=fr["count"] if DATABASE_URL else fr[0]; offers=er["count"] if DATABASE_URL else er[0]
            return self.send_json({"user":dict(u) if u else None,"listings":listings,"favourites":favs,"offers":offers})
        if path=="/api/my-cars":
            with connect() as db: rows=db.execute("SELECT * FROM cars WHERE owner_id=? ORDER BY id DESC",(uid,)).fetchall()
            return self.send_json([car_dict(r) for r in rows])
        if path=="/api/exchanges":
            with connect() as db:
                rows=db.execute("""SELECT e.*, target.name AS target_name, offered.name AS offered_name
                    FROM exchanges e JOIN cars target ON target.id=e.target_car_id
                    LEFT JOIN cars offered ON offered.id=e.offered_car_id
                    WHERE e.from_user=? OR target.owner_id=? ORDER BY e.id DESC""",(uid,uid)).fetchall()
            return self.send_json([dict(r) for r in rows])
        return super().do_GET()
    def do_POST(self):
        try:
            path=urlparse(self.path).path; data=self.read_json(); uid=user_id(self.headers,data=data); now=NOW().isoformat()
            if path=="/api/session":
                first=str(data.get("first_name") or "Пользователь")[:80]; username=str(data.get("username") or "")[:80]
                with connect() as db: db.execute("INSERT INTO users(id,first_name,username,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET first_name=excluded.first_name,username=excluded.username,updated_at=excluded.updated_at",(uid,first,username,now,now))
                return self.send_json({"ok":True,"user":uid})
            if path=="/api/cars":
                name=str(data.get("name","")).strip(); price=int(data.get("price") or 0); year=int(data.get("year") or 0); km=int(str(data.get("km","0")).replace(" км","").replace(" ","") or 0)
                if len(name)<2 or price<1000 or not 1950<=year<=NOW().year+1 or km<0: return self.send_json({"error":"Проверьте марку, цену, год и пробег"},400)
                urgent=bool(data.get("urgent")); deal="Срочно" if urgent else ("Обмен" if data.get("type")=="Обмен" else "Продажа"); until=(NOW()+timedelta(hours=24)).isoformat() if urgent else None
                phone=str(data.get("phone","")).strip()
                if phone and len(re.sub(r"\D","",phone))<10: return self.send_json({"error":"Проверьте номер телефона"},400)
                image=str(data.get("image", ""))
                if image and (not image.startswith("data:image/") or len(image)>3_000_000): return self.send_json({"error":"Фотография слишком большая"},400)
                with connect() as db:
                    cur=db.execute("INSERT INTO cars(name,price,year,km,type,urgent,description,phone,owner_id,created_at,updated_at,urgent_until,image) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(name[:80],price,year,f"{km:,}".replace(","," ")+" км",deal,int(urgent),str(data.get("description", ""))[:2000],phone[:40],uid,now,now,until,image)); cid=cur.lastrowid
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
            if path=="/api/exchanges":
                target=int(data.get("target_car_id") or 0); offered=int(data.get("offered_car_id") or 0) or None
                with connect() as db:
                    if not db.execute("SELECT 1 FROM cars WHERE id=? AND status='active'",(target,)).fetchone(): return self.send_json({"error":"Объявление не найдено"},404)
                    db.execute("INSERT INTO exchanges(from_user,target_car_id,offered_car_id,message,created_at) VALUES(?,?,?,?,?)",(uid,target,offered,str(data.get("message", ""))[:500],now))
                return self.send_json({"ok":True},201)
            return self.send_json({"error":"Маршрут не найден"},404)
        except (ValueError,TypeError,json.JSONDecodeError,sqlite3.IntegrityError) as e: return self.send_json({"error":str(e)},400)
    def do_DELETE(self):
        m=re.fullmatch(r"/api/cars/(\d+)",urlparse(self.path).path); uid=user_id(self.headers)
        if not m: return self.send_json({"error":"Маршрут не найден"},404)
        with connect() as db:
            cur=db.execute("UPDATE cars SET status='deleted',updated_at=? WHERE id=? AND owner_id=?",(NOW().isoformat(),int(m.group(1)),uid))
        return self.send_json({"ok":bool(cur.rowcount)},200 if cur.rowcount else 403)
    def do_PUT(self):
        try:
            m=re.fullmatch(r"/api/cars/(\d+)",urlparse(self.path).path); data=self.read_json(); uid=user_id(self.headers,data=data)
            if not m: return self.send_json({"error":"Маршрут не найден"},404)
            status={"archive":"archived","activate":"active"}.get(data.get("action"))
            if not status: return self.send_json({"error":"Неизвестное действие"},400)
            with connect() as db: cur=db.execute("UPDATE cars SET status=?,updated_at=? WHERE id=? AND owner_id=?",(status,NOW().isoformat(),int(m.group(1)),uid))
            return self.send_json({"ok":bool(cur.rowcount),"status":status},200 if cur.rowcount else 403)
        except (ValueError,json.JSONDecodeError) as e: return self.send_json({"error":str(e)},400)

if __name__=="__main__":
    port=int(os.environ.get("PORT","4173")); init_db(); print(f"KRUG on {port}"); ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
