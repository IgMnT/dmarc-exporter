import imaplib
import gzip
import os
import xml.etree.ElementTree as ET
import pandas as pd
import email
import time
import zipfile
import psycopg2
import datetime
import glob
from dotenv import load_dotenv

if os.path.isfile('.env'):
    load_dotenv()

IMAP_SERVER = os.getenv("DMARC_MAIL_SERVER")
IMAP_PORT = os.getenv("DMARC_MAIL_PORT")
USERNAME = os.getenv("DMARC_MAIL_USER")
PASSWORD = os.getenv("DMARC_MAIL_PASSWORD")
download_folder = '/app/dmarc-zip'
DB_HOST = os.getenv("PG_HOST")
DB_NAME = os.getenv("PG_DATABASE")
DB_USER = os.getenv("PG_USER")
DB_PASSWORD = os.getenv("PG_PASSWORD")
DB_PORT = os.getenv("PG_PORT")



def limpar_pasta():
    files = glob.glob(os.path.join(download_folder, '*'))
    for f in files:
        os.remove(f)
    print("pasta limpa!")



def conectar_db():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    return conn

def descompactar_arquivo_zip(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(download_folder)
        file_names = zip_ref.namelist()  
    print(f"Arquivos {file_names} extraídos.")
    return os.path.join(download_folder, file_names[0])

def descompactar_arquivo_gz(gz_path):
    with gzip.open(gz_path, 'rb') as f_in:
        file_name = os.path.basename(gz_path).replace('.gz', '')
        output_path = os.path.join(download_folder, file_name)
        with open(output_path, 'wb') as f_out:
            f_out.write(f_in.read())
    return output_path

def processar_xml(xml_path, email_date):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    records = []
    
    # Report Metadata
    rm_orgname = root.find('./report_metadata/org_name').text
    rm_email = root.find('./report_metadata/email').text
    rm_reportid = root.find('./report_metadata/report_id').text
    
    try:
        date_begin = datetime.datetime.fromtimestamp(int(root.find('./report_metadata/date_range/begin').text))
        date_end = datetime.datetime.fromtimestamp(int(root.find('./report_metadata/date_range/end').text))
        # Extrair apenas a data (sem horário) do date_begin
        report_date = date_begin.date().isoformat()
    except (ValueError, OSError) as e:
        print(f"Erro ao converter a data: {e}")
        return records

    # Policy Published
    policy_published = root.find('./policy_published')
    policy_published_domain = policy_published.find('./domain').text if policy_published is not None and policy_published.find('./domain') is not None else None
    policy_published_adkim = policy_published.find('./adkim').text if policy_published is not None and policy_published.find('./adkim') is not None else None
    policy_published_aspf = policy_published.find('./aspf').text if policy_published is not None and policy_published.find('./aspf') is not None else None
    policy_published_policy = policy_published.find('./p').text if policy_published is not None and policy_published.find('./p') is not None else None
    
    try:
        policy_published_percent = int(policy_published.find('./pct').text) if policy_published is not None and policy_published.find('./pct') is not None else None
    except (ValueError, TypeError):
        policy_published_percent = None
        print("Erro ao converter percent para inteiro")

    # Tratamento específico para sp (subdomain policy) que pode estar ausente
    sp_element = policy_published.find('./sp') if policy_published is not None else None
    policy_published_subdomain_policy = sp_element.text if sp_element is not None else None

    for record in root.findall('.//record'):
        # Row Info
        row = record.find('./row')
        if row is not None:
            source_ip = row.find('./source_ip').text if row.find('./source_ip') is not None else None
            try:
                count = int(row.find('./count').text) if row.find('./count') is not None else 0
            except (ValueError, TypeError):
                count = 0
                print("Erro ao converter count para inteiro")
            
            # Policy Evaluated
            policy_evaluated = row.find('./policy_evaluated')
            policy_evaluated_disposition = policy_evaluated.find('./disposition').text if policy_evaluated is not None and policy_evaluated.find('./disposition') is not None else None
            policy_evaluated_dkim = policy_evaluated.find('./dkim').text if policy_evaluated is not None and policy_evaluated.find('./dkim') is not None else None
            policy_evaluated_spf = policy_evaluated.find('./spf').text if policy_evaluated is not None and policy_evaluated.find('./spf') is not None else None
        else:
            source_ip = None
            count = 0
            policy_evaluated_disposition = None
            policy_evaluated_dkim = None
            policy_evaluated_spf = None

        # Header From
        identifiers = record.find('./identifiers')
        header_from = identifiers.find('./header_from').text if identifiers is not None and identifiers.find('./header_from') is not None else None

        # Auth Results
        auth_results = record.find('./auth_results')
        if auth_results is not None:
            dkim = auth_results.find('./dkim')
            spf = auth_results.find('./spf')

            auth_dkim_domain = dkim.find('./domain').text if dkim is not None and dkim.find('./domain') is not None else None
            auth_dkim_result = dkim.find('./result').text if dkim is not None and dkim.find('./result') is not None else None
            auth_dkim_selector = dkim.find('./selector').text if dkim is not None and dkim.find('./selector') is not None else None
            
            auth_spf_domain = spf.find('./domain').text if spf is not None and spf.find('./domain') is not None else None
            auth_spf_result = spf.find('./result').text if spf is not None and spf.find('./result') is not None else None
        else:
            auth_dkim_domain = None
            auth_dkim_result = None
            auth_dkim_selector = None
            auth_spf_domain = None
            auth_spf_result = None

        records.append({
            'rm_orgname': rm_orgname,
            'rm_email': rm_email,
            'rm_reportid': rm_reportid,
            'date_begin': date_begin,
            'date_end': date_end,
            'report_date': report_date,  
            'policy_published_domain': policy_published_domain,
            'policy_published_adkim': policy_published_adkim,
            'policy_published_aspf': policy_published_aspf,
            'policy_published_policy': policy_published_policy,
            'policy_published_percent': policy_published_percent,
            'policy_published_subdomain_policy': policy_published_subdomain_policy,
            'source_ip': source_ip,
            'count': count,
            'policy_evaluated_disposition': policy_evaluated_disposition,
            'policy_evaluated_dkim': policy_evaluated_dkim,
            'policy_evaluated_spf': policy_evaluated_spf,
            'header_from': header_from,
            'auth_dkim_domain': auth_dkim_domain,
            'auth_dkim_result': auth_dkim_result,
            'auth_dkim_selector': auth_dkim_selector,
            'auth_spf_domain': auth_spf_domain,
            'auth_spf_result': auth_spf_result
        })
    return records

def criar_tabela_if_not_exists():
    conn = conectar_db()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables 
        WHERE table_name = 'dmarc_reports'
    );
    """)

    exists = cursor.fetchone()[0]

    if not exists:
        create_table_query = """
        CREATE TABLE IF NOT EXISTS dmarc_reports (
            id SERIAL PRIMARY KEY,
            rm_orgname VARCHAR(255),
            rm_email VARCHAR(255),
            rm_reportid VARCHAR(255),
            date_begin TIMESTAMP,
            date_end TIMESTAMP,
            report_date DATE,
            policy_published_domain VARCHAR(255),
            policy_published_adkim VARCHAR(50),
            policy_published_aspf VARCHAR(50),
            policy_published_policy VARCHAR(50),
            policy_published_percent INT,
            policy_published_subdomain_policy VARCHAR(50),
            source_ip VARCHAR(45),
            count INT,
            policy_evaluated_disposition VARCHAR(50),
            policy_evaluated_dkim VARCHAR(50),
            policy_evaluated_spf VARCHAR(50),
            header_from VARCHAR(255),
            auth_dkim_domain VARCHAR(255),
            auth_dkim_result VARCHAR(50),
            auth_dkim_selector VARCHAR(255),
            auth_spf_domain VARCHAR(255),
            auth_spf_result VARCHAR(50) 
        );
        """

        cursor.execute(create_table_query)
        conn.commit()
        print("Tabela 'dmarc_reports' criada pois não existia.")

    cursor.close()
    conn.close()

def inserir_no_db(records):

    criar_tabela_if_not_exists()

    conn = conectar_db()
    cursor = conn.cursor()
    insert_query = """
    INSERT INTO dmarc_reports (
        rm_orgname, rm_email, rm_reportid, 
        date_begin, date_end, report_date,
        policy_published_domain, policy_published_adkim, policy_published_aspf, policy_published_policy, 
        policy_published_percent, policy_published_subdomain_policy, source_ip, 
        count, policy_evaluated_disposition, policy_evaluated_dkim, 
        policy_evaluated_spf, header_from, auth_dkim_domain, 
        auth_dkim_result, auth_dkim_selector, 
        auth_spf_domain, auth_spf_result
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """
    
    for record in records:
        cursor.execute(insert_query, (
            record['rm_orgname'], record['rm_email'], record['rm_reportid'],
            record['date_begin'], record['date_end'], record['report_date'],
            record['policy_published_domain'], record['policy_published_adkim'], record['policy_published_aspf'], record['policy_published_policy'],
            record['policy_published_percent'], record['policy_published_subdomain_policy'], record['source_ip'],
            record['count'], record['policy_evaluated_disposition'], record['policy_evaluated_dkim'],
            record['policy_evaluated_spf'], record['header_from'], record['auth_dkim_domain'],
            record['auth_dkim_result'], record['auth_dkim_selector'],
            record['auth_spf_domain'], record['auth_spf_result']
        ))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Banco de dados atualizado com {len(records)} registros.")

def executarScript():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(USERNAME, PASSWORD)
        print("Login bem-sucedido!")
    except imaplib.IMAP4.error:
        print("Falha no login. Verifique suas credenciais.")
        return

    pasta = "INBOX"
    status, messages = mail.select(pasta)

    if status != "OK":
        print(f"Erro ao selecionar a pasta {pasta}.")
        return
    
    if status != "OK":
        print("Erro ao buscar mensagens não lidas.")
        return

    status, messages = mail.search(None, 'UNSEEN')

    for num in messages[0].split():
        status, msg_data = mail.fetch(num, '(RFC822)')
        raw_email = msg_data[0][1]

        msg = email.message_from_bytes(raw_email)
        email_date = msg['Date']

        for part in msg.walk():
            if part.get_content_disposition() == 'attachment':
                filename = part.get_filename()
                if filename:
                    file_path = os.path.join(download_folder, filename)
                    with open(file_path, 'wb') as f:
                        f.write(part.get_payload(decode=True))
                    print(f"Anexo {file_path} baixado.")

                    if file_path.endswith('.gz'):
                        xml_path = descompactar_arquivo_gz(file_path)
                        records = processar_xml(xml_path, email_date)
                        inserir_no_db(records)

                    else:
                        xml_path = descompactar_arquivo_zip(file_path)
                        records = processar_xml(xml_path, email_date)
                        inserir_no_db(records)
executarScript()
