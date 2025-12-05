# update_master.py
# Viene eseguito automaticamente ad ogni deploy
import pandas as pd
import glob
import os
import re

DATA_DIR = "data"
MASTER_PATH = f"{DATA_DIR}/master_sales.parquet"

def create_master():
    files = sorted(glob.glob(f"{DATA_DIR}/Classifica week*.xlsx"))
    if not files:
        print("Nessun file Excel trovato")
        return

    dfs = []
    for f in files:
        match = re.search(r'week\s*(\d+)', os.path.basename(f), re.I)
        week_num = match.group(1) if match else "999"
        try:
            df = pd.read_excel(f, sheet_name="Export")
            df["week"] = f"Settimana {week_num}"
            df["source_file"] = os.path.basename(f)
            dfs.append(df)
        except Exception as e:
            print(f"Errore lettura {f}: {e}")

    if not dfs:
        return

    master = pd.concat(dfs, ignore_index=True)

    # Pulizia dati una volta per tutte
    master["units"] = pd.to_numeric(master["units"], errors="coerce").fillna(0).astype(int)
    if "title" in master.columns:
        master["title"] = master["title"].astype(str).str.strip()
    if "publisher" in master.columns:
        master["publisher"] = master["publisher"].astype(str).str.strip().str.title()

    # Rinomina collana se esiste
    for col in ["collana", "collection", "series", "Collection/Series"]:
        if col in master.columns:
            master = master.rename(columns={col: "collana"})
            break

    master.to_parquet(MASTER_PATH, compression="zstd")
    print(f"Master Parquet creato: {master.shape[0]:,} righe, {os.path.getsize(MASTER_PATH)/1024/1024:.1f} MB")

if __name__ == "__main__":
    create_master()
