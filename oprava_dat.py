import sqlite3

print("Spúšťam opravu dát v databáze...")

try:
    conn = sqlite3.connect('data/naklady.db')
    cursor = conn.cursor()

    # Dopyt, ktorý nájde všetky podiely, kde je podielnik zároveň platcom
    query = """
    UPDATE podielnici
    SET zaplatene = 1
    WHERE zaplatene = 0 AND id IN (
        SELECT p.id
        FROM podielnici p
        JOIN vydavky v ON p.vydavok_id = v.id
        WHERE p.pouzivatel_id = v.kto_platil_id
    );
    """

    cursor.execute(query)
    # Zistíme, koľko riadkov bolo zmenených
    pocet_zmien = cursor.rowcount
    conn.commit()

    print(f"Hotovo. Počet opravených záznamov: {pocet_zmien}")
    if pocet_zmien > 0:
        print("Vaša kategória 'Káva' by sa teraz mala archivovať správne.")
    else:
        print("Žiadne chybné záznamy neboli nájdené.")

except Exception as e:
    print(f"Nastala chyba: {e}")
finally:
    if 'conn' in locals() and conn:
        conn.close()