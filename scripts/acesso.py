"""Login do WordPress do GEMEC usado pelo app e pelo main.py.

Fica em config.json, na pasta do app (so neste PC, fora do git): o app pede
usuario e senha na primeira vez que abre e grava ali (tambem na tela
Configuracoes). Sem o arquivo valem GEMEC_USUARIO / GEMEC_SENHA; o main.py
pelo terminal pergunta a senha.
"""
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ = os.path.join(RAIZ, "config.json")


def ler():
    try:
        with open(ARQ, encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, ValueError):
        c = {}
    return {"usuario": c.get("usuario") or os.environ.get("GEMEC_USUARIO") or "gemec",
            "senha": c.get("senha") or os.environ.get("GEMEC_SENHA") or ""}


def tem_login():
    return bool(ler()["senha"])


def gravar(usuario, senha):
    tmp = ARQ + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"usuario": usuario, "senha": senha}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ARQ)


def aplicar():
    """Poe o login nas variaveis de ambiente (gm.py e as tarefas leem dali)."""
    c = ler()
    os.environ["GEMEC_USUARIO"] = c["usuario"]
    os.environ["GEMEC_SENHA"] = c["senha"]
    return c
