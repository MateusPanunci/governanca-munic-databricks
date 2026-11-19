"""Valida o radar IMDM (planilha do especialista) e gera os CSVs que o pipeline lê.

Cada edição tem o seu radar, independente das outras: as abas são fixas e cada
linha diz a que edição pertence (coluna `edicao`). Ano novo = linhas novas, nunca
aba nova nem código novo.

Uso, na raiz do repositório:
    python config/radar/validar_radar.py
    python config/radar/validar_radar.py --dados 2024=Base_MUNIC_2024_20251107.xlsx --dados 2019=Base_MUNIC_2019.xlsx

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
ABAS = {"Dimensoes": "dimensoes.csv", "Itens": "itens.csv", "Niveis": "niveis.csv"}
COLUNAS = {
    "Dimensoes": ["edicao", "dimensao", "ordem", "peso", "entra_no_imdm", "descricao"],
    "Itens": ["edicao", "dimensao", "item", "descricao", "variaveis", "regra", "pontuacao", "excecao"],
    "Niveis": ["edicao", "nivel", "nome", "minimo", "maximo"],
}

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
    anos = set()
    for aba in ABAS:
        for e in cat[aba]["edicao"]:
            if re.fullmatch(r"\d{4}", e):
                anos.add(int(e))
    return sorted(anos)


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
    so_edicao: valida só essa edição (o notebook usa a edição do job).
    """
    erros: list[str] = []
    avisos: list[str] = []
    dims, itens, niveis = cat["Dimensoes"], cat["Itens"], cat["Niveis"]

    # edição precisa ser um ano em todas as abas
    for aba in ABAS:
        for r in cat[aba].itertuples():
            if not re.fullmatch(r"\d{4}", r.edicao):
                erros.append(f"{aba} linha {r.linha_planilha}: edição '{r.edicao}' não é um ano (ex.: 2024)")

    anos = edicoes(cat) if so_edicao is None else [so_edicao]
    for ano in anos:
        e = str(ano)
        d = dims[dims["edicao"] == e]
        it = itens[itens["edicao"] == e]
        nv = niveis[niveis["edicao"] == e]

        if d.empty:
            erros.append(f"{ano}: nenhuma dimensão na aba Dimensoes")
        if it.empty:
            erros.append(f"{ano}: nenhum item na aba Itens")
        if nv.empty:
            erros.append(f"{ano}: nenhuma faixa de maturidade na aba Niveis")

        # ---- dimensões do ano
        nomes = []
        for r in d.itertuples():
            onde = f"{ano}, Dimensoes linha {r.linha_planilha}"
            if not r.dimensao:
                erros.append(f"{onde}: nome da dimensão vazio")
            nomes.append(r.dimensao)
            if numero(r.peso) is None or numero(r.peso) <= 0:
                erros.append(f"{onde}: peso '{r.peso}' deve ser número maior que 0")
            if r.entra_no_imdm.lower() not in SIM_NAO:
                erros.append(f"{onde}: entra_no_imdm deve ser 'sim' ou 'nao' (está '{r.entra_no_imdm}')")
        repetidas = sorted({n for n in nomes if n and nomes.count(n) > 1})
        if repetidas:
            erros.append(f"{ano}: dimensão declarada mais de uma vez {repetidas}")
        codigos = {}
        for n in set(nomes):
            if n:
                codigos.setdefault(codigo_dimensao(n), []).append(n)
        for cod, ns in codigos.items():
            if len(ns) > 1:
                erros.append(f"{ano}: dimensões com nomes que só diferem em acento/maiúscula {sorted(ns)}")
        ordens = [r.ordem for r in d.itertuples()]
        if any(not re.fullmatch(r"\d+", o) for o in ordens):
            erros.append(f"{ano}: 'ordem' das dimensões deve ser número inteiro (encontrado: {', '.join(ordens)})")
        elif ordens and sorted(int(o) for o in ordens) != list(range(1, len(ordens) + 1)):
            erros.append(f"{ano}: a ordem das dimensões deve ser 1, 2, 3… sem buracos nem repetições "
                         f"(encontrado: {', '.join(sorted(ordens, key=int))})")
        if not d.empty and not (d["entra_no_imdm"].str.lower() == "sim").any():
            erros.append(f"{ano}: nenhuma dimensão entra no IMDM")
        validas = set(nomes)

        # ---- itens do ano
        nomes_itens = list(it["item"])
        for n in sorted({n for n in nomes_itens if n and nomes_itens.count(n) > 1}):
            erros.append(f"{ano}: item '{n}' aparece mais de uma vez")
        dono: dict[str, str] = {}
        itens_por_dim = {n: 0 for n in validas}
        for r in it.itertuples():
            onde = f"{ano}, Itens linha {r.linha_planilha} ('{r.item or 'sem nome'}')"
            if not r.item:
                erros.append(f"{onde}: nome do item vazio")
            if r.dimensao not in validas:
                sugestao = difflib.get_close_matches(r.dimensao, list(validas), n=1, cutoff=0.6)
                dica = f" — você quis dizer '{sugestao[0]}'?" if sugestao else f" (dimensões de {ano}: {sorted(validas)})"
                erros.append(f"{onde}: usa a dimensão '{r.dimensao}', que não existe em {ano}{dica}")
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
                erros.append(f"{ano}: a dimensão '{nome}' entra no IMDM mas não tem nenhum item")
            elif n == 0:
                avisos.append(f"{ano}: a dimensão '{nome}' não tem itens (está fora do IMDM)")

        # ---- níveis de maturidade do ano
        faixas = []
        for r in nv.itertuples():
            mn, mx = numero(r.minimo), numero(r.maximo)
            if mn is None or mx is None or mn >= mx:
                erros.append(f"{ano}, Niveis linha {r.linha_planilha}: mínimo/máximo inválidos ('{r.minimo}', '{r.maximo}')")
            else:
                faixas.append((mn, mx, r.nome))
        faixas.sort()
        if faixas:
            if faixas[0][0] != 0 or faixas[-1][1] != 100:
                erros.append(f"{ano}: as faixas de maturidade devem começar em 0 e terminar em 100")
            for (a0, a1, an), (b0, b1, bn) in zip(faixas, faixas[1:]):
                if b0 != a1:
                    erros.append(f"{ano}: buraco ou sobreposição entre os níveis '{an}' e '{bn}'")

        # ---- conferência contra a base do ano
        if dados is not None and ano not in dados:
            avisos.append(f"{ano}: códigos não conferidos contra a base do IBGE (use --dados {ano}=<arquivo>)")
        if dados and ano in dados:
            base = dados[ano]
            for r in it.itertuples():
                onde = f"{ano}, Itens linha {r.linha_planilha} ('{r.item}')"
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
    return erros, avisos


def resumo(cat: dict[str, pd.DataFrame]) -> dict:
    out = {}
    for ano in edicoes(cat):
        e = str(ano)
        d = cat["Dimensoes"][cat["Dimensoes"]["edicao"] == e].copy()
        d["o"] = pd.to_numeric(d["ordem"], errors="coerce")
        it = cat["Itens"][cat["Itens"]["edicao"] == e]
        out[e] = {
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
            var.append({"edicao": int(r.edicao), "item": r.item, "dimensao": r.dimensao,
                        "dimensao_codigo": codigo_dimensao(r.dimensao), "cod_variable": v, "ordem": i,
                        "e_ancora": i == 1, "regra": r.regra, "excecao": r.excecao})
        pts, _ = ler_pontuacao(r.pontuacao)
        if r.regra in ("CATEGORICO_ESCALONADO", "ESCADA_MAIOR_NIVEL"):
            for chave, p in pts.items():
                multi = len(vs) > 1
                pont.append({"edicao": int(r.edicao), "item": r.item,
                             "cod_variable": chave.lower() if multi else vs[0],
                             "resposta": "Sim" if multi else chave, "pontos": p})
    return {"variaveis": pd.DataFrame(var), "pontuacao": pd.DataFrame(pont)}


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
    for ano, r in resumo(cat).items():
        dims = ", ".join(f"{d['ordem']}. {d['dimensao']} ({d['itens']})" for d in r["dimensoes"])
        print(f"{ano}: {r['itens']} itens | {dims}")
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
