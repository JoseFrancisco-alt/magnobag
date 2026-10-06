"""Roda o Magnobag em produção (no ar), com um servidor de verdade e SEM modo debug.

No computador, para desenvolver, continue usando:  python site/app.py
Na hospedagem, o comando de início é:              python site/servidor.py

Variáveis de ambiente usadas no ar:
  SECRET_KEY   chave longa e aleatória (obrigatória)
  HTTPS=1      quando o site estiver em https (a hospedagem normalmente já dá)
  PORT         porta (a hospedagem define sozinha)
Nunca defina PAGAMENTO_TESTE no ar: ele libera a assinatura sem cobrar.
"""
import os
import sys

from waitress import serve

from app import app

if __name__ == "__main__":
    if not os.environ.get("SECRET_KEY"):
        sys.exit("Defina a variável SECRET_KEY antes de colocar o site no ar.")
    if os.environ.get("PAGAMENTO_TESTE") == "1":
        sys.exit("PAGAMENTO_TESTE=1 libera assinatura de graça. Remova essa variável no ar.")
    porta = int(os.environ.get("PORT", 8000))
    print(f"Magnobag no ar na porta {porta}")
    serve(app, host="0.0.0.0", port=porta)
