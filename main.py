"""Atualiza o site do GEMEC (gemec.unifei.edu.br) a partir do Curriculo Lattes.

    python main.py             atualizacao completa: baixa o CV de todos os
                               membros, gera o relatorio, refaz no site as
                               publicacoes, os resumos e a pagina Estatisticas
                               e completa os perfis (uns 30 minutos)
    python main.py novos       so membros cadastrados no site que ainda nao tem
                               CV baixado (se a completa venceu, 7 dias, faz a
                               completa); sem nada novo, termina na hora
    python main.py perfis      so completa os perfis com o que esta no Lattes
                               (formacao, ORCID, titulacao, temas, foto)
    python main.py membro <id16>   so um membro: baixa o CV dele, refaz o site
                               (os outros com o CV que ja esta baixado) e
                               completa o perfil dele
    python main.py cv <id16>   so baixa o CV de alguem para o cache (nao mexe
                               no site; o app usa para puxar dados e foto)
    python main.py faltam      lista quem ainda nao tem CV baixado
    python main.py abrir       abre no navegador os CVs que faltam, para salvar
                               a mao em scripts/lattes/baixados/

O usuario e a senha do WordPress do GEMEC vem de config.json (o app pede na
primeira vez que abre e grava ali, so neste PC); sem ele, de
GEMEC_USUARIO/GEMEC_SENHA ou a senha e perguntada aqui.
"""
import getpass
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(AQUI, "scripts", "lattes"), os.path.join(AQUI, "scripts")]
import acesso  # noqa: E402
acesso.aplicar()
os.environ["PYTHONUTF8"] = "1"

import lattes  # noqa: E402
import perfis  # noqa: E402


def completo():
    lattes.cmd_semanal()
    perfis.completar()


def novos():
    lattes.cmd_auto()
    perfis.completar()


def membro():
    if len(sys.argv) < 3:
        sys.exit("Uso: python main.py membro <link ou id de 16 digitos do Lattes>")
    lid = lattes.cmd_membro(sys.argv[2])
    if lid:  # sem Lattes (so ORCID) nao ha perfil a completar
        perfis.completar(so={lid})


COMANDOS = {
    "completo": completo,
    "novos": novos,
    "membro": membro,
    "cv": lambda: lattes.cmd_cv(sys.argv[2] if len(sys.argv) > 2 else ""),
    "perfis": perfis.completar,
    "faltam": lattes.cmd_faltam,
    "abrir": lattes.cmd_abrir,
}

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "completo"
    if cmd not in COMANDOS:
        sys.exit(__doc__)
    if cmd in ("completo", "novos", "membro", "perfis") and not os.environ.get("GEMEC_SENHA"):
        if not sys.stdin or not sys.stdin.isatty():
            sys.exit("Sem login salvo: abra o app e entre com o usuario e a senha do WordPress do GEMEC.")
        os.environ["GEMEC_SENHA"] = getpass.getpass("Senha do WordPress do GEMEC (usuario %s): " % os.environ["GEMEC_USUARIO"])
    try:
        COMANDOS[cmd]()
    except SystemExit as e:
        if e.code not in (None, 0):
            print("\nTerminou com erro:", e.code)
            sys.exit(1)
        raise
    print("\nPronto.")
