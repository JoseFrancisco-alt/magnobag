# Magnobag

Site de estudo com cadastro de usuários, lista de ativos (ações da B3 e cripto) e painel de análise:
gráficos de preço, médias móveis, RSI, backtest de estratégias e a taxa de acerto real de um "palpite" diário.

**Não é recomendação de investimento.** O site mostra dados e resultados passados, não sinais de compra ou venda.

## Visual

Design system escuro, estilo dashboard SaaS. Cores, fontes e espaçamentos ficam em `:root`, no começo
de `static/style.css`. Fontes: Clash Display (títulos) e General Sans (texto), do Fontshare, e Geist Mono
(números). Microinterações em `static/ui.js`: blocos que surgem do desfoque ao rolar e cartões que inclinam
com o mouse. Tudo respeita a opção de "reduzir movimento" do sistema.

Referências usadas: SaaSFrame, Fontshare, Inspotype, Refero Styles, Godly, Awwwards, Brik, Inspora,
Spell UI (Blur Reveal, Tilt Card, Animated Gradient) e Jitter.

## Como rodar

```bash
pip install flask pandas yfinance
python site/app.py
```

Abra http://127.0.0.1:5000 e crie uma conta. Para contas grátis e de dono, copie os arquivos `contas_*.exemplo.txt` tirando o `.exemplo`.


## Estrutura

| Arquivo | O que faz |
|---|---|
| `app.py` | Rotas do site (cadastro, login, painel, favoritos) e a API que alimenta os gráficos |
| `analise.py` | Baixa os preços (yfinance), calcula indicadores e roda os backtests |
| `templates/` | Páginas HTML (Jinja) |
| `static/ativo.js` | Desenha os gráficos com Chart.js |
| `static/style.css` | Visual (modo claro e escuro automáticos) |

## Assinatura (R$ 4,00/mês) e contas grátis

| | Plano grátis (degustação) | Assinatura |
|---|---|---|
| Ativos acompanhados | até 2 | ilimitado |
| Gráfico de preço | 6 meses | 5 anos |
| Notícias por ativo | 3 | todas |
| RSI, backtest e taxa de acerto | bloqueado | ✓ |
| Simulador de gale | bloqueado | ✓ |

Os limites ficam no começo do `app.py` (`GRATIS_MAX_ATIVOS`, `GRATIS_DIAS_GRAFICO`, `GRATIS_MAX_NOTICIAS`)
e o preço em `PRECO_ASSINATURA`. Os limites valem também na API, não só na tela.

**Contas grátis:** coloque os e-mails em `contas_gratis.txt`, um por linha, exatamente como foram
usados no cadastro. Essas contas entram sem pagar.

**Pagamento:** hoje o botão "Assinar" é um **pagamento de teste**. Ele só funciona com o site em modo
debug ou com `PAGAMENTO_TESTE=1`, e libera o acesso sem cobrar nada. Para cobrar de verdade: criar uma
conta no Mercado Pago (ou Stripe), trocar a rota `/assinar` para abrir o checkout deles e marcar
`premium = 1` só quando o webhook de pagamento aprovado chegar.

## Mascote do dono (Mimikyu em pixel art)

Só as contas em `contas_dono.txt` veem o mascote no canto inferior direito (a trava é no servidor:
`/api/mascote` responde 403 para os outros). A cada 5 minutos ele busca avisos sobre os ativos do dono:
média do dia subindo/caindo, quedas e altas acima de 2%, cruzamento das médias, RSI esticado, notícia nova
e os horários de cada ativo (quando mais se mexe, quando fica parado e se algum horário sobe mais que o acaso).
Ele muda de cara conforme o aviso (calmo, feliz, triste, alerta) e uma bolinha vermelha indica novidade.
O desenho fica em `static/mascote.js` (`DESENHO`, 28x28, gerado por `tools/gerar_mascote.py`).
Para usar uma imagem própria, coloque `static/mascote.gif` (ou `.png`/`.webp`): ela substitui o desenho
e o humor aparece num selinho (📈 📉 ❗ 📰 ⏰). Ele avisa fatos, não dá ordens de compra ou venda.

## Notícias

`noticias.py` busca as manchetes dos últimos 7 dias no RSS do Google News (só título, fonte e link).
Elas aparecem na aba **Notícias** (todos os seus ativos juntos, com filtro) e no fim da página de cada ativo.

## Segurança

- Senhas guardadas só como hash; consultas SQL com parâmetros (sem SQL injection).
- **Token CSRF** em todo formulário: outro site não consegue enviar formulários em nome de quem está logado.
- **Limite de login**: 5 senhas erradas (por IP ou por e-mail) bloqueiam novas tentativas por 15 minutos.
- Cabeçalhos de segurança (anti-iframe, anti-sniffing, HSTS quando `HTTPS=1`).
- Limites do plano grátis e funções do dono checados no servidor, não só na tela.

## No ar (Vercel + Supabase)

**Site:** https://magnobag.vercel.app (plano Hobby da Vercel, região São Paulo).
Cada `git push` na branch `main` publica sozinho.

- Banco: Supabase, organização/projeto **magnobag** (São Paulo, Data API desligada). Tabelas em
  `supabase/schema.sql`, com RLS ligado e sem políticas de propósito (a API pública não lê nada;
  só o site, com a senha do banco, acessa).
- Variáveis na Vercel: `DATABASE_URL`, `SECRET_KEY`, `HTTPS=1`, `CONTAS_DONO` (e `CONTAS_GRATIS`, se quiser).
- **Trocou a senha do banco?** Cada "Reset password" no Supabase invalida a anterior. Rode
  `python site/tools/testar_banco.py` (lê a senha copiada, testa e já copia o `DATABASE_URL` pronto),
  cole na Vercel e faça um novo deploy.
- Plano Hobby é só para uso não comercial: ao começar a cobrar assinaturas, passe para o Pro.

## Colocar no ar (outra hospedagem)

Desenvolvimento (no seu computador): `python site/app.py`.
No ar: `python site/servidor.py` (servidor waitress, **sem** modo debug). Precisa das variáveis:

| Variável | Valor |
|---|---|
| `SECRET_KEY` | texto longo e aleatório (o servidor não sobe sem ela) |
| `HTTPS` | `1` quando o site estiver em https |
| `PAGAMENTO_TESTE` | **não definir** no ar (o servidor se recusa a subir com ela) |

Dependências: `pip install -r site/requirements.txt`.
Atenção ao banco: o `radar.db` precisa ficar num disco que não se apaga a cada deploy
(volume persistente) ou ser trocado por PostgreSQL (ex.: Supabase).
