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
        f"Formato de XML não suportado: {type(xml_base).__name__}"
    )


def _texto(elemento, xpath):

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
            f"Ambiente: {'HOMOLOGAÇÃO' if homologacao else 'PRODUÇÃO'}"
        )
        log_pynfe(
            f"Certificado: {certificado_path}"
        )

        # ==========================================
        # 2. CONVERTER XML
        # ==========================================

        log_pynfe("Convertendo XML...")

        xml_element = _converter_xml(xml_base)

        log_pynfe(
            f"Tag raiz recebida: {xml_element.tag}"
        )

        # ==========================================
        # 3. ASSINAR XML
        # ==========================================

        log_pynfe("Carregando certificado A1...")

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

        log_pynfe("XML assinado com sucesso")

        # ==========================================
        # DEBUG DA ASSINATURA
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
                "XML retornado pelo PyNFe não contém Signature"
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
        # 5. AUTORIZAÇÃO NFC-e
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

        if isinstance(resposta, tuple):

            log_pynfe(
                f"Retorno recebido como tuple com {len(resposta)} elementos"
            )

            xml_retorno = None

            for parte in resposta:

                if isinstance(parte, etree._Element):
                    xml_retorno = parte
                    break

                if isinstance(parte, bytes):

                    try:
                        xml_retorno = etree.fromstring(parte)
                        break
                    except Exception:
                        pass

                if isinstance(parte, str):

                    try:
                        xml_retorno = etree.fromstring(
                            parte.encode("utf-8")
                        )
                        break
                    except Exception:
                        pass

            if xml_retorno is None:
                raise Exception(
                    f"Não foi possível localizar XML no retorno PyNFe: {resposta}"
                )

        elif isinstance(resposta, etree._Element):

            xml_retorno = resposta

        elif isinstance(resposta, bytes):

            xml_retorno = etree.fromstring(
                resposta
            )

        elif isinstance(resposta, str):

            xml_retorno = etree.fromstring(
                resposta.encode("utf-8")
            )

        else:

            raise Exception(
                f"Retorno desconhecido do PyNFe: {type(resposta).__name__}"
            )

        # ==========================================
        # 7. DEBUG RETORNO SEFAZ
        # ==========================================

        retorno_string = etree.tostring(
            xml_retorno,
            encoding="unicode",
            pretty_print=True
        )

        log_pynfe("RETORNO SEFAZ:")
        print(retorno_string)

        # ==========================================
        # 8. STATUS
        # ==========================================

        cstat = _texto(
            xml_retorno,
            "//*[local-name()='cStat']"
        )

        motivo = _texto(
            xml_retorno,
            "//*[local-name()='xMotivo']"
        )

        log_pynfe(
            f"cStat: {cstat}"
        )

        log_pynfe(
            f"xMotivo: {motivo}"
        )

        if not cstat:
            raise Exception(
                "SEFAZ não retornou cStat"
            )

        # 100 = autorizado
        # 150 = autorizado fora do prazo

        if str(cstat) not in ("100", "150"):

            raise Exception(
                f"SEFAZ rejeitou NFC-e. "
                f"cStat={cstat}, "
                f"motivo={motivo}"
            )

        # ==========================================
        # 9. PROTOCOLO
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
                "NFC-e autorizada mas protocolo não foi retornado"
            )

        if not chave:

            # tenta pegar a chave do próprio XML enviado

            inf_nfe = xml_assinado.xpath(
                "//*[local-name()='infNFe']"
            )

            if inf_nfe:

                id_nfe = inf_nfe[0].get("Id")

                if id_nfe and id_nfe.startswith("NFe"):
                    chave = id_nfe[3:]

        if not chave:
            raise Exception(
                "Não foi possível identificar a chave da NFC-e"
            )

        # ==========================================
        # 10. QR CODE
        # ==========================================
        #
        # O QR Code não é criado aqui artificialmente.
        #
        # O XML gerado pelo nosso nfce_xml.py deve
        # conter infNFeSupl/qrCode quando aplicável.
        #

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

        log_pynfe("========================================")
        log_pynfe("NFC-e AUTORIZADA")
        log_pynfe("========================================")

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

        log_pynfe("========================================")
        log_pynfe("ERRO NA EMISSÃO")
        log_pynfe(str(e))
        log_pynfe("========================================")

        raise
