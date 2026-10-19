import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = "cope-tex-secret-2025"

DB = "cope_tex.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS operateurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        poste TEXT,
        code TEXT UNIQUE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        ref TEXT UNIQUE,
        gamme TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS ofs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        num TEXT UNIQUE,
        article_id INTEGER,
        article_nom TEXT,
        gamme TEXT,
        qte INTEGER,
        date_livraison TEXT,
        avancement TEXT,
        date_creation TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS saisies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        of_id INTEGER,
        of_num TEXT,
        article TEXT,
        operation TEXT,
        operateur TEXT,
        date TEXT,
        heure INTEGER,
        qte INTEGER,
        rebut INTEGER DEFAULT 0,
        timestamp TEXT
    )""")
    # Créer le chef d'atelier par défaut
    c.execute("SELECT * FROM operateurs WHERE code='CHEF'")
    if not c.fetchone():
        c.execute("INSERT INTO operateurs (nom, poste, code) VALUES (?, ?, ?)",
                  ("Chef d'atelier", "Administration", "CHEF"))
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

import json

@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"], poste=session.get("poste"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        conn = get_db()
        op = conn.execute("SELECT * FROM operateurs WHERE code=?", (code,)).fetchone()
        conn.close()
        if op:
            session["user"] = op["nom"]
            session["poste"] = op["poste"]
            session["user_id"] = op["id"]
            return redirect(url_for("home"))
        return render_template("login.html", error="Code incorrect")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------- API OPÉRATEURS ----------
@app.route("/api/operateurs", methods=["GET"])
def get_operateurs():
    conn = get_db()
    ops = conn.execute("SELECT * FROM operateurs WHERE code != 'CHEF' ORDER BY nom").fetchall()
    conn.close()
    return jsonify([dict(o) for o in ops])

@app.route("/api/operateurs", methods=["POST"])
def add_operateur():
    data = request.json
    conn = get_db()
    try:
        conn.execute("INSERT INTO operateurs (nom, poste, code) VALUES (?, ?, ?)",
                     (data["nom"], data.get("poste", ""), data["code"].upper()))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        conn.close()

@app.route("/api/operateurs/<int:oid>", methods=["DELETE"])
def del_operateur(oid):
    conn = get_db()
    conn.execute("DELETE FROM operateurs WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ---------- API ARTICLES ----------
@app.route("/api/articles", methods=["GET"])
def get_articles():
    conn = get_db()
    arts = conn.execute("SELECT * FROM articles ORDER BY nom").fetchall()
    conn.close()
    result = []
    for a in arts:
        d = dict(a)
        d["gamme"] = json.loads(d["gamme"]) if d["gamme"] else []
        result.append(d)
    return jsonify(result)

@app.route("/api/articles", methods=["POST"])
def add_article():
    data = request.json
    conn = get_db()
    try:
        conn.execute("INSERT INTO articles (nom, ref, gamme) VALUES (?, ?, ?)",
                     (data["nom"], data["ref"], json.dumps(data["gamme"])))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        conn.close()

@app.route("/api/articles/<int:aid>", methods=["DELETE"])
def del_article(aid):
    conn = get_db()
    conn.execute("DELETE FROM articles WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ---------- API OF ----------
@app.route("/api/ofs", methods=["GET"])
def get_ofs():
    conn = get_db()
    ofs = conn.execute("SELECT * FROM ofs ORDER BY id DESC").fetchall()
    conn.close()
    result = []
    for o in ofs:
        d = dict(o)
        d["gamme"] = json.loads(d["gamme"]) if d["gamme"] else []
        d["avancement"] = json.loads(d["avancement"]) if d["avancement"] else []
        result.append(d)
    return jsonify(result)

@app.route("/api/ofs", methods=["POST"])
def add_of():
    data = request.json
    conn = get_db()
    try:
        count = conn.execute("SELECT COUNT(*) FROM ofs").fetchone()[0]
        num = f"OF-{datetime.now().year}-{count+1:03d}"
        gamme = data["gamme"]
        avancement = [0] * len(gamme)
        conn.execute("""INSERT INTO ofs (num, article_id, article_nom, gamme, qte, date_livraison, avancement, date_creation)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                     (num, data["article_id"], data["article_nom"], json.dumps(gamme),
                      data["qte"], data["date_livraison"], json.dumps(avancement),
                      datetime.now().isoformat()))
        conn.commit()
        return jsonify({"ok": True, "num": num})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        conn.close()

@app.route("/api/ofs/<int:oid>", methods=["DELETE"])
def del_of(oid):
    conn = get_db()
    conn.execute("DELETE FROM ofs WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ---------- API SAISIES ----------
@app.route("/api/saisies", methods=["GET"])
def get_saisies():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    conn = get_db()
    s = conn.execute("SELECT * FROM saisies WHERE date=? ORDER BY id DESC", (date,)).fetchall()
    conn.close()
    return jsonify([dict(x) for x in s])

@app.route("/api/saisies", methods=["POST"])
def add_saisie():
    data = request.json
    conn = get_db()
    try:
        # Mettre à jour l'avancement de l'OF
        of = conn.execute("SELECT * FROM ofs WHERE id=?", (data["of_id"],)).fetchone()
        if not of:
            return jsonify({"ok": False, "error": "OF introuvable"}), 404
        avancement = json.loads(of["avancement"])
        op_idx = data["op_index"]
        avancement[op_idx] = avancement[op_idx] + data["qte"]
        conn.execute("UPDATE ofs SET avancement=? WHERE id=?",
                     (json.dumps(avancement), data["of_id"]))
        # Enregistrer la saisie
        conn.execute("""INSERT INTO saisies (of_id, of_num, article, operation, operateur, date, heure, qte, rebut, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (data["of_id"], of["num"], of["article_nom"], data["operation"],
                      session.get("user", "?"), datetime.now().strftime("%Y-%m-%d"),
                      data["heure"], data["qte"], data.get("rebut", 0),
                      datetime.now().isoformat()))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        conn.close()

@app.route("/api/rapport", methods=["GET"])
def rapport():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    conn = get_db()
    rows = conn.execute("""SELECT operateur, SUM(qte) as total, SUM(rebut) as rebuts
                          FROM saisies WHERE date=? GROUP BY operateur""", (date,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)