"""Utilitário de teste: marca como não lidas as mensagens de uma pasta IMAP,
para reprocessar relatórios DMARC. Lê as credenciais do .env."""
import imaplib
import os

from dotenv import load_dotenv

load_dotenv()

DMARC_MAIL_SERVER = os.getenv("DMARC_MAIL_SERVER")
DMARC_MAIL_USER = os.getenv("DMARC_MAIL_USER")
DMARC_MAIL_PASSWORD = os.getenv("DMARC_MAIL_PASSWORD")
DMARC_MAIL_PORT = int(os.getenv("DMARC_MAIL_PORT", "993"))
DMARC_MAIL_FOLDER = os.getenv("DMARC_MAIL_FOLDER", "INBOX")


def marcar_como_nao_lida():
    try:
        mail = imaplib.IMAP4_SSL(DMARC_MAIL_SERVER, DMARC_MAIL_PORT)
        mail.login(DMARC_MAIL_USER, DMARC_MAIL_PASSWORD)
        print("Login bem-sucedido!")
    except imaplib.IMAP4.error:
        print("Falha no login. Verifique suas credenciais.")
        return

    status, _ = mail.select(DMARC_MAIL_FOLDER)
    if status != "OK":
        print(f"Erro ao selecionar a pasta {DMARC_MAIL_FOLDER}.")
        return

    status, messages = mail.search(None, "ALL")
    if status != "OK":
        print("Erro ao buscar mensagens.")
        return

    for num in messages[0].split():
        mail.store(num, "-FLAGS", "\\Seen")
        print(f"Email {num.decode('utf-8')} marcado como não lido.")

    mail.logout()


if __name__ == "__main__":
    marcar_como_nao_lida()
