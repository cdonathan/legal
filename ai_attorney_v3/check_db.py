import sqlite3
import os
db_path = "/home/cliff/redact/ai_attorney_v3/provisions.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM provisions WHERE form_type = 'NDA'")
print(f"NDA clauses: {cur.fetchone()[0]}")
cur.execute("SELECT DISTINCT form_type, COUNT(*) FROM provisions GROUP BY form_type ORDER BY COUNT(*) DESC")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")
print()
print("NDA clauses:")
cur.execute("SELECT id, prov_desc, risk_level FROM provisions WHERE form_type = 'NDA' ORDER BY category_id, id")
for row in cur.fetchall():
    print(f"  [{row[0]}] {(row[1] or '')[:60]} (risk: {row[2]})")
conn.close()
