import imaplib
import os
from dotenv import load_dotenv

if os.path.isfile('.env'):
    load_dotenv()

DMARC_MAIL_SERVER= 'imap.campos.rj.gov.br'
DMARC_MAIL_USER='igormagro'
DMARC_MAIL_PASSWORD='Mudar123'
DMARC_MAIL_PORT=993

def marcar_como_nao_lida():
    try:
        mail = imaplib.IMAP4_SSL(DMARC_MAIL_SERVER, DMARC_MAIL_PORT)
        mail.login(DMARC_MAIL_USER, DMARC_MAIL_PASSWORD)
        print("Login bem-sucedido!")
    except imaplib.IMAP4.error:
        print("Falha no login. Verifique suas credenciais.")
        return

    pasta = '"Infraestrutura de TI do CIDAC&IBk-s Inbox/CORP"'
    status, messages = mail.select(pasta)

    if status != "OK":
        print(f"Erro ao selecionar a pasta {pasta}.")
        return

    status, messages = mail.search(None, 'ALL')

    if status != "OK":
        print("Erro ao buscar mensagens.")
        return

    for num in messages[0].split():
        mail.store(num, '-FLAGS', '\\Seen')
        print(f"Email {num.decode('utf-8')} marcado como não lido.")

    mail.logout()

marcar_como_nao_lida()