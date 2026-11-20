"""Dashboard IMDM — Índice de Maturidade Digital Municipal (MUNIC/IBGE).

Lê só a camada semantic (contrato de consumo). Nenhuma regra de pontuação aqui:
dimensões, itens e pesos vêm do radar de cada edição, definido pelo especialista.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import dados

st.set_page_config(page_title="IMDM · Maturidade Digital Municipal", page_icon="📡", layout="wide")

AZUL, LARANJA, CINZA = "#2a78d6", "#eb6834", "#8a8984"
AZUL_SOFT, LARANJA_SOFT = "rgba(42,120,214,0.18)", "rgba(235,104,52,0.10)"
NIVEL_CORES = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
PORTES = ["Pequeno I", "Pequeno II", "Médio", "Grande I", "Grande II"]
PORTE_ROTULO = {"Pequeno I": "≤ 20 mil", "Pequeno II": "20–50 mil", "Médio": "50–100 mil",
                "Grande I": "100–500 mil", "Grande II": "> 500 mil"}
STATUS_ICONE = {"Sim": "✅ Sim", "Parcial": "🟡 Parcial", "Não": "❌ Não", "Salto (0)": "➖ Salto (0)",
                "Não sabe": "❔ Não sabe", "Não informou": "❔ Não informou", "Não se aplica": "⚪ Não se aplica",
                "Recusa": "⛔ Recusa"}

st.markdown("""
<style>
.block-container{padding-top:1.6rem}
.kpi{background:var(--secondary-background-color);border-radius:10px;padding:10px 14px;height:100%}
.kpi .k{font-size:.82rem;opacity:.75}
.kpi .v{font-size:1.55rem;font-weight:700;line-height:1.25;margin:2px 0}
.kpi .v.sm{font-size:1.05rem;line-height:1.35}
.kpi .d{font-size:.8rem;opacity:.8}
.kpi .up{color:#0a8a0a;font-weight:600}.kpi .down{color:#c53030;font-weight:600}
</style>
""", unsafe_allow_html=True)


def kpi(col, rotulo, valor, detalhe="", delta=None, sufixo_delta=" vs Brasil", pequeno=False):
    """Card de indicador. delta numérico ganha cor; detalhe é texto neutro."""
    import html
    d = ""
    if delta is not None and not (isinstance(delta, float) and np.isnan(delta)):
        cls = "up" if delta > 0.05 else "down" if delta < -0.05 else ""
        d = f'<span class="{cls}">{delta:+.1f}</span>{html.escape(sufixo_delta)}'.replace(".", ",", 1)
    extra = " · ".join(x for x in [d, html.escape(str(detalhe)) if detalhe else ""] if x)
    col.markdown(f'<div class="kpi"><div class="k">{html.escape(rotulo)}</div>'
                 f'<div class="v{" sm" if pequeno else ""}">{html.escape(str(valor))}</div>'
                 f'<div class="d">{extra or "&nbsp;"}</div></div>', unsafe_allow_html=True)


def quebra(txt, largura=24):
    """Quebra rótulos longos em linhas (<br>) para os eixos dos gráficos."""
    palavras, linhas, atual = str(txt).split(), [], ""
    for p in palavras:
        if len(atual) + len(p) + 1 > largura and atual:
            linhas.append(atual)
            atual = p
        else:
            atual = (atual + " " + p).strip()
    linhas.append(atual)
    return "<br>".join(linhas)


# ------------------------------------------------------------------ dados
painel_all = dados.view("vw_painel_municipio")
score_all = dados.view("vw_score_dimensao")
radar_all = dados.view("vw_radar_dimensao")
lgpd_all = dados.view("vw_auditoria_lgpd")
qual_all = dados.view("agg_qualidade_item")

EDICOES = sorted(painel_all["ano_edicao"].unique(), reverse=True)


def fmt(v, casas=1, suf=""):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".") + suf


def nivel_num(rotulo):
    try:
        return int(str(rotulo).split("-")[0])
    except ValueError:
        return None


# ------------------------------------------------------------------ filtros (barra lateral, valem para todas as telas)
ss = st.session_state
for k, v in {"ano": int(EDICOES[0]), "regiao": "Todas", "uf": "Todas", "porte": "Todos", "mun": None, "dim": None}.items():
    ss.setdefault(k, v)

with st.sidebar:
    st.markdown("### 📡 IMDM")
    st.caption("Índice de Maturidade Digital Municipal · IBGE MUNIC")
    ss.ano = st.selectbox("Edição", EDICOES, index=EDICOES.index(ss.ano) if ss.ano in EDICOES else 0)
    pan = painel_all[painel_all["ano_edicao"] == ss.ano]
    regioes = ["Todas"] + sorted(pan["regiao"].dropna().unique())
    if ss.regiao not in regioes:
        ss.regiao = "Todas"
    ss.regiao = st.selectbox("Macrorregião", regioes, index=regioes.index(ss.regiao))
    ufs = ["Todas"] + sorted(pan.loc[(ss.regiao == "Todas") | (pan["regiao"] == ss.regiao), "uf_sigla"].unique())
    if ss.uf not in ufs:
        ss.uf = "Todas"
    ss.uf = st.selectbox("Estado (UF)", ufs, index=ufs.index(ss.uf))
    portes = ["Todos"] + [p for p in PORTES if p in set(pan["porte_municipio"])]
    ss.porte = st.selectbox("Porte populacional", portes, index=portes.index(ss.porte) if ss.porte in portes else 0,
                            format_func=lambda p: p if p == "Todos" else f"{p} ({PORTE_ROTULO.get(p, '')})")
    base_mun = pan
    if ss.regiao != "Todas":
        base_mun = base_mun[base_mun["regiao"] == ss.regiao]
    if ss.uf != "Todas":
        base_mun = base_mun[base_mun["uf_sigla"] == ss.uf]
    opcoes = base_mun.sort_values("nome")
    rotulos = {r.cod_ibge: f"{r.nome} ({r.uf_sigla})" for r in opcoes.itertuples()}
    lista = [None] + list(rotulos)
    if ss.mun not in rotulos:
        ss.mun = None
    ss.mun = st.selectbox("Município", lista, index=lista.index(ss.mun),
                          format_func=lambda c: "Todos" if c is None else rotulos[c],
                          help="Digite para buscar. Ao escolher um município, os indicadores passam a ser do município.")
    if st.button("Limpar filtros", use_container_width=True):
        for k in ("regiao", "uf"):
            ss[k] = "Todas"
        ss.porte, ss.mun = "Todos", None
        st.rerun()
    st.divider()
    sha = pan["radar_sha256"].dropna().iloc[0] if pan["radar_sha256"].notna().any() else ""
    st.caption(f"Radar {ss.ano}: {len(radar_all[radar_all['ano_edicao'] == ss.ano])} dimensões · versão `{sha[:10]}`")


# ------------------------------------------------------------------ recorte atual
ANO = ss.ano
pan = painel_all[painel_all["ano_edicao"] == ANO].copy()
dims = radar_all[radar_all["ano_edicao"] == ANO].drop_duplicates("dimensao_codigo").sort_values("dimensao_ordem")
score = score_all[score_all["ano_edicao"] == ANO]
lgpd = lgpd_all[lgpd_all["ano_edicao"] == ANO]
MUN = pan[pan["cod_ibge"] == ss.mun].iloc[0] if ss.mun else None


def area(df):
    if ss.regiao != "Todas":
        df = df[df["regiao"] == ss.regiao]
    if ss.uf != "Todas":
        df = df[df["uf_sigla"] == ss.uf]
    if ss.porte != "Todos":
        df = df[df["porte_municipio"] == ss.porte]
    return df


def rotulo_selecao():
    if MUN is not None:
        return f"{MUN['nome']} ({MUN['uf_sigla']})"
    s = ss.uf if ss.uf != "Todas" else ss.regiao if ss.regiao != "Todas" else "Brasil"
    return s + (f" · {ss.porte}" if ss.porte != "Todos" else "")


def e_brasil():
    return ss.regiao == "Todas" and ss.uf == "Todas" and ss.porte == "Todos" and MUN is None


def perfil_dims(cods):
    """Score médio por dimensão para um conjunto de municípios (só IMDM válido)."""
    validos = set(pan.loc[pan["cod_ibge"].isin(cods) & pan["score_global_imdm"].notna(), "cod_ibge"])
    s = score[score["cod_ibge"].isin(validos)]
    return s.groupby("dimensao_codigo")["score"].mean().to_dict(), len(validos)


def referencia():
    """Série intermediária do radar: UF do município, região da UF, ou região com porte."""
    if MUN is not None:
        return MUN["uf_sigla"], pan[pan["uf_sigla"] == MUN["uf_sigla"]]
    if ss.uf != "Todas" and ss.porte != "Todos":
        return ss.uf, pan[pan["uf_sigla"] == ss.uf]
    if ss.uf != "Todas":
        reg = pan.loc[pan["uf_sigla"] == ss.uf, "regiao"].iloc[0]
        return reg, pan[pan["regiao"] == reg]
    if ss.regiao != "Todas" and ss.porte != "Todos":
        return ss.regiao, pan[pan["regiao"] == ss.regiao]
    return None, None


SEL = area(pan) if MUN is None else pan[pan["cod_ibge"] == ss.mun]
BR_DIMS, BR_N = perfil_dims(pan["cod_ibge"])
BR_IMDM = pan["score_global_imdm"].mean()


# ------------------------------------------------------------------ gráficos
def radar(series, altura=430):
    eixos = [quebra(n, 18) for n in dims["dimensao_nome"]]
    cods = dims["dimensao_codigo"].tolist()
    fig = go.Figure()
    for s in reversed(series):
        r = [s["valores"].get(c) for c in cods]
        if all(v is None or (isinstance(v, float) and np.isnan(v)) for v in r):
            continue
        fig.add_trace(go.Scatterpolar(
            r=r + r[:1], theta=eixos + eixos[:1], name=s["nome"], mode="lines+markers" if s.get("principal") else "lines",
            line=dict(color=s["cor"], width=3 if s.get("principal") else 2, dash=s.get("dash", "solid")),
            fill="toself" if s.get("fill") else "none", fillcolor=s.get("fill"),
            hovertemplate="%{theta}<br>" + s["nome"] + ": %{r:.1f}<extra></extra>"))
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickvals=[20, 40, 60, 80, 100], angle=90, tickfont_size=10)),
                      legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center"), margin=dict(l=90, r=90, t=40, b=50),
                      height=altura, font=dict(size=11))
    return fig


def barras_h(rotulos, valores, ref=None, cores=None, maximo=100, sufixo="", altura=None, nome_ref="Brasil", largura_rotulo=26):
    rotulos = [quebra(r, largura_rotulo) for r in rotulos]
    fig = go.Figure(go.Bar(x=valores, y=rotulos, orientation="h", marker_color=cores or AZUL,
                           text=[fmt(v, 1, sufixo) for v in valores], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.1f}" + sufixo + "<extra></extra>", name="Seleção"))
    if ref is not None:
        fig.add_trace(go.Scatter(x=ref, y=rotulos, mode="markers", name=nome_ref,
                                 marker=dict(symbol="line-ns", size=22, color="#111", line=dict(width=3, color="#111")),
                                 hovertemplate="%{y}<br>" + nome_ref + ": %{x:.1f}" + sufixo + "<extra></extra>"))
    fig.update_layout(xaxis=dict(range=[0, maximo * 1.12], showgrid=True, gridcolor="#eee"), yaxis=dict(autorange="reversed"),
                      margin=dict(l=10, r=30, t=10, b=10), height=altura or max(170, 42 * len(rotulos) + 50),
                      showlegend=False, bargap=0.35)
    return fig


def ranking(df_valores, rotulo_col, valor_col, ref, titulo_valor, chave, destaque=None):
    d = df_valores.sort_values(valor_col, ascending=False)
    corte = len(d) > 30
    if corte:
        sel = d[d[rotulo_col] == destaque]
        d = pd.concat([d.head(15), sel, d.tail(15)]).drop_duplicates().sort_values(valor_col, ascending=False)
    cores = [LARANJA if r == destaque else AZUL for r in d[rotulo_col]]
    fig = go.Figure(go.Bar(x=d[rotulo_col], y=d[valor_col], marker_color=cores,
                           hovertemplate="%{x}<br>" + titulo_valor + ": %{y:.1f}<extra></extra>"))
    fig.add_hline(y=ref, line_dash="dash", line_color="#222", annotation_text=f"Brasil {fmt(ref)}", annotation_position="top right")
    fig.update_layout(yaxis=dict(range=[0, 100], title=None), xaxis=dict(title=None, tickangle=-45 if len(d) > 12 else 0),
                      margin=dict(l=10, r=10, t=20, b=10), height=320, bargap=0.25)
    return fig, corte


def histograma(valores, ref, marca=None):
    cont, bordas = np.histogram(valores.dropna(), bins=np.arange(0, 101, 10))
    fig = go.Figure(go.Bar(x=[f"{int(a)}–{int(b)}" for a, b in zip(bordas[:-1], bordas[1:])], y=cont, marker_color=AZUL,
                           hovertemplate="%{x} pontos: %{y} municípios<extra></extra>"))
    fig.add_vline(x=min(ref // 10, 9), line_dash="dash", line_color="#222", annotation_text=f"Brasil {fmt(ref)}")
    if marca is not None:
        fig.add_vline(x=min(marca[1] // 10, 9), line_color=LARANJA, line_width=3, annotation_text=marca[0],
                      annotation_position="bottom right")
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=300, bargap=0.08, yaxis_title="municípios")
    return fig


def por_porte(df_sel, df_br, coluna):
    s = df_sel.groupby("porte_municipio")[coluna].mean().reindex(PORTES)
    b = df_br.groupby("porte_municipio")[coluna].mean().reindex(PORTES)
    x = [f"{p}<br>{PORTE_ROTULO[p]}" for p in PORTES]
    fig = go.Figure([go.Bar(x=x, y=s.values, name="Seleção", marker_color=AZUL, hovertemplate="%{x}: %{y:.1f}<extra>Seleção</extra>"),
                     go.Bar(x=x, y=b.values, name="Brasil", marker_color=CINZA, hovertemplate="%{x}: %{y:.1f}<extra>Brasil</extra>")])
    fig.update_layout(barmode="group", yaxis=dict(range=[0, 100]), margin=dict(l=10, r=10, t=10, b=10), height=300,
                      legend=dict(orientation="h", y=1.12), bargap=0.25)
    return fig


def mapa(df, destaque=None, altura=420):
    coord = dados.coordenadas()
    d = df.merge(coord, on="cod_ibge", how="inner")
    d["nivel"] = d["nivel_maturidade_mmd"].map(nivel_num)
    fig = go.Figure()
    nulos = d[d["score_global_imdm"].isna()]
    if len(nulos):
        fig.add_trace(go.Scattergeo(lat=nulos["lat"], lon=nulos["lon"], mode="markers", name="IMDM nulo",
                                    marker=dict(size=4, color="#cfcdc7"), text=nulos["nome"], hovertemplate="%{text}: nulo<extra></extra>"))
    v = d[d["score_global_imdm"].notna()]
    fig.add_trace(go.Scattergeo(
        lat=v["lat"], lon=v["lon"], mode="markers", name="IMDM", customdata=v[["cod_ibge"]],
        marker=dict(size=4 if len(v) > 1500 else 7, color=v["score_global_imdm"], cmin=0, cmax=100,
                    colorscale=[[0, NIVEL_CORES[0]], [0.5, NIVEL_CORES[2]], [1, NIVEL_CORES[4]]],
                    colorbar=dict(title="IMDM", thickness=10, len=0.6)),
        text=v["nome"] + " (" + v["uf_sigla"] + ")", hovertemplate="%{text}<br>IMDM %{marker.color:.1f}<extra></extra>"))
    if destaque is not None:
        p = d[d["cod_ibge"] == destaque]
        fig.add_trace(go.Scattergeo(lat=p["lat"], lon=p["lon"], mode="markers", name="Selecionado",
                                    marker=dict(size=16, color=LARANJA, line=dict(width=2, color="white")),
                                    text=p["nome"], hovertemplate="%{text}<extra></extra>"))
    fig.update_geos(fitbounds="locations", showcountries=True, countrycolor="#bbb", showland=True, landcolor="#f6f5f2",
                    showocean=False, showlakes=False, projection_type="mercator")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=altura, showlegend=False)
    return fig


def nivel_dist(df, destaque=None):
    d = df["nivel_maturidade_mmd"].dropna()
    cont = d.value_counts().sort_index()
    total = cont.sum()
    nomes = list(cont.index)
    cores = [LARANJA if destaque == n else NIVEL_CORES[min(nivel_num(n) or 1, 5) - 1] for n in nomes]
    return barras_h(nomes, [c / total * 100 if total else 0 for c in cont.values], cores=cores, sufixo="%")


# ------------------------------------------------------------------ páginas
def pagina_visao_geral():
    st.title("Visão geral")
    st.caption(f"MUNIC {ANO} · {rotulo_selecao()}")
    cols = st.columns(5)
    if MUN is not None:
        m = MUN
        if pd.isna(m["score_global_imdm"]):
            kpi(cols[0], "IMDM", "nulo", f"motivo: {m['motivo_imdm_nulo']}")
        else:
            kpi(cols[0], "IMDM do município", fmt(m["score_global_imdm"]), delta=m["score_global_imdm"] - BR_IMDM)
            kpi(cols[1], "Ranking na UF", f"{int(m['rank_uf'])}º de {int(m['total_uf'])}", m["uf_sigla"])
            kpi(cols[2], "Ranking no Brasil", f"{int(m['rank_brasil'])}º de {int(m['total_brasil']):,}".replace(",", "."),
                f"no porte: {int(m['rank_porte'])}º de {int(m['total_porte'])}")
            kpi(cols[3], "Nível de maturidade", str(m["nivel_maturidade_mmd"]))
        resp = lgpd.loc[lgpd["cod_ibge"] == m["cod_ibge"], ["mgov32_responsavel_lgpd", "mgov33_local_responsavel"]]
        r32 = resp.iloc[0, 0] if len(resp) and resp.iloc[0, 0] else "—"
        kpi(cols[4], "Responsável LGPD", r32, resp.iloc[0, 1] if r32 == "Sim" and resp.iloc[0, 1] else "", pequeno=False)
    else:
        sel_v = SEL["score_global_imdm"]
        kpi(cols[0], "IMDM médio", fmt(sel_v.mean()), "média dos municípios válidos" if e_brasil() else "",
            delta=None if e_brasil() else sel_v.mean() - BR_IMDM)
        kpi(cols[1], "Municípios", fmt(len(SEL), 0), f"{fmt(sel_v.notna().sum(), 0)} com IMDM · {sel_v.isna().sum()} nulos")
        lg = lgpd[lgpd["cod_ibge"].isin(SEL["cod_ibge"])]
        if lg["mgov32_responsavel_lgpd"].notna().any():
            pct = lg["tem_responsavel_lgpd"].fillna(False).mean() * 100
            pct_br = lgpd["tem_responsavel_lgpd"].fillna(False).mean() * 100
            kpi(cols[2], "Com responsável LGPD", fmt(pct, 1, "%"), "Mgov32 = Sim" if e_brasil() else "",
                delta=None if e_brasil() else pct - pct_br, sufixo_delta=" p.p. vs Brasil")
        else:
            kpi(cols[2], "Com responsável LGPD", "—", "bloco não coletado nesta edição")
        moda = SEL["nivel_maturidade_mmd"].mode()
        kpi(cols[3], "Nível mais comum", moda.iloc[0] if len(moda) else "—",
            f"{fmt((SEL['nivel_maturidade_mmd'] == moda.iloc[0]).mean() * 100, 0)}% dos municípios" if len(moda) else "")
        medias, _ = perfil_dims(SEL["cod_ibge"])
        if medias:
            fraca = min(medias, key=medias.get)
            kpi(cols[4], "Dimensão mais fraca", dims.set_index("dimensao_codigo").loc[fraca, "dimensao_nome"],
                f"{fmt(medias[fraca])} pontos", pequeno=True)

    # radar + dimensões + LGPD
    sel_dims = score[score["cod_ibge"] == ss.mun].set_index("dimensao_codigo")["score"].to_dict() if MUN is not None else perfil_dims(SEL["cod_ibge"])[0]
    ref_nome, ref_df = referencia()
    series = [dict(nome="Brasil" if e_brasil() else rotulo_selecao(), valores=sel_dims, cor=AZUL, fill=AZUL_SOFT, principal=True)]
    if ref_df is not None:
        series.append(dict(nome=ref_nome, valores=perfil_dims(ref_df["cod_ibge"])[0], cor=LARANJA, fill=LARANJA_SOFT))
    if not e_brasil():
        series.append(dict(nome="Brasil", valores=BR_DIMS, cor=CINZA, dash="dash"))

    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c1:
        st.subheader("Score por dimensão")
        st.caption("Barra = seleção · traço = Brasil")
        st.plotly_chart(barras_h(dims["dimensao_nome"].tolist(), [sel_dims.get(c) for c in dims["dimensao_codigo"]],
                                 ref=[BR_DIMS.get(c) for c in dims["dimensao_codigo"]]), use_container_width=True)
        fora = dims.loc[~dims["entra_no_imdm"].astype(bool), "dimensao_nome"].tolist()
        if fora:
            st.caption("Fora do IMDM (descritivas): " + ", ".join(fora))
    with c2:
        st.subheader("Radar de maturidade")
        st.plotly_chart(radar(series), use_container_width=True)
    with c3:
        st.subheader("LGPD · onde fica o responsável")
        base = lgpd[lgpd["cod_ibge"].isin((pan[pan["uf_sigla"] == MUN["uf_sigla"]] if MUN is not None else SEL)["cod_ibge"])]
        loc = base.loc[base["tem_responsavel_lgpd"].fillna(False), "mgov33_local_responsavel"].dropna()
        loc = loc[loc != "Não sabe informar"]
        if len(loc):
            dist = loc.value_counts(normalize=True) * 100
            curto = {k: k.replace("Na Secretaria de Administraçõ, Finanças ou Planejamento", "Sec. Administração/Finanças")
                         .replace("No departamento ou área de Tecnologia da Informação (TI)", "Área de TI")
                         .replace("Na Controladoria ou Corregedoria municipal", "Controladoria/Corregedoria")
                         .replace("No gabinete do(a) Prefeito(a)", "Gabinete do prefeito")
                         .replace("No departamento jurídico ou procuradoria municipal", "Jurídico/Procuradoria")
                         .replace("Em comitê ou comissão municipal específica", "Comitê/comissão") for k in dist.index}
            local_mun = lgpd.loc[lgpd["cod_ibge"] == ss.mun, "mgov33_local_responsavel"] if MUN is not None else pd.Series(dtype=str)
            cores = [LARANJA if len(local_mun) and k == local_mun.iloc[0] else AZUL for k in dist.index]
            st.plotly_chart(barras_h([curto[k] for k in dist.index], dist.values, cores=cores, sufixo="%"), use_container_width=True)
            st.caption(f"Mgov33 (não pontua) · base: {len(loc):,} municípios com responsável".replace(",", ".")
                       + (f" de {MUN['uf_sigla']}" if MUN is not None else ""))
        else:
            st.info("Bloco de LGPD não coletado nesta edição.")

    # ranking, distribuição e porte
    c1, c2, c3 = st.columns([1.4, 1, 1])
    with c1:
        if MUN is not None or ss.uf != "Todas":
            uf = MUN["uf_sigla"] if MUN is not None else ss.uf
            base = pan[(pan["uf_sigla"] == uf) & pan["score_global_imdm"].notna()]
            if ss.porte != "Todos":
                base = base[base["porte_municipio"] == ss.porte]
            st.subheader(f"IMDM por município · {uf}")
            fig, corte = ranking(base, "nome", "score_global_imdm", BR_IMDM, "IMDM", "rk_mun",
                                destaque=MUN["nome"] if MUN is not None else None)
        else:
            base = area(pan).groupby("uf_sigla", as_index=False)["score_global_imdm"].mean()
            st.subheader("IMDM médio por UF" + (f" · {ss.regiao}" if ss.regiao != "Todas" else ""))
            fig, corte = ranking(base, "uf_sigla", "score_global_imdm", BR_IMDM, "IMDM médio", "rk_uf",
                                destaque=ss.uf if ss.uf != "Todas" else None)
        ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="rank_vg", selection_mode="points")
        st.caption("Clique numa barra para filtrar · tracejado = média Brasil" + (" · 15 maiores e 15 menores" if corte else ""))
        pontos = (ev or {}).get("selection", {}).get("points", []) if isinstance(ev, dict) else getattr(getattr(ev, "selection", None), "points", [])
        if pontos:
            x = pontos[0].get("x")
            if MUN is None and ss.uf == "Todas" and x in set(pan["uf_sigla"]):
                ss.uf = x
                st.rerun()
            elif x in set(base.get("nome", [])):
                ss.mun = base.loc[base["nome"] == x, "cod_ibge"].iloc[0]
                st.rerun()
    with c2:
        st.subheader("Distribuição do IMDM")
        hist_base = pan[pan["uf_sigla"] == MUN["uf_sigla"]] if MUN is not None else SEL
        marca = (MUN["nome"], MUN["score_global_imdm"]) if MUN is not None and pd.notna(MUN["score_global_imdm"]) else None
        st.plotly_chart(histograma(hist_base["score_global_imdm"], BR_IMDM, marca), use_container_width=True)
        st.caption(f"Municípios {'de ' + MUN['uf_sigla'] if MUN is not None else 'da seleção'} por faixa de 10 pontos")
    with c3:
        st.subheader("IMDM por porte")
        st.plotly_chart(por_porte(area(pan) if MUN is None else pan[pan["uf_sigla"] == MUN["uf_sigla"]], pan, "score_global_imdm"),
                        use_container_width=True)
        st.caption("O índice acompanha o porte — compare dentro da mesma faixa")

    # mapa, níveis e tabela
    c1, c2, c3 = st.columns([1.3, 1, 1.2])
    with c1:
        st.subheader("Mapa do IMDM")
        mapa_df = pan[pan["uf_sigla"] == MUN["uf_sigla"]] if MUN is not None else area(pan)
        st.plotly_chart(mapa(mapa_df, ss.mun), use_container_width=True)
    with c2:
        st.subheader("Níveis de maturidade")
        nb = pan[pan["uf_sigla"] == MUN["uf_sigla"]] if MUN is not None else SEL
        st.plotly_chart(nivel_dist(nb, MUN["nivel_maturidade_mmd"] if MUN is not None else None), use_container_width=True)
    with c3:
        st.subheader("Maiores e menores IMDM")
        t = (pan[pan["uf_sigla"] == MUN["uf_sigla"]] if MUN is not None else SEL).dropna(subset=["score_global_imdm"])
        t = t.sort_values("score_global_imdm", ascending=False)
        t = pd.concat([t.head(5), t.tail(5)]) if len(t) > 10 else t
        tab = t[["cod_ibge", "nome", "uf_sigla", "score_global_imdm", "nivel_maturidade_mmd"]].rename(
            columns={"nome": "Município", "uf_sigla": "UF", "score_global_imdm": "IMDM", "nivel_maturidade_mmd": "Nível"})
        ev = st.dataframe(tab.drop(columns="cod_ibge"), hide_index=True, use_container_width=True, on_select="rerun",
                          selection_mode="single-row", key="tab_vg", column_config={"IMDM": st.column_config.NumberColumn(format="%.1f")})
        st.caption("Clique numa linha para abrir o perfil do município")
        linhas = ev.selection.rows if hasattr(ev, "selection") else []
        if linhas:
            ss.mun = tab.iloc[linhas[0]]["cod_ibge"]
            st.switch_page(PAG_PERFIL)


def pagina_perfil():
    st.title("Perfil do município")
    if MUN is None:
        st.info("Escolha um município no filtro **Município** da barra lateral, numa barra do ranking ou numa linha da tabela da Visão geral.")
        sug = area(pan).dropna(subset=["score_global_imdm"]).nlargest(12, "populacao_total")
        cols = st.columns(4)
        for i, r in enumerate(sug.itertuples()):
            if cols[i % 4].button(f"{r.nome} ({r.uf_sigla})", key=f"sug{r.cod_ibge}", use_container_width=True):
                ss.mun = r.cod_ibge
                st.rerun()
        return
    m = MUN
    st.caption(f"{m['uf_sigla']} · {m['regiao']} · {m['porte_municipio']} ({PORTE_ROTULO.get(m['porte_municipio'], '')}) · "
               f"{fmt(m['populacao_total'], 0)} habitantes · IBGE {m['cod_ibge']} · MUNIC {ANO}")
    st.header(f"{m['nome']} ({m['uf_sigla']})")
    c = st.columns(6)
    nulo = pd.isna(m["score_global_imdm"])
    kpi(c[0], "IMDM", "nulo" if nulo else fmt(m["score_global_imdm"]), delta=None if nulo else m["score_global_imdm"] - BR_IMDM)
    kpi(c[1], "Nível", "—" if nulo else str(m["nivel_maturidade_mmd"]), pequeno=True)
    kpi(c[2], "Ranking UF", "—" if nulo else f"{int(m['rank_uf'])}º de {int(m['total_uf'])}")
    kpi(c[3], "Ranking Brasil", "—" if nulo else f"{int(m['rank_brasil'])}º", "" if nulo else f"de {fmt(m['total_brasil'], 0)}")
    kpi(c[4], "Ranking no porte", "—" if nulo else f"{int(m['rank_porte'])}º de {int(m['total_porte'])}", m["porte_municipio"])
    outras = painel_all[(painel_all["cod_ibge"] == m["cod_ibge"]) & (painel_all["ano_edicao"] != ANO)].sort_values("ano_edicao")
    if len(outras) and pd.notna(outras.iloc[-1]["score_global_imdm"]) and not nulo:
        o = outras.iloc[-1]
        kpi(c[5], f"IMDM {int(o['ano_edicao'])}", fmt(o["score_global_imdm"]), "radares podem diferir",
            delta=m["score_global_imdm"] - o["score_global_imdm"], sufixo_delta=f" até {ANO}")
    else:
        kpi(c[5], "Outras edições", "—", "sem IMDM em outra edição")
    if nulo:
        st.warning(f"IMDM nulo nesta edição: {m['motivo_imdm_nulo']}.")

    uf_df = pan[pan["uf_sigla"] == m["uf_sigla"]]
    mun_dims = score[score["cod_ibge"] == m["cod_ibge"]].set_index("dimensao_codigo")["score"].to_dict()
    itens = dados.itens_do_municipio(m["cod_ibge"], ANO)
    ado = dados.adocao_uf_porte(ANO)
    ado_uf = ado[ado["uf_sigla"] == m["uf_sigla"]].groupby("item")[["soma_pontos", "soma_peso"]].sum()
    ado_porte = ado[ado["porte_municipio"] == m["porte_municipio"]].groupby("item")[["soma_pontos", "soma_peso"]].sum()
    pct_uf = (ado_uf["soma_pontos"] / ado_uf["soma_peso"] * 100).to_dict()
    pct_porte = (ado_porte["soma_pontos"] / ado_porte["soma_peso"] * 100).to_dict()

    c1, c2, c3 = st.columns([1, 1.4, 1])
    with c1:
        st.subheader("Lacunas e destaques")
        st.caption(f"Comparado aos municípios do mesmo porte ({m['porte_municipio']})")
        if len(itens):
            it = itens.assign(porte=itens["item"].map(pct_porte))
            lac = it[it["status_item"].isin(["Não", "Salto (0)"]) & (it["porte"] >= 50)].nlargest(7, "porte")
            dst = it[(it["status_item"] == "Sim") & (it["porte"] < 35)].nsmallest(6, "porte")
            st.markdown("**O que falta e a maioria do porte já tem**")
            st.markdown("\n".join(f"- **{r.item}** · {r.dimensao_nome} · {fmt(r.porte, 0)}% do porte tem" for r in lac.itertuples())
                        or "_Nenhuma lacuna relevante._")
            st.markdown("**Destaques (tem, mas é raro no porte)**")
            st.markdown("\n".join(f"- **{r.item}** · só {fmt(r.porte, 0)}% do porte tem" for r in dst.itertuples())
                        or "_Nenhum destaque raro._")
    with c2:
        st.subheader("Radar do município")
        st.plotly_chart(radar([dict(nome=m["nome"], valores=mun_dims, cor=AZUL, fill=AZUL_SOFT, principal=True),
                               dict(nome=m["uf_sigla"], valores=perfil_dims(uf_df["cod_ibge"])[0], cor=LARANJA, fill=LARANJA_SOFT),
                               dict(nome="Brasil", valores=BR_DIMS, cor=CINZA, dash="dash")]), use_container_width=True)
    with c3:
        st.subheader(f"Localização · {m['uf_sigla']}")
        st.plotly_chart(mapa(uf_df, m["cod_ibge"], altura=380), use_container_width=True)

    st.subheader(f"Os {len(itens)} itens do radar {ANO}")
    st.caption("Resposta do município em cada item · à direita, % de adoção na UF e no mesmo porte (Parcial conta pela fração)")
    for d in dims.itertuples():
        di = itens[itens["dimensao_codigo"] == d.dimensao_codigo]
        if di.empty:
            continue
        sim = (di["status_item"] == "Sim").sum()
        with st.expander(f"{d.dimensao_ordem}. {d.dimensao_nome} — score {fmt(mun_dims.get(d.dimensao_codigo))} · {sim} de {len(di)} itens completos",
                         expanded=d.dimensao_ordem == 1):
            tab = pd.DataFrame({
                "Status": di["status_item"].map(lambda s: STATUS_ICONE.get(s, s)),
                "Item": di["item"],
                f"% {m['uf_sigla']}": di["item"].map(pct_uf),
                "% porte": di["item"].map(pct_porte),
                "Resposta (IBGE)": di["resposta_original"],
                "Código": di["variavel_ancora"],
                "Descrição": di["item_descricao"],
            })
            st.dataframe(tab, hide_index=True, use_container_width=True, column_config={
                f"% {m['uf_sigla']}": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
                "% porte": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100)})


def pagina_dimensoes():
    st.title("Dimensões")
    st.caption(f"MUNIC {ANO} · {rotulo_selecao().split(' (')[0] if MUN is None else (ss.uf if ss.uf != 'Todas' else 'Brasil')} "
               "· nesta tela vale a área filtrada (o município selecionado não restringe)")
    nomes = dict(zip(dims["dimensao_codigo"], dims["dimensao_nome"]))
    if ss.dim not in nomes:
        ss.dim = dims["dimensao_codigo"].iloc[0]
    ss.dim = st.segmented_control("Dimensão", list(nomes), format_func=lambda c: nomes[c], default=ss.dim) or ss.dim
    d = dims.set_index("dimensao_codigo").loc[ss.dim]
    area_pan = area(pan)
    validos = area_pan[area_pan["score_global_imdm"].notna()]["cod_ibge"]
    sd = score[(score["dimensao_codigo"] == ss.dim)]
    sd_sel = sd[sd["cod_ibge"].isin(validos)]
    sd_br = sd[sd["cod_ibge"].isin(pan.loc[pan["score_global_imdm"].notna(), "cod_ibge"])]

    ado = dados.adocao_uf_porte(ANO)
    ado = ado[ado["dimensao_codigo"] == ss.dim]
    a_sel = ado.copy()
    if ss.regiao != "Todas":
        a_sel = a_sel[a_sel["regiao"] == ss.regiao]
    if ss.uf != "Todas":
        a_sel = a_sel[a_sel["uf_sigla"] == ss.uf]
    if ss.porte != "Todos":
        a_sel = a_sel[a_sel["porte_municipio"] == ss.porte]
    g_sel = a_sel.groupby("item")[["soma_pontos", "soma_peso"]].sum()
    g_br = ado.groupby("item")[["soma_pontos", "soma_peso"]].sum()
    p_sel = (g_sel["soma_pontos"] / g_sel["soma_peso"] * 100).sort_values(ascending=False)
    p_br = (g_br["soma_pontos"] / g_br["soma_peso"] * 100)

    c = st.columns(4)
    kpi(c[0], f"Score médio · {d['dimensao_nome']}", fmt(sd_sel["score"].mean()),
        delta=None if e_brasil() else sd_sel["score"].mean() - sd_br["score"].mean())
    kpi(c[1], "Municípios com score ≥ 50", fmt((sd_sel["score"] >= 50).mean() * 100, 1, "%"),
        "" if e_brasil() else f"Brasil {fmt((sd_br['score'] >= 50).mean() * 100, 1, '%')}")
    if len(p_sel):
        kpi(c[2], "Item mais adotado", p_sel.index[0], fmt(p_sel.iloc[0], 0, "% de adoção"), pequeno=True)
        kpi(c[3], "Item menos adotado", p_sel.index[-1], fmt(p_sel.iloc[-1], 0, "% de adoção"), pequeno=True)
    st.caption(f"Peso da dimensão: {fmt(d['dimensao_peso'], 0)} · {'entra' if d['entra_no_imdm'] else 'não entra'} no IMDM · "
               f"{len(p_br)} itens · {d['descricao'] or ''}")

    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.subheader(f"Adoção dos itens ({len(p_sel)})")
        st.caption("% de adoção na seleção · traço = Brasil · Parcial conta pela fração")
        st.plotly_chart(barras_h(list(p_sel.index), p_sel.values, ref=[p_br.get(i) for i in p_sel.index], sufixo="%"),
                        use_container_width=True)
    with c2:
        if ss.uf != "Todas":
            base = sd_sel.merge(pan[["cod_ibge", "nome"]], on="cod_ibge")
            st.subheader(f"Score por município · {ss.uf}")
            fig, _ = ranking(base, "nome", "score", sd_br["score"].mean(), "Score", "rk_dmun")
        else:
            base = sd_sel.groupby("uf_sigla", as_index=False)["score"].mean()
            st.subheader("Score médio por UF")
            fig, _ = ranking(base, "uf_sigla", "score", sd_br["score"].mean(), "Score médio", "rk_duf")
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("Distribuição do score")
        st.plotly_chart(histograma(sd_sel["score"], sd_br["score"].mean()), use_container_width=True)
    st.subheader("Score por porte")
    st.plotly_chart(por_porte(sd_sel, sd_br, "score"), use_container_width=True)


def pagina_qualidade():
    st.title("Qualidade dos dados")
    st.caption(f"MUNIC {ANO} · {rotulo_selecao() if MUN is None else (ss.uf if ss.uf != 'Todas' else 'Brasil')} · respostas das variáveis do radar")
    sel = area(pan)
    q = qual_all[qual_all["ano_edicao"] == ANO]
    if ss.regiao != "Todas":
        q = q[q["regiao"] == ss.regiao]
    if ss.uf != "Todas":
        q = q[q["uf_sigla"] == ss.uf]
    tot = q[["respostas", "validas", "nao_sabe", "nao_informou", "salto_logico", "recusa"]].sum()
    nulos = sel["motivo_imdm_nulo"].value_counts()
    c = st.columns(5)
    kpi(c[0], "Municípios", fmt(len(sel), 0))
    kpi(c[1], "Com IMDM válido", fmt(sel["score_global_imdm"].notna().sum(), 0),
        fmt(sel["score_global_imdm"].notna().mean() * 100, 1, "% da seleção"))
    kpi(c[2], "IMDM nulo", fmt(sel["score_global_imdm"].isna().sum(), 0),
        " · ".join(f"{k}: {v}" for k, v in nulos.items()) or "nenhum")
    kpi(c[3], "Respostas “Não sabe”", fmt(tot["nao_sabe"] / tot["respostas"] * 100 if tot["respostas"] else 0, 2, "%"),
        f"{fmt(tot['nao_sabe'], 0)} de {fmt(tot['respostas'], 0)} respostas")
    kpi(c[4], "Saltos lógicos (“-”)", fmt(tot["salto_logico"] / tot["respostas"] * 100 if tot["respostas"] else 0, 1, "%"),
        "valem 0 no cálculo")
    if ss.porte != "Todos":
        st.caption("O filtro de porte não se aplica às contagens por variável (agregadas por UF).")

    c1, c2, c3 = st.columns([1.2, 1, 1.2])
    with c1:
        st.subheader("“Não sabe” por variável")
        g = q.groupby(["cod_variable", "item"])[["nao_sabe", "respostas"]].sum()
        g = (g["nao_sabe"] / g["respostas"] * 100).sort_values(ascending=False)
        g = g[g > 0].head(10)
        if len(g):
            st.plotly_chart(barras_h([f"{v} · {i}" for v, i in g.index], g.values, maximo=max(5, g.max()), sufixo="%"),
                            use_container_width=True)
        else:
            st.info("Nenhuma resposta “Não sabe” na seleção.")
    with c2:
        st.subheader("IMDM nulo por motivo")
        if len(nulos):
            st.plotly_chart(barras_h(list(nulos.index), nulos.values, maximo=max(nulos.max(), 1)), use_container_width=True)
        else:
            st.success("Nenhum município com IMDM nulo na seleção.")
    with c3:
        st.subheader("“Não sabe” por UF")
        u = q.groupby("uf_sigla")[["nao_sabe", "respostas"]].sum()
        u = (u["nao_sabe"] / u["respostas"] * 100).sort_values(ascending=False)
        st.plotly_chart(barras_h(list(u.index[:15]), u.values[:15], maximo=max(1, u.max() if len(u) else 1), sufixo="%"),
                        use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Regras de tratamento")
        st.dataframe(pd.DataFrame([
            ("Sim", "1 ponto"), ("Não", "0"), ("“-” (salto lógico)", "0"), ("Não sabe informar / Não informou", "0, com peso"),
            ("Não se aplica (exceção da LAI)", "sai do denominador"), ("Escalonados e escadas", "pontos da planilha do radar"),
            ("Grupos do portal", "fração de “Sim”"), ("Recusa", "IMDM nulo"),
            ("Dimensão do IMDM sem item válido", "IMDM nulo"),
            ("IMDM", "média ponderada das dimensões do radar do ano"),
        ], columns=["Resposta", "Tratamento"]), hide_index=True, use_container_width=True)
    with c2:
        st.subheader("Radar de cada edição")
        r = radar_all.sort_values(["ano_edicao", "dimensao_ordem"])
        st.dataframe(r[["ano_edicao", "dimensao_ordem", "dimensao_nome", "dimensao_peso", "entra_no_imdm"]].rename(columns={
            "ano_edicao": "Edição", "dimensao_ordem": "Ordem", "dimensao_nome": "Dimensão", "dimensao_peso": "Peso",
            "entra_no_imdm": "Entra no IMDM"}), hide_index=True, use_container_width=True)
        st.caption("Definido pelo especialista em config/radar/radar_imdm.xlsx; validado e versionado no pipeline.")


PAG_VISAO = st.Page(pagina_visao_geral, title="Visão geral", icon="🗺️", default=True)
PAG_PERFIL = st.Page(pagina_perfil, title="Perfil do município", icon="🏛️", url_path="perfil")
PAG_DIM = st.Page(pagina_dimensoes, title="Dimensões", icon="🧭", url_path="dimensoes")
PAG_QUAL = st.Page(pagina_qualidade, title="Qualidade dos dados", icon="🔎", url_path="qualidade")
st.navigation([PAG_VISAO, PAG_PERFIL, PAG_DIM, PAG_QUAL]).run()
