# update_master.py
# Viene eseguito automaticamente ad ogni push su GitHub
import pandas as pd
import glob
import os
import re

DATA_DIR = "data"
MASTER_PATH = f"{DATA_DIR}/master_sales.parquet"

print("update_master.py in esecuzione...")

files = sorted(glob.glob(f"{DATA_DIR}/Classifica week*.xlsx"))
if not files:
    print("Nessun file Excel trovato")
    exit()

dfs = []
for f in files:
    week_match = re.search(r'(?:week|Settimana)\s*(\d+)', f, re.I)
    week_num = week_match.group(1) if week_match else "999"
    try:
        df = pd.read_excel(f, sheet_name="Export")
        df["week"] = f"Settimana {week_num}"
        df["source_file"] = os.path.basename(f)
        dfs.append(df)
        print(f"Caricato {os.path.basename(f)}")
    except Exception as e:
        print(f"Errore con {f}: {e}")

if not dfs:
    print("Nessun dato caricato")
    exit()

master = pd.concat(dfs, ignore_index=True)

# Pulizia definitiva
master["units"] = pd.to_numeric(master["units"], errors="coerce").fillna(0).astype(int)
if "title" in master.columns:
    master["title"] = master["title"].astype(str).str.strip()
if "publisher" in master.columns:
    master["publisher"] = master["publisher"].astype(str).str.strip().str.title()

# Rinomina collana
for col in ["collana", "collection", "series", "Collection/Series"]:
    if col in master.columns:
        master = master.rename(columns={col: "collana"})
        break

master.to_parquet(MASTER_PATH, compression="zstd")
size_mb = os.path.getsize(MASTER_PATH) / (1024*1024)
print(f"master_sales.parquet creato/aggiornato: {master.shape[0]:,} righe, {size_mb:.1f} MB")
