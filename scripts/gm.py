"""Acesso ao WordPress do GEMEC (login por cookie + REST com nonce).
A senha vem da variavel de ambiente GEMEC_SENHA, nunca do arquivo."""
import os, re, requests
from urllib.parse import urljoin
BASE = "https://gemec.unifei.edu.br"
USER = os.environ.get("GEMEC_USUARIO", "gemec")
s = requests.Session()
# O servidor nao envia o certificado intermediario; o bundle o inclui.
s.verify = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bundle.pem")
s.headers["User-Agent"] = "Mozilla/5.0 (gemec-admin)"

def login():
    s.get(BASE + "/wp-login.php")  # cookie de teste antes do POST
    r = s.post(BASE + "/wp-login.php", data={"log": USER, "pwd": os.environ["GEMEC_SENHA"], "wp-submit": "Log In",
        "redirect_to": BASE + "/wp-admin/", "testcookie": "1"}, allow_redirects=True)
    if not any(c.name.startswith("wordpress_logged_in") for c in s.cookies):
        raise SystemExit("login falhou: " + r.url)
    s.headers["X-WP-Nonce"] = s.get(BASE + "/wp-admin/admin-ajax.php?action=rest-nonce").text.strip()
    return s

def rest(path, method="GET", **kw):
    """/?rest_route= com a query separada; DELETE/PUT viram POST + override (nginx da 405)."""
    p, _, q = path.partition("?")
    url = BASE + "/?rest_route=" + p + ("&" + q if q else "")
    if method in ("DELETE", "PUT", "PATCH"):
        kw.setdefault("headers", {})["X-HTTP-Method-Override"] = method
        method = "POST"
    r = s.request(method, url, **kw)
    return r

def ok(r):
    if r.status_code >= 400:
        raise SystemExit(f"{r.status_code} {r.url}\n{r.text[:800]}")
    return r.json()

def nonce_de(pagina, padrao):
    h = s.get(BASE + "/wp-admin/" + pagina).text
    m = re.search(padrao, h)
    return m.group(1) if m else None

def enviar_zip(tipo, zip_path):
    """tipo: 'plugin' ou 'theme'. Reenvio sobrescreve seguindo o link overwrite."""
    pag = "plugin-install.php?tab=upload" if tipo == "plugin" else "theme-install.php?browse=popular&upload"
    h = s.get(BASE + "/wp-admin/" + pag).text
    n = re.search(r'name="_wpnonce" value="([^"]+)"', h).group(1)
    campo = "pluginzip" if tipo == "plugin" else "themezip"
    with open(zip_path, "rb") as f:
        r = s.post(BASE + f"/wp-admin/update.php?action=upload-{tipo}", data={"_wpnonce": n, "_wp_http_referer": "/wp-admin/" + pag, "install-" + tipo + "-submit": "Install Now"},
                   files={campo: (os.path.basename(zip_path), f, "application/zip")})
    m = re.search(r'href="([^"]*overwrite=update-' + tipo + r'[^"]*)"', r.text)
    if m:
        url = urljoin(BASE + "/wp-admin/", m.group(1).replace("&amp;", "&"))
        r = s.get(url)
    # So o miolo da pagina: o menu lateral sempre tem "Installed Plugins"
    h = r.text
    i = h.find('class="wrap"')
    h = h[i:] if i >= 0 else h
    h = h.split('id="wpfooter"')[0]
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()
    baixo = txt.lower()
    if any(f in baixo for f in ("failed", "could not", "falhou", "não pôde", "nao pode")):
        return False, txt[-1500:]
    if any(f in baixo for f in ("successfully", "sucesso")):
        return True, ""
    return False, txt[-1500:]
