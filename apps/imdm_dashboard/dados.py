"""Acesso à camada semantic do IMDM.

No Databricks Apps, lê as views `munic_catalog.semantic.*` pelo SQL warehouse ligado ao app
(recurso `sql-warehouse`, variável DATABRICKS_WAREHOUSE_ID), com as credenciais do próprio app.
Para desenvolver fora do Databricks, defina IMDM_LOCAL_DIR com uma pasta de .parquet
exportados das mesmas views (um arquivo por view, mesmo nome).
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

CATALOGO = os.getenv("IMDM_CATALOG", "munic_catalog")
SCHEMA = os.getenv("IMDM_SCHEMA", "semantic")
LOCAL = os.getenv("IMDM_LOCAL_DIR")
AQUI = Path(__file__).resolve().parent


@st.cache_resource(show_spinner=False)
def _conexao():
    from databricks import sql
    from databricks.sdk.core import Config

    cfg = Config()
    warehouse = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID não definido: ligue um SQL warehouse ao app (recurso 'sql-warehouse').")
    return sql.connect(
        server_hostname=cfg.host,
        http_path=f"/sql/1.0/warehouses/{warehouse}",
        credentials_provider=lambda: cfg.authenticate,
    )


def _consulta(sql_texto: str, parametros: dict | None = None) -> pd.DataFrame:
    with _conexao().cursor() as cur:
        cur.execute(sql_texto, parametros or {})
        return cur.fetchall_arrow().to_pandas()


def _local(view: str) -> pd.DataFrame:
    return pd.read_parquet(Path(LOCAL) / f"{view}.parquet")


@st.cache_data(ttl=3600, show_spinner="Lendo a camada semantic…")
def view(nome: str) -> pd.DataFrame:
    """View inteira (todas as edições). Usada para as views pequenas."""
    df = _local(nome) if LOCAL else _consulta(f"SELECT * FROM {CATALOGO}.{SCHEMA}.{nome}")
    if "regiao" in df.columns:
        df["regiao"] = df["regiao"].astype(str).str.replace(r"^\d+\s*-\s*", "", regex=True)
    if "cod_ibge" in df.columns:
        df["cod_ibge"] = df["cod_ibge"].astype(str)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def itens_do_municipio(cod_ibge: str, ano: int) -> pd.DataFrame:
    """Itens do radar de um município numa edição (vw_item_municipio, ~64 linhas)."""
    if LOCAL:
        df = _local("vw_item_municipio")
        df = df[(df["cod_ibge"].astype(str) == str(cod_ibge)) & (df["ano_edicao"] == ano)]
    else:
        df = _consulta(
            f"SELECT * FROM {CATALOGO}.{SCHEMA}.vw_item_municipio WHERE cod_ibge = :cod AND ano_edicao = :ano",
            {"cod": str(cod_ibge), "ano": int(ano)},
        )
    return df.reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner="Calculando adoção dos itens…")
def adocao_uf_porte(ano: int) -> pd.DataFrame:
    """Somas de pontos e peso por item × UF × porte (para % de adoção em qualquer recorte)."""
    cols = ["uf_sigla", "regiao", "porte_municipio", "dimensao_codigo", "dimensao_nome", "dimensao_ordem",
            "item", "item_descricao", "variavel_ancora"]
    if LOCAL:
        df = _local("vw_item_municipio")
        df = df[df["ano_edicao"] == ano]
        out = df.groupby(cols, dropna=False).agg(soma_pontos=("pontos_obtidos", "sum"), soma_peso=("peso_aplicado", "sum"),
                                                 municipios=("cod_ibge", "count")).reset_index()
    else:
        out = _consulta(
            f"""SELECT {", ".join(cols)}, SUM(pontos_obtidos) AS soma_pontos, SUM(peso_aplicado) AS soma_peso,
                       COUNT(*) AS municipios
                FROM {CATALOGO}.{SCHEMA}.vw_item_municipio WHERE ano_edicao = :ano
                GROUP BY {", ".join(cols)}""",
            {"ano": int(ano)},
        )
    out["regiao"] = out["regiao"].astype(str).str.replace(r"^\d+\s*-\s*", "", regex=True)
    return out


@st.cache_data(show_spinner=False)
def coordenadas() -> pd.DataFrame:
    """Sede dos municípios (lat/lon) — arquivo estático do app (kelvins/municipios-brasileiros, MIT)."""
    df = pd.read_csv(AQUI / "data" / "coordenadas_municipios.csv", dtype={"cod_ibge": str})
    return df
