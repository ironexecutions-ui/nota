from fpdf import FPDF
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import os
import re
import qrcode
import tempfile


# =========================================================
# CONFIGURAÇÕES
# =========================================================

STORAGE_DIR = Path("/var/www/iron-storage")

COR_AZUL = (24, 48, 82)
COR_AZUL_CLARO = (235, 241, 249)
COR_TEXTO = (38, 48, 62)
COR_CINZA = (105, 116, 132)
COR_BORDA = (210, 218, 229)
COR_BRANCO = (255, 255, 255)


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def _num(valor):
    return re.sub(r"\D", "", str(valor or ""))


def _texto(valor):
    texto = str(valor or "").strip()
    return texto.encode("latin-1", "replace").decode("latin-1")


def _moeda(valor):
    try:
        numero = float(valor or 0)

        return (
            f"R$ {numero:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    except (ValueError, TypeError):
        return "R$ 0,00"


def _quantidade(valor):
    try:
        return (
            f"{float(valor or 0):,.4f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    except (ValueError, TypeError):
        return "0"


def _data_emissao(dados):
    valor = dados.get("data_emissao")

    if not valor:
        return datetime.now().strftime("%d/%m/%Y %H:%M")

    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")

    try:
        return datetime.fromisoformat(
            str(valor).replace("Z", "+00:00")
        ).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(valor)


def _logo_comercio(comercio):
    """
    Localiza a imagem da loja na VPS.

    A coluna imagem guarda uma URL pública:
    https://backend.ironexecutions.com.br/arquivos/imagem.png

    O arquivo físico fica em:
    /var/www/iron-storage/imagem.png
    """

    imagem = str(comercio.get("imagem") or "").strip()

    if not imagem:
        return None

    try:
        nome_arquivo = os.path.basename(
            urlparse(imagem).path
        )

        if not nome_arquivo:
            return None

        caminho = STORAGE_DIR / nome_arquivo

        if caminho.is_file():
            return str(caminho)

        print(
            "[DANFE NF-e] Logo não encontrado:",
            caminho
        )

    except Exception as erro:
        print(
            "[DANFE NF-e] Erro ao localizar logo:",
            repr(erro)
        )

    return None


# =========================================================
# CLASSE PDF
# =========================================================

class DANFENFePDF(FPDF):

    def __init__(self):
        super().__init__("P", "mm", "A4")

        self.set_margins(10, 10, 10)

        self.set_auto_page_break(
            auto=True,
            margin=17
        )

    def header(self):
        self.set_text_color(*COR_TEXTO)

    def footer(self):
        self.set_y(-13)

        self.set_draw_color(*COR_BORDA)
        self.line(10, self.get_y(), 200, self.get_y())

        self.set_y(-11)

        self.set_font("Arial", "", 7)
        self.set_text_color(*COR_CINZA)

        self.cell(
            130,
            5,
            "DANFE | Documento Auxiliar da Nota Fiscal Eletronica"
        )

        self.cell(
            60,
            5,
            f"Pagina {self.page_no()}",
            align="R"
        )

    def titulo_secao(self, titulo):
        self.set_fill_color(*COR_AZUL_CLARO)
        self.set_draw_color(*COR_BORDA)
        self.set_text_color(*COR_AZUL)

        self.set_font("Arial", "B", 8)

        self.cell(
            0,
            7,
            _texto(titulo.upper()),
            border=1,
            ln=True,
            fill=True
        )

    def campo(
        self,
        largura,
        altura,
        rotulo,
        valor,
        destaque=False
    ):
        x = self.get_x()
        y = self.get_y()

        self.set_draw_color(*COR_BORDA)
        self.set_fill_color(*COR_BRANCO)

        self.rect(
            x,
            y,
            largura,
            altura,
            style="DF"
        )

        self.set_xy(x + 2, y + 1)

        self.set_font("Arial", "", 6)
        self.set_text_color(*COR_CINZA)

        self.cell(
            largura - 4,
            3,
            _texto(rotulo.upper())
        )

        self.set_xy(x + 2, y + 5)

        self.set_font(
            "Arial",
            "B" if destaque else "",
            8
        )

        self.set_text_color(
            *COR_AZUL if destaque else COR_TEXTO
        )

        self.cell(
            largura - 4,
            altura - 6,
            _texto(valor)
        )

        self.set_xy(
            x + largura,
            y
        )

    def verificar_espaco(self, altura):
        if self.get_y() + altura > 280:
            self.add_page()
            return True

        return False

    def cabecalho_produtos(self):
        self.set_fill_color(*COR_AZUL)
        self.set_text_color(*COR_BRANCO)
        self.set_draw_color(*COR_AZUL)

        self.set_font("Arial", "B", 7)

        larguras = [10, 76, 22, 18, 32, 32]

        titulos = [
            "ITEM",
            "DESCRICAO",
            "QUANTIDADE",
            "UN.",
            "V. UNITARIO",
            "V. TOTAL"
        ]

        for largura, titulo in zip(larguras, titulos):
            self.cell(
                largura,
                8,
                titulo,
                border=1,
                align="C",
                fill=True
            )

        self.ln()

        self.set_text_color(*COR_TEXTO)


# =========================================================
# GERAR DANFE NF-e
# =========================================================

def gerar_danfe_nfe(
    dados,
    chave,
    protocolo,
    caminho_saida
):
    """
    Gera o DANFE A4 da NF-e autorizada.

    Utiliza os dados comerciais da tabela
    comercios_cadastradas para personalizar
    o documento com o nome e o logo da loja.

    O QR Code inserido no quadro superior contém
    a chave de acesso de 44 dígitos da NF-e.

    Não altera o XML autorizado nem transmite
    novamente a NF-e para a SEFAZ.
    """

    comercio = dados["comercio"]
    fiscal = dados["fiscal"]
    venda = dados["venda"]
    destinatario = dados["destinatario"]
    itens = dados["itens"]

    numero = dados["numero_nfe"]
    serie = fiscal["serie_nfe"]

    pdf = DANFENFePDF()

    pdf.add_page()

    # =====================================================
    # 1. CABEÇALHO PERSONALIZADO DA LOJA
    # =====================================================

    logo = _logo_comercio(comercio)

    x_nome = 12

    if logo:
        try:
            pdf.image(
                logo,
                x=12,
                y=12,
                w=25,
                h=25,
                type=""
            )

            x_nome = 42

        except Exception as erro:
            print(
                "[DANFE NF-e] Erro ao inserir logo:",
                repr(erro)
            )

    nome_loja = (
        comercio.get("loja")
        or fiscal.get("razao_social")
        or "Estabelecimento"
    )

    pdf.set_xy(x_nome, 12)

    pdf.set_font("Arial", "B", 17)
    pdf.set_text_color(*COR_AZUL)

    pdf.cell(
        112,
        8,
        _texto(nome_loja)
    )

    pdf.set_xy(x_nome, 21)

    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(*COR_CINZA)

    pdf.cell(
        112,
        5,
        _texto(fiscal.get("razao_social"))
    )

    pdf.set_xy(x_nome, 27)

    pdf.cell(
        112,
        5,
        "CNPJ: " + _num(comercio.get("cnpj"))
    )

    endereco_emitente = (
        f"{comercio.get('rua') or ''}, "
        f"{comercio.get('numero') or ''} | "
        f"{comercio.get('bairro') or ''}"
    )

    pdf.set_xy(x_nome, 33)

    pdf.cell(
        112,
        5,
        _texto(endereco_emitente)
    )

    # =====================================================
    # 2. QUADRO DA NF-e COM QR CODE
    # =====================================================

    pdf.set_fill_color(*COR_AZUL)
    pdf.set_draw_color(*COR_AZUL)

    pdf.rect(
        158,
        11,
        40,
        29,
        style="DF"
    )

    # O QR Code contém a chave de acesso da NF-e.
    # Ele não substitui o QR Code oficial de consulta da SEFAZ.
    chave_qr = _num(chave)

    if len(chave_qr) != 44:
        raise ValueError(
            "A chave de acesso da NF-e deve conter exatamente 44 dígitos "
            "para gerar o QR Code."
        )

    qr_img = qrcode.make(chave_qr)

    arquivo_qr = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False
    )

    caminho_qr = arquivo_qr.name
    arquivo_qr.close()

    try:
        qr_img.save(caminho_qr)

        pdf.image(
            caminho_qr,
            x=165,
            y=12,
            w=26,
            h=26
        )

    finally:
        if os.path.exists(caminho_qr):
            os.remove(caminho_qr)

    # =====================================================
    # 3. IDENTIFICAÇÃO DO DOCUMENTO
    # =====================================================

    pdf.set_y(45)

    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(*COR_AZUL)

    pdf.cell(
        0,
        7,
        "DANFE",
        align="C",
        ln=True
    )

    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(*COR_CINZA)

    pdf.cell(
        0,
        5,
        "Documento Auxiliar da Nota Fiscal Eletronica",
        align="C",
        ln=True
    )

    pdf.ln(5)

    # =====================================================
    # 4. EMITENTE
    # =====================================================

    pdf.titulo_secao("Identificacao do emitente")

    y = pdf.get_y()

    pdf.set_xy(10, y)

    pdf.campo(
        125,
        13,
        "Nome comercial",
        nome_loja,
        destaque=True
    )

    pdf.campo(
        65,
        13,
        "CNPJ",
        _num(comercio.get("cnpj"))
    )

    pdf.set_xy(10, y + 13)

    pdf.campo(
        95,
        13,
        "Razao social",
        fiscal.get("razao_social")
    )

    pdf.campo(
        45,
        13,
        "Inscricao estadual",
        _num(fiscal.get("inscricao_estadual"))
    )

    pdf.campo(
        50,
        13,
        "Serie / Numero",
        f"{serie} / {numero}"
    )

    pdf.set_xy(10, y + 26)

    endereco = (
        f"{comercio.get('rua') or ''}, "
        f"{comercio.get('numero') or ''}, "
        f"{comercio.get('bairro') or ''}"
    )

    pdf.campo(
        125,
        13,
        "Endereco",
        endereco
    )

    cidade = (
        f"{comercio.get('cidade') or ''} / "
        f"{comercio.get('estado') or ''}"
    )

    pdf.campo(
        65,
        13,
        "Municipio / UF",
        cidade
    )

    pdf.set_y(y + 44)

    # =====================================================
    # 5. DESTINATARIO
    # =====================================================

    pdf.titulo_secao("Dados do destinatario")

    y = pdf.get_y()

    pdf.set_xy(10, y)

    pdf.campo(
        125,
        13,
        "Nome / Razao social",
        destinatario.get("nome"),
        destaque=True
    )

    pdf.campo(
        65,
        13,
        "CPF / CNPJ",
        _num(destinatario.get("documento"))
    )

    pdf.set_xy(10, y + 13)

    endereco_destinatario = (
        f"{destinatario.get('logradouro') or ''}, "
        f"{destinatario.get('numero') or ''} "
        f"{destinatario.get('complemento') or ''}"
    )

    pdf.campo(
        125,
        13,
        "Endereco",
        endereco_destinatario
    )

    pdf.campo(
        65,
        13,
        "CEP",
        _num(destinatario.get("cep"))
    )

    pdf.set_xy(10, y + 26)

    municipio_destinatario = (
        f"{destinatario.get('municipio') or ''} / "
        f"{destinatario.get('uf') or ''}"
    )

    pdf.campo(
        125,
        13,
        "Municipio / UF",
        municipio_destinatario
    )

    pdf.campo(
        65,
        13,
        "Data de emissao",
        _data_emissao(dados)
    )

    pdf.set_y(y + 44)

    # =====================================================
    # 6. CHAVE DE ACESSO E PROTOCOLO
    # =====================================================

    pdf.titulo_secao("Identificacao da NF-e")

    y = pdf.get_y()

    pdf.set_xy(10, y)

    pdf.campo(
        190,
        14,
        "Chave de acesso",
        " ".join(
            str(chave)[i:i + 4]
            for i in range(0, len(str(chave)), 4)
        ),
        destaque=True
    )

    pdf.set_xy(10, y + 14)

    pdf.campo(
        190,
        14,
        "Protocolo de autorizacao de uso",
        protocolo
    )

    pdf.set_y(y + 33)

    # =====================================================
    # 7. PRODUTOS E SERVIÇOS
    # =====================================================

    pdf.titulo_secao("Dados dos produtos / servicos")

    pdf.cabecalho_produtos()

    larguras = [10, 76, 22, 18, 32, 32]

    for idx, item in enumerate(itens, 1):

        nome = _texto(item.get("nome"))

        quantidade = _quantidade(
            item.get("quantidade")
        )

        unidade = _texto(
            item.get("unidade_fiscal") or "UN"
        )

        valor_unitario = _moeda(
            item.get("valor_unitario_fiscal")
        )

        valor_total = _moeda(
            item.get("valor_total_fiscal")
        )

        # Altura dinâmica conforme o tamanho da descrição.
        altura_descricao = max(
            8,
            len(nome) // 75 * 4 + 8
        )

        if pdf.get_y() + altura_descricao > 277:
            pdf.add_page()
            pdf.titulo_secao("Continuação dos produtos")
            pdf.cabecalho_produtos()

        x_inicial = 10
        y_inicial = pdf.get_y()

        pdf.set_draw_color(*COR_BORDA)

        pdf.set_fill_color(
            247 if idx % 2 == 0 else 255,
            249 if idx % 2 == 0 else 255,
            252 if idx % 2 == 0 else 255
        )

        pdf.rect(
            x_inicial,
            y_inicial,
            190,
            altura_descricao,
            style="DF"
        )

        pdf.set_font("Arial", "", 7)
        pdf.set_text_color(*COR_TEXTO)

        # Número do item.
        pdf.set_xy(x_inicial, y_inicial)

        pdf.cell(
            larguras[0],
            altura_descricao,
            str(idx),
            align="C"
        )

        # Descrição completa.
        pdf.set_xy(
            x_inicial + larguras[0] + 1,
            y_inicial + 2
        )

        pdf.multi_cell(
            larguras[1] - 2,
            4,
            nome
        )

        # Demais colunas.
        valores = [
            quantidade,
            unidade,
            valor_unitario,
            valor_total
        ]

        posicao_x = (
            x_inicial
            + larguras[0]
            + larguras[1]
        )

        for largura, valor in zip(
            larguras[2:],
            valores
        ):
            pdf.set_xy(
                posicao_x,
                y_inicial
            )

            pdf.cell(
                largura,
                altura_descricao,
                valor,
                align="C"
            )

            posicao_x += largura

        # Separadores verticais.
        posicao_x = x_inicial

        for largura in larguras[:-1]:
            posicao_x += largura

            pdf.line(
                posicao_x,
                y_inicial,
                posicao_x,
                y_inicial + altura_descricao
            )

        pdf.set_y(
            y_inicial + altura_descricao
        )

    # =====================================================
    # 8. TOTAL DA NOTA
    # =====================================================

    pdf.ln(5)

    pdf.verificar_espaco(18)

    pdf.set_fill_color(*COR_AZUL_CLARO)
    pdf.set_draw_color(*COR_BORDA)

    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*COR_AZUL)

    pdf.cell(
        125,
        14,
        "VALOR TOTAL DA NF-e",
        border=1,
        fill=True
    )

    pdf.set_font("Arial", "B", 14)

    pdf.cell(
        65,
        14,
        _moeda(dados.get("total_nf")),
        border=1,
        fill=True,
        align="R",
        ln=True
    )

    # =====================================================
    # 9. CONTATO DA LOJA
    # =====================================================

    contato = []

    if comercio.get("email"):
        contato.append(str(comercio["email"]))

    if comercio.get("celular"):
        contato.append(str(comercio["celular"]))

    if contato:

        pdf.ln(6)

        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(*COR_AZUL)

        pdf.cell(
            0,
            5,
            _texto(nome_loja),
            ln=True
        )

        pdf.set_font("Arial", "", 7)
        pdf.set_text_color(*COR_CINZA)

        pdf.cell(
            0,
            4,
            _texto(" | ".join(contato)),
            ln=True
        )

    # =====================================================
    # 10. SALVAR PDF
    # =====================================================

    caminho = Path(caminho_saida)

    caminho.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    pdf.output(str(caminho))

    print(
        "[DANFE NF-e] PDF profissional gerado:",
        caminho
    )

    return str(caminho)
