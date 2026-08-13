"""Локальный сервер MVP «КРУГ»: объявления, подписки и SQLite."""
import json, os, sqlite3
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB = ROOT / "krug.db"

def connect():
    db = sqlite3.connect(DB); db.row_factory = sqlite3.Row; return db

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS cars(id INTEGER PRIMARY KEY, name TEXT NOT NULL, price INTEGER NOT NULL, year INTEGER NOT NULL, km TEXT NOT NULL, type TEXT NOT NULL, urgent INTEGER NOT NULL DEFAULT 0, pos TEXT NOT NULL DEFAULT '50% 50%', description TEXT DEFAULT '', phone TEXT DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY, telegram_user TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'urgent', created_at TEXT NOT NULL, UNIQUE(telegram_user,kind));
        """)
        if not db.execute("SELECT COUNT(*) FROM cars").fetchone()[0]:
            seed=[("Toyota RAV4",2890000,2021,"54 000 км","Продажа",0,"70% 50%"),("Kia K5",2470000,2020,"72 000 км","Обмен",0,"18% 50%"),("Lada Granta",690000,2019,"91 000 км","Срочно",1,"49% 50%"),("Hyundai Solaris",1450000,2018,"86 000 км","Срочно",1,"48% 50%"),("Ford Focus",290000,2007,"181 000 км","Обмен",0,"23% 50%"),("ВАЗ 2114",95000,2008,"210 000 км","Срочно",1,"48% 50%")]
            now=datetime.now(timezone.utc).isoformat()
            db.executemany("INSERT INTO cars(name,price,year,km,type,urgent,pos,created_at) VALUES(?,?,?,?,?,?,?,?)",[(*x,now) for x in seed])

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
    def send_json(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def read_json(self):
        n=int(self.headers.get("Content-Length","0"));
        if n>1_000_000: raise ValueError("Слишком большой запрос")
        return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/api/health": return self.send_json({"ok":True,"service":"krug"})
        if path=="/api/cars":
            with connect() as db: rows=db.execute("SELECT * FROM cars ORDER BY urgent DESC,id DESC").fetchall()
            return self.send_json([dict(x) for x in rows])
        return super().do_GET()
    def do_POST(self):
        try:
            path=urlparse(self.path).path; data=self.read_json(); now=datetime.now(timezone.utc).isoformat()
            if path=="/api/cars":
                if any(not data.get(k) for k in ("name","price","year")): return self.send_json({"error":"Заполните марку, цену и год"},400)
                urgent=int(bool(data.get("urgent"))); deal="Срочно" if urgent else data.get("type","Продажа")
                with connect() as db:
                    cur=db.execute("INSERT INTO cars(name,price,year,km,type,urgent,description,phone,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(str(data["name"])[:80],int(data["price"]),int(data["year"]),str(data.get("km","0 км"))[:30],deal,urgent,str(data.get("description",""))[:2000],str(data.get("phone",""))[:40],now)); new_id=cur.lastrowid
                return self.send_json({"ok":True,"id":new_id},HTTPStatus.CREATED)
            if path=="/api/subscriptions":
                with connect() as db: db.execute("INSERT OR IGNORE INTO subscriptions(telegram_user,kind,created_at) VALUES(?,?,?)",(str(data.get("user","local-user"))[:80],"urgent",now))
                return self.send_json({"ok":True},HTTPStatus.CREATED)
            return self.send_json({"error":"Маршрут не найден"},404)
        except (ValueError,TypeError,json.JSONDecodeError) as e: return self.send_json({"error":str(e)},400)

if __name__=="__main__":
    port=int(os.environ.get("PORT","4173"))
    init_db(); print(f"КРУГ запущен на порту {port}"); ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
