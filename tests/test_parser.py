import importlib.util
import os
from unittest.mock import MagicMock

import pytest

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "dmarc-exporter.py")
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "google_report.xml")

# O nome do arquivo tem hífen, então o módulo é carregado pelo caminho
spec = importlib.util.spec_from_file_location("dmarc_exporter", SRC)
dmarc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dmarc)


@pytest.fixture
def records():
    return dmarc.processar_xml(FIXTURE, email_date=None)


def test_um_registro_por_record(records):
    assert len(records) == 2


def test_metadados_e_politica(records):
    r = records[0]
    assert r["rm_orgname"] == "google.com"
    assert r["rm_reportid"] == "12345678901234567890"
    assert r["policy_published_domain"] == "example.org"
    assert r["policy_published_policy"] == "quarantine"
    assert r["policy_published_subdomain_policy"] == "none"
    assert r["policy_published_percent"] == 100
    assert r["report_date"] == r["date_begin"].date().isoformat()


def test_resultados_de_autenticacao(records):
    ok, falha = records
    assert (ok["source_ip"], ok["count"]) == ("203.0.113.10", 42)
    assert (ok["auth_dkim_result"], ok["auth_dkim_selector"], ok["auth_spf_result"]) == ("pass", "mail", "pass")

    # Registro sem bloco <dkim> em auth_results
    assert (falha["source_ip"], falha["count"]) == ("198.51.100.7", 3)
    assert falha["policy_evaluated_disposition"] == "quarantine"
    assert falha["auth_dkim_domain"] is None and falha["auth_dkim_result"] is None
    assert (falha["auth_spf_domain"], falha["auth_spf_result"]) == ("spoofer.example", "fail")


def conn_com_relatorio(existente):
    """Conexão falsa: a consulta de duplicidade devolve `existente`."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,) if existente else None
    return conn


def test_insere_relatorio_novo_em_lote(records):
    conn = conn_com_relatorio(existente=False)
    dmarc.inserir_no_db(conn, records)

    executemany = conn.cursor.return_value.executemany
    executemany.assert_called_once()
    assert len(executemany.call_args.args[1]) == 2
    conn.commit.assert_called_once()


def test_ignora_relatorio_ja_importado(records):
    conn = conn_com_relatorio(existente=True)
    dmarc.inserir_no_db(conn, records)

    conn.cursor.return_value.executemany.assert_not_called()
    conn.commit.assert_not_called()
