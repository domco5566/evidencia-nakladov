import sqlite3
import os

print(">>> Spúšťam inicializáciu databázy...")

# Vytvoríme priečinok 'data', ak neexistuje
# Render ho vytvorí automaticky vďaka mountu disku, ale lokálne je to užitočné
if not os.path.exists('data'):
    os.makedirs('data')

# Pripojíme sa k databáze (vytvorí sa, ak neexistuje)
conn = sqlite3.connect('data/naklady.db')
cursor = conn.cursor()

# Vytvorenie tabuľky pre používateľov, ak neexistuje
cursor.execute("""
CREATE TABLE IF NOT EXISTS pouzivatelia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meno TEXT NOT NULL UNIQUE
);
""")

# Vytvorenie tabuľky pre výdavky, ak neexistuje
cursor.execute("""
CREATE TABLE IF NOT EXISTS vydavky (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazov TEXT NOT NULL,
    celkova_suma REAL NOT NULL,
    kto_platil_id INTEGER NOT NULL,
    datum_vytvorenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kto_platil_id) REFERENCES pouzivatelia(id)
);
""")

# Vytvorenie tabuľky pre podielnikov, ak neexistuje
cursor.execute("""
CREATE TABLE IF NOT EXISTS podielnici (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vydavok_id INTEGER NOT NULL,
    pouzivatel_id INTEGER NOT NULL,
    suma_podielu REAL NOT NULL,
    zaplatene INTEGER NOT NULL DEFAULT 0,  -- 0 for Nie, 1 for Áno
    FOREIGN KEY (vydavok_id) REFERENCES vydavky(id) ON DELETE CASCADE,
    FOREIGN KEY (pouzivatel_id) REFERENCES pouzivatelia(id)
);
""")

# Vloženie počiatočných používateľov, iba ak ešte neexistujú
print(">>> Vkladám počiatočných používateľov (ak je to potrebné)...")
pouzivatelia = ['Peter', 'Zuzana', 'Martin', 'Jana', 'Michal', 'Dominik', 'Robo', 'Milan', 'Pali', 'Palijr', 'Marek', 'Jakub', 'Lukas']
for meno in pouzivatelia:
    # INSERT OR IGNORE vloží záznam, len ak neporuší UNIQUE obmedzenie (meno)
    cursor.execute("INSERT OR IGNORE INTO pouzivatelia (meno) VALUES (?)", (meno,))

print(">>> Inicializácia databázy dokončená.")

# Uloženie zmien a zatvorenie spojenia
conn.commit()
conn.close()