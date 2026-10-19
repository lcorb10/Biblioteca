"""Carga schema.sql (tablas + datos de ejemplo) en el servidor MySQL configurado.

Uso:
    python cargar_bd.py                     -> usa config.toml (o variables de entorno MYSQL_*)
    python cargar_bd.py config.nube.toml    -> usa otro archivo, por ejemplo la base en la nube

Ojo: el script empieza con DROP DATABASE IF EXISTS biblioteca, así que borra
esa base si ya existe y la vuelve a crear con los datos de ejemplo.
"""
import re
import sys
import tomllib
from pathlib import Path

import pymysql

BASE = Path(__file__).resolve().parent


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            cfg = tomllib.load(f)["mysql"]
    else:
        import db
        cfg = db.CONFIG["mysql"]

    sql = (BASE / "schema.sql").read_text(encoding="utf-8")
    sql = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    sentencias = [s.strip().rstrip(";") for s in re.split(r";\s*\n", sql) if s.strip()]

    conn = pymysql.connect(host=cfg["host"], port=int(cfg.get("port", 3306)), user=cfg["user"],
                           password=cfg["password"], charset="utf8mb4", autocommit=True,
                           ssl={"ssl": {}} if cfg.get("ssl") else None)
    with conn.cursor() as cur:
        for s in sentencias:
            cur.execute(s)
        for t in ("libro", "ejemplar", "usuario", "prestamo", "devolucion"):
            cur.execute(f"SELECT COUNT(*) FROM biblioteca.{t}")
            print(f"{t:<11} {cur.fetchone()[0]}")
    conn.close()
    print(f"Listo: {len(sentencias)} sentencias ejecutadas en {cfg['host']}.")


if __name__ == "__main__":
    main()
