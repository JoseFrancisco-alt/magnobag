"""Magnobag: site com cadastro, lista de ativos e painel de análise."""
import os
import re
import secrets
import sqlite3
from datetime import date, timedelta
import time
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

import analise
import noticias

PASTA = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(PASTA, "radar.db")
TICKER_VALIDO = re.compile(r"^[A-Z0-9.\-=^]{1,15}$")
FAVORITOS_INICIAIS = ["PETR4.SA", "BTC-USD"]
ARQUIVO_CONTAS_GRATIS = os.path.join(PASTA, "contas_gratis.txt")
ARQUIVO_CONTAS_DONO = os.path.join(PASTA, "contas_dono.txt")
# Imagem própria pro mascote: se existir em static/, substitui o desenho em pixel art
IMAGENS_MASCOTE = ["mascote.gif", "mascote.png", "mascote.webp"]
PRECO_ASSINATURA = "R$ 4,00/mês"
# Plano grátis (degustação): poucos ativos, gráfico curto, poucas notícias, sem backtest nem simulador
GRATIS_MAX_ATIVOS = 2
GRATIS_DIAS_GRAFICO = 180
GRATIS_MAX_NOTICIAS = 3

# Na Vercel (ou outra nuvem) o banco é PostgreSQL (Supabase); no computador, SQLite.
DATABASE_URL = os.environ.get("DATABASE_URL")
NA_VERCEL = bool(os.environ.get("VERCEL"))


def chave_secreta():
    """SECRET_KEY do ambiente ou, se não houver, uma chave aleatória salva em arquivo
    (assim ninguém é deslogado quando o servidor reinicia)."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    if NA_VERCEL:
        raise RuntimeError("Defina SECRET_KEY nas variáveis de ambiente da Vercel.")
    arquivo = os.path.join(PASTA, ".secret_key")
    if not os.path.exists(arquivo):
        with open(arquivo, "w") as f:
            f.write(secrets.token_hex(32))
    with open(arquivo) as f:
        return f.read().strip()


app = Flask(__name__)
app.secret_key = chave_secreta()
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
# no ar (com HTTPS), o cookie de login só viaja criptografado
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("HTTPS") == "1"


# ---------- segurança ----------

def token_csrf():
    """Token secreto por sessão: todo formulário do site manda ele de volta."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["campo_csrf"] = lambda: Markup(f'<input type="hidden" name="csrf" value="{token_csrf()}">')


@app.before_request
def conferir_csrf():
    # impede que outro site envie formulários em nome de quem está logado aqui
    if request.method == "POST":
        enviado = request.form.get("csrf") or request.headers.get("X-CSRF-Token") or ""
        if not secrets.compare_digest(enviado, session.get("csrf", "")):
            abort(400, "Formulário expirado. Volte e tente de novo.")


@app.after_request
def cabecalhos_seguranca(resposta):
    resposta.headers["X-Content-Type-Options"] = "nosniff"       # não "adivinhar" tipo de arquivo
    resposta.headers["X-Frame-Options"] = "DENY"                 # ninguém coloca o site dentro de um iframe
    resposta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if app.config["SESSION_COOKIE_SECURE"]:
        resposta.headers["Strict-Transport-Security"] = "max-age=31536000"
    return resposta


# limite de tentativas de login (contra quem tenta adivinhar senha)
MAX_TENTATIVAS = 5
JANELA_TENTATIVAS = 15 * 60
_tentativas = {}


def _falhas_recentes(chave):
    agora = time.time()
    _tentativas[chave] = [t for t in _tentativas.get(chave, []) if agora - t < JANELA_TENTATIVAS]
    return _tentativas[chave]


def login_bloqueado(*chaves):
    return any(len(_falhas_recentes(c)) >= MAX_TENTATIVAS for c in chaves)


def registrar_falha(*chaves):
    for c in chaves:
        _falhas_recentes(c).append(time.time())


# ---------- banco de dados ----------

class BancoPostgres:
    """Deixa o PostgreSQL com a mesma cara do sqlite3 que o resto do código usa."""

    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        # prepare_threshold=None: o "pooler" do Supabase não aceita comandos preparados
        self.conexao = psycopg.connect(url, row_factory=dict_row, prepare_threshold=None)

    @staticmethod
    def _traduzir(sql):
        sql = sql.replace("?", "%s").replace("ORDER BY rowid", "ORDER BY criado_em")
        if sql.startswith("INSERT OR IGNORE"):
            sql = sql.replace("INSERT OR IGNORE", "INSERT", 1) + " ON CONFLICT DO NOTHING"
        return sql

    def execute(self, sql, parametros=()):
        return self.conexao.execute(self._traduzir(sql), parametros)

    def executemany(self, sql, lista):
        with self.conexao.cursor() as cursor:
            cursor.executemany(self._traduzir(sql), lista)

    def commit(self):
        self.conexao.commit()

    def rollback(self):
        self.conexao.rollback()

    def close(self):
        self.conexao.close()


def _erros_duplicado():
    erros = [sqlite3.IntegrityError]
    if DATABASE_URL:
        import psycopg
        erros.append(psycopg.errors.UniqueViolation)
    return tuple(erros)


def banco():
    if "db" not in g:
        if DATABASE_URL:
            g.db = BancoPostgres(DATABASE_URL)
        else:
            g.db = sqlite3.connect(BANCO)
            g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def fechar_banco(_erro):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def criar_tabelas():
    if DATABASE_URL:
        return  # no PostgreSQL as tabelas são criadas pela migração (supabase/schema.sql)
    with sqlite3.connect(BANCO) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                senha_hash TEXT NOT NULL,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS favoritos (
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                ticker TEXT NOT NULL,
                PRIMARY KEY (usuario_id, ticker)
            );
        """)
        colunas = [linha[1] for linha in db.execute("PRAGMA table_info(usuarios)")]
        if "premium" not in colunas:  # bancos criados antes do plano pago
            db.execute("ALTER TABLE usuarios ADD COLUMN premium INTEGER NOT NULL DEFAULT 0")
        if "nome" not in [linha[1] for linha in db.execute("PRAGMA table_info(favoritos)")]:
            db.execute("ALTER TABLE favoritos ADD COLUMN nome TEXT")  # nome amigável vindo da busca


# ---------- login ----------

def login_obrigatorio(rota):
    @wraps(rota)
    def protegida(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return rota(*args, **kwargs)
    return protegida


def ler_emails(caminho):
    """E-mails de um arquivo, um por linha (linhas com # são ignoradas)."""
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            return {linha.strip().lower() for linha in arquivo
                    if linha.strip() and not linha.lstrip().startswith("#")}
    except FileNotFoundError:
        return set()


def emails_do_ambiente(nome):
    """Na nuvem, as listas vêm de variáveis de ambiente (e-mails separados por vírgula)."""
    return {e.strip().lower() for e in os.environ.get(nome, "").split(",") if e.strip()}


def contas_donos():
    return ler_emails(ARQUIVO_CONTAS_DONO) | emails_do_ambiente("CONTAS_DONO")


def contas_gratis():
    # o dono sempre tem acesso total, sem precisar estar também na lista de contas grátis
    return ler_emails(ARQUIVO_CONTAS_GRATIS) | emails_do_ambiente("CONTAS_GRATIS") | contas_donos()


def eh_dono():
    """A conta logada é do dono do site (contas_dono.txt)?"""
    if "usuario_id" not in session:
        return False
    linha = banco().execute("SELECT email FROM usuarios WHERE id = ?", (session["usuario_id"],)).fetchone()
    return bool(linha) and linha["email"] in contas_donos()


def situacao_conta():
    """Devolve (assinante, conta_gratis) do usuário logado. Quem não é assinante usa o plano grátis."""
    if "usuario_id" not in session:
        return False, False
    linha = banco().execute("SELECT email, premium FROM usuarios WHERE id = ?",
                            (session["usuario_id"],)).fetchone()
    if linha is None:
        return False, False
    gratis = linha["email"] in contas_gratis()
    return gratis or bool(linha["premium"]), gratis


def assinatura_obrigatoria(rota):
    @wraps(rota)
    @login_obrigatorio
    def protegida(*args, **kwargs):
        if not situacao_conta()[0]:
            if request.path.startswith("/api/"):
                return jsonify({"erro": "Assinatura necessária."}), 402
            return redirect(url_for("plano"))
        return rota(*args, **kwargs)
    return protegida


def endereco_imagem_mascote():
    """Imagem própria do mascote: arquivo em static/ (no computador) ou guardada no banco (no ar)."""
    arquivo = next((n for n in IMAGENS_MASCOTE if os.path.exists(os.path.join(PASTA, "static", n))), None)
    if arquivo:
        return url_for("static", filename=arquivo)
    if DATABASE_URL:
        try:
            if banco().execute("SELECT 1 FROM arquivos WHERE nome = 'mascote'").fetchone():
                return url_for("imagem_mascote")
        except Exception:
            banco().rollback()  # tabela ainda não existe: segue com o desenho em pixel art
    return None


@app.context_processor
def variaveis_globais():
    acesso, gratis = situacao_conta()
    dono = eh_dono()
    imagem = endereco_imagem_mascote() if dono else None
    return {"tem_acesso": acesso, "conta_gratis": gratis, "preco": PRECO_ASSINATURA, "eh_dono": dono,
            "imagem_mascote": imagem,
            "gratis_max_ativos": GRATIS_MAX_ATIVOS, "gratis_max_noticias": GRATIS_MAX_NOTICIAS}


def favoritos_do_usuario():
    favoritos = [linha["ticker"] for linha in banco().execute(
        "SELECT ticker FROM favoritos WHERE usuario_id = ? ORDER BY rowid",
        (session["usuario_id"],))]
    # quem cancelou a assinatura continua vendo só os primeiros ativos
    return favoritos if situacao_conta()[0] else favoritos[:GRATIS_MAX_ATIVOS]


def ticker_ou_404(ticker):
    ticker = ticker.upper().strip()
    if not TICKER_VALIDO.match(ticker):
        abort(404)
    return ticker


@app.route("/")
def inicio():
    return redirect(url_for("painel" if "usuario_id" in session else "login"))


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        if not nome or "@" not in email:
            flash("Preencha nome e um e-mail válido.", "erro")
        elif len(senha) < 8:
            flash("A senha precisa ter pelo menos 8 caracteres.", "erro")
        else:
            db = banco()
            try:
                novo_id = db.execute(
                    "INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?) RETURNING id",
                    (nome, email, generate_password_hash(senha))).fetchone()["id"]
            except _erros_duplicado():
                db.rollback()
                flash("Esse e-mail já tem cadastro.", "erro")
            else:
                db.executemany("INSERT INTO favoritos (usuario_id, ticker) VALUES (?, ?)",
                               [(novo_id, t) for t in FAVORITOS_INICIAIS])
                db.commit()
                session.clear()
                session["usuario_id"] = novo_id
                session["nome"] = nome
                return redirect(url_for("painel"))
    return render_template("cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        chaves = (f"ip:{request.remote_addr}", f"email:{email}")
        if login_bloqueado(*chaves):
            flash("Muitas tentativas erradas. Espere 15 minutos e tente de novo.", "erro")
            return render_template("login.html"), 429
        usuario = banco().execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()
        if usuario and check_password_hash(usuario["senha_hash"], request.form.get("senha", "")):
            for c in chaves:
                _tentativas.pop(c, None)
            session.clear()
            session["usuario_id"] = usuario["id"]
            session["nome"] = usuario["nome"]
            return redirect(url_for("painel"))
        registrar_falha(*chaves)
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("login.html")


@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("login"))


# ---------- páginas ----------

def nomes_dos_ativos():
    """Nomes do catálogo + os nomes guardados quando o ativo foi adicionado pela busca."""
    guardados = {linha["ticker"]: linha["nome"] for linha in banco().execute(
        "SELECT ticker, nome FROM favoritos WHERE usuario_id = ? AND nome IS NOT NULL",
        (session["usuario_id"],))}
    return {**guardados, **analise.NOMES}


@app.route("/painel")
@login_obrigatorio
def painel():
    return render_template("painel.html", favoritos=favoritos_do_usuario(),
                           catalogo=analise.CATALOGO, nomes=nomes_dos_ativos())


@app.route("/noticias")
@login_obrigatorio
def pagina_noticias():
    return render_template("noticias.html", favoritos=favoritos_do_usuario(), nomes=nomes_dos_ativos())


@app.route("/ativo/<ticker>")
@login_obrigatorio
def ativo(ticker):
    ticker = ticker_ou_404(ticker)
    favorito = banco().execute(
        "SELECT 1 FROM favoritos WHERE usuario_id = ? AND ticker = ?",
        (session["usuario_id"], ticker)).fetchone() is not None
    return render_template("ativo.html", ticker=ticker, favorito=favorito,
                           nome=analise.NOMES.get(ticker, ticker))


@app.post("/favoritos/adicionar")
@login_obrigatorio
def adicionar_favorito():
    ticker = request.form.get("ticker", "").upper().strip()
    if not TICKER_VALIDO.match(ticker):
        flash("Código inválido. Exemplos: PETR4.SA, BTC-USD.", "erro")
    elif not situacao_conta()[0] and len(favoritos_do_usuario()) >= GRATIS_MAX_ATIVOS:
        flash(f"No plano grátis você acompanha até {GRATIS_MAX_ATIVOS} ativos. "
              f"Remova um ou assine por {PRECO_ASSINATURA} para acompanhar quantos quiser.", "erro")
    elif analise.baixar(ticker).empty:
        flash(f"Não encontrei dados para {ticker}.", "erro")
    else:
        nome = request.form.get("nome", "").strip()[:60] or None
        banco().execute("INSERT OR IGNORE INTO favoritos (usuario_id, ticker, nome) VALUES (?, ?, ?)",
                        (session["usuario_id"], ticker, nome))
        banco().commit()
    return redirect(request.form.get("voltar") or url_for("painel"))


@app.post("/favoritos/remover")
@login_obrigatorio
def remover_favorito():
    banco().execute("DELETE FROM favoritos WHERE usuario_id = ? AND ticker = ?",
                    (session["usuario_id"], request.form.get("ticker", "").upper()))
    banco().commit()
    return redirect(request.form.get("voltar") or url_for("painel"))


# ---------- assinatura ----------

def pagamento_de_teste():
    # Enquanto não houver Mercado Pago/Stripe integrado, o "pagamento" só funciona em
    # modo de desenvolvimento ou com PAGAMENTO_TESTE=1, e libera o acesso na hora.
    return app.debug or os.environ.get("PAGAMENTO_TESTE") == "1"


@app.route("/plano")
@login_obrigatorio
def plano():
    if situacao_conta()[0]:
        return redirect(url_for("painel"))
    return render_template("plano.html", preco=PRECO_ASSINATURA, teste=pagamento_de_teste())


@app.route("/simulador")
@assinatura_obrigatoria
def simulador():
    return render_template("simulador.html")


@app.post("/assinar")
@login_obrigatorio
def assinar():
    if not pagamento_de_teste():
        flash("Pagamento ainda não configurado.", "erro")
        return redirect(url_for("plano"))
    banco().execute("UPDATE usuarios SET premium = 1 WHERE id = ?", (session["usuario_id"],))
    banco().commit()
    flash("Pagamento de teste aprovado. Bem-vindo ao Magnobag!", "sucesso")
    return redirect(url_for("painel"))


@app.post("/cancelar")
@login_obrigatorio
def cancelar():
    banco().execute("UPDATE usuarios SET premium = 0 WHERE id = ?", (session["usuario_id"],))
    banco().commit()
    flash("Assinatura cancelada.", "sucesso")
    return redirect(url_for("plano"))


# ---------- API usada pelos gráficos ----------

@app.route("/api/analise/<ticker>")
@login_obrigatorio
def api_analise(ticker):
    dados = analise.calcular(ticker_ou_404(ticker))
    if dados is None:
        return jsonify({"erro": "Sem dados para esse ativo."}), 404
    if not situacao_conta()[0]:
        dados = versao_gratis(dados)
    return jsonify(dados)


def versao_gratis(dados):
    """Plano grátis: só os últimos meses do gráfico de preço, sem RSI, backtest e palpite."""
    corte = (date.today() - timedelta(days=GRATIS_DIAS_GRAFICO)).isoformat()
    inicio = next((i for i, d in enumerate(dados["serie"]["datas"]) if d >= corte), 0)
    serie = {chave: valores[inicio:] for chave, valores in dados["serie"].items() if chave != "rsi"}
    return {**dados, "serie": serie, "estrategias": [], "palpite": None, "limitado": True}


@app.route("/api/resumo/<ticker>")
@login_obrigatorio
def api_resumo(ticker):
    dados = analise.calcular(ticker_ou_404(ticker))
    if dados is None:
        return jsonify({"erro": "Sem dados para esse ativo."}), 404
    return jsonify({"nome": dados["nome"], "moeda": dados["moeda"], **dados["resumo"]})


@app.route("/api/buscar")
@login_obrigatorio
def api_buscar():
    """Sugestões para o campo de busca do painel (nome da empresa, moeda ou código)."""
    return jsonify(analise.buscar_ativos(request.args.get("q", "")[:40]))


@app.route("/api/noticias/<ticker>")
@login_obrigatorio
def api_noticias(ticker):
    try:
        lista = noticias.buscar(ticker_ou_404(ticker))
        return jsonify(lista if situacao_conta()[0] else lista[:GRATIS_MAX_NOTICIAS])
    except Exception:
        app.logger.exception("Falha ao buscar notícias de %s", ticker)
        return jsonify({"erro": "Não consegui buscar as notícias agora."}), 502



# ---------- mascote (só para o dono) ----------

@app.route("/mascote-imagem")
@login_obrigatorio
def imagem_mascote():
    """Entrega a imagem do mascote guardada no banco, e só para o dono (ela não fica pública)."""
    if not eh_dono() or not DATABASE_URL:  # no computador a imagem vem de static/, não do banco
        abort(404)
    linha = banco().execute("SELECT tipo, dados FROM arquivos WHERE nome = 'mascote'").fetchone()
    if not linha:
        abort(404)
    resposta = app.response_class(bytes(linha["dados"]), mimetype=linha["tipo"])
    resposta.headers["Cache-Control"] = "private, max-age=86400"
    return resposta


def _pct(valor):
    return f"{abs(valor) * 100:.1f}".replace(".", ",") + "%"


def texto_horarios(nome, h):
    """Resumo honesto dos horários: quando o ativo mais se mexe, quando fica parado e que nenhum horário garante alta."""
    sessao = "negocia 24h" if h["24h"] else f"negocia das {h['abertura']}h às {h['fechamento']}h"
    partes = [
        f"Horários de {nome} (últimos {h['dias']} dias): ele {sessao}.",
        f"Mais agitado: {h['agitada']}h (mexe ~{_pct(h['movimento_agitada'])} na hora).",
        f"Mais calmo: {h['calma']}h (~{_pct(h['movimento_calma'])}).",
    ]
    if h["mais_volume"] is not None and h["mais_volume"] != h["agitada"]:
        partes.append(f"Mais negócios acontecendo: {h['mais_volume']}h.")
    # com poucos dias e vários horários testados, algum passa de 60% por sorte;
    # o limite abaixo (~2,5 desvios acima de 50%) separa isso do que vale ficar de olho
    limite = 0.5 + 1.25 / h["dias"] ** 0.5
    chance = h["chance_mais_sobe"] * 100
    if h["chance_mais_sobe"] > limite:
        partes.append(f"{h['mais_sobe']}h subiu em {chance:.0f}% das vezes, acima do que a sorte explicaria, "
                      f"mas {h['dias']} dias é pouco pra confiar. Vale ficar de olho, não apostar.")
    else:
        partes.append(f"Nenhum horário sobe com frequência confiável: o 'melhor' foi {h['mais_sobe']}h "
                      f"({chance:.0f}%), dentro do que a sorte explica em {h['dias']} dias.")
    return " ".join(partes)


@app.route("/api/mascote")
@login_obrigatorio
def api_mascote():
    """Avisos do mascote: fatos sobre os ativos do dono, nunca ordens de compra ou venda."""
    if not eh_dono():
        return jsonify({"erro": "Só para o dono do site."}), 403

    avisos, variacoes = [], []
    for ticker in favoritos_do_usuario():
        dados = analise.calcular(ticker)
        if dados is None:
            continue
        r, nome = dados["resumo"], ticker.replace(".SA", "")
        v = r["variacao_dia"]
        variacoes.append(v)
        if v <= -0.02:
            avisos.append({"humor": "triste", "texto": f"{nome} caiu {_pct(v)} hoje. Dia pesado pra ele.", "ticker": ticker})
        elif v >= 0.02:
            avisos.append({"humor": "feliz", "texto": f"{nome} subiu {_pct(v)} hoje!", "ticker": ticker})
        if r["cruzou_hoje"] == "alta":
            avisos.append({"humor": "feliz", "texto": f"{nome}: a média de 20 dias passou pra cima da de 50 hoje. Virou tendência de alta.", "ticker": ticker})
        elif r["cruzou_hoje"] == "baixa":
            avisos.append({"humor": "triste", "texto": f"{nome}: a média de 20 dias caiu pra baixo da de 50 hoje. Virou tendência de baixa.", "ticker": ticker})
        if r["rsi"] > 75:
            avisos.append({"humor": "alerta", "texto": f"{nome} está com RSI {r['rsi']:.0f}: subiu rápido demais nos últimos dias.", "ticker": ticker})
        elif r["rsi"] < 25:
            avisos.append({"humor": "alerta", "texto": f"{nome} está com RSI {r['rsi']:.0f}: caiu rápido demais nos últimos dias.", "ticker": ticker})
        try:
            h = analise.horarios(ticker)
        except Exception:
            h = None
        if h:
            avisos.append({"humor": "relogio", "texto": texto_horarios(nome, h), "ticker": ticker})
        try:
            ultima = noticias.buscar(ticker)[:1]
        except Exception:
            ultima = []
        for n in ultima:
            avisos.append({"humor": "noticia", "tipo": "noticia", "texto": f"Notícia nova sobre {nome}: {n['titulo']}",
                           "link": n["link"], "data": n["data"], "ticker": ticker})

    if variacoes:
        media = sum(variacoes) / len(variacoes)
        if media >= 0.005:
            geral = {"humor": "feliz", "texto": f"Seus ativos estão subindo hoje: média de +{_pct(media)}."}
        elif media <= -0.005:
            geral = {"humor": "triste", "texto": f"Seus ativos estão caindo hoje: média de -{_pct(media)}."}
        else:
            geral = {"humor": "calmo", "texto": "Dia calmo: seus ativos quase não se mexeram hoje."}
        avisos.insert(0, geral)
    return jsonify(avisos)


criar_tabelas()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
