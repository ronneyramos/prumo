"""Backup completo do Prumo ERP (todas as empresas) para a pasta backups/.

Exporta cada tabela do schema public em JSON, a lista de usuários (sem senhas)
e os arquivos do Storage (fotos do RDO). Compacta em backups/prumo_AAAA-MM-DD.zip
e mantém só os últimos N backups.

Uso:  python scripts/backup_supabase.py            (ou dê dois cliques em backup.bat)
      python scripts/backup_supabase.py --manter 12

Só LÊ o banco. Usa a SUPABASE_SERVICE_KEY de streamlit/.env.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime

from dotenv import dotenv_values
from supabase import create_client

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "backups")
LOTE = 1000  # limite de linhas por requisição do PostgREST


def _cliente():
    env = dotenv_values(os.path.join(RAIZ, "streamlit", ".env"))
    url, chave = env.get("SUPABASE_URL"), env.get("SUPABASE_SERVICE_KEY")
    if not url or not chave:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_KEY não encontradas em streamlit/.env")
    return create_client(url, chave)


def _tabelas(adm) -> list[str]:
    r = adm.rpc("exec_sql_readonly", {"query_text":
        "select c.relname as nome from pg_class c join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'public' and c.relkind = 'r' order by 1"}).execute().data
    if isinstance(r, dict) and r.get("error"):
        sys.exit(f"Erro ao listar tabelas: {r['error']}")
    return [x["nome"] for x in r]


def _exportar_tabela(adm, tabela: str) -> list[dict]:
    linhas, inicio = [], 0
    while True:
        lote = adm.table(tabela).select("*").range(inicio, inicio + LOTE - 1).execute().data or []
        linhas.extend(lote)
        if len(lote) < LOTE:
            return linhas
        inicio += LOTE


def _salvar(pasta: str, nome: str, dados) -> None:
    with open(os.path.join(pasta, nome), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1, default=str)


def _exportar_storage(adm, pasta: str) -> int:
    total = 0
    for bucket in adm.storage.list_buckets():
        b = adm.storage.from_(bucket.id)
        pendentes = [""]
        while pendentes:
            prefixo = pendentes.pop()
            for item in b.list(prefixo, {"limit": 1000}) or []:
                caminho = f"{prefixo}/{item['name']}".lstrip("/")
                if item.get("id") is None:          # pasta
                    pendentes.append(caminho)
                    continue
                local = os.path.join(pasta, "storage", bucket.id, *caminho.split("/"))
                os.makedirs(os.path.dirname(local), exist_ok=True)
                with open(local, "wb") as f:
                    f.write(b.download(caminho))
                total += 1
    return total


def _limpar_antigos(manter: int) -> list[str]:
    zips = sorted(f for f in os.listdir(DESTINO) if f.startswith("prumo_") and f.endswith(".zip"))
    removidos = zips[:-manter] if manter > 0 else []
    for f in removidos:
        os.remove(os.path.join(DESTINO, f))
    return removidos


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manter", type=int, default=8, help="quantos backups manter (padrão 8)")
    args = ap.parse_args()

    adm = _cliente()
    carimbo = datetime.now().strftime("%Y-%m-%d_%H%M")
    os.makedirs(DESTINO, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        pasta = os.path.join(tmp, f"prumo_{carimbo}")
        os.makedirs(os.path.join(pasta, "tabelas"))
        resumo = {}
        for t in _tabelas(adm):
            linhas = _exportar_tabela(adm, t)
            _salvar(os.path.join(pasta, "tabelas"), f"{t}.json", linhas)
            resumo[t] = len(linhas)
            print(f"  {t:32} {len(linhas):>6} linhas")

        usuarios = [{"id": u.id, "email": u.email, "criado_em": u.created_at,
                     "ultimo_login": u.last_sign_in_at, "metadata": u.user_metadata}
                    for u in adm.auth.admin.list_users(per_page=1000)]
        _salvar(pasta, "usuarios.json", usuarios)
        arquivos = _exportar_storage(adm, pasta)
        _salvar(pasta, "resumo.json", {"gerado_em": carimbo, "tabelas": resumo,
                                       "usuarios": len(usuarios), "arquivos_storage": arquivos})

        zip_final = shutil.make_archive(os.path.join(DESTINO, f"prumo_{carimbo}"), "zip", pasta)

    removidos = _limpar_antigos(args.manter)
    tam = os.path.getsize(zip_final) / 1024
    print(f"\n✅ Backup: {zip_final} ({tam:,.0f} KB) — {sum(resumo.values())} linhas em "
          f"{len(resumo)} tabelas, {len(usuarios)} usuários, {arquivos} arquivo(s) do Storage")
    if removidos:
        print(f"   Removidos backups antigos: {', '.join(removidos)}")


if __name__ == "__main__":
    main()
