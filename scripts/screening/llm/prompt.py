"""Blocos de prompt do screening dual-LLM e da arbitragem (3º LLM).

O bloco de sistema é estável (idêntico em todas as chamadas) → marcado
para prompt caching. O bloco do usuário carrega só os dados do registro.
"""
from __future__ import annotations

import pandas as pd

_CRITERIA_CORE = """\
Você é um avaliador de revisão sistemática em economia. Decida se o estudo \
fornecido pelo usuário deve ser INCLUÍDO no corpus de uma SLR sobre IMPACTOS \
DA INTELIGÊNCIA ARTIFICIAL NO EMPREGO.

CRITÉRIOS DE INCLUSÃO:
- Período de publicação: 2013-01-01 a 2026-06-30.
- Idioma: inglês, português, espanhol ou francês.
- Tipo de IA: ML supervisionado/não-supervisionado, deep learning, NLP, visão \
computacional, LLMs/IA generativa, ou robôs com componente de IA.
- Desfecho: efeito sobre o emprego (nível, criação/destruição de postos, \
exposição ocupacional, demanda por trabalho).
- Tipo: periódico revisado por pares; working paper de instituição reconhecida \
(NBER, IZA, CEPR, BIS, OECD, IPEA, BCB, FGV); capítulo indexado.

CRITÉRIOS DE EXCLUSÃO:
- E1: tema fora do escopo (produtividade individual sem ligação com emprego; \
IA em educação/saúde/ética/governança sem conexão com mercado de trabalho).
- E2: tecnologia fora do escopo (robótica industrial pré-IA, automação \
puramente mecânica, sistemas especialistas legados sem aprendizado).
- E3: tipo de documento inválido (editorial, resenha, opinião, blog, white \
paper sem metodologia, tese não publicada).
- E4: texto completo inacessível. NÃO APLICÁVEL nesta fase — você avalia \
apenas título e resumo; nunca exclua por E4 no screening.
- E5: qualidade insuficiente (sem metodologia descrita ou sem evidência \
verificável aparente no resumo)."""

_SCREENING_CONTRACT = """

Na dúvida genuína, responda "duvida" (será resolvido na leitura de texto \
completo) — nunca exclua por incerteza.

Responda EXCLUSIVAMENTE com um objeto JSON estrito, sem texto antes ou depois:
{"decisao": "incluir" | "excluir" | "duvida", "justificativa": "1-2 frases \
citando o critério", "confianca": <float entre 0 e 1>, "criterio": "E1".."E5" \
quando decisao=excluir, senão null}"""

_ARBITER_CONTRACT = """

Esta é a DECISÃO FINAL desta fase de seleção: a resposta de dúvida NÃO é \
permitida. Decida "incluir" ou "excluir" mesmo em casos limítrofes. Na \
incerteza genuína, prefira "incluir" (o estudo segue para leitura de texto \
completo, onde poderá ser excluído).

Responda EXCLUSIVAMENTE com um objeto JSON estrito, sem texto antes ou depois:
{"decisao": "incluir" | "excluir", "justificativa": "1-2 frases citando o \
critério", "confianca": <float entre 0 e 1>}"""

_CRITERIA = _CRITERIA_CORE + _SCREENING_CONTRACT
_ARBITER_CRITERIA = _CRITERIA_CORE + _ARBITER_CONTRACT


def build_system_block() -> list[dict]:
    """Bloco de sistema estável → elegível a prompt caching."""
    return [{
        "type": "text",
        "text": _CRITERIA,
        "cache_control": {"type": "ephemeral"},
    }]


def build_arbiter_system_block() -> list[dict]:
    """Bloco de sistema do árbitro: mesmos critérios, contrato BINÁRIO estrito
    (sem "duvida"). Estável → elegível a prompt caching."""
    return [{
        "type": "text",
        "text": _ARBITER_CRITERIA,
        "cache_control": {"type": "ephemeral"},
    }]


def build_user_block(row: pd.Series) -> str:
    """Bloco variável: apenas os dados do registro."""
    return (
        f"Título: {row.get('title', '')}\n"
        f"Autores: {row.get('authors', '')}\n"
        f"Ano: {row.get('year', '')}\n"
        f"Periódico: {row.get('venue', '')}\n"
        f"Resumo: {row.get('abstract', '')}"
    )
