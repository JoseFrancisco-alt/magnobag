"""Monta e testa o endereço do banco (DATABASE_URL) para colar na Vercel.

Uso:  python site/tools/testar_banco.py
1. Copie a senha no Supabase (Reset password -> Generate -> copiar -> Reset password).
2. Rode este programa e só aperte Enter: ele lê a senha direto da área de transferência
   (não precisa colar nada, e a senha não aparece na tela).
3. Se funcionar, a linha completa já fica copiada: é só dar Ctrl+V no DATABASE_URL da Vercel.
"""
import subprocess
import sys
from urllib.parse import quote

PROJETO = "yeskyxmiadvvwxdkgoeg"
HOST = "aws-1-sa-east-1.pooler.supabase.com:6543"


def ler_area_de_transferencia():
    resultado = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                               capture_output=True, text=True, encoding="utf-8")
    return (resultado.stdout or "").strip()


def copiar(texto):
    subprocess.run("clip", input=texto.encode("utf-16-le"), check=True)


input("Copie a senha no Supabase e aperte Enter aqui (não precisa colar nada)... ")
senha = ler_area_de_transferencia()

# confere o que veio, sem mostrar a senha
if not senha:
    sys.exit("A área de transferência está vazia. Copie a senha no Supabase e tente de novo.")
if senha.startswith("postgres"):
    sys.exit("O que está copiado é um endereço, não a senha. Copie só a senha no Supabase.")
if "\n" in senha or " " in senha:
    sys.exit("O que está copiado tem espaço ou várias linhas: não parece a senha. Copie de novo no Supabase.")
tipos = []
if any(c.isupper() for c in senha): tipos.append("maiúsculas")
if any(c.islower() for c in senha): tipos.append("minúsculas")
if any(c.isdigit() for c in senha): tipos.append("números")
if any(not c.isalnum() for c in senha): tipos.append("símbolos")
print(f"Li uma senha de {len(senha)} caracteres ({', '.join(tipos)}).")
if len(senha) < 12:
    sys.exit("Senha curta demais para ser a gerada pelo Supabase. Copie de novo pelo botão de copiar.")

url = f"postgresql://postgres.{PROJETO}:{quote(senha, safe='')}@{HOST}/postgres"
print("Testando conexão com o banco...")
try:
    import psycopg
    with psycopg.connect(url, prepare_threshold=None, connect_timeout=10) as conexao:
        conexao.execute("select 1")
except Exception as erro:
    mensagem = str(erro).replace(senha, "***")
    if "password authentication failed" in mensagem:
        print("\nO banco RECUSOU essa senha: ela não é a senha atual do Supabase.")
        print("Se você acabou de fazer o Reset, espere uns minutos e tente de novo (Enter).")
    else:
        print("\nNão conectou:", mensagem.splitlines()[0])
    sys.exit(1)

copiar(url)
print("\nFUNCIONOU! A linha completa do DATABASE_URL já está copiada.")
print("Na Vercel: DATABASE_URL -> Edit -> clique no campo Value -> Ctrl+V -> Save.")
