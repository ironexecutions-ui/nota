from lxml import etree

from pynfe.processamento.assinatura import AssinaturaA1
from pynfe.processamento.comunicacao import ComunicacaoSefaz


NAMESPACE_NFE = "http://www.portalfiscal.inf.br/nfe"


def log_pynfe(msg):
    print(f"[PyNFe] {msg}")


def _converter_xml(xml_base):

    if xml_base is None:
        raise Exception("XML NFC-e não informado")

    if isinstance(xml_base, etree._Element):
        return xml_base

    if isinstance(xml_base, bytes):
        return etree.fromstring(xml_base)

    if isinstance(xml_base, str):
        return etree.fromstring(
            xml_base.encode("utf-8")
        )

    raise Exception(
        f"Formato de XML não suportado: "
        f"{type(xml_base).__name__}"
    )


def _texto(elemento, xpath):

    if elemento is None:
        return None

    resultado = elemento.xpath(
        xpath,
        namespaces={"nfe": NAMESPACE_NFE}
    )

    if not resultado:
        return None

    item = resultado[0]

    if isinstance(item, etree._Element):
        return item.text

    return str(item)


def _tem_retorno_sefaz(elemento):
    """
    Verifica se o elemento XML contém uma resposta
    fiscal da SEFAZ.
    """

    if not isinstance(elemento, etree._Element):
        return False

    nomes_retorno = {
        "retEnviNFe",
        "retConsReciNFe",
        "retConsSitNFe",
        "protNFe",
        "nfeProc"
    }

    nome_raiz = etree.QName(elemento).localname

    if nome_raiz in nomes_retorno:
        return True

    candidatos = elemento.xpath(
        ".//*["
        "local-name()='retEnviNFe' or "
        "local-name()='retConsReciNFe' or "
        "local-name()='retConsSitNFe' or "
        "local-name()='protNFe' or "
        "local-name()='nfeProc'"
        "]"
    )

    return bool(candidatos)


def _normalizar_elemento_retorno(elemento):
    """
    Recebe qualquer estrutura XML retornada pelo PyNFe
    e procura o ponto correto para leitura da resposta.
    """

    if not isinstance(elemento, etree._Element):
        return None

    nome_raiz = etree.QName(elemento).localname

    log_pynfe(
        f"Analisando XML de retorno. Raiz: {nome_raiz}"
    )

    # Caso normal da autorização
    if nome_raiz == "retEnviNFe":
        return elemento

    # Algumas versões do PyNFe devolvem nfeProc
    if nome_raiz == "nfeProc":
        return elemento

    # Protocolo isolado
    if nome_raiz == "protNFe":
        return elemento

    # Outros retornos fiscais
    if nome_raiz in (
        "retConsReciNFe",
        "retConsSitNFe"
    ):
        return elemento

    # Procura retEnviNFe internamente
    candidatos = elemento.xpath(
        ".//*[local-name()='retEnviNFe']"
    )

    if candidatos:
        return candidatos[0]

    # Procura nfeProc
    candidatos = elemento.xpath(
        ".//*[local-name()='nfeProc']"
    )

    if candidatos:
        return candidatos[0]

    # Procura protocolo
    candidatos = elemento.xpath(
        ".//*[local-name()='protNFe']"
    )

    if candidatos:
        return candidatos[0]

    return None


def _converter_parte_para_xml(parte):
    """
    Tenta converter uma parte retornada pelo PyNFe
    para lxml Element.
    """

    if isinstance(parte, etree._Element):
        return parte

    if isinstance(parte, bytes):

        if not parte.strip():
            return None

        try:
            return etree.fromstring(parte)
        except Exception:
            return None

    if isinstance(parte, str):

        texto = parte.strip()

        if not texto.startswith("<"):
            return None

        try:
            return etree.fromstring(
                texto.encode("utf-8")
            )
        except Exception:
            return None

    return None


def emitir_com_pynfe(
    xml_base,
    certificado_path,
    certificado_senha,
    uf,
    homologacao=True
):

    log_pynfe("========================================")
    log_pynfe("INICIANDO EMISSÃO NFC-e COM PyNFe")
    log_pynfe("========================================")

    try:

        # ==========================================
        # 1. VALIDAR PARÂMETROS
        # ==========================================

        if not certificado_path:
            raise Exception(
                "Caminho do certificado não informado"
            )

        if not certificado_senha:
            raise Exception(
                "Senha do certificado não informada"
            )

        if not uf:
            raise Exception(
                "UF do emitente não informada"
            )

        uf = str(uf).strip().lower()

        log_pynfe(f"UF: {uf}")

        log_pynfe(
            f"Ambiente: "
            f"{'HOMOLOGAÇÃO' if homologacao else 'PRODUÇÃO'}"
        )

        log_pynfe(
            f"Certificado: {certificado_path}"
        )

        # ==========================================
        # 2. CONVERTER XML
        # ==========================================

        log_pynfe("Convertendo XML...")

        xml_element = _converter_xml(
            xml_base
        )

        log_pynfe(
            f"Tag raiz recebida: {xml_element.tag}"
        )

        # ==========================================
        # 3. ASSINAR XML
        # ==========================================

        log_pynfe(
            "Carregando certificado A1..."
        )

        assinatura = AssinaturaA1(
            certificado_path,
            certificado_senha
        )

        log_pynfe("Assinando XML...")

        xml_assinado = assinatura.assinar(
            xml_element
        )

        if xml_assinado is None:
            raise Exception(
                "PyNFe não retornou XML assinado"
            )

        log_pynfe(
            "XML assinado com sucesso"
        )

        # ==========================================
        # DEBUG XML ASSINADO
        # ==========================================

        DEBUG_XML_PATH = "/tmp/nfce_debug.xml"

        xml_debug_bytes = etree.tostring(
            xml_assinado,
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True
        )

        with open(
            DEBUG_XML_PATH,
            "wb"
        ) as arquivo_debug:

            arquivo_debug.write(
                xml_debug_bytes
            )

        log_pynfe(
            f"XML assinado salvo para debug em: "
            f"{DEBUG_XML_PATH}"
        )

        # ==========================================
        # VALIDAR SIGNATURE
        # ==========================================

        assinatura_xml = xml_assinado.xpath(
            "//*[local-name()='Signature']"
        )

        if assinatura_xml:

            log_pynfe(
                "Tag Signature encontrada no XML"
            )

        else:

            raise Exception(
                "XML retornado pelo PyNFe "
                "não contém Signature"
            )

        # ==========================================
        # 4. COMUNICAÇÃO SEFAZ
        # ==========================================

        log_pynfe(
            "Criando comunicação com SEFAZ..."
        )

        comunicacao = ComunicacaoSefaz(
            uf,
            certificado_path,
            certificado_senha,
            homologacao
        )

        # ==========================================
        # 5. AUTORIZAÇÃO
        # ==========================================

        log_pynfe(
            "Enviando NFC-e modelo 65 para SEFAZ..."
        )

        resposta = comunicacao.autorizacao(
            modelo="nfce",
            nota_fiscal=xml_assinado,
            id_lote=1,
            ind_sinc=1
        )

        log_pynfe(
            f"Tipo retorno PyNFe: {type(resposta)}"
        )

        # ==========================================
        # 6. NORMALIZAR RETORNO
        # ==========================================

        xml_retorno = None

        if isinstance(resposta, tuple):

            log_pynfe(
                f"Retorno recebido como tuple "
                f"com {len(resposta)} elementos"
            )

            # --------------------------------------
            # Primeiro procura XML válido diretamente
            # dentro da tuple.
            # --------------------------------------

            for indice, parte in enumerate(resposta):

                log_pynfe(
                    f"PARTE [{indice}] "
                    f"tipo={type(parte)}"
                )

                elemento_parte = (
                    _converter_parte_para_xml(parte)
                )

                if elemento_parte is not None:

                    nome = etree.QName(
                        elemento_parte
                    ).localname

                    log_pynfe(
                        f"PARTE [{indice}] XML "
                        f"com raiz: {nome}"
                    )

                    if _tem_retorno_sefaz(
                        elemento_parte
                    ):

                        candidato = (
                            _normalizar_elemento_retorno(
                                elemento_parte
                            )
                        )

                        if candidato is not None:

                            xml_retorno = candidato

                            log_pynfe(
                                f"Resposta SEFAZ encontrada "
                                f"na PARTE [{indice}]"
                            )

                            break

            # --------------------------------------
            # Se não achou XML direto, procura
            # requests.Response dentro da tuple.
            # --------------------------------------

            if xml_retorno is None:

                response_http = None

                for parte in resposta:

                    if (
                        hasattr(parte, "status_code")
                        and hasattr(parte, "content")
                    ):

                        response_http = parte
                        break

                if response_http is not None:

                    log_pynfe(
                        f"HTTP SEFAZ: "
                        f"{response_http.status_code}"
                    )

                    conteudo = (
                        response_http.content
                    )

                    if not conteudo:
                        raise Exception(
                            "SEFAZ retornou resposta "
                            "HTTP sem conteúdo"
                        )

                    try:

                        raiz_http = etree.fromstring(
                            conteudo
                        )

                    except Exception as erro_xml:

                        raise Exception(
                            "Resposta da SEFAZ não é "
                            f"XML válido: {erro_xml}"
                        )

                    xml_retorno = (
                        _normalizar_elemento_retorno(
                            raiz_http
                        )
                    )

                    if xml_retorno is None:
                        xml_retorno = raiz_http

            if xml_retorno is None:

                raise Exception(
                    "Não foi possível localizar "
                    "o XML de resposta da SEFAZ "
                    "dentro do retorno do PyNFe"
                )

        elif isinstance(
            resposta,
            etree._Element
        ):

            xml_retorno = (
                _normalizar_elemento_retorno(
                    resposta
                )
            )

            if xml_retorno is None:
                xml_retorno = resposta

        elif isinstance(
            resposta,
            bytes
        ):

            raiz = etree.fromstring(
                resposta
            )

            xml_retorno = (
                _normalizar_elemento_retorno(
                    raiz
                )
            )

            if xml_retorno is None:
                xml_retorno = raiz

        elif isinstance(
            resposta,
            str
        ):

            raiz = etree.fromstring(
                resposta.encode("utf-8")
            )

            xml_retorno = (
                _normalizar_elemento_retorno(
                    raiz
                )
            )

            if xml_retorno is None:
                xml_retorno = raiz

        else:

            raise Exception(
                f"Retorno desconhecido do PyNFe: "
                f"{type(resposta).__name__}"
            )

        if xml_retorno is None:

            raise Exception(
                "Não foi possível obter "
                "o XML de retorno da SEFAZ"
            )

        # ==========================================
        # 7. DEBUG RETORNO
        # ==========================================

        retorno_string = etree.tostring(
            xml_retorno,
            encoding="unicode",
            pretty_print=True
        )

        log_pynfe(
            "RETORNO NORMALIZADO SEFAZ:"
        )

        print(retorno_string)

        # ==========================================
        # 8. STATUS
        # ==========================================

        nome_retorno = etree.QName(
            xml_retorno
        ).localname

        log_pynfe(
            f"Raiz utilizada para análise: "
            f"{nome_retorno}"
        )

        cstat_lote = _texto(
            xml_retorno,
            "./*[local-name()='cStat']"
        )

        motivo_lote = _texto(
            xml_retorno,
            "./*[local-name()='xMotivo']"
        )

        log_pynfe(
            f"cStat lote: {cstat_lote}"
        )

        log_pynfe(
            f"xMotivo lote: {motivo_lote}"
        )

        # ==========================================
        # PROCURAR infProt
        # ==========================================

        inf_prot_lista = xml_retorno.xpath(
            ".//*[local-name()='infProt']"
        )

        # Caso a própria raiz seja infProt
        if (
            etree.QName(
                xml_retorno
            ).localname
            == "infProt"
        ):

            inf_prot_lista = [
                xml_retorno
            ]

        if inf_prot_lista:

            inf_prot = inf_prot_lista[0]

            cstat = _texto(
                inf_prot,
                "./*[local-name()='cStat']"
            )

            motivo = _texto(
                inf_prot,
                "./*[local-name()='xMotivo']"
            )

            log_pynfe(
                f"cStat NFC-e: {cstat}"
            )

            log_pynfe(
                f"xMotivo NFC-e: {motivo}"
            )

        else:

            cstat = cstat_lote
            motivo = motivo_lote

            log_pynfe(
                "Resposta não contém infProt"
            )

        if not cstat:

            raise Exception(
                "SEFAZ não retornou cStat"
            )

        # ==========================================
        # 9. VERIFICAR AUTORIZAÇÃO
        # ==========================================

        if str(cstat) not in (
            "100",
            "150"
        ):

            raise Exception(
                f"SEFAZ rejeitou NFC-e. "
                f"cStat={cstat}, "
                f"motivo={motivo}"
            )

        # ==========================================
        # 10. PROTOCOLO
        # ==========================================

        protocolo = _texto(
            xml_retorno,
            "//*[local-name()='nProt']"
        )

        chave = _texto(
            xml_retorno,
            "//*[local-name()='chNFe']"
        )

        if not protocolo:

            raise Exception(
                "NFC-e autorizada mas protocolo "
                "não foi retornado"
            )

        # ==========================================
        # CHAVE DO XML ASSINADO COMO FALLBACK
        # ==========================================

        if not chave:

            inf_nfe = xml_assinado.xpath(
                "//*[local-name()='infNFe']"
            )

            if inf_nfe:

                id_nfe = inf_nfe[0].get(
                    "Id"
                )

                if (
                    id_nfe
                    and id_nfe.startswith("NFe")
                ):

                    chave = id_nfe[3:]

        if not chave:

            raise Exception(
                "Não foi possível identificar "
                "a chave da NFC-e"
            )

        # ==========================================
        # 11. QR CODE
        # ==========================================

        qr_code = _texto(
            xml_assinado,
            "//*[local-name()='qrCode']"
        )

        log_pynfe(
            f"Protocolo: {protocolo}"
        )

        log_pynfe(
            f"Chave: {chave}"
        )

        log_pynfe(
            f"QR Code: {qr_code}"
        )

        log_pynfe(
            "========================================"
        )

        log_pynfe(
            "NFC-e AUTORIZADA"
        )

        log_pynfe(
            "========================================"
        )

        return {
            "ok": True,
            "cstat": str(cstat),
            "motivo": motivo,
            "protocolo": protocolo,
            "chave": chave,
            "qr_code": qr_code,
            "xml_assinado": etree.tostring(
                xml_assinado,
                encoding="unicode",
                pretty_print=False
            ),
            "xml_retorno": retorno_string
        }

    except Exception as e:

        log_pynfe(
            "========================================"
        )

        log_pynfe(
            "ERRO NA EMISSÃO"
        )

        log_pynfe(
            str(e)
        )

        log_pynfe(
            "========================================"
        )

        raise
