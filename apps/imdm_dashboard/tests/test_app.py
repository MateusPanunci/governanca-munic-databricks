"""Teste de fumaça do dashboard: abre cada tela com muitas combinações de filtros (radar, edição, região,
UF, porte, município e dimensão) e falha se alguma der erro.

Roda fora do Databricks, sobre um export .parquet da camada semantic (um arquivo por tabela):

    set IMDM_LOCAL_DIR=C:\\caminho\\semantic_parquet      (PowerShell: $env:IMDM_LOCAL_DIR="...")
    python tests/test_app.py            # completo (alguns minutos)
    python tests/test_app.py --rapido   # amostra menor

Também funciona com pytest (pytest tests/test_app.py).
"""
from __future__ import annotations

import logging
import os
import sys
import warnings
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGINAS = ["visao", "perfil", "dimensoes", "qualidade"]


def _dados():
    pasta = os.getenv("IMDM_LOCAL_DIR")
    if not pasta:
        raise SystemExit("Defina IMDM_LOCAL_DIR com a pasta dos .parquet da semantic.")
    pan = pd.read_parquet(Path(pasta) / "vw_painel_municipio.parquet").astype({"cod_ibge": str})
    rad = pd.read_parquet(Path(pasta) / "vw_radar_dimensao.parquet")
    radares = pd.read_parquet(Path(pasta) / "vw_radares.parquet")
    return pan, rad, radares


def cenarios(rapido=False):
    """Combinações de filtros por radar e edição: regiões × UFs × portes, municípios-limite e cada dimensão.
    O radar padrão passa pela matriz escolhida; os demais radares, pela amostra menor (--rapido)."""
    pan, rad, radares = _dados()
    padrao = radares.loc[radares["padrao"].astype(bool), "radar"].tolist()
    for radar in sorted(radares["radar"], key=lambda r: (r not in padrao, r)):
        yield from _cenarios_radar(pan[pan["radar"] == radar], rad[rad["radar"] == radar], radar,
                                   rapido or radar not in padrao)


def _cenarios_radar(pan, rad, radar, rapido):
    for ano in sorted(pan["ano_edicao"].unique(), reverse=True):
        p = pan[pan["ano_edicao"] == ano]
        dims = rad.loc[rad["ano_edicao"] == ano, "dimensao_codigo"].drop_duplicates().tolist()
        portes = ["Todos"] + sorted(p["porte_municipio"].dropna().unique())
        if rapido:
            portes = portes[:2] + portes[-1:]
        combos = []
        for reg in ["Todas"] + sorted(p["regiao"].dropna().unique()):
            ufs = ["Todas"] + sorted(p.loc[p["regiao"] == reg, "uf_sigla"].unique()) if reg != "Todas" else ["Todas", "DF"]
            if rapido:
                ufs = ufs[:2]
            for uf in ufs:
                for porte in portes:
                    combos.append(dict(f_radar=radar, f_ano=int(ano), f_regiao=reg, f_uf=uf, f_porte=porte))
        # municípios: IMDM nulo, menores, maiores, únicos na UF (DF) e uma amostra
        ordem = p.sort_values("score_global_imdm", na_position="first")
        muns = (ordem.head(4)["cod_ibge"].tolist() + ordem.dropna(subset=["score_global_imdm"]).tail(2)["cod_ibge"].tolist()
                + p.loc[p["uf_sigla"] == "DF", "cod_ibge"].tolist()[:1]
                + p.sample(3 if rapido else 8, random_state=int(ano))["cod_ibge"].tolist())
        for m in dict.fromkeys(muns):
            r = p[p["cod_ibge"] == m].iloc[0]
            combos.append(dict(f_radar=radar, f_ano=int(ano), f_regiao=r["regiao"], f_uf=r["uf_sigla"], f_porte="Todos", f_mun=m))
        for c in combos:
            for pagina in PAGINAS:
                if pagina == "dimensoes":
                    for d in (dims if not rapido or c.get("f_mun") is None else dims[:1]):
                        yield pagina, {**c, "f_dim": d}
                else:
                    yield pagina, c


def rodar(pagina, estado):
    os.environ["IMDM_PAGINA"] = pagina
    at = AppTest.from_file(APP, default_timeout=180)
    for k, v in estado.items():
        at.session_state[k] = v
    at.run()
    return [e.value for e in at.exception]


def test_todas_as_telas():
    warnings.filterwarnings("ignore")
    logging.disable(logging.CRITICAL)
    rapido = "--rapido" in sys.argv
    falhas, n = [], 0
    for pagina, estado in cenarios(rapido):
        n += 1
        erros = rodar(pagina, estado)
        if erros:
            falhas.append((pagina, estado, erros[0][:300]))
            print("FALHA", pagina, estado, erros[0][:200], flush=True)
    print(f"{n} execuções, {len(falhas)} com erro")
    assert not falhas, f"{len(falhas)} combinações com erro; primeira: {falhas[0]}"


if __name__ == "__main__":
    test_todas_as_telas()
