"""
Lê contatos cadastrados no Supabase e envia mensagem de WhatsApp
via Z-API para até MAX_CONTATOS números diferentes.

Uso:
    python main.py
"""

import os
import sys
import logging
import requests
from dotenv import load_dotenv
from supabase import create_client

# Carrega as variáveis do arquivo .env
load_dotenv()

# Configuração global de logs para exibir data, hora, nível e a mensagem
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Recuperação das variáveis de ambiente
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ZAPI_INSTANCE_ID = os.getenv("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

# Tratamento seguro caso a conversão de MAX_CONTATOS falhe
try:
    MAX_CONTATOS = int(os.getenv("MAX_CONTATOS", 3))
except ValueError:
    logger.warning("Valor de MAX_CONTATOS inválido no .env. Usando o padrão: 3")
    MAX_CONTATOS = 3


def checar_env():
    # garante que nenhuma variável obrigatória ficou faltando
    obrigatorias = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "ZAPI_INSTANCE_ID": ZAPI_INSTANCE_ID,
        "ZAPI_TOKEN": ZAPI_TOKEN,
    }
    faltando = [k for k, v in obrigatorias.items() if not v]
    if faltando:
        logger.error("Faltam variáveis no .env: %s", ", ".join(faltando))
        sys.exit(1)


def buscar_contatos(supabase, limite):
    # busca os contatos na tabela 'contatos', já limitando a quantidade
    try:
        resp = (
            supabase.table("contatos")
            .select("nome, telefone")
            .order("id")
            .limit(limite)
            .execute()
        )
        return resp.data or []
    except Exception:
        logger.exception("Erro ao buscar contatos no Supabase")
        return []


def enviar_mensagem(telefone, mensagem):
    # Monta a requisição e envia a mensagem via Z-API
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    headers = {"Content-Type": "application/json"}
    if ZAPI_CLIENT_TOKEN:
        headers["Client-Token"] = ZAPI_CLIENT_TOKEN

    # Estrutura plana de payload compatível com a rota /send-text da Z-API
    payload = {
        "phone": telefone,
        "message": mensagem
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        
        # loga a resposta da Z-API (inclui os IDs de protocolo da mensagem)
        logger.info("Mensagem enviada para %s | resposta: %s", telefone, resp.text)
        return True
    
    except requests.exceptions.RequestException:
        logger.exception("Falha ao enviar mensagem para %s", telefone)
        return False


def main():
    # Inicializa validando as configurações
    checar_env()

    logger.info("Conectando ao Supabase...")
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        logger.exception("Erro ao conectar no Supabase. Verifique SUPABASE_URL e SUPABASE_KEY.")
        sys.exit(1)

    logger.info("Buscando até %s contato(s)...", MAX_CONTATOS)
    contatos = buscar_contatos(supabase, MAX_CONTATOS)

    if not contatos:
        logger.warning("Nenhum contato encontrado.")
        return

    logger.info("Encontrados %s contato(s). Iniciando envio...", len(contatos))
    sucesso = falha = 0
    
    # Envia a mensagem pra cada contato, se um falhar, os outros continuam
    for contato in contatos:
        nome = (contato.get("nome") or "").strip() or "amigo(a)"
        telefone = contato.get("telefone", "").strip()

        # Ignora registros incompletos vindos da tabela do banco de dados
        if not telefone:
            logger.warning("Contato '%s' sem telefone, pulando.", nome)
            falha += 1
            continue

        mensagem = f"Olá, {nome} tudo bem com você?"
        if enviar_mensagem(telefone, mensagem):
            sucesso += 1
        else:
            falha += 1

    logger.info("Concluído. Sucesso: %s | Falhas: %s", sucesso, falha)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Erro inesperado durante a execução.")
        sys.exit(1)