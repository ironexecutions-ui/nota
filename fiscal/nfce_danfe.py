from fpdf import FPDF
from datetime import datetime
import qrcode
import tempfile
import os


def log(msg):
    print(f"[NFCe-DANFE][{datetime.now().strftime('%H:%M:%S')}] {msg}")


def gerar_danfe_nfce(
    emitente,
    chave,
    numero,
    serie,
    total,
    qr_code_url
):
    """
    Gera DANFE NFC-e simplificado (modelo térmico)
    """

    log("===== INÍCIO GERAÇÃO DANFE NFC-e =====")

    try:
        log(f"Emitente: {emitente.get('razao_social')}")
        log(f"NFC-e nº {numero} | Série {serie}")
        log(f"Total: R$ {total:.2f}")

        pdf = FPDF(unit="mm", format=(80, 200))
        pdf.set_auto_page_break(auto=True, margin=5)
        pdf.add_page()

        pdf.set_font("Courier", size=8)

        # ===============================
        # CABEÇALHO
        # ===============================
        log("Gerando cabeçalho do DANFE")

        pdf.multi_cell(0, 4, emitente["razao_social"], align="C")
        pdf.multi_cell(0, 4, f"CNPJ: {emitente['cnpj']}", align="C")
        pdf.ln(2)

        # ===============================
        # IDENTIFICAÇÃO
        # ===============================
        log("Inserindo identificação da NFC-e")

        pdf.cell(0, 4, f"NFC-e Nº {numero} Série {serie}", ln=True)
        pdf.cell(
            0,
            4,
            f"Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            ln=True
        )

        pdf.ln(2)
        pdf.cell(0, 4, "-" * 32, ln=True)

        # ===============================
        # TOTAL
        # ===============================
        log("Inserindo total da NFC-e")

        pdf.cell(0, 5, f"TOTAL R$: {total:.2f}", ln=True)

        pdf.ln(2)
        pdf.cell(0, 4, "-" * 32, ln=True)

        # ===============================
        # QR CODE
        # ===============================
        log("Gerando QR Code da NFC-e")

        if not qr_code_url:
            raise Exception("QR Code URL não informada")

        qr_img = qrcode.make(qr_code_url)

        tmp_qr = os.path.join(tempfile.gettempdir(), "qr_nfce.png")
        qr_img.save(tmp_qr)

        if not os.path.exists(tmp_qr):
            raise Exception("Falha ao gerar imagem do QR Code")

        pdf.image(tmp_qr, x=15, w=50)

        pdf.ln(52)

        log("QR Code inserido no DANFE")

        # ===============================
        # CHAVE E TEXTO LEGAL
        # ===============================
        log("Inserindo chave de acesso")

        pdf.multi_cell(0, 4, "Chave de acesso:", align="C")
        pdf.multi_cell(0, 4, chave, align="C")

        pdf.ln(2)
        pdf.multi_cell(
            0,
            4,
            "Consulte pela chave de acesso em:\n"
            "www.sistema.fazenda.sp.gov.br",
            align="C"
        )

        log("===== FIM GERAÇÃO DANFE NFC-e =====")
        return pdf

    except Exception as e:
        log("ERRO AO GERAR DANFE NFC-e")
        log(str(e))
        raise
