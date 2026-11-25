"""Acesso à camada semantic do IMDM.

No Databricks Apps, lê as tabelas `munic_catalog.semantic.*` pelo SQL warehouse ligado ao app
(recurso `sql-warehouse`, variável DATABRICKS_WAREHOUSE_ID), com as credenciais do próprio app.
Para desenvolver fora do Databricks, defina IMDM_LOCAL_DIR com uma pasta de .parquet
exportados das mesmas tabelas (um arquivo por tabela, mesmo nome).

Desempenho:
- as tabelas da abertura são lidas em paralelo, uma conexão por leitura;
- tudo fica em cache até o app reiniciar ou alguém clicar em "Recarregar dados"
  (os dados só mudam quando o pipeline roda);
- o tempo de cada leitura vai para os Logs do app (prefixo [dados]).
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import streamlit as st

CATALOGO = os.getenv("IMDM_CATALOG", "munic_catalog")
SCHEMA = os.getenv("IMDM_SCHEMA", "semantic")
LOCAL = os.getenv("IMDM_LOCAL_DIR")
AQUI = Path(__file__).resolve().parent
CACHE_TTL = 12 * 3600

# Tabelas lidas na abertura do app (todas pequenas: até ~30 mil linhas)
TABELAS_BASE = ["vw_radares", "vw_painel_municipio", "vw_score_dimensao", "vw_radar_dimensao", "vw_auditoria_lgpd",
                "agg_qualidade_item"]
TABELAS_SEM_RADAR = {"vw_auditoria_lgpd", "vw_radares"}
COLS_ADOCAO = ["uf_sigla", "regiao", "porte_municipio", "dimensao_codigo", "dimensao_nome", "dimensao_ordem",
               "item", "item_descricao", "variavel_ancora"]


def _log(msg: str) -> None:
    print(f"[dados] {msg}", flush=True)


# ------------------------------------------------------------------ conexão
def _nova_conexao():
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


_lock = threading.Lock()
_compartilhada = {"con": None}


def _consulta(sql_texto: str, parametros: dict | None = None, *, propria: bool = False) -> pd.DataFrame:
    """Executa uma consulta. Se a conexão compartilhada caiu (sessão expirada), reconecta e tenta de novo uma vez."""
    if propria:   # leituras paralelas: uma conexão por thread
        con = _nova_conexao()
        try:
            with con.cursor() as cur:
                cur.execute(sql_texto, parametros or {})
                return cur.fetchall_arrow().to_pandas()
        finally:
            con.close()
    with _lock:
        for tentativa in (1, 2):
            try:
                if _compartilhada["con"] is None:
                    _compartilhada["con"] = _nova_conexao()
                with _compartilhada["con"].cursor() as cur:
                    cur.execute(sql_texto, parametros or {})
                    return cur.fetchall_arrow().to_pandas()
            except Exception as e:   # noqa: BLE001 — sessão expirada, warehouse reiniciado etc.
                _log(f"consulta falhou (tentativa {tentativa}): {type(e).__name__}: {str(e)[:200]}")
                try:
                    if _compartilhada["con"] is not None:
                        _compartilhada["con"].close()
                except Exception:   # noqa: BLE001
                    pass
                _compartilhada["con"] = None
                if tentativa == 2:
                    raise


def _local(nome: str) -> pd.DataFrame:
    return pd.read_parquet(Path(LOCAL) / f"{nome}.parquet")


def _ajustar(df: pd.DataFrame) -> pd.DataFrame:
    if "regiao" in df.columns:
        df["regiao"] = df["regiao"].astype(str).str.replace(r"^\d+\s*-\s*", "", regex=True)
    if "cod_ibge" in df.columns:
        df["cod_ibge"] = df["cod_ibge"].astype(str)
    return df


def _ler(nome: str, propria: bool = False) -> pd.DataFrame:
    t = time.perf_counter()
    try:
        df = _local(nome) if LOCAL else _consulta(f"SELECT * FROM {CATALOGO}.{SCHEMA}.{nome}", propria=propria)
    except Exception:   # noqa: BLE001
        if nome != "vw_radares":
            raise
        # semantic de antes dos vários radares: um radar só, sem cadastro
        _log("vw_radares indisponível; usando um radar único 'A'")
        df = pd.DataFrame([{"radar": "A", "nome": "Radar", "descricao": "", "padrao": True}])
    if nome not in TABELAS_SEM_RADAR and "radar" not in df.columns:
        df["radar"] = "A"   # semantic de antes dos vários radares
    _log(f"{nome}: {len(df):,} linhas em {time.perf_counter() - t:.1f}s")
    return _ajustar(df)


# ------------------------------------------------------------------ leituras com cache
@st.cache_data(ttl=CACHE_TTL, show_spinner="Carregando os dados do IMDM…")
def base() -> dict[str, pd.DataFrame]:
    """As tabelas da abertura, lidas em paralelo."""
    t = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(TABELAS_BASE)) as ex:
        resultado = dict(zip(TABELAS_BASE, ex.map(lambda n: _ler(n, propria=True), TABELAS_BASE)))
    _log(f"abertura: {time.perf_counter() - t:.1f}s no total")
    return resultado


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def itens_do_municipio(cod_ibge: str, ano: int, radar: str) -> pd.DataFrame:
    """Itens de um radar para um município numa edição (vw_item_municipio, ~64 linhas)."""
    t = time.perf_counter()
    if LOCAL:
        df = _local("vw_item_municipio")
        if "radar" not in df.columns:
            df["radar"] = "A"
        df = df[(df["cod_ibge"].astype(str) == str(cod_ibge)) & (df["ano_edicao"] == ano) & (df["radar"] == radar)]
    else:
        df = _consulta(
            f"SELECT * FROM {CATALOGO}.{SCHEMA}.vw_item_municipio "
            "WHERE cod_ibge = :cod AND ano_edicao = :ano AND radar = :radar",
            {"cod": str(cod_ibge), "ano": int(ano), "radar": str(radar)},
        )
    _log(f"itens de {cod_ibge}/{ano}/radar {radar}: {len(df)} linhas em {time.perf_counter() - t:.1f}s")
    return _ajustar(df.reset_index(drop=True))


@st.cache_data(ttl=CACHE_TTL, show_spinner="Carregando a adoção dos itens…")
def adocao_uf_porte(ano: int, radar: str) -> pd.DataFrame:
    """Somas de pontos e peso por item × UF × porte, de um radar (para % de adoção em qualquer recorte).

    Lê a tabela pronta `agg_adocao_uf_porte`. Se ela ainda não existir (semantic antiga),
    agrega a `vw_item_municipio` na hora — mais lento, mas o app continua funcionando.
    """
    t = time.perf_counter()
    if LOCAL:
        caminho = Path(LOCAL) / "agg_adocao_uf_porte.parquet"
        if caminho.exists():
            out = pd.read_parquet(caminho)
            if "radar" not in out.columns:
                out["radar"] = "A"
            out = out[(out["ano_edicao"] == ano) & (out["radar"] == radar)]
        else:
            df = _local("vw_item_municipio")
            if "radar" not in df.columns:
                df["radar"] = "A"
            df = df[(df["ano_edicao"] == ano) & (df["radar"] == radar)]
            out = df.groupby(COLS_ADOCAO, dropna=False).agg(
                soma_pontos=("pontos_obtidos", "sum"), soma_peso=("peso_aplicado", "sum"),
                municipios=("cod_ibge", "count")).reset_index()
    else:
        try:
            out = _consulta(f"SELECT * FROM {CATALOGO}.{SCHEMA}.agg_adocao_uf_porte WHERE ano_edicao = :ano AND radar = :radar",
                            {"ano": int(ano), "radar": str(radar)})
        except Exception:   # noqa: BLE001 — tabela ainda não publicada pelo gold_to_semantic novo
            _log("agg_adocao_uf_porte indisponível; agregando vw_item_municipio na hora")
            out = _consulta(
                f"""SELECT {", ".join(COLS_ADOCAO)}, SUM(pontos_obtidos) AS soma_pontos, SUM(peso_aplicado) AS soma_peso,
                           COUNT(*) AS municipios
                    FROM {CATALOGO}.{SCHEMA}.vw_item_municipio WHERE ano_edicao = :ano AND radar = :radar
                    GROUP BY {", ".join(COLS_ADOCAO)}""",
                {"ano": int(ano), "radar": str(radar)},
            )
    _log(f"adoção {ano}/radar {radar}: {len(out):,} linhas em {time.perf_counter() - t:.1f}s")
    for c in ("soma_pontos", "soma_peso"):
        out[c] = pd.to_numeric(out[c], errors="coerce").astype(float)
    return _ajustar(out)


@st.cache_data(show_spinner=False)
def coordenadas() -> pd.DataFrame:
    """Sede dos municípios (lat/lon) — arquivo estático do app (kelvins/municipios-brasileiros, MIT)."""
    return pd.read_csv(AQUI / "data" / "coordenadas_municipios.csv", dtype={"cod_ibge": str})


def recarregar() -> None:
    """Descarta o cache (usado pelo botão "Recarregar dados" depois de rodar o pipeline)."""
    st.cache_data.clear()
