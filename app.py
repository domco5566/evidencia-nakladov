import sqlite3
from flask import Flask, render_template, request, redirect, url_for, g

# --- Konfigurácia aplikácie ---
app = Flask(__name__)
app.config['DATABASE'] = 'data/naklady.db'


# --- Pomocné funkcie pre prácu s DB ---
def get_db():
    """Vytvorí a vráti spojenie s databázou pre aktuálny request."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row  # Umožní pristupovať k stĺpcom podľa mena
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Automaticky uzavrie spojenie s DB po skončení requestu."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    """Spustí dopyt na databázu a vráti výsledky."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


# --- Hlavné routy (stránky) aplikácie ---

@app.route("/", methods=['GET', 'POST'])
def login():
    """Prihlasovacia stránka."""
    if request.method == 'POST':
        meno = request.form['meno'].strip()
        user = query_db('SELECT * FROM pouzivatelia WHERE meno = ?', [meno], one=True)
        if user:
            return redirect(url_for('dashboard', meno=meno))
        else:
            return render_template('login.html', error="Používateľ neexistuje.")
    return render_template('login.html')


@app.route("/dashboard/<meno>", methods=['GET', 'POST'])
def dashboard(meno):
    """Hlavná stránka s aktívnymi nákladmi."""
    user = query_db('SELECT * FROM pouzivatelia WHERE meno = ?', [meno], one=True)
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Logika pre vytvorenie nového výdavku
        nazov = request.form['nazov']
        suma = float(request.form['suma'])
        ostatni_podielnici_ids = request.form.getlist('podielnici')
        finalny_zoznam_ids = ostatni_podielnici_ids + [str(user['id'])]

        db = get_db()
        cursor = db.cursor()

        cursor.execute('INSERT INTO vydavky (nazov, celkova_suma, kto_platil_id) VALUES (?, ?, ?)',
                       (nazov, suma, user['id']))
        vydavok_id = cursor.lastrowid

        pocet_podielnikov = len(finalny_zoznam_ids)
        suma_podielu = round(suma / pocet_podielnikov, 2) if pocet_podielnikov > 0 else suma

        # OPRAVENÁ ČASŤ: Správne nastavenie stavu 'zaplatene' pre platcu
        for pid in finalny_zoznam_ids:
            je_zaplatene = 1 if int(pid) == user['id'] else 0
            cursor.execute(
                'INSERT INTO podielnici (vydavok_id, pouzivatel_id, suma_podielu, zaplatene) VALUES (?, ?, ?, ?)',
                (vydavok_id, int(pid), suma_podielu, je_zaplatene))
        db.commit()
        return redirect(url_for('dashboard', meno=meno))

    # Logika pre zobrazenie dashboardu
    vsetci_pouzivatelia = query_db('SELECT * FROM pouzivatelia')

    # Získame iba AKTÍVNE výdavky
    vydavky = query_db("""
                       SELECT DISTINCT v.id, v.nazov, v.celkova_suma, p.meno as kto_platil
                       FROM vydavky v
                                JOIN pouzivatelia p ON v.kto_platil_id = p.id
                                JOIN podielnici pd ON v.id = pd.vydavok_id
                       WHERE pd.zaplatene = 0
                       ORDER BY v.datum_vytvorenia DESC
                       """)

    dlhujes_suma = query_db("""
                            SELECT IFNULL(SUM(suma_podielu), 0) as total
                            FROM podielnici
                            WHERE pouzivatel_id = ?
                              AND zaplatene = 0
                              AND vydavok_id IN (SELECT id FROM vydavky WHERE kto_platil_id != ?)
                            """, [user['id'], user['id']], one=True)['total']

    dlzia_ti_suma = query_db("""
                             SELECT IFNULL(SUM(p.suma_podielu), 0) as total
                             FROM podielnici p
                                      JOIN vydavky v ON p.vydavok_id = v.id
                             WHERE v.kto_platil_id = ?
                               AND p.pouzivatel_id != ? AND p.zaplatene = 0
                             """, [user['id'], user['id']], one=True)['total']

    return render_template('dashboard.html',
                           user=user,
                           vydavky=vydavky,
                           pouzivatelia=vsetci_pouzivatelia,
                           dlhujes=dlhujes_suma,
                           dlzia_ti=dlzia_ti_suma)


@app.route("/vydavok/<int:vydavok_id>/<meno>")
def vydavok_detail(vydavok_id, meno):
    """Detail konkrétneho výdavku."""
    user = query_db('SELECT * FROM pouzivatelia WHERE meno = ?', [meno], one=True)
    vydavok = query_db(
        'SELECT v.*, p.meno as kto_platil FROM vydavky v JOIN pouzivatelia p ON v.kto_platil_id = p.id WHERE v.id = ?',
        [vydavok_id], one=True)
    podielnici = query_db("""
                          SELECT pd.*, p.meno
                          FROM podielnici pd
                                   JOIN pouzivatelia p ON pd.pouzivatel_id = p.id
                          WHERE pd.vydavok_id = ?
                          """, [vydavok_id])
    return render_template('vydavok.html', user=user, vydavok=vydavok, podielnici=podielnici)


@app.route("/zaplatit/<int:podiel_id>/<meno>")
def zaplatit(podiel_id, meno):
    """Označí podiel ako zaplatený."""
    podiel = query_db('SELECT * FROM podielnici WHERE id = ?', [podiel_id], one=True)
    if podiel:
        db = get_db()
        db.execute('UPDATE podielnici SET zaplatene = 1 WHERE id = ?', [podiel_id])
        db.commit()
        return redirect(url_for('vydavok_detail', vydavok_id=podiel['vydavok_id'], meno=meno))
    return redirect(url_for('dashboard', meno=meno))


@app.route("/vydavok/vymazat/<int:vydavok_id>/<meno>")
def vymazat_vydavok(vydavok_id, meno):
    """Vymaže celý výdavok aj s jeho podielnikmi."""
    user = query_db('SELECT * FROM pouzivatelia WHERE meno = ?', [meno], one=True)
    vydavok = query_db('SELECT * FROM vydavky WHERE id = ?', [vydavok_id], one=True)

    if not user or not vydavok or user['id'] != vydavok['kto_platil_id']:
        return redirect(url_for('dashboard', meno=meno))

    db = get_db()
    db.execute('DELETE FROM podielnici WHERE vydavok_id = ?', [vydavok_id])
    db.execute('DELETE FROM vydavky WHERE id = ?', [vydavok_id])
    db.commit()
    return redirect(url_for('dashboard', meno=meno))


@app.route("/vydavok/upravit/<int:vydavok_id>/<meno>", methods=['GET', 'POST'])
def upravit_vydavok(vydavok_id, meno):
    """Zobrazí formulár na úpravu a spracuje ho."""
    user = query_db('SELECT * FROM pouzivatelia WHERE meno = ?', [meno], one=True)
    vydavok = query_db('SELECT * FROM vydavky WHERE id = ?', [vydavok_id], one=True)

    if not user or not vydavok or user['id'] != vydavok['kto_platil_id']:
        return redirect(url_for('dashboard', meno=meno))

    if request.method == 'POST':
        ostatni_podielnici_ids = request.form.getlist('podielnici')
        finalny_zoznam_ids = ostatni_podielnici_ids + [str(user['id'])]

        db = get_db()
        db.execute('DELETE FROM podielnici WHERE vydavok_id = ?', [vydavok_id])

        pocet_podielnikov = len(finalny_zoznam_ids)
        suma_podielu = round(vydavok['celkova_suma'] / pocet_podielnikov, 2) if pocet_podielnikov > 0 else vydavok[
            'celkova_suma']

        # OPRAVENÁ ČASŤ: Správne nastavenie stavu 'zaplatene' pre platcu pri úprave
        for pid in finalny_zoznam_ids:
            je_zaplatene = 1 if int(pid) == user['id'] else 0
            db.execute(
                'INSERT INTO podielnici (vydavok_id, pouzivatel_id, suma_podielu, zaplatene) VALUES (?, ?, ?, ?)',
                (vydavok_id, int(pid), suma_podielu, je_zaplatene))
        db.commit()
        return redirect(url_for('vydavok_detail', vydavok_id=vydavok_id, meno=meno))

    vsetci_pouzivatelia = query_db('SELECT * FROM pouzivatelia')
    aktualni_podielnici = query_db('SELECT pouzivatel_id FROM podielnici WHERE vydavok_id = ?', [vydavok_id])
    aktualni_podielnici_ids = [p['pouzivatel_id'] for p in aktualni_podielnici]

    return render_template('upravit_vydavok.html',
                           user=user,
                           vydavok=vydavok,
                           vsetci_pouzivatelia=vsetci_pouzivatelia,
                           aktualni_podielnici_ids=aktualni_podielnici_ids)


@app.route("/archiv/<meno>")
def archiv(meno):
    """Zobrazí stránku s archivovanými výdavkami a štatistikami."""
    user = query_db('SELECT * FROM pouzivatelia WHERE meno = ?', [meno], one=True)
    if not user:
        return redirect(url_for('login'))

    nakupne_statistiky = query_db("""
                                  SELECT p.meno,
                                         COUNT(v.id)         as pocet_nakupov,
                                         SUM(v.celkova_suma) as celkova_suma
                                  FROM vydavky v
                                           JOIN pouzivatelia p ON v.kto_platil_id = p.id
                                  GROUP BY p.meno
                                  ORDER BY pocet_nakupov DESC, celkova_suma DESC
                                  """)

    archivovane_vydavky = query_db("""
                                   SELECT v.id, v.nazov, v.celkova_suma, p.meno as kto_platil
                                   FROM vydavky v
                                            JOIN pouzivatelia p ON v.kto_platil_id = p.id
                                   WHERE NOT EXISTS (SELECT 1
                                                     FROM podielnici pd
                                                     WHERE pd.vydavok_id = v.id
                                                       AND pd.zaplatene = 0)
                                   ORDER BY v.datum_vytvorenia DESC
                                   """)

    return render_template('archiv.html',
                           user=user,
                           statistiky=nakupne_statistiky,
                           vydavky=archivovane_vydavky)


# --- Spustenie aplikácie ---
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')