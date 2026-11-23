from fpdf import FPDF
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import os
import re
import qrcode
import tempfile


# =========================================================
# IDENTIDADE VISUAL
# =========================================================

STORAGE_DIR = Path("/var/www/iron-storage")

# Paleta institucional: azul profundo, azul aço e tons neutros.
COR_NAVY = (15, 37, 64)
COR_BLUE = (32, 69, 108)
COR_BLUE_LIGHT = (235, 241, 248)
COR_INK = (35, 45, 58)
COR_MUTED = (105, 117, 132)
COR_LINE = (205, 214, 224)
COR_SOFT = (247, 249, 252)
COR_WHITE = (255, 255, 255)
COR_ACCENT = (48, 111, 166)


# =========================================================
# FUNCOES AUXILIARES
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
    A coluna imagem contem uma URL publica.
    O arquivo fisico correspondente fica em STORAGE_DIR.
    """
    imagem = str(comercio.get("imagem") or "").strip()

    if not imagem:
        return None

    try:
        nome_arquivo = os.path.basename(urlparse(imagem).path)
        if not nome_arquivo:
            return None

        caminho = STORAGE_DIR / nome_arquivo
        if caminho.is_file():
            return str(caminho)

        print("[DANFE NF-e] Logo nao encontrado:", caminho)

    except Exception as erro:
        print("[DANFE NF-e] Erro ao localizar logo:", repr(erro))

    return None


def _texto_ajustado(pdf, texto, largura, fonte="Arial", estilo="", tamanho=7):
    """Reduz a fonte somente quando necessario para caber no campo."""
    texto = _texto(texto)
    tamanho_atual = tamanho

    while tamanho_atual > 5:
        pdf.set_font(fonte, estilo, tamanho_atual)
        if pdf.get_string_width(texto) <= largura:
            break
        tamanho_atual -= 0.2

    return texto, tamanho_atual


def _quebrar_linhas(pdf, texto, largura):
    """Quebra o texto por palavras, sem descartar a descricao."""
    texto = _texto(texto)
    palavras = texto.split()
    linhas = []
    linha = ""

    for palavra in palavras:
        teste = palavra if not linha else f"{linha} {palavra}"

        if pdf.get_string_width(teste) <= largura:
            linha = teste
            continue

        if linha:
            linhas.append(linha)
            linha = ""

        # Trata tambem palavras isoladas maiores que a coluna.
        if pdf.get_string_width(palavra) > largura:
            parte = ""
            for caractere in palavra:
                if pdf.get_string_width(parte + caractere) <= largura:
                    parte += caractere
                else:
                    if parte:
                        linhas.append(parte)
                    parte = caractere
            linha = parte
        else:
            linha = palavra

    if linha:
        linhas.append(linha)

    return linhas or [""]


# =========================================================
# CLASSE PDF
# =========================================================

class DANFENFePDF(FPDF):

    def __init__(self):
        super().__init__("P", "mm", "A4")
        self.set_margins(10, 10, 10)
        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()

    def header(self):
        # Faixa superior repetida em todas as paginas.
        self.set_fill_color(*COR_NAVY)
        self.rect(0, 0, 210, 3, style="F")

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*COR_LINE)
        self.set_line_width(0.25)
        self.line(10, self.get_y(), 200, self.get_y())

        self.set_y(-11)
        self.set_font("Arial", "", 6.5)
        self.set_text_color(*COR_MUTED)
        self.cell(
            145, 4,
            "DANFE | Documento Auxiliar da Nota Fiscal Eletronica",
            align="L"
        )
        self.cell(
            45, 4,
            f"Pagina {self.page_no()}/{{nb}}",
            align="R"
        )

    def titulo_secao(self, titulo, subtitulo=None):
        self.ln(2)
        y = self.get_y()

        self.set_fill_color(*COR_NAVY)
        self.rect(10, y, 2, 7.2, style="F")

        self.set_xy(14, y)
        self.set_font("Arial", "B", 7.4)
        self.set_text_color(*COR_NAVY)
        self.cell(130, 7.2, _texto(titulo.upper()))

        if subtitulo:
            self.set_font("Arial", "", 6.2)
            self.set_text_color(*COR_MUTED)
            self.cell(56, 7.2, _texto(subtitulo), align="R")

        self.set_y(y + 8)
        self.set_draw_color(*COR_LINE)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(1)

    def campo(self, largura, altura, rotulo, valor, destaque=False):
        """
        Campo editorial com rotulo pequeno e valor bem hierarquizado.
        Mantem a interface chamada pelo gerador.
        """
        x = self.get_x()
        y = self.get_y()

        self.set_fill_color(*COR_WHITE)
        self.set_draw_color(*COR_LINE)
        self.set_line_width(0.22)
        self.rect(x, y, largura, altura, style="DF")

        # Pequeno detalhe superior para separar visualmente os campos.
        self.set_fill_color(*(COR_ACCENT if destaque else COR_BLUE_LIGHT))
        self.rect(x, y, largura, 0.8, style="F")

        self.set_xy(x + 2.2, y + 1.8)
        self.set_font("Arial", "B", 5.6)
        self.set_text_color(*COR_MUTED)
        self.cell(largura - 4.4, 3, _texto(rotulo.upper()))

        valor_texto, tamanho = _texto_ajustado(
            self,
            valor,
            largura - 4.4,
            fonte="Arial",
            estilo="B" if destaque else "",
            tamanho=8 if destaque else 7.3
        )

        self.set_xy(x + 2.2, y + 5.4)
        self.set_font("Arial", "B" if destaque else "", tamanho)
        self.set_text_color(*(COR_NAVY if destaque else COR_INK))
        self.cell(largura - 4.4, altura - 6.1, valor_texto)

        self.set_xy(x + largura, y)

    def verificar_espaco(self, altura):
        if self.get_y() + altura > 278:
            self.add_page()
            return True
        return False

    def cabecalho_produtos(self):
        self.set_fill_color(*COR_NAVY)
        self.set_draw_color(*COR_NAVY)
        self.set_text_color(*COR_WHITE)
        self.set_font("Arial", "B", 6.2)

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
                largura, 8, titulo,
                border=0, align="C", fill=True
            )

        self.ln()
        self.set_text_color(*COR_INK)


# =========================================================
# COMPONENTES DE LAYOUT
# =========================================================

def _desenhar_cabecalho_empresa(pdf, comercio, fiscal, nome_loja, chave):
    logo = _logo_comercio(comercio)
    x_nome = 12

    # Cartao branco do emitente com contorno discreto.
    pdf.set_fill_color(*COR_WHITE)
    pdf.set_draw_color(*COR_LINE)
    pdf.rect(10, 9, 190, 34, style="DF")

    if logo:
        try:
            pdf.image(logo, x=14, y=14, w=22, h=22, type="")
            x_nome = 41
        except Exception as erro:
            print("[DANFE NF-e] Erro ao inserir logo:", repr(erro))

    pdf.set_xy(x_nome, 13)
    nome, tamanho = _texto_ajustado(
        pdf, nome_loja, 109, "Arial", "B", 15
    )
    pdf.set_font("Arial", "B", tamanho)
    pdf.set_text_color(*COR_NAVY)
    pdf.cell(109, 7, nome)

    pdf.set_xy(x_nome, 21)
    pdf.set_font("Arial", "", 7.2)
    pdf.set_text_color(*COR_MUTED)
    pdf.cell(109, 4, _texto(fiscal.get("razao_social")))

    pdf.set_xy(x_nome, 27)
    pdf.set_font("Arial", "B", 6.8)
    pdf.set_text_color(*COR_INK)
    pdf.cell(109, 4, "CNPJ: " + _num(comercio.get("cnpj")))

    endereco_emitente = (
        f"{comercio.get('rua') or ''}, "
        f"{comercio.get('numero') or ''} | "
        f"{comercio.get('bairro') or ''}"
    )
    pdf.set_xy(x_nome, 33)
    pdf.set_font("Arial", "", 6.4)
    pdf.set_text_color(*COR_MUTED)
    pdf.cell(109, 4, _texto(endereco_emitente))

    # Bloco destacado de identificacao do documento.
    pdf.set_fill_color(*COR_NAVY)
    pdf.rect(154, 10, 45, 32, style="F")

    pdf.set_xy(156, 11)
    pdf.set_font("Arial", "B", 6)
    pdf.set_text_color(207, 220, 235)
    pdf.cell(41, 4, "DOCUMENTO FISCAL", align="C")

    chave_qr = _num(chave)
    if len(chave_qr) != 44:
        raise ValueError(
            "A chave de acesso da NF-e deve conter exatamente 44 digitos "
            "para gerar o QR Code."
        )

    qr_img = qrcode.make(chave_qr)
    arquivo_qr = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    caminho_qr = arquivo_qr.name
    arquivo_qr.close()

    try:
        qr_img.save(caminho_qr)
        pdf.image(caminho_qr, x=166, y=16, w=21, h=21)
    finally:
        if os.path.exists(caminho_qr):
            os.remove(caminho_qr)


def _desenhar_linha_produto(pdf, indice, item, larguras):
    nome = _texto(item.get("nome"))
    quantidade = _quantidade(item.get("quantidade"))
    unidade = _texto(item.get("unidade_fiscal") or "UN")
    valor_unitario = _moeda(item.get("valor_unitario_fiscal"))
    valor_total = _moeda(item.get("valor_total_fiscal"))

    pdf.set_font("Arial", "", 6.8)
    linhas = _quebrar_linhas(pdf, nome, larguras[1] - 4)
    altura = max(9, len(linhas) * 3.6 + 3)

    if pdf.get_y() + altura > 278:
        pdf.add_page()
        pdf.titulo_secao("Continuação dos produtos e serviços")
        pdf.cabecalho_produtos()

    x = 10
    y = pdf.get_y()

    pdf.set_fill_color(*(COR_SOFT if indice % 2 == 0 else COR_WHITE))
    pdf.set_draw_color(*COR_LINE)
    pdf.rect(x, y, 190, altura, style="DF")

    # Item.
    pdf.set_xy(x, y)
    pdf.set_font("Arial", "B", 6.7)
    pdf.set_text_color(*COR_MUTED)
    pdf.cell(larguras[0], altura, str(indice), align="C")

    # Descricao completa.
    pdf.set_xy(x + larguras[0] + 2, y + 1.5)
    pdf.set_font("Arial", "", 6.8)
    pdf.set_text_color(*COR_INK)
    for linha in linhas:
        pdf.cell(larguras[1] - 4, 3.6, linha, ln=1)

    # Quantidade, unidade e valores.
    valores = [quantidade, unidade, valor_unitario, valor_total]
    posicao_x = x + larguras[0] + larguras[1]

    for coluna, (largura, valor) in enumerate(zip(larguras[2:], valores)):
        pdf.set_xy(posicao_x, y)
        pdf.set_font("Arial", "B" if coluna == 3 else "", 6.5)
        pdf.set_text_color(*(COR_NAVY if coluna == 3 else COR_INK))
        pdf.cell(largura, altura, _texto(valor), align="C")
        posicao_x += largura

    # Divisorias verticais leves.
    posicao_x = x
    pdf.set_draw_color(*COR_LINE)
    for largura in larguras[:-1]:
        posicao_x += largura
        pdf.line(posicao_x, y, posicao_x, y + altura)

    pdf.set_y(y + altura)


# =========================================================
# GERAR DANFE NF-e
# =========================================================

def gerar_danfe_nfe(dados, chave, protocolo, caminho_saida):
    """
    Gera o PDF A4 auxiliar da NF-e autorizada.

    Preserva todos os dados utilizados pela implementacao original:
    emitente, destinatario, identificacao fiscal, chave de acesso,
    protocolo, produtos, quantidades, unidades, valores, total e contatos.

    O QR Code gerado contem a chave de acesso de 44 digitos.
    Ele nao substitui o QR Code oficial de consulta da SEFAZ.
    Esta funcao nao altera o XML autorizado nem transmite novamente a NF-e.
    """
    comercio = dados["comercio"]
    fiscal = dados["fiscal"]
    venda = dados["venda"]  # Mantido para compatibilidade.
    destinatario = dados["destinatario"]
    itens = dados["itens"]

    numero = dados["numero_nfe"]
    serie = fiscal["serie_nfe"]

    pdf = DANFENFePDF()
    pdf.add_page()

    nome_loja = (
        comercio.get("loja")
        or fiscal.get("razao_social")
        or "Estabelecimento"
    )

    # =====================================================
    # 1. CABECALHO INSTITUCIONAL
    # =====================================================

    _desenhar_cabecalho_empresa(
        pdf, comercio, fiscal, nome_loja, chave
    )

    pdf.set_y(47)

    # Faixa de titulo e identificacao resumida.
    pdf.set_fill_color(*COR_BLUE_LIGHT)
    pdf.rect(10, 47, 190, 13, style="F")

    pdf.set_xy(14, 48)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(*COR_NAVY)
    pdf.cell(75, 7, "DANFE")

    pdf.set_xy(14, 55)
    pdf.set_font("Arial", "", 6.8)
    pdf.set_text_color(*COR_MUTED)
    pdf.cell(120, 3.5, "Documento Auxiliar da Nota Fiscal Eletronica")

    pdf.set_xy(135, 49)
    pdf.set_font("Arial", "B", 6)
    pdf.set_text_color(*COR_MUTED)
    pdf.cell(60, 3, "SERIE / NUMERO", align="R")

    pdf.set_xy(135, 52)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*COR_NAVY)
    pdf.cell(60, 5, f"{serie} / {numero}", align="R")

    pdf.set_y(63)

    # =====================================================
    # 2. IDENTIFICACAO DO EMITENTE
    # =====================================================

    pdf.titulo_secao("Identificacao do emitente")
    y = pdf.get_y()

    pdf.set_xy(10, y)
    pdf.campo(125, 12, "Nome comercial", nome_loja, destaque=True)
    pdf.campo(65, 12, "CNPJ", _num(comercio.get("cnpj")))

    pdf.set_xy(10, y + 12)
    pdf.campo(95, 12, "Razao social", fiscal.get("razao_social"))
    pdf.campo(45, 12, "Inscricao estadual", _num(fiscal.get("inscricao_estadual")))
    pdf.campo(50, 12, "Serie / Numero", f"{serie} / {numero}")

    pdf.set_xy(10, y + 24)
    endereco = (
        f"{comercio.get('rua') or ''}, "
        f"{comercio.get('numero') or ''}, "
        f"{comercio.get('bairro') or ''}"
    )
    pdf.campo(125, 12, "Endereco", endereco)

    cidade = (
        f"{comercio.get('cidade') or ''} / "
        f"{comercio.get('estado') or ''}"
    )
    pdf.campo(65, 12, "Municipio / UF", cidade)
    pdf.set_y(y + 39)

    # =====================================================
    # 3. DADOS DO DESTINATARIO
    # =====================================================

    pdf.titulo_secao("Dados do destinatario")
    y = pdf.get_y()

    pdf.set_xy(10, y)
    pdf.campo(125, 12, "Nome / Razao social", destinatario.get("nome"), destaque=True)
    pdf.campo(65, 12, "CPF / CNPJ", _num(destinatario.get("documento")))

    pdf.set_xy(10, y + 12)
    endereco_destinatario = (
        f"{destinatario.get('logradouro') or ''}, "
        f"{destinatario.get('numero') or ''} "
        f"{destinatario.get('complemento') or ''}"
    )
    pdf.campo(125, 12, "Endereco", endereco_destinatario)
    pdf.campo(65, 12, "CEP", _num(destinatario.get("cep")))

    pdf.set_xy(10, y + 24)
    municipio_destinatario = (
        f"{destinatario.get('municipio') or ''} / "
        f"{destinatario.get('uf') or ''}"
    )
    pdf.campo(125, 12, "Municipio / UF", municipio_destinatario)
    pdf.campo(65, 12, "Data de emissao", _data_emissao(dados))
    pdf.set_y(y + 39)

    # =====================================================
    # 4. CHAVE DE ACESSO E PROTOCOLO
    # =====================================================

    pdf.titulo_secao("Identificacao da NF-e")
    y = pdf.get_y()

    pdf.set_xy(10, y)
    chave_formatada = " ".join(
        str(chave)[i:i + 4]
        for i in range(0, len(str(chave)), 4)
    )
    pdf.campo(190, 13, "Chave de acesso", chave_formatada, destaque=True)

    pdf.set_xy(10, y + 13)
    pdf.campo(190, 13, "Protocolo de autorizacao de uso", protocolo)
    pdf.set_y(y + 29)

    # =====================================================
    # 5. PRODUTOS E SERVICOS
    # =====================================================

    pdf.titulo_secao("Dados dos produtos / servicos")
    larguras = [10, 76, 22, 18, 32, 32]
    pdf.cabecalho_produtos()

    for idx, item in enumerate(itens, 1):
        _desenhar_linha_produto(pdf, idx, item, larguras)

    # =====================================================
    # 6. TOTAL DA NOTA
    # =====================================================

    pdf.ln(4)
    pdf.verificar_espaco(19)

    y = pdf.get_y()
    pdf.set_fill_color(*COR_NAVY)
    pdf.rect(10, y, 190, 16, style="F")

    pdf.set_xy(14, y + 2)
    pdf.set_font("Arial", "B", 6.2)
    pdf.set_text_color(205, 218, 232)
    pdf.cell(110, 4, "VALOR TOTAL DA NF-e")

    pdf.set_xy(14, y + 7)
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*COR_WHITE)
    pdf.cell(110, 6, "Total da operacao")

    pdf.set_xy(125, y + 3)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(*COR_WHITE)
    pdf.cell(70, 9, _moeda(dados.get("total_nf")), align="R")

    pdf.set_y(y + 19)

    # =====================================================
    # 7. CONTATO DA LOJA
    # =====================================================

    contato = []

    if comercio.get("email"):
        contato.append(str(comercio["email"]))

    if comercio.get("celular"):
        contato.append(str(comercio["celular"]))

    if contato:
        pdf.ln(2)
        pdf.set_draw_color(*COR_LINE)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)

        pdf.set_font("Arial", "B", 7)
        pdf.set_text_color(*COR_NAVY)
        pdf.cell(190, 4, _texto(nome_loja), ln=1)

        pdf.set_font("Arial", "", 6.5)
        pdf.set_text_color(*COR_MUTED)
        pdf.cell(190, 4, _texto(" | ".join(contato)), ln=1)

    # =====================================================
    # 8. SALVAR PDF
    # =====================================================

    caminho = Path(caminho_saida)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(caminho))

    print("[DANFE NF-e] PDF profissional gerado:", caminho)
    return str(caminho)
