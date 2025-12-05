# create_parquet.py → SI ESEGUE AUTOMATICAMENTE AD OGNI DEPLOY
import pandas as pd
import glob
import os
import re

print("Creazione / aggiornamento master_sales.parquet...")

DATA_DIR = "data"
MASTER = f"{DATA_DIR}/master_sales.parquet"

files = sorted(glob.glob(f"{DATA_DIR}/Classifica week*.xlsx"))

if not files:
    print("Nessun file Excel trovato.")
    exit()

dfs = []
for f in files:
    match = re.search(r'(?:week|Settimana)\s*(\d+)', os.path.basename(f), re.I)
    week_num = match.group(1) if match else "999"
    try:
        df = pd.read_excel(f, sheet_name="Export")
        df["week"] = f"Settimana {week_num}"
        df["source_file"] = os.path.basename(f)
        dfs.append(df)
        print(f"Caricato: {os.path.basename(f)}")
    except Exception as e:
        print(f"Errore su {f}: {e}")

if not dfs:
    print("Nessun dato caricato.")
    exit()

master = pd.concat(dfs, ignore_index=True)

# Pulizia
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

master.to_parquet(MASTER, compression="zstd")
print(f"master_sales.parquet creato! → {master.shape[0]:,} righe, {os.path.getsize(MASTER)/1e6:.1f} MB")
