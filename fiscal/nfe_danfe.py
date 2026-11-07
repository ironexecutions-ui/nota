from fpdf import FPDF
from datetime import datetime
from pathlib import Path
import re


def _num(valor):
    return re.sub(r"\D", "", str(valor or ""))


def _texto(valor):
    texto = str(valor or "").strip()
    return texto.encode("latin-1", "replace").decode("latin-1")


def _moeda(valor):
    return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_danfe_nfe(dados, chave, protocolo, caminho_saida):
    """
    Gera uma representação auxiliar A4 do DANFE da NF-e autorizada.
    O XML autorizado continua sendo o documento fiscal principal.
    """
    comercio = dados["comercio"]
    fiscal = dados["fiscal"]
    venda = dados["venda"]
    destinatario = dados["destinatario"]
    itens = dados["itens"]
    numero = dados["numero_nfe"]
    serie = fiscal["serie_nfe"]

    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 8, "DANFE - DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRONICA", ln=True, align="C")
    pdf.set_font("Arial", "", 8)
    pdf.cell(0, 5, "Representacao grafica da NF-e, consulte a validade pela chave de acesso.", ln=True, align="C")
    pdf.ln(3)

    pdf.set_font("Arial", "B", 10)
    pdf.cell(125, 8, _texto(fiscal.get("razao_social")), border=1)
    pdf.set_font("Arial", "", 8)
    pdf.cell(65, 8, f"NF-e: {numero}  Serie: {serie}", border=1, ln=True)
    pdf.cell(125, 7, _texto(comercio.get("rua")) + ", " + _texto(comercio.get("numero")), border=1)
    pdf.cell(65, 7, "CNPJ: " + _num(comercio.get("cnpj")), border=1, ln=True)
    pdf.cell(125, 7, _texto(comercio.get("bairro")) + " / " + _texto(comercio.get("cidade")) + " - " + _texto(comercio.get("estado")), border=1)
    pdf.cell(65, 7, "IE: " + _num(fiscal.get("inscricao_estadual")), border=1, ln=True)
    pdf.ln(3)

    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 7, "DESTINATARIO", border=1, ln=True)
    pdf.set_font("Arial", "", 8)
    pdf.cell(125, 7, _texto(destinatario.get("nome")), border=1)
    pdf.cell(65, 7, "CPF/CNPJ: " + _num(destinatario.get("documento")), border=1, ln=True)
    endereco = (
        _texto(destinatario.get("logradouro")) + ", "
        + _texto(destinatario.get("numero")) + " "
        + _texto(destinatario.get("complemento"))
    )
    pdf.cell(125, 7, endereco, border=1)
    pdf.cell(65, 7, "CEP: " + _num(destinatario.get("cep")), border=1, ln=True)
    pdf.cell(125, 7, _texto(destinatario.get("bairro")) + " / " + _texto(destinatario.get("municipio")) + " - " + _texto(destinatario.get("uf")), border=1)
    pdf.cell(65, 7, "Emissao: " + datetime.now().strftime("%d/%m/%Y %H:%M"), border=1, ln=True)
    pdf.ln(3)

    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 7, "DADOS DA NF-e", border=1, ln=True)
    pdf.set_font("Arial", "", 8)
    pdf.multi_cell(0, 6, "CHAVE DE ACESSO: " + str(chave), border=1)
    pdf.multi_cell(0, 6, "PROTOCOLO DE AUTORIZACAO: " + str(protocolo), border=1)
    pdf.ln(3)

    pdf.set_font("Arial", "B", 8)
    pdf.cell(0, 7, "DADOS DOS PRODUTOS / SERVICOS", border=1, ln=True)
    widths = [12, 75, 22, 25, 27, 29]
    headers = ["Item", "Descricao", "Qtd.", "Un.", "V. Unit.", "V. Total"]
    for width, label in zip(widths, headers):
        pdf.cell(width, 7, label, border=1, align="C")
    pdf.ln()

    pdf.set_font("Arial", "", 7)
    for idx, item in enumerate(itens, 1):
        nome = _texto(item.get("nome"))
        if len(nome) > 42:
            nome = nome[:39] + "..."
        vals = [
            str(idx),
            nome,
            f"{float(item.get('quantidade') or 0):.4f}",
            _texto(item.get("unidade_fiscal") or "UN"),
            _moeda(item.get("valor_unitario_fiscal")),
            _moeda(item.get("valor_total_fiscal")),
        ]
        for width, value in zip(widths, vals):
            pdf.cell(width, 7, value, border=1, align="L" if value == nome else "C")
        pdf.ln()

    pdf.ln(3)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 9, "VALOR TOTAL DA NF-e: " + _moeda(dados.get("total_nf")), border=1, ln=True, align="R")
    pdf.set_font("Arial", "", 8)
    pdf.multi_cell(0, 6, "Documento auxiliar. O XML autorizado e a consulta da chave de acesso sao a referencia fiscal da operacao.")
    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(caminho_saida))
    return str(caminho_saida)
