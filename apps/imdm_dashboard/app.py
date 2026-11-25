"""Dashboard IMDM — Índice de Maturidade Digital Municipal (MUNIC/IBGE).

Lê só a camada semantic (contrato de consumo). Nenhuma regra de pontuação aqui:
dimensões, itens e pesos vêm do radar de cada edição, definido pelo especialista.

Tema claro/escuro: menu ⋮ (canto superior direito) → Light / Dark. As cores dos gráficos funcionam nos dois.
Município: filtro ativo só na Visão geral e no Perfil (Dimensões e Qualidade são telas de área).
Testes: tests/test_app.py abre todas as telas com todas as combinações de filtros.
"""
from __future__ import annotations

import html
import os
from types import SimpleNamespace

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import dados

st.set_page_config(page_title="IMDM · Maturidade Digital Municipal", page_icon="📡", layout="wide")

# ------------------------------------------------------------------ cores
# Valem nos dois temas (claro e escuro): trocar o tema no menu ⋮ não reexecuta o script,
# então nenhuma cor fixa pode depender do tema ativo. Fundos dos gráficos ficam transparentes.
AZUL, LARANJA, CINZA = "#2a78d6", "#eb6834", "#8a8984"
AZUL_SOFT, LARANJA_SOFT = "rgba(42,120,214,0.20)", "rgba(235,104,52,0.14)"
NIVEL_CORES = ["#a9cdf6", "#6aa6ec", "#3987e5", "#1f66c1", "#174e94"]
T = SimpleNamespace(
    referencia="#8c8c8c",                  # traço "Brasil" nas barras (cinza médio: lê no claro e no escuro)
    linha="#8c8c8c",                       # linhas tracejadas de média
    grade="rgba(128,128,128,0.22)",
    grade_radar="rgba(128,128,128,0.40)",
    terra="rgba(128,128,128,0.12)",
    fronteira="rgba(128,128,128,0.55)",
    nulo="rgba(128,128,128,0.55)",
    contorno="#ffffff",
    sobe="#16a34a",
    desce="#dc2626",
)

PORTES = ["Pequeno I", "Pequeno II", "Médio", "Grande I", "Grande II"]
PORTE_ROTULO = {"Pequeno I": "≤ 20 mil", "Pequeno II": "20–50 mil", "Médio": "50–100 mil",
                "Grande I": "100–500 mil", "Grande II": "> 500 mil"}
STATUS_ICONE = {"Sim": "✅ Sim", "Parcial": "🟡 Parcial", "Não": "❌ Não", "Salto (0)": "➖ Salto (0)",
                "Não sabe": "❔ Não sabe", "Não informou": "❔ Não informou", "Não se aplica": "⚪ Não se aplica",
                "Recusa": "⛔ Recusa"}

st.markdown(f"""
<style>
.block-container{{padding-top:3.2rem}}
.kpi{{background:rgba(128,128,128,0.09);border-radius:10px;padding:10px 14px;height:100%}}
.kpi .k{{font-size:.82rem;opacity:.75}}
.kpi .v{{font-size:1.55rem;font-weight:700;line-height:1.25;margin:2px 0}}
.kpi .v.sm{{font-size:1.05rem;line-height:1.35}}
.kpi .d{{font-size:.8rem;opacity:.8}}
.kpi .up{{color:{T.sobe};font-weight:600}}.kpi .down{{color:{T.desce};font-weight:600}}
.cab{{display:flex;align-items:center;gap:22px;padding:4px 0 14px;margin-bottom:6px;border-bottom:1px solid rgba(128,128,128,0.25)}}
.cab-logo{{position:relative;flex:none}}
.cab-logo img{{height:72px;width:auto;display:block}}
.cab-logo-txt{{position:absolute;inset:0;background-color:currentColor;
  -webkit-mask-size:100% 100%;mask-size:100% 100%;-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat}}
.cab-tit{{font-size:1.45rem;font-weight:700;line-height:1.2}}
.cab-org{{font-size:.92rem;opacity:.85;margin-top:2px}}
.cab-aviso{{font-size:.76rem;opacity:.6;margin-top:3px}}
@media (max-width:700px){{.cab{{flex-direction:column;align-items:flex-start;gap:8px}}.cab-logo img{{height:56px}}}}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ utilitários
def vazio(v) -> bool:
    """True para None, NaN, NA e string vazia."""
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        return False
    return isinstance(v, str) and not v.strip()


def fmt(v, casas=1, suf=""):
    if vazio(v):
        return "—"
    return f"{float(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".") + suf


def texto(v, padrao="—"):
    return padrao if vazio(v) else str(v)


def pct(num, den):
    """num/den × 100, com NaN quando den é 0 (sem divisão por zero)."""
    num, den = np.asarray(num, dtype=float), np.asarray(den, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / np.where(den > 0, den, 1) * 100, np.nan)


def nivel_num(rotulo):
    try:
        return int(str(rotulo).split("-")[0])
    except ValueError:
        return None


def kpi(col, rotulo, valor, detalhe="", delta=None, sufixo_delta=" vs Brasil", pequeno=False):
    """Card de indicador. delta numérico ganha cor; detalhe é texto neutro."""
    d = ""
    if not vazio(delta):
        cls = "up" if delta > 0.05 else "down" if delta < -0.05 else ""
        d = f'<span class="{cls}">{delta:+.1f}</span>{html.escape(sufixo_delta)}'.replace(".", ",", 1)
    extra = " · ".join(x for x in [d, html.escape(str(detalhe)) if not vazio(detalhe) else ""] if x)
    col.markdown(f'<div class="kpi"><div class="k">{html.escape(rotulo)}</div>'
                 f'<div class="v{" sm" if pequeno else ""}">{html.escape(texto(valor))}</div>'
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


def grafico(fig, key, **kw):
    """st.plotly_chart com chave fixa (evita IDs duplicados) e largura total."""
    return st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False}, **kw)


# ------------------------------------------------------------------ dados
try:
    _b = dados.base()
except Exception as e:   # noqa: BLE001
    st.error("Não foi possível ler a camada semantic. Confira se o pipeline rodou (gold_to_semantic), "
             "se o app tem permissão de leitura no schema e se o SQL warehouse está ligado.")
    with st.expander("Detalhes técnicos"):
        st.code(f"{type(e).__name__}: {e}")
    st.stop()

# Tabelas por radar (coluna `radar`); a de LGPD não depende de radar
_painel_todos = _b["vw_painel_municipio"]
_score_todos = _b["vw_score_dimensao"]
_radar_todos = _b["vw_radar_dimensao"]
_qual_todos = _b["agg_qualidade_item"]
lgpd_all = _b["vw_auditoria_lgpd"]
RADARES = _b["vw_radares"].copy()
RADARES = RADARES[RADARES["radar"].isin(set(_painel_todos["radar"]))]
if RADARES.empty or _painel_todos.empty:
    st.warning("A camada semantic está vazia: rode o pipeline para ao menos uma edição.")
    st.stop()
RADARES["padrao"] = RADARES["padrao"].astype("boolean").fillna(False).astype(bool)
RADARES = RADARES.sort_values(["padrao", "radar"], ascending=[False, True]).reset_index(drop=True)
RADAR_PADRAO = RADARES["radar"].iloc[0]
RADAR_INFO = {r.radar: r for r in RADARES.itertuples()}


def rotulo_radar(cod):
    r = RADAR_INFO.get(cod)
    nome = texto(getattr(r, "nome", None), "") if r is not None else ""
    return f"{cod} · {nome}" if nome else str(cod)


# ------------------------------------------------------------------ filtros (barra lateral, valem para todas as telas)
ss = st.session_state


def pedir(**kw):
    """Pede uma mudança de filtro vinda de um clique (aplicada no início da próxima execução)."""
    ss["_pendente"] = {**ss.get("_pendente", {}), **kw}


def limpar_filtros():
    ss.f_regiao, ss.f_uf, ss.f_porte, ss.f_mun = "Todas", "Todas", "Todos", None
    ss.pop("_ult_rank_vg", None)


for _k, _v in ss.pop("_pendente", {}).items():
    ss[f"f_{_k}"] = _v


def garantir(chave, opcoes, padrao):
    """Mantém o valor do filtro só se ainda for uma opção válida (ex.: depois de trocar a edição)."""
    if chave not in ss or ss[chave] not in opcoes:
        ss[chave] = padrao


# ------------------------------------------------------------------ páginas e navegação
# As funções das páginas estão mais abaixo; os invólucros só as chamam na hora de rodar.
PAGINAS_SEM_MUNICIPIO = {"dimensoes", "qualidade"}   # telas de área: o filtro de município fica desativado


def _p_visao():
    pagina_visao_geral()


def _p_perfil():
    pagina_perfil()


def _p_dimensoes():
    pagina_dimensoes()


def _p_qualidade():
    pagina_qualidade()


PAG_VISAO = st.Page(_p_visao, title="Visão geral", icon="🗺️", url_path="visao", default=True)
PAG_PERFIL = st.Page(_p_perfil, title="Perfil do município", icon="🏛️", url_path="perfil")
PAG_DIM = st.Page(_p_dimensoes, title="Dimensões", icon="🧭", url_path="dimensoes")
PAG_QUAL = st.Page(_p_qualidade, title="Qualidade dos dados", icon="🔎", url_path="qualidade")

# IMDM_PAGINA: usado só pelos testes automáticos (tests/test_app.py) para abrir uma tela direto
_PAGINA_TESTE = os.getenv("IMDM_PAGINA")
NAV = None if _PAGINA_TESTE else st.navigation([PAG_VISAO, PAG_PERFIL, PAG_DIM, PAG_QUAL])
PAGINA = _PAGINA_TESTE or (NAV.url_path or "visao")
MUNICIPIO_ATIVO = PAGINA not in PAGINAS_SEM_MUNICIPIO


with st.sidebar:
    st.markdown("### 📡 IMDM")
    st.caption("Índice de Maturidade Digital Municipal · IBGE MUNIC")
    lista_radares = RADARES["radar"].tolist()
    garantir("f_radar", lista_radares, RADAR_PADRAO)
    st.selectbox("Radar", lista_radares, key="f_radar", format_func=rotulo_radar,
                 help="Metodologia do IMDM definida pelo especialista. Cada radar cobre todas as edições; "
                      "as respostas do IBGE são as mesmas, muda só a forma de pontuar.")
    _desc = texto(getattr(RADAR_INFO[ss.f_radar], "descricao", None), "")
    if _desc:
        st.caption(_desc)
    painel_all = _painel_todos[_painel_todos["radar"] == ss.f_radar]
    score_all = _score_todos[_score_todos["radar"] == ss.f_radar]
    radar_all = _radar_todos[_radar_todos["radar"] == ss.f_radar]
    qual_all = _qual_todos[_qual_todos["radar"] == ss.f_radar]
    EDICOES = sorted((int(a) for a in painel_all["ano_edicao"].dropna().unique()), reverse=True)
    garantir("f_ano", EDICOES, EDICOES[0])
    st.selectbox("Edição", EDICOES, key="f_ano")
    _pan = painel_all[painel_all["ano_edicao"] == ss.f_ano]
    regioes = ["Todas"] + sorted(_pan["regiao"].dropna().unique())
    garantir("f_regiao", regioes, "Todas")
    st.selectbox("Macrorregião", regioes, key="f_regiao")
    _r = _pan if ss.f_regiao == "Todas" else _pan[_pan["regiao"] == ss.f_regiao]
    ufs = ["Todas"] + sorted(_r["uf_sigla"].dropna().unique())
    garantir("f_uf", ufs, "Todas")
    st.selectbox("Estado (UF)", ufs, key="f_uf")
    portes = ["Todos"] + [p for p in PORTES if p in set(_pan["porte_municipio"])]
    garantir("f_porte", portes, "Todos")
    st.selectbox("Porte populacional", portes, key="f_porte",
                 format_func=lambda p: p if p == "Todos" else f"{p} ({PORTE_ROTULO.get(p, '')})")
    _m = _r if ss.f_uf == "Todas" else _r[_r["uf_sigla"] == ss.f_uf]
    if ss.f_porte != "Todos":
        _m = _m[_m["porte_municipio"] == ss.f_porte]
    rotulos = {r.cod_ibge: f"{r.nome} ({r.uf_sigla})" for r in _m.sort_values("nome").itertuples()}
    lista = [None] + list(rotulos)
    garantir("f_mun", lista, None)
    if MUNICIPIO_ATIVO:
        # f_mun guarda a escolha; w_mun é só o widget (assim a escolha sobrevive às telas sem município)
        ss.w_mun = ss.f_mun
        st.selectbox("Município", lista, key="w_mun", format_func=lambda c: "Todos" if c is None else rotulos.get(c, c),
                     on_change=lambda: ss.__setitem__("f_mun", ss.w_mun),
                     help="Digite para buscar. Ao escolher um município, os indicadores passam a ser do município.")
    else:
        st.selectbox("Município", ["Não se aplica nesta tela"], key="w_mun_off", disabled=True,
                     help="Esta tela mostra a área filtrada (região, UF e porte). "
                          "O município escolhido continua valendo na Visão geral e no Perfil.")
    st.button("Limpar filtros", width="stretch", on_click=limpar_filtros)
    st.divider()
    sha = _pan["radar_sha256"].dropna()
    st.caption(f"Radar {ss.f_radar} em {ss.f_ano}: "
               f"{radar_all.loc[radar_all['ano_edicao'] == ss.f_ano, 'dimensao_codigo'].nunique()} dimensões · "
               f"planilha `{(sha.iloc[0] if len(sha) else '')[:10]}`")
    st.button("Recarregar dados", width="stretch", on_click=dados.recarregar,
              help="Use depois de rodar o pipeline. Sem isso, o app guarda os dados por 12 horas.")
    st.caption("Tema claro ou escuro: menu ⋮ no canto superior direito")

FIL = SimpleNamespace(radar=ss.f_radar, ano=int(ss.f_ano), regiao=ss.f_regiao, uf=ss.f_uf, porte=ss.f_porte,
                      mun=ss.f_mun if MUNICIPIO_ATIVO else None)


# ------------------------------------------------------------------ cabeçalho (todas as telas)
@st.cache_data(show_spinner=False)
def _logo_base64(nome):
    import base64
    return base64.b64encode((dados.AQUI / "assets" / nome).read_bytes()).decode()


def cabecalho():
    """Logo + título + secretaria.

    O logo é montado em duas camadas: a palavra BRASIL colorida (igual nos dois temas) e os textos
    "GOVERNO DO" / "DO LADO DO POVO BRASILEIRO" como máscara pintada com a cor do texto do tema
    (escura no claro, clara no escuro). Assim o logo acompanha o tema na hora, inclusive quando ele é
    trocado no menu ⋮ (o que não reexecuta o app). Fonte: as versões oficiais para fundo claro e escuro."""
    marca, textos = _logo_base64("logo_gov_marca.png"), _logo_base64("logo_gov_textos.png")
    st.markdown(f"""
<style>
.cab-logo-txt{{-webkit-mask-image:url(data:image/png;base64,{textos});mask-image:url(data:image/png;base64,{textos})}}
</style>
<div class="cab">
  <div class="cab-logo" role="img" aria-label="Governo do Brasil">
    <img src="data:image/png;base64,{marca}" alt=""/>
    <div class="cab-logo-txt"></div>
  </div>
  <div class="cab-txt">
    <div class="cab-tit">Painel de Maturidade Digital Municipal</div>
    <div class="cab-org">Secretaria de Governo Digital · Ministério da Gestão e da Inovação em Serviços Públicos</div>
    <div class="cab-aviso">Projeto acadêmico · UEL — não é publicação oficial do Governo Federal · dados: IBGE, Pesquisa MUNIC</div>
  </div>
</div>""", unsafe_allow_html=True)


cabecalho()


# ------------------------------------------------------------------ recorte atual
ANO = FIL.ano
pan = painel_all[painel_all["ano_edicao"] == ANO].copy()
dims = (radar_all[radar_all["ano_edicao"] == ANO].drop_duplicates("dimensao_codigo")
        .sort_values("dimensao_ordem").reset_index(drop=True))
score = score_all[score_all["ano_edicao"] == ANO]
lgpd = lgpd_all[lgpd_all["ano_edicao"] == ANO]
MUN = pan[pan["cod_ibge"] == FIL.mun].iloc[0] if FIL.mun is not None and (pan["cod_ibge"] == FIL.mun).any() else None
DIM_NOME = dict(zip(dims["dimensao_codigo"], dims["dimensao_nome"]))


def area(df):
    if FIL.regiao != "Todas":
        df = df[df["regiao"] == FIL.regiao]
    if FIL.uf != "Todas":
        df = df[df["uf_sigla"] == FIL.uf]
    if FIL.porte != "Todos":
        df = df[df["porte_municipio"] == FIL.porte]
    return df


def rotulo_selecao():
    if MUN is not None:
        return f"{MUN['nome']} ({MUN['uf_sigla']})"
    s = FIL.uf if FIL.uf != "Todas" else FIL.regiao if FIL.regiao != "Todas" else "Brasil"
    return s + (f" · {FIL.porte}" if FIL.porte != "Todos" else "")


def rotulo_area():
    """Rótulo da área filtrada, sem o município (telas Dimensões e Qualidade)."""
    s = FIL.uf if FIL.uf != "Todas" else FIL.regiao if FIL.regiao != "Todas" else "Brasil"
    return s + (f" · {FIL.porte}" if FIL.porte != "Todos" else "")


def e_brasil():
    return FIL.regiao == "Todas" and FIL.uf == "Todas" and FIL.porte == "Todos" and MUN is None


def perfil_dims(cods):
    """Score médio por dimensão para um conjunto de municípios (só IMDM válido)."""
    validos = set(pan.loc[pan["cod_ibge"].isin(cods) & pan["score_global_imdm"].notna(), "cod_ibge"])
    s = score[score["cod_ibge"].isin(validos)]
    return s.groupby("dimensao_codigo")["score"].mean().to_dict(), len(validos)


def referencia():
    """Série intermediária do radar: UF do município, região da UF, ou região com porte."""
    if MUN is not None:
        return MUN["uf_sigla"], pan[pan["uf_sigla"] == MUN["uf_sigla"]]
    if FIL.uf != "Todas" and FIL.porte != "Todos":
        return FIL.uf, pan[pan["uf_sigla"] == FIL.uf]
    if FIL.uf != "Todas":
        reg = pan.loc[pan["uf_sigla"] == FIL.uf, "regiao"]
        if len(reg):
            return reg.iloc[0], pan[pan["regiao"] == reg.iloc[0]]
    if FIL.regiao != "Todas" and FIL.porte != "Todos":
        return FIL.regiao, pan[pan["regiao"] == FIL.regiao]
    return None, None


def aviso_sem_municipios():
    st.warning(f"Nenhum município com esta combinação de filtros ({rotulo_selecao()}). "
               "Ajuste os filtros na barra lateral ou clique em **Limpar filtros**.")


SEL = area(pan) if MUN is None else pan[pan["cod_ibge"] == FIL.mun]
BR_DIMS, BR_N = perfil_dims(pan["cod_ibge"])
BR_IMDM = pan["score_global_imdm"].mean()


# ------------------------------------------------------------------ gráficos
def radar(series, altura=430):
    eixos = [quebra(n, 18) for n in dims["dimensao_nome"]]
    cods = dims["dimensao_codigo"].tolist()
    fig = go.Figure()
    for s in reversed(series):
        r = [s["valores"].get(c) for c in cods]
        if all(vazio(v) for v in r):
            continue
        fig.add_trace(go.Scatterpolar(
            r=r + r[:1], theta=eixos + eixos[:1], name=s["nome"], mode="lines+markers" if s.get("principal") else "lines",
            line=dict(color=s["cor"], width=3 if s.get("principal") else 2, dash=s.get("dash", "solid")),
            fill="toself" if s.get("fill") else "none", fillcolor=s.get("fill"),
            hovertemplate="%{theta}<br>" + s["nome"] + ": %{r:.1f}<extra></extra>"))
    fig.update_layout(polar=dict(bgcolor="rgba(0,0,0,0)",
                                 radialaxis=dict(range=[0, 100], tickvals=[20, 40, 60, 80, 100], angle=90, tickfont_size=10,
                                                 gridcolor=T.grade_radar, linecolor=T.grade_radar),
                                 angularaxis=dict(gridcolor=T.grade_radar, linecolor=T.grade_radar)),
                      legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center"), margin=dict(l=90, r=90, t=40, b=50),
                      height=altura, font=dict(size=11))
    return fig


def barras_h(rotulos, valores, ref=None, cores=None, maximo=100, sufixo="", altura=None, nome_ref="Brasil", largura_rotulo=26):
    rotulos = [quebra(r, largura_rotulo) for r in rotulos]
    valores = [None if vazio(v) else float(v) for v in valores]
    por_barra = max(42, 14 * max((r.count("<br>") + 1 for r in rotulos), default=1) + 14)
    fig = go.Figure(go.Bar(x=valores, y=rotulos, orientation="h", marker_color=cores or AZUL,
                           text=[fmt(v, 1, sufixo) for v in valores], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.1f}" + sufixo + "<extra></extra>", name="Seleção"))
    if ref is not None:
        fig.add_trace(go.Scatter(x=[None if vazio(v) else float(v) for v in ref], y=rotulos, mode="markers", name=nome_ref,
                                 marker=dict(symbol="line-ns", size=22, color=T.referencia, line=dict(width=4, color=T.referencia)),
                                 hovertemplate="%{y}<br>" + nome_ref + ": %{x:.1f}" + sufixo + "<extra></extra>"))
    maximo = maximo if not vazio(maximo) and maximo > 0 else 100
    fig.update_layout(xaxis=dict(range=[0, maximo * 1.12], showgrid=True, gridcolor=T.grade), yaxis=dict(autorange="reversed", automargin=True),
                      margin=dict(l=10, r=30, t=10, b=10), height=altura or max(170, por_barra * len(rotulos) + 50),
                      showlegend=False, bargap=0.35)
    return fig


def linha_media(fig, valor, horizontal=True, rotulo=None):
    if vazio(valor):
        return
    txt = rotulo or f"Brasil {fmt(valor)}"
    if horizontal:
        fig.add_hline(y=valor, line_dash="dash", line_color=T.linha, annotation_text=txt, annotation_position="top right")
    else:
        fig.add_vline(x=min(int(valor // 10), 9), line_dash="dash", line_color=T.linha, annotation_text=txt)


def ranking(df_valores, rotulo_col, valor_col, ref, titulo_valor, destaque=None):
    d = df_valores.dropna(subset=[valor_col]).sort_values(valor_col, ascending=False)
    corte = len(d) > 30
    if corte:
        sel = d[d[rotulo_col] == destaque]
        d = pd.concat([d.head(15), sel, d.tail(15)]).drop_duplicates().sort_values(valor_col, ascending=False)
    cores = [LARANJA if r == destaque else AZUL for r in d[rotulo_col]]
    fig = go.Figure(go.Bar(x=d[rotulo_col], y=d[valor_col], marker_color=cores,
                           hovertemplate="%{x}<br>" + titulo_valor + ": %{y:.1f}<extra></extra>"))
    linha_media(fig, ref)
    fig.update_layout(yaxis=dict(range=[0, 100], title=None, gridcolor=T.grade),
                      xaxis=dict(title=None, tickangle=-45 if len(d) > 12 else 0, type="category"),
                      margin=dict(l=10, r=10, t=20, b=10), height=320, bargap=0.25)
    return fig, corte


def histograma(valores, ref, marca=None):
    cont, bordas = np.histogram(pd.Series(valores, dtype=float).dropna(), bins=np.arange(0, 101, 10))
    fig = go.Figure(go.Bar(x=[f"{int(a)}–{int(b)}" for a, b in zip(bordas[:-1], bordas[1:])], y=cont, marker_color=AZUL,
                           hovertemplate="%{x} pontos: %{y} municípios<extra></extra>"))
    linha_media(fig, ref, horizontal=False)
    if marca is not None and not vazio(marca[1]):
        fig.add_vline(x=min(int(marca[1] // 10), 9), line_color=LARANJA, line_width=3, annotation_text=marca[0],
                      annotation_position="bottom right")
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=300, bargap=0.08, yaxis=dict(title="municípios", gridcolor=T.grade))
    return fig


def por_porte(df_sel, df_br, coluna):
    s = df_sel.groupby("porte_municipio")[coluna].mean().reindex(PORTES)
    b = df_br.groupby("porte_municipio")[coluna].mean().reindex(PORTES)
    x = [f"{p}<br>{PORTE_ROTULO[p]}" for p in PORTES]
    fig = go.Figure([go.Bar(x=x, y=s.values, name="Seleção", marker_color=AZUL, hovertemplate="%{x}: %{y:.1f}<extra>Seleção</extra>"),
                     go.Bar(x=x, y=b.values, name="Brasil", marker_color=CINZA, hovertemplate="%{x}: %{y:.1f}<extra>Brasil</extra>")])
    fig.update_layout(barmode="group", yaxis=dict(range=[0, 100], gridcolor=T.grade), margin=dict(l=10, r=10, t=10, b=10), height=300,
                      legend=dict(orientation="h", y=1.12), bargap=0.25)
    return fig


def mapa(df, destaque=None, altura=420):
    coord = dados.coordenadas()
    d = df.merge(coord[["cod_ibge", "lat", "lon"]], on="cod_ibge", how="inner")
    fig = go.Figure()
    nulos = d[d["score_global_imdm"].isna()]
    if len(nulos):
        fig.add_trace(go.Scattergeo(lat=nulos["lat"], lon=nulos["lon"], mode="markers", name="IMDM nulo",
                                    marker=dict(size=5, color=T.nulo), text=nulos["nome"], hovertemplate="%{text}: nulo<extra></extra>"))
    v = d[d["score_global_imdm"].notna()]
    if len(v):
        fig.add_trace(go.Scattergeo(
            lat=v["lat"], lon=v["lon"], mode="markers", name="IMDM",
            marker=dict(size=4 if len(v) > 1500 else 7, color=v["score_global_imdm"], cmin=0, cmax=100,
                        colorscale=[[0, NIVEL_CORES[0]], [0.5, NIVEL_CORES[2]], [1, NIVEL_CORES[4]]],
                        colorbar=dict(title="IMDM", thickness=10, len=0.6)),
            text=v["nome"] + " (" + v["uf_sigla"] + ")", hovertemplate="%{text}<br>IMDM %{marker.color:.1f}<extra></extra>"))
    if destaque is not None:
        p = d[d["cod_ibge"] == destaque]
        if len(p):
            fig.add_trace(go.Scattergeo(lat=p["lat"], lon=p["lon"], mode="markers", name="Selecionado",
                                        marker=dict(size=16, color=LARANJA, line=dict(width=2, color=T.contorno)),
                                        text=p["nome"], hovertemplate="%{text}<extra></extra>"))
    fig.update_geos(fitbounds="locations" if len(d) else False, showcountries=True, countrycolor=T.fronteira,
                    showland=True, landcolor=T.terra, showocean=False, showlakes=False, projection_type="mercator",
                    bgcolor="rgba(0,0,0,0)", showframe=False)
    if not len(d):
        fig.update_geos(lataxis_range=[-34, 6], lonaxis_range=[-75, -34])
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=altura, showlegend=False)
    return fig


def nivel_dist(df, destaque=None):
    cont = df["nivel_maturidade_mmd"].dropna().value_counts().sort_index()
    total = cont.sum()
    nomes = list(cont.index)
    cores = [LARANJA if destaque == n else NIVEL_CORES[min(max(nivel_num(n) or 1, 1), 5) - 1] for n in nomes]
    return barras_h(nomes, [c / total * 100 if total else 0 for c in cont.values], cores=cores, sufixo="%")


def selecao_nova(ev, chave):
    """Pontos clicados num gráfico — só quando a seleção mudou (evita reaplicar o mesmo clique em loop)."""
    sel = getattr(ev, "selection", None) if not isinstance(ev, dict) else ev.get("selection")
    pontos = (sel.get("points", []) if isinstance(sel, dict) else getattr(sel, "points", [])) if sel else []
    assinatura = tuple(str(p.get("x")) for p in pontos)
    if not pontos or ss.get(chave) == assinatura:
        return []
    ss[chave] = assinatura
    return pontos


# ------------------------------------------------------------------ páginas
def pagina_visao_geral():
    st.title("Visão geral")
    st.caption(f"MUNIC {ANO} · {rotulo_selecao()}")
    if SEL.empty:
        aviso_sem_municipios()
        return
    cols = st.columns(5)
    if MUN is not None:
        m = MUN
        if vazio(m["score_global_imdm"]):
            kpi(cols[0], "IMDM", "nulo", f"motivo: {texto(m['motivo_imdm_nulo'])}")
        else:
            kpi(cols[0], "IMDM do município", fmt(m["score_global_imdm"]), delta=m["score_global_imdm"] - BR_IMDM)
            kpi(cols[1], "Ranking na UF", f"{int(m['rank_uf'])}º de {int(m['total_uf'])}", m["uf_sigla"])
            kpi(cols[2], "Ranking no Brasil", f"{int(m['rank_brasil'])}º de {fmt(m['total_brasil'], 0)}",
                f"no porte: {int(m['rank_porte'])}º de {int(m['total_porte'])}")
            kpi(cols[3], "Nível de maturidade", texto(m["nivel_maturidade_mmd"]))
        resp = lgpd.loc[lgpd["cod_ibge"] == m["cod_ibge"], ["mgov32_responsavel_lgpd", "mgov33_local_responsavel"]]
        r32 = texto(resp.iloc[0, 0]) if len(resp) else "—"
        kpi(cols[4], "Responsável LGPD", r32, texto(resp.iloc[0, 1], "") if r32 == "Sim" else "")
    else:
        sel_v = SEL["score_global_imdm"]
        kpi(cols[0], "IMDM médio", fmt(sel_v.mean()), "média dos municípios válidos" if e_brasil() else "",
            delta=None if e_brasil() else sel_v.mean() - BR_IMDM)
        kpi(cols[1], "Municípios", fmt(len(SEL), 0), f"{fmt(sel_v.notna().sum(), 0)} com IMDM · {sel_v.isna().sum()} nulos")
        lg = lgpd[lgpd["cod_ibge"].isin(SEL["cod_ibge"])]
        if lg["mgov32_responsavel_lgpd"].notna().any():
            tem = lambda df: df["tem_responsavel_lgpd"].astype("boolean").fillna(False).astype(bool).mean() * 100  # noqa: E731
            kpi(cols[2], "Com responsável LGPD", fmt(tem(lg), 1, "%"), "Mgov32 = Sim" if e_brasil() else "",
                delta=None if e_brasil() else tem(lg) - tem(lgpd), sufixo_delta=" p.p. vs Brasil")
        else:
            kpi(cols[2], "Com responsável LGPD", "—", "bloco não coletado nesta edição")
        moda = SEL["nivel_maturidade_mmd"].dropna().mode()
        kpi(cols[3], "Nível mais comum", moda.iloc[0] if len(moda) else "—",
            f"{fmt((SEL['nivel_maturidade_mmd'] == moda.iloc[0]).mean() * 100, 0)}% dos municípios" if len(moda) else "")
        medias, _ = perfil_dims(SEL["cod_ibge"])
        medias = {k: v for k, v in medias.items() if not vazio(v) and k in DIM_NOME}
        if medias:
            fraca = min(medias, key=medias.get)
            kpi(cols[4], "Dimensão mais fraca", DIM_NOME[fraca], f"{fmt(medias[fraca])} pontos", pequeno=True)

    # radar + dimensões + LGPD
    sel_dims = (score[score["cod_ibge"] == FIL.mun].set_index("dimensao_codigo")["score"].to_dict() if MUN is not None
                else perfil_dims(SEL["cod_ibge"])[0])
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
        grafico(barras_h(dims["dimensao_nome"].tolist(), [sel_dims.get(c) for c in dims["dimensao_codigo"]],
                         ref=[BR_DIMS.get(c) for c in dims["dimensao_codigo"]], largura_rotulo=18), "vg_dims")
        fora = dims.loc[~dims["entra_no_imdm"].astype(bool), "dimensao_nome"].tolist()
        if fora:
            st.caption("Fora do IMDM (descritivas): " + ", ".join(fora))
    with c2:
        st.subheader("Radar de maturidade")
        grafico(radar(series), "vg_radar")
    with c3:
        st.subheader("LGPD · onde fica o responsável")
        base = lgpd[lgpd["cod_ibge"].isin((pan[pan["uf_sigla"] == MUN["uf_sigla"]] if MUN is not None else SEL)["cod_ibge"])]
        tem_resp = base["tem_responsavel_lgpd"].astype("boolean").fillna(False).astype(bool)
        loc = base.loc[tem_resp, "mgov33_local_responsavel"].dropna()
        loc = loc[~loc.isin(["Não sabe informar", "Não informou", "Recusa", "-"])]
        if len(loc):
            dist = loc.value_counts(normalize=True) * 100
            curto = {k: k.replace("Na Secretaria de Administraçõ, Finanças ou Planejamento", "Sec. Administração/ Finanças")
                         .replace("No departamento ou área de Tecnologia da Informação (TI)", "Área de TI")
                         .replace("Na Controladoria ou Corregedoria municipal", "Controladoria/ Corregedoria")
                         .replace("No gabinete do(a) Prefeito(a)", "Gabinete do prefeito")
                         .replace("No departamento jurídico ou procuradoria municipal", "Jurídico/Procuradoria")
                         .replace("Em comitê ou comissão municipal específica", "Comitê/comissão") for k in dist.index}
            local_mun = lgpd.loc[lgpd["cod_ibge"] == FIL.mun, "mgov33_local_responsavel"] if MUN is not None else pd.Series(dtype=str)
            cores = [LARANJA if len(local_mun) and k == local_mun.iloc[0] else AZUL for k in dist.index]
            grafico(barras_h([curto[k] for k in dist.index], dist.values, cores=cores, sufixo="%", largura_rotulo=16), "vg_lgpd")
            st.caption(f"Mgov33 (não pontua) · base: {fmt(len(loc), 0)} municípios com responsável"
                       + (f" de {MUN['uf_sigla']}" if MUN is not None else ""))
        elif lgpd["mgov32_responsavel_lgpd"].notna().any():
            st.info("Nenhum município da seleção declarou responsável pela LGPD.")
        else:
            st.info("Bloco de LGPD não coletado nesta edição.")

    # ranking, distribuição e porte
    c1, c2, c3 = st.columns([1.4, 1, 1])
    with c1:
        if MUN is not None or FIL.uf != "Todas":
            uf = MUN["uf_sigla"] if MUN is not None else FIL.uf
            base = pan[(pan["uf_sigla"] == uf) & pan["score_global_imdm"].notna()]
            if FIL.porte != "Todos":
                base = base[base["porte_municipio"] == FIL.porte]
            st.subheader(f"IMDM por município · {uf}")
            fig, corte = ranking(base, "nome", "score_global_imdm", BR_IMDM, "IMDM",
                                 destaque=MUN["nome"] if MUN is not None else None)
        else:
            base = area(pan).groupby("uf_sigla", as_index=False)["score_global_imdm"].mean()
            st.subheader("IMDM médio por UF" + (f" · {FIL.regiao}" if FIL.regiao != "Todas" else ""))
            fig, corte = ranking(base, "uf_sigla", "score_global_imdm", BR_IMDM, "IMDM médio")
        ev = grafico(fig, "rank_vg", on_select="rerun", selection_mode="points")
        st.caption("Clique numa barra para filtrar · tracejado = média Brasil" + (" · 15 maiores e 15 menores" if corte else ""))
        pontos = selecao_nova(ev, "_ult_rank_vg")
        if pontos:
            x = pontos[0].get("x")
            if MUN is None and FIL.uf == "Todas" and x in set(pan["uf_sigla"]):
                pedir(uf=x)
                st.rerun()
            elif "nome" in base.columns and x in set(base["nome"]):
                cod = base.loc[base["nome"] == x, "cod_ibge"].iloc[0]
                if cod != FIL.mun:
                    pedir(mun=cod, uf=base.loc[base["nome"] == x, "uf_sigla"].iloc[0])
                    st.rerun()
    with c2:
        st.subheader("Distribuição do IMDM")
        hist_base = pan[pan["uf_sigla"] == MUN["uf_sigla"]] if MUN is not None else SEL
        marca = (MUN["nome"], MUN["score_global_imdm"]) if MUN is not None else None
        grafico(histograma(hist_base["score_global_imdm"], BR_IMDM, marca), "vg_hist")
        st.caption(f"Municípios {'de ' + MUN['uf_sigla'] if MUN is not None else 'da seleção'} por faixa de 10 pontos")
    with c3:
        st.subheader("IMDM por porte")
        grafico(por_porte(area(pan) if MUN is None else pan[pan["uf_sigla"] == MUN["uf_sigla"]], pan, "score_global_imdm"), "vg_porte")
        st.caption("O índice acompanha o porte — compare dentro da mesma faixa")

    # mapa, níveis e tabela
    c1, c2, c3 = st.columns([1.3, 1, 1.2])
    with c1:
        st.subheader("Mapa do IMDM")
        mapa_df = pan[pan["uf_sigla"] == MUN["uf_sigla"]] if MUN is not None else area(pan)
        grafico(mapa(mapa_df, FIL.mun), "vg_mapa")
    with c2:
        st.subheader("Níveis de maturidade")
        nb = pan[pan["uf_sigla"] == MUN["uf_sigla"]] if MUN is not None else SEL
        grafico(nivel_dist(nb, MUN["nivel_maturidade_mmd"] if MUN is not None else None), "vg_niveis")
    with c3:
        st.subheader("Maiores e menores IMDM")
        t = (pan[pan["uf_sigla"] == MUN["uf_sigla"]] if MUN is not None else SEL).dropna(subset=["score_global_imdm"])
        t = t.sort_values("score_global_imdm", ascending=False)
        t = pd.concat([t.head(5), t.tail(5)]) if len(t) > 10 else t
        tab = t[["cod_ibge", "nome", "uf_sigla", "score_global_imdm", "nivel_maturidade_mmd"]].rename(
            columns={"nome": "Município", "uf_sigla": "UF", "score_global_imdm": "IMDM", "nivel_maturidade_mmd": "Nível"})
        tab = tab.reset_index(drop=True)
        if tab.empty:
            st.info("Nenhum município com IMDM válido na seleção.")
            return
        ev = st.dataframe(tab.drop(columns="cod_ibge"), hide_index=True, width="stretch", on_select="rerun",
                          selection_mode="single-row", key="tab_vg", column_config={"IMDM": st.column_config.NumberColumn(format="%.1f")})
        st.caption("Clique numa linha para abrir o perfil do município")
        linhas = ev.selection.rows if hasattr(ev, "selection") else []
        if linhas and linhas[0] < len(tab):
            escolhido = tab.iloc[linhas[0]]
            pedir(mun=escolhido["cod_ibge"], uf=escolhido["UF"])
            st.switch_page(PAG_PERFIL)


def pagina_perfil():
    st.title("Perfil do município")
    if MUN is None:
        st.info("Escolha um município no filtro **Município** da barra lateral, numa barra do ranking ou numa linha da tabela da Visão geral.")
        sug = area(pan).dropna(subset=["score_global_imdm"]).nlargest(12, "populacao_total")
        if sug.empty:
            aviso_sem_municipios()
            return
        cols = st.columns(4)
        for i, r in enumerate(sug.itertuples()):
            if cols[i % 4].button(f"{r.nome} ({r.uf_sigla})", key=f"sug{r.cod_ibge}", width="stretch"):
                pedir(mun=r.cod_ibge, uf=r.uf_sigla)
                st.rerun()
        return
    m = MUN
    st.caption(f"{m['uf_sigla']} · {m['regiao']} · {m['porte_municipio']} ({PORTE_ROTULO.get(m['porte_municipio'], '')}) · "
               f"{fmt(m['populacao_total'], 0)} habitantes · IBGE {m['cod_ibge']} · MUNIC {ANO}")
    st.header(f"{m['nome']} ({m['uf_sigla']})")
    c = st.columns(6)
    nulo = vazio(m["score_global_imdm"])
    kpi(c[0], "IMDM", "nulo" if nulo else fmt(m["score_global_imdm"]), delta=None if nulo else m["score_global_imdm"] - BR_IMDM)
    kpi(c[1], "Nível", "—" if nulo else texto(m["nivel_maturidade_mmd"]), pequeno=True)
    kpi(c[2], "Ranking UF", "—" if nulo else f"{int(m['rank_uf'])}º de {int(m['total_uf'])}")
    kpi(c[3], "Ranking Brasil", "—" if nulo else f"{int(m['rank_brasil'])}º", "" if nulo else f"de {fmt(m['total_brasil'], 0)}")
    kpi(c[4], "Ranking no porte", "—" if nulo else f"{int(m['rank_porte'])}º de {int(m['total_porte'])}", m["porte_municipio"])
    outras = painel_all[(painel_all["cod_ibge"] == m["cod_ibge"]) & (painel_all["ano_edicao"] != ANO)].sort_values("ano_edicao")
    outras = outras[outras["score_global_imdm"].notna()]
    if len(outras) and not nulo:
        o = outras.iloc[-1]
        kpi(c[5], f"IMDM {int(o['ano_edicao'])}", fmt(o["score_global_imdm"]), "radares podem diferir",
            delta=m["score_global_imdm"] - o["score_global_imdm"], sufixo_delta=f" até {ANO}" if ANO > o["ano_edicao"] else f" desde {ANO}")
    else:
        kpi(c[5], "Outras edições", "—", "sem IMDM em outra edição")
    if nulo:
        st.warning(f"IMDM nulo nesta edição: {texto(m['motivo_imdm_nulo'])}.")

    uf_df = pan[pan["uf_sigla"] == m["uf_sigla"]]
    mun_dims = score[score["cod_ibge"] == m["cod_ibge"]].set_index("dimensao_codigo")["score"].to_dict()
    itens = dados.itens_do_municipio(m["cod_ibge"], ANO, FIL.radar)
    ado = dados.adocao_uf_porte(ANO, FIL.radar)
    ado_uf = ado[ado["uf_sigla"] == m["uf_sigla"]].groupby("item")[["soma_pontos", "soma_peso"]].sum()
    ado_porte = ado[ado["porte_municipio"] == m["porte_municipio"]].groupby("item")[["soma_pontos", "soma_peso"]].sum()
    pct_uf = dict(zip(ado_uf.index, pct(ado_uf["soma_pontos"], ado_uf["soma_peso"])))
    pct_porte = dict(zip(ado_porte.index, pct(ado_porte["soma_pontos"], ado_porte["soma_peso"])))

    c1, c2, c3 = st.columns([1, 1.4, 1])
    with c1:
        st.subheader("Lacunas e destaques")
        st.caption(f"Comparado aos municípios do mesmo porte ({m['porte_municipio']})")
        if len(itens):
            it = itens.assign(porte=pd.to_numeric(itens["item"].map(pct_porte), errors="coerce"))
            lac = it[it["status_item"].isin(["Não", "Salto (0)"]) & (it["porte"] >= 50)].nlargest(7, "porte")
            dst = it[(it["status_item"] == "Sim") & (it["porte"] < 35)].nsmallest(6, "porte")
            st.markdown("**O que falta e a maioria do porte já tem**")
            st.markdown("\n".join(f"- **{r.item}** · {r.dimensao_nome} · {fmt(r.porte, 0)}% do porte tem" for r in lac.itertuples())
                        or "_Nenhuma lacuna relevante._")
            st.markdown("**Destaques (tem, mas é raro no porte)**")
            st.markdown("\n".join(f"- **{r.item}** · só {fmt(r.porte, 0)}% do porte tem" for r in dst.itertuples())
                        or "_Nenhum destaque raro._")
        else:
            st.info("Sem itens do radar para este município nesta edição.")
    with c2:
        st.subheader("Radar do município")
        grafico(radar([dict(nome=m["nome"], valores=mun_dims, cor=AZUL, fill=AZUL_SOFT, principal=True),
                       dict(nome=m["uf_sigla"], valores=perfil_dims(uf_df["cod_ibge"])[0], cor=LARANJA, fill=LARANJA_SOFT),
                       dict(nome="Brasil", valores=BR_DIMS, cor=CINZA, dash="dash")]), "pf_radar")
    with c3:
        st.subheader(f"Localização · {m['uf_sigla']}")
        grafico(mapa(uf_df, m["cod_ibge"], altura=380), "pf_mapa")

    st.subheader(f"Os {len(itens)} itens do radar {ANO}")
    st.caption("Resposta do município em cada item · à direita, % de adoção na UF e no mesmo porte (Parcial conta pela fração)")
    for d in dims.itertuples():
        di = itens[itens["dimensao_codigo"] == d.dimensao_codigo] if len(itens) else itens
        if di.empty:
            continue
        sim = (di["status_item"] == "Sim").sum()
        with st.expander(f"{d.dimensao_ordem}. {d.dimensao_nome} — score {fmt(mun_dims.get(d.dimensao_codigo))} · {sim} de {len(di)} itens completos",
                         expanded=d.Index == 0):
            col_uf = f"% {m['uf_sigla']}"
            tab = pd.DataFrame({
                "Status": di["status_item"].map(lambda s: STATUS_ICONE.get(s, s)),
                "Item": di["item"],
                col_uf: pd.to_numeric(di["item"].map(pct_uf), errors="coerce"),
                "% porte": pd.to_numeric(di["item"].map(pct_porte), errors="coerce"),
                "Resposta (IBGE)": di["resposta_original"],
                "Código": di["variavel_ancora"],
                "Descrição": di["item_descricao"],
            })
            st.dataframe(tab, hide_index=True, width="stretch", key=f"pf_itens_{d.dimensao_codigo}", column_config={
                col_uf: st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
                "% porte": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100)})


def pagina_dimensoes():
    st.title("Dimensões")
    st.caption(f"MUNIC {ANO} · {rotulo_area()}")
    if dims.empty:
        st.warning(f"O radar de {ANO} não tem dimensões carregadas.")
        return
    cods = dims["dimensao_codigo"].tolist()
    garantir("f_dim", cods, cods[0])
    dim = st.segmented_control("Dimensão", cods, format_func=lambda c: DIM_NOME.get(c, c), key="f_dim", required=True) or cods[0]
    d = dims.set_index("dimensao_codigo").loc[dim]
    area_pan = area(pan)
    if area_pan.empty:
        aviso_sem_municipios()
        return
    validos = area_pan.loc[area_pan["score_global_imdm"].notna(), "cod_ibge"]
    sd = score[score["dimensao_codigo"] == dim]
    sd_sel = sd[sd["cod_ibge"].isin(validos)]
    sd_br = sd[sd["cod_ibge"].isin(pan.loc[pan["score_global_imdm"].notna(), "cod_ibge"])]
    br_media = sd_br["score"].mean()

    ado = dados.adocao_uf_porte(ANO, FIL.radar)
    ado = ado[ado["dimensao_codigo"] == dim]
    a_sel = area(ado)
    g_sel = a_sel.groupby("item")[["soma_pontos", "soma_peso"]].sum()
    g_br = ado.groupby("item")[["soma_pontos", "soma_peso"]].sum()
    p_sel = pd.Series(pct(g_sel["soma_pontos"], g_sel["soma_peso"]), index=g_sel.index).dropna().sort_values(ascending=False)
    p_br = pd.Series(pct(g_br["soma_pontos"], g_br["soma_peso"]), index=g_br.index)

    c = st.columns(4)
    kpi(c[0], f"Score médio · {d['dimensao_nome']}", fmt(sd_sel["score"].mean()),
        delta=None if e_brasil() else sd_sel["score"].mean() - br_media, pequeno=len(str(d["dimensao_nome"])) > 30)
    kpi(c[1], "Municípios com score ≥ 50", fmt((sd_sel["score"] >= 50).mean() * 100 if len(sd_sel) else None, 1, "%"),
        "" if e_brasil() else f"Brasil {fmt((sd_br['score'] >= 50).mean() * 100 if len(sd_br) else None, 1, '%')}")
    if len(p_sel):
        kpi(c[2], "Item mais adotado", p_sel.index[0], fmt(p_sel.iloc[0], 0, "% de adoção"), pequeno=True)
        kpi(c[3], "Item menos adotado", p_sel.index[-1], fmt(p_sel.iloc[-1], 0, "% de adoção"), pequeno=True)
    st.caption(f"Peso da dimensão: {fmt(d['dimensao_peso'], 0)} · {'entra' if bool(d['entra_no_imdm']) else 'não entra'} no IMDM · "
               f"{len(p_br)} itens" + (f" · {d['descricao']}" if not vazio(d["descricao"]) else ""))

    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.subheader(f"Adoção dos itens ({len(p_sel)})")
        st.caption("% de adoção na seleção · traço = Brasil · Parcial conta pela fração")
        if len(p_sel):
            grafico(barras_h(list(p_sel.index), p_sel.values, ref=[p_br.get(i) for i in p_sel.index], sufixo="%"), "dm_itens")
        else:
            st.info("Sem itens pontuados nesta seleção.")
    with c2:
        if FIL.uf != "Todas":
            base = sd_sel[["cod_ibge", "nome", "score"]]
            st.subheader(f"Score por município · {FIL.uf}")
            fig, _ = ranking(base, "nome", "score", br_media, "Score")
        else:
            base = sd_sel.groupby("uf_sigla", as_index=False)["score"].mean()
            st.subheader("Score médio por UF")
            fig, _ = ranking(base, "uf_sigla", "score", br_media, "Score médio")
        grafico(fig, "dm_rank")
        st.subheader("Distribuição do score")
        grafico(histograma(sd_sel["score"], br_media), "dm_hist")
    st.subheader("Score por porte")
    grafico(por_porte(sd_sel, sd_br, "score"), "dm_porte")


def pagina_qualidade():
    st.title("Qualidade dos dados")
    st.caption(f"MUNIC {ANO} · {rotulo_area()} · respostas das variáveis do radar")
    sel = area(pan)
    if sel.empty:
        aviso_sem_municipios()
        return
    q = qual_all[qual_all["ano_edicao"] == ANO]
    if FIL.regiao != "Todas":
        q = q[q["regiao"] == FIL.regiao]
    if FIL.uf != "Todas":
        q = q[q["uf_sigla"] == FIL.uf]
    tot = q[["respostas", "validas", "nao_sabe", "nao_informou", "salto_logico", "recusa"]].sum()
    nulos = sel["motivo_imdm_nulo"].dropna().value_counts()
    c = st.columns(5)
    kpi(c[0], "Municípios", fmt(len(sel), 0))
    kpi(c[1], "Com IMDM válido", fmt(sel["score_global_imdm"].notna().sum(), 0),
        fmt(sel["score_global_imdm"].notna().mean() * 100, 1, "% da seleção"))
    kpi(c[2], "IMDM nulo", fmt(sel["score_global_imdm"].isna().sum(), 0),
        " · ".join(f"{k}: {v}" for k, v in nulos.items()) or "nenhum")
    kpi(c[3], "Respostas “Não sabe”", fmt(pct(tot["nao_sabe"], tot["respostas"]), 2, "%"),
        f"{fmt(tot['nao_sabe'], 0)} de {fmt(tot['respostas'], 0)} respostas")
    kpi(c[4], "Saltos lógicos (“-”)", fmt(pct(tot["salto_logico"], tot["respostas"]), 1, "%"), "valem 0 no cálculo")
    if FIL.porte != "Todos":
        st.caption("O filtro de porte não se aplica às contagens por variável (agregadas por UF).")

    sem_nao_sabe = tot["nao_sabe"] == 0
    c1, c2, c3 = st.columns([1.2, 1, 1.2])
    with c1:
        st.subheader("“Não sabe” por variável")
        if sem_nao_sabe:
            st.info(f"Nenhuma resposta “Não sabe informar” nas variáveis do radar {ANO}"
                    + ("" if e_brasil() else " nesta seleção") + ".")
        else:
            g = q.groupby(["cod_variable", "item"])[["nao_sabe", "respostas"]].sum()
            g = pd.Series(pct(g["nao_sabe"], g["respostas"]), index=g.index).sort_values(ascending=False)
            g = g[g > 0].head(10)
            grafico(barras_h([f"{v} · {i}" for v, i in g.index], g.values, maximo=max(5, g.max()), sufixo="%"), "ql_var")
    with c2:
        st.subheader("IMDM nulo por motivo")
        if len(nulos):
            grafico(barras_h(list(nulos.index), nulos.values, maximo=max(nulos.max(), 1)), "ql_nulos")
        else:
            st.success("Nenhum município com IMDM nulo na seleção.")
    with c3:
        st.subheader("“Não sabe” por UF")
        if sem_nao_sabe:
            st.info("Sem respostas “Não sabe” para comparar entre UFs.")
        else:
            u = q.groupby("uf_sigla")[["nao_sabe", "respostas"]].sum()
            u = pd.Series(pct(u["nao_sabe"], u["respostas"]), index=u.index).sort_values(ascending=False).head(15)
            grafico(barras_h(list(u.index), u.values, maximo=max(1, u.max()), sufixo="%"), "ql_uf")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Regras de tratamento")
        st.dataframe(pd.DataFrame([
            ("Sim", "1 ponto"), ("Não", "0"), ("“-” (salto lógico)", "0"), ("Não sabe informar / Não informou", "0, com peso"),
            ("Não se aplica (exceção da LAI)", "sai do denominador"), ("Escalonados e escadas", "pontos da planilha do radar"),
            ("Grupos do portal", "fração de “Sim”"), ("Recusa", "IMDM nulo"),
            ("Dimensão do IMDM sem item válido", "IMDM nulo"),
            ("IMDM", "média ponderada das dimensões do radar do ano"),
        ], columns=["Resposta", "Tratamento"]), hide_index=True, width="stretch", key="ql_regras")
    with c2:
        st.subheader(f"Radar {FIL.radar} em cada edição")
        r = radar_all.sort_values(["ano_edicao", "dimensao_ordem"], ascending=[False, True])
        st.dataframe(r[["ano_edicao", "dimensao_ordem", "dimensao_nome", "dimensao_peso", "entra_no_imdm"]].rename(columns={
            "ano_edicao": "Edição", "dimensao_ordem": "Ordem", "dimensao_nome": "Dimensão", "dimensao_peso": "Peso",
            "entra_no_imdm": "Entra no IMDM"}), hide_index=True, width="stretch", key="ql_radar")
        st.caption("Definido pelo especialista em config/radar/radar_imdm.xlsx; validado e versionado no pipeline.")
        if len(RADARES) > 1:
            st.markdown("**Radares cadastrados**")
            st.dataframe(RADARES[["radar", "nome", "descricao", "padrao"]].rename(columns={
                "radar": "Radar", "nome": "Nome", "descricao": "Descrição", "padrao": "Padrão"}),
                hide_index=True, width="stretch", key="ql_radares")


if _PAGINA_TESTE:
    {"visao": pagina_visao_geral, "perfil": pagina_perfil, "dimensoes": pagina_dimensoes, "qualidade": pagina_qualidade}[_PAGINA_TESTE]()
else:
    NAV.run()
