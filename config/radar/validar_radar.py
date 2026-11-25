"""Valida os radares IMDM (planilha do especialista) e gera os CSVs que o pipeline lê.

Um RADAR é uma metodologia completa (ex.: 'A', 'B') e define TODAS as edições da
MUNIC. Dentro de um radar, cada edição tem o seu desenho (dimensões, itens e códigos
do IBGE daquele ano). As abas são fixas e cada linha diz a que radar e a que edição
pertence (colunas `radar` e `edicao`). Radar novo ou ano novo = linhas novas, nunca
aba nova nem código novo.

Uso, na raiz do repositório:
    python config/radar/validar_radar.py
    python config/radar/validar_radar.py --dados 2024=Base_MUNIC_2024_20251107.xlsx --dados 2019=Base_MUNIC_2019.xlsx
    (cada radar é validado em cada edição; todo radar precisa ter todas as edições)

Sem ERRO, os CSVs em config/radar/csv/ são regravados e entram no mesmo commit da
planilha. O notebook pipeline/load_radar_config importa este módulo e roda as MESMAS
regras sobre os CSVs (e contra a silver da edição) antes de gravar as tabelas
config.radar_*. Uma regra de validação vive só aqui.

Dependências: pandas (sempre) e openpyxl (só para ler a planilha .xlsx).
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
XLSX_PADRAO = AQUI / "radar_imdm.xlsx"
CSV_DIR_PADRAO = AQUI / "csv"

# Abas editadas pelo especialista -> CSV gerado
ABAS = {"Radares": "radares.csv", "Dimensoes": "dimensoes.csv", "Itens": "itens.csv", "Niveis": "niveis.csv"}
ABAS_DEFINICAO = ("Dimensoes", "Itens", "Niveis")   # as que têm radar × edição
COLUNAS = {
    "Radares": ["radar", "nome", "descricao", "padrao"],
    "Dimensoes": ["radar", "edicao", "dimensao", "ordem", "peso", "entra_no_imdm", "descricao"],
    "Itens": ["radar", "edicao", "dimensao", "item", "descricao", "variaveis", "regra", "pontuacao", "excecao"],
    "Niveis": ["radar", "edicao", "nivel", "nome", "minimo", "maximo"],
}
RE_RADAR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,19}$")

# Vocabulário fechado: o que o código do pipeline sabe calcular.
# Regra nova = mudança no código (decisão técnica), não na planilha.
REGRAS = {
    "SIM_POSITIVO": "1 variável; 'Sim' = 1, demais respostas = 0. Pontuação vazia.",
    "CATEGORICO_ESCALONADO": "1 variável: pontuação por resposta (Ativa=1; ...). "
                             "Várias variáveis (formato de publicação): pontuação por variável marcada 'Sim' "
                             "(mgov0711=1; mgov0712=0,5; ...), vale a maior.",
    "ESCADA_MAIOR_NIVEL": "Várias variáveis; pontuação por variável marcada 'Sim'; vale a maior.",
    "GRUPO_PROPORCIONAL": "Várias variáveis; fração de 'Sim' no grupo (0 a 1). Pontuação vazia.",
}
EXCECOES = {
    "": "sem exceção",
    "NAO_SE_APLICA_SEM_PEDIDO_LAI": "mgov05: 'Não publica' + mgov04 = 'Não' sai do denominador",
}
SIM_NAO = {"sim", "nao"}
RE_VARIAVEL = re.compile(r"^(mtic|mgov)[0-9a-z]+$")
# Estados da MUNIC com tratamento próprio no pipeline (não precisam de pontuação)
ESTADOS_ESPECIAIS = {"-", "Não sabe informar", "Não informou", "Recusa", "Não se aplica"}


# --------------------------------------------------------------------------- leitura
def _normalizar(df: pd.DataFrame, aba: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    faltando = [c for c in COLUNAS[aba] if c not in df.columns]
    if faltando:
        raise ValueError(f"Aba '{aba}': colunas obrigatórias ausentes {faltando} (não renomeie as colunas)")
    df = df[COLUNAS[aba]].astype(str).apply(lambda s: s.str.strip())
    df = df.replace({"nan": "", "None": ""})
    df = df[(df != "").any(axis=1)].reset_index(drop=True)
    df.insert(0, "linha_planilha", df.index + 2)   # nº da linha no Excel, para as mensagens
    return df


def ler_planilha(caminho: Path | str = XLSX_PADRAO) -> dict[str, pd.DataFrame]:
    abas = pd.read_excel(caminho, sheet_name=list(ABAS), dtype=str, keep_default_na=False)
    return {aba: _normalizar(df, aba) for aba, df in abas.items()}


def ler_csvs(pasta: Path | str = CSV_DIR_PADRAO) -> dict[str, pd.DataFrame]:
    pasta = Path(pasta)
    return {aba: _normalizar(pd.read_csv(pasta / arq, dtype=str, keep_default_na=False), aba)
            for aba, arq in ABAS.items()}


def variaveis(texto: str) -> list[str]:
    return [v.strip().lower() for v in re.split(r"[;,\s]+", str(texto)) if v.strip()]


def numero(texto) -> float | None:
    try:
        return float(str(texto).replace(",", ".").strip())
    except ValueError:
        return None


def ler_pontuacao(texto: str) -> tuple[dict[str, float], list[str]]:
    """'Ativa=1; Em manutenção=0,5' -> ({'Ativa': 1.0, 'Em manutenção': 0.5}, erros)."""
    pares, erros = {}, []
    for parte in [p for p in str(texto).split(";") if p.strip()]:
        if "=" not in parte:
            erros.append(f"trecho sem '=': '{parte.strip()}'")
            continue
        chave, valor = parte.rsplit("=", 1)
        chave, pts = chave.strip(), numero(valor)
        if not chave:
            erros.append(f"trecho sem resposta antes do '=': '{parte.strip()}'")
        elif pts is None:
            erros.append(f"pontos não numéricos em '{parte.strip()}'")
        elif not 0 <= pts <= 1:
            erros.append(f"pontos fora de 0 a 1 em '{parte.strip()}'")
        elif chave in pares:
            erros.append(f"resposta repetida '{chave}'")
        else:
            pares[chave] = pts
    return pares, erros


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower().strip()


def codigo_dimensao(nome: str) -> str:
    """Código estável derivado do nome (ex.: 'Serviços digitais' -> 'servicos_digitais')."""
    return re.sub(r"[^a-z0-9]+", "_", _sem_acento(nome)).strip("_")


def edicoes(cat: dict[str, pd.DataFrame]) -> list[int]:
    """Edições que aparecem em algum radar (todo radar precisa ter todas)."""
    anos = set()
    for aba in ABAS_DEFINICAO:
        for e in cat[aba]["edicao"]:
            if re.fullmatch(r"\d{4}", e):
                anos.add(int(e))
    return sorted(anos)


def radares(cat: dict[str, pd.DataFrame]) -> list[str]:
    """Radares cadastrados na aba Radares, na ordem da planilha."""
    return [r for r in cat["Radares"]["radar"] if r]


def radar_padrao(cat: dict[str, pd.DataFrame]) -> str | None:
    p = cat["Radares"][cat["Radares"]["padrao"].str.lower() == "sim"]["radar"]
    return p.iloc[0] if len(p) == 1 else None


# --------------------------------------------------------------------------- dados do IBGE
def perfil_xlsx_munic(caminho: Path | str) -> dict:
    """Base MUNIC (.xlsx do IBGE) -> {'colunas': set, 'valores': {col: set}}."""
    abas = pd.read_excel(caminho, sheet_name=None, dtype=str)
    colunas, valores = set(), {}
    for nome, df in abas.items():
        if "dicion" in nome.lower():
            continue
        for c in df.columns:
            cl = str(c).strip().lower()
            if cl.startswith(("mtic", "mgov")) and df[c].notna().any():
                colunas.add(cl)
                valores.setdefault(cl, set()).update(df[c].dropna().astype(str).str.strip())
    return {"colunas": colunas, "valores": valores}


# --------------------------------------------------------------------------- validação
def validar(cat: dict[str, pd.DataFrame], dados: dict[int, dict] | None = None,
            so_edicao: int | None = None) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). Qualquer erro bloqueia a exportação e a carga.

    dados: opcional, {edicao: {'colunas': set, 'valores': {col: set}}} com o que existe
    na base daquela edição (XLSX do IBGE localmente ou silver no Databricks).
    so_edicao: valida só essa edição, em todos os radares (o notebook usa a edição do job).
    """
    erros: list[str] = []
    avisos: list[str] = []
    dims, itens, niveis = cat["Dimensoes"], cat["Itens"], cat["Niveis"]

    # ---- aba Radares
    cad = cat["Radares"]
    codigos_radar = list(cad["radar"])
    if cad.empty:
        erros.append("Radares: nenhum radar cadastrado (a aba Radares precisa de pelo menos uma linha)")
    for r in cad.itertuples():
        onde = f"Radares linha {r.linha_planilha}"
        if not RE_RADAR.match(r.radar):
            erros.append(f"{onde}: código do radar '{r.radar}' inválido (use letras, números, '-' ou '_', até 20 caracteres; ex.: A, B, LGPD2)")
        if not r.nome:
            erros.append(f"{onde}: radar '{r.radar}' sem nome")
        if r.padrao.lower() not in SIM_NAO:
            erros.append(f"{onde}: padrao deve ser 'sim' ou 'nao' (está '{r.padrao}')")
    for n in sorted({c for c in codigos_radar if c and codigos_radar.count(c) > 1}):
        erros.append(f"Radares: o radar '{n}' está cadastrado mais de uma vez")
    n_padrao = int((cad["padrao"].str.lower() == "sim").sum())
    if not cad.empty and n_padrao != 1:
        erros.append(f"Radares: exatamente um radar deve ter padrao = sim (encontrados: {n_padrao})")
    cadastrados = set(codigos_radar)

    # ---- toda linha: radar cadastrado e edição = ano
    for aba in ABAS_DEFINICAO:
        for r in cat[aba].itertuples():
            if not re.fullmatch(r"\d{4}", r.edicao):
                erros.append(f"{aba} linha {r.linha_planilha}: edição '{r.edicao}' não é um ano (ex.: 2024)")
            if r.radar not in cadastrados:
                por_minuscula = {c.lower(): c for c in cadastrados}
                sugestao = ([por_minuscula[r.radar.lower()]] if r.radar.lower() in por_minuscula
                            else difflib.get_close_matches(r.radar, list(cadastrados), n=1, cutoff=0.5))
                dica = f" — você quis dizer '{sugestao[0]}'?" if sugestao else " (cadastre-o na aba Radares)"
                erros.append(f"{aba} linha {r.linha_planilha}: radar '{r.radar}' não está na aba Radares{dica}")

    # ---- todo radar tem TODAS as edições (um radar é um pacote completo, nunca só um ano)
    anos_todos = edicoes(cat)
    anos = anos_todos if so_edicao is None else [so_edicao]
    rads = [r for r in codigos_radar if r in cadastrados and RE_RADAR.match(r)]
    rads = list(dict.fromkeys(rads))
    for rad in rads:
        for aba in ABAS_DEFINICAO:
            tem = {int(e) for e in cat[aba].loc[cat[aba]["radar"] == rad, "edicao"] if re.fullmatch(r"\d{4}", e)}
            faltam = sorted(set(anos_todos) - tem)
            if not tem:
                erros.append(f"Radar {rad}: nenhuma linha na aba {aba}")
            elif faltam:
                erros.append(f"Radar {rad}: faltam as edições {faltam} na aba {aba} "
                             f"(todo radar precisa ter todas as edições: {anos_todos})")

    for rad in rads:
        for ano in anos:
            e = str(ano)
            rot = f"Radar {rad}, {ano}"
            d = dims[(dims["radar"] == rad) & (dims["edicao"] == e)]
            it = itens[(itens["radar"] == rad) & (itens["edicao"] == e)]
            nv = niveis[(niveis["radar"] == rad) & (niveis["edicao"] == e)]

            if d.empty:
                erros.append(f"{rot}: nenhuma dimensão na aba Dimensoes")
            if it.empty:
                erros.append(f"{rot}: nenhum item na aba Itens")
            if nv.empty:
                erros.append(f"{rot}: nenhuma faixa de maturidade na aba Niveis")

            # ---- dimensões do ano
            nomes = []
            for r in d.itertuples():
                onde = f"{rot}, Dimensoes linha {r.linha_planilha}"
                if not r.dimensao:
                    erros.append(f"{onde}: nome da dimensão vazio")
                nomes.append(r.dimensao)
                if numero(r.peso) is None or numero(r.peso) <= 0:
                    erros.append(f"{onde}: peso '{r.peso}' deve ser número maior que 0")
                if r.entra_no_imdm.lower() not in SIM_NAO:
                    erros.append(f"{onde}: entra_no_imdm deve ser 'sim' ou 'nao' (está '{r.entra_no_imdm}')")
            repetidas = sorted({n for n in nomes if n and nomes.count(n) > 1})
            if repetidas:
                erros.append(f"{rot}: dimensão declarada mais de uma vez {repetidas}")
            codigos = {}
            for n in set(nomes):
                if n:
                    codigos.setdefault(codigo_dimensao(n), []).append(n)
            for cod, ns in codigos.items():
                if len(ns) > 1:
                    erros.append(f"{rot}: dimensões com nomes que só diferem em acento/maiúscula {sorted(ns)}")
            ordens = [r.ordem for r in d.itertuples()]
            if any(not re.fullmatch(r"\d+", o) for o in ordens):
                erros.append(f"{rot}: 'ordem' das dimensões deve ser número inteiro (encontrado: {', '.join(ordens)})")
            elif ordens and sorted(int(o) for o in ordens) != list(range(1, len(ordens) + 1)):
                erros.append(f"{rot}: a ordem das dimensões deve ser 1, 2, 3… sem buracos nem repetições "
                             f"(encontrado: {', '.join(sorted(ordens, key=int))})")
            if not d.empty and not (d["entra_no_imdm"].str.lower() == "sim").any():
                erros.append(f"{rot}: nenhuma dimensão entra no IMDM")
            validas = set(nomes)

            # ---- itens do ano
            nomes_itens = list(it["item"])
            for n in sorted({n for n in nomes_itens if n and nomes_itens.count(n) > 1}):
                erros.append(f"{rot}: item '{n}' aparece mais de uma vez")
            dono: dict[str, str] = {}
            itens_por_dim = {n: 0 for n in validas}
            for r in it.itertuples():
                onde = f"{rot}, Itens linha {r.linha_planilha} ('{r.item or 'sem nome'}')"
                if not r.item:
                    erros.append(f"{onde}: nome do item vazio")
                if r.dimensao not in validas:
                    sugestao = difflib.get_close_matches(r.dimensao, list(validas), n=1, cutoff=0.6)
                    dica = f" — você quis dizer '{sugestao[0]}'?" if sugestao else f" (dimensões do Radar {rad} em {ano}: {sorted(validas)})"
                    erros.append(f"{onde}: usa a dimensão '{r.dimensao}', que não existe no Radar {rad} em {ano}{dica}")
                else:
                    itens_por_dim[r.dimensao] += 1
                vs = variaveis(r.variaveis)
                if not vs:
                    erros.append(f"{onde}: sem códigos do IBGE na coluna variaveis")
                for v in vs:
                    if not RE_VARIAVEL.match(v):
                        erros.append(f"{onde}: código '{v}' fora do padrão do IBGE (mtic…/mgov…)")
                    if v in dono:
                        erros.append(f"{onde}: a variável {v} já está no item '{dono[v]}'")
                    dono[v] = r.item
                if r.regra not in REGRAS:
                    erros.append(f"{onde}: regra '{r.regra}' não existe (use: {', '.join(REGRAS)})")
                    continue
                if r.excecao not in EXCECOES:
                    erros.append(f"{onde}: exceção '{r.excecao}' não existe")
                pts, errs = ler_pontuacao(r.pontuacao)
                erros += [f"{onde}: pontuação — {x}" for x in errs]
                if r.regra in ("SIM_POSITIVO", "GRUPO_PROPORCIONAL"):
                    if r.regra == "SIM_POSITIVO" and len(vs) != 1:
                        erros.append(f"{onde}: SIM_POSITIVO usa exatamente 1 variável (tem {len(vs)})")
                    if r.regra == "GRUPO_PROPORCIONAL" and len(vs) < 2:
                        erros.append(f"{onde}: GRUPO_PROPORCIONAL precisa de 2 ou mais variáveis")
                    if r.pontuacao:
                        avisos.append(f"{onde}: regra {r.regra} não usa a coluna pontuacao (será ignorada)")
                else:
                    if not pts and not errs:
                        erros.append(f"{onde}: regra {r.regra} exige a coluna pontuacao preenchida")
                    if r.regra == "ESCADA_MAIOR_NIVEL" and len(vs) < 2:
                        erros.append(f"{onde}: ESCADA_MAIOR_NIVEL precisa de 2 ou mais variáveis")
                    if len(vs) > 1 and pts:
                        chaves = {k.lower() for k in pts}
                        if chaves != set(vs):
                            erros.append(f"{onde}: com várias variáveis, a pontuação deve listar cada variável do item "
                                         f"(faltam {sorted(set(vs) - chaves)}, sobram {sorted(chaves - set(vs))})")
                if r.excecao == "NAO_SE_APLICA_SEM_PEDIDO_LAI" and vs != ["mgov05"]:
                    erros.append(f"{onde}: a exceção {r.excecao} só vale para o item com a variável mgov05")

            for nome, n in sorted(itens_por_dim.items()):
                linha = d[d["dimensao"] == nome]
                entra = not linha.empty and linha["entra_no_imdm"].iloc[0].lower() == "sim"
                if n == 0 and entra:
                    erros.append(f"{rot}: a dimensão '{nome}' entra no IMDM mas não tem nenhum item")
                elif n == 0:
                    avisos.append(f"{rot}: a dimensão '{nome}' não tem itens (está fora do IMDM)")

            # ---- níveis de maturidade do ano
            faixas = []
            for r in nv.itertuples():
                mn, mx = numero(r.minimo), numero(r.maximo)
                if mn is None or mx is None or mn >= mx:
                    erros.append(f"{rot}, Niveis linha {r.linha_planilha}: mínimo/máximo inválidos ('{r.minimo}', '{r.maximo}')")
                else:
                    faixas.append((mn, mx, r.nome))
            faixas.sort()
            if faixas:
                if faixas[0][0] != 0 or faixas[-1][1] != 100:
                    erros.append(f"{rot}: as faixas de maturidade devem começar em 0 e terminar em 100")
                for (a0, a1, an), (b0, b1, bn) in zip(faixas, faixas[1:]):
                    if b0 != a1:
                        erros.append(f"{rot}: buraco ou sobreposição entre os níveis '{an}' e '{bn}'")

            # ---- conferência contra a base do ano
            if dados is not None and ano not in dados:
                avisos.append(f"{ano}: códigos não conferidos contra a base do IBGE (use --dados {ano}=<arquivo>)")
            if dados and ano in dados:
                base = dados[ano]
                for r in it.itertuples():
                    onde = f"{rot}, Itens linha {r.linha_planilha} ('{r.item}')"
                    vs = variaveis(r.variaveis)
                    faltam = [v for v in vs if v not in base["colunas"]]
                    if faltam:
                        erros.append(f"{onde}: códigos sem dados na base de {ano} {faltam}")
                    if r.regra == "CATEGORICO_ESCALONADO" and len(vs) == 1 and vs[0] in base["valores"]:
                        pts, _ = ler_pontuacao(r.pontuacao)
                        observados = base["valores"][vs[0]] - ESTADOS_ESPECIAIS
                        sem = sorted(observados - set(pts))
                        if sem:
                            erros.append(f"{onde}: respostas da base sem pontuação: {sem}")
                        nunca = sorted(set(pts) - observados)
                        if nunca:
                            avisos.append(f"{onde}: respostas na pontuação que não aparecem na base de {ano}: {nunca}")
                    if r.excecao == "NAO_SE_APLICA_SEM_PEDIDO_LAI" and "mgov04" not in base["colunas"]:
                        avisos.append(f"{onde}: mgov04 sem dados em {ano}; a exceção não poderá ser aplicada")
    return erros, list(dict.fromkeys(avisos))


def resumo(cat: dict[str, pd.DataFrame]) -> dict:
    """{radar: {edicao: {'dimensoes': [...], 'itens': n}}}."""
    out = {}
    for rad in radares(cat):
        out[rad] = {}
        for ano in edicoes(cat):
            e = str(ano)
            dims = cat["Dimensoes"]
            d = dims[(dims["radar"] == rad) & (dims["edicao"] == e)].copy()
            d["o"] = pd.to_numeric(d["ordem"], errors="coerce")
            it = cat["Itens"][(cat["Itens"]["radar"] == rad) & (cat["Itens"]["edicao"] == e)]
            out[rad][e] = {
                "dimensoes": [{"ordem": int(r.o) if pd.notna(r.o) else None, "dimensao": r.dimensao,
                               "entra_no_imdm": r.entra_no_imdm, "itens": int((it["dimensao"] == r.dimensao).sum())}
                              for r in d.sort_values("o").itertuples()],
                "itens": int(len(it)),
            }
    return out


# --------------------------------------------------------------------------- exportação
def tabelas_derivadas(cat: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Formas 'longas' que o pipeline usa (geradas, nunca editadas)."""
    var, pont = [], []
    dims = cat["Dimensoes"]
    for r in cat["Itens"].itertuples():
        vs = variaveis(r.variaveis)
        for i, v in enumerate(vs, 1):
            var.append({"radar": r.radar, "edicao": int(r.edicao), "item": r.item, "dimensao": r.dimensao,
                        "dimensao_codigo": codigo_dimensao(r.dimensao), "cod_variable": v, "ordem": i,
                        "e_ancora": i == 1, "regra": r.regra, "excecao": r.excecao})
        pts, _ = ler_pontuacao(r.pontuacao)
        if r.regra in ("CATEGORICO_ESCALONADO", "ESCADA_MAIOR_NIVEL"):
            for chave, p in pts.items():
                multi = len(vs) > 1
                pont.append({"radar": r.radar, "edicao": int(r.edicao), "item": r.item,
                             "cod_variable": chave.lower() if multi else vs[0],
                             "resposta": "Sim" if multi else chave, "pontos": p})
    colunas_var = ["radar", "edicao", "item", "dimensao", "dimensao_codigo", "cod_variable", "ordem", "e_ancora", "regra", "excecao"]
    colunas_pont = ["radar", "edicao", "item", "cod_variable", "resposta", "pontos"]
    return {"variaveis": pd.DataFrame(var, columns=colunas_var), "pontuacao": pd.DataFrame(pont, columns=colunas_pont)}


def sha256_arquivo(caminho: Path | str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 16), b""):
            h.update(bloco)
    return h.hexdigest()


def exportar_csvs(cat: dict[str, pd.DataFrame], pasta: Path, origem: Path) -> dict:
    pasta.mkdir(parents=True, exist_ok=True)
    for aba, arq in ABAS.items():
        cat[aba].drop(columns="linha_planilha").to_csv(pasta / arq, index=False, encoding="utf-8", lineterminator="\n")
    for nome, df in tabelas_derivadas(cat).items():
        df.to_csv(pasta / f"{nome}.csv", index=False, encoding="utf-8", lineterminator="\n")
    versao = {
        "planilha": origem.name,
        "sha256_planilha": sha256_arquivo(origem),
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "radar_padrao": radar_padrao(cat),
        "resumo": resumo(cat),
    }
    (pasta / "radar_versao.json").write_text(json.dumps(versao, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return versao


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--planilha", default=str(XLSX_PADRAO))
    ap.add_argument("--saida", default=str(CSV_DIR_PADRAO))
    ap.add_argument("--dados", action="append", default=[], metavar="ANO=ARQUIVO.xlsx",
                    help="confere contra a base MUNIC do ano (pode repetir)")
    ap.add_argument("--so-validar", action="store_true", help="valida sem regravar os CSVs")
    args = ap.parse_args(argv)

    planilha = Path(args.planilha)
    cat = ler_planilha(planilha)
    dados = {}
    for par in args.dados:
        ano, _, arq = par.partition("=")
        print(f"Lendo base MUNIC {ano}: {arq}")
        dados[int(ano)] = perfil_xlsx_munic(arq)

    erros, avisos = validar(cat, dados)
    for a in avisos:
        print(f"[AVISO] {a}")
    for e in erros:
        print(f"[ERRO]  {e}")
    for rad, por_ano in resumo(cat).items():
        marca = " (padrão)" if rad == radar_padrao(cat) else ""
        print(f"Radar {rad}{marca}")
        for ano, r in por_ano.items():
            dims = ", ".join(f"{d['ordem']}. {d['dimensao']} ({d['itens']})" for d in r["dimensoes"])
            print(f"  {ano}: {r['itens']} itens | {dims}")
    if erros:
        print(f"\n{len(erros)} erro(s): os CSVs NÃO foram gerados. Corrija a planilha e rode de novo.")
        return 1
    if args.so_validar:
        print("\nOK: planilha válida (CSVs não regravados por --so-validar).")
        return 0
    versao = exportar_csvs(cat, Path(args.saida), planilha)
    print(f"\nOK: CSVs gerados em {args.saida} (sha256 da planilha {versao['sha256_planilha'][:12]}…). "
          "Faça commit da planilha E dos CSVs juntos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
