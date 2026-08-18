from datetime import datetime

from signxml import XMLSigner, methods

from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding
)

from cryptography.hazmat.backends import default_backend

from lxml import etree


def log(msg):

    print(
        f"[NFCe-ASSINATURA]"
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"{msg}"
    )


def assinar_xml(
    xml_bytes,
    certificado_path,
    senha
):
    """
    Assina XML NFC-e corretamente
    Compatível SEFAZ SP NFC-e 4.00
    """

    log("===== INÍCIO ASSINATURA XML =====")

    try:

        # ==========================================
        # CERTIFICADO
        # ==========================================
        log("Lendo certificado A1")

        if not certificado_path:

            raise Exception(
                "Caminho do certificado não informado"
            )

        with open(certificado_path, "rb") as f:

            pfx_data = f.read()

        log("Certificado carregado do disco")

        private_key, certificate, _ = (
            pkcs12.load_key_and_certificates(

                pfx_data,

                senha.encode(),

                backend=default_backend()
            )
        )

        if private_key is None or certificate is None:

            raise Exception(
                "Certificado A1 inválido "
                "ou senha incorreta"
            )

        log(
            "Certificado e chave privada "
            "carregados com sucesso"
        )

        cert_pem = certificate.public_bytes(
            Encoding.PEM
        )

        # ==========================================
        # PARSE XML
        # ==========================================
        log("Fazendo parse do XML")

        xml = etree.fromstring(
            xml_bytes
        )

        # ==========================================
        # COM NAMESPACE
        # ==========================================
        infNFe = xml.find(
            ".//{http://www.portalfiscal.inf.br/nfe}infNFe"
        )

        if infNFe is None:

            raise Exception(
                "Nó <infNFe> não encontrado no XML"
            )

        infNFe_id = infNFe.get("Id")

        if not infNFe_id:

            raise Exception(
                "Atributo Id do <infNFe> "
                "não encontrado"
            )

        log(
            f"infNFe encontrado "
            f"com Id {infNFe_id}"
        )

        # ==========================================
        # ASSINATURA XMLDSIG
        # ==========================================
        log("Iniciando assinatura XMLDSig")

        signer = XMLSigner(

            method=methods.enveloped,

            signature_algorithm="rsa-sha256",

            digest_algorithm="sha256",

            c14n_algorithm=(
                "http://www.w3.org/TR/"
                "2001/REC-xml-c14n-20010315"
            )
        )

        signed_infNFe = signer.sign(

            infNFe,

            key=private_key,

            cert=cert_pem,

            reference_uri=f"#{infNFe_id}"
        )

        log("Assinatura gerada com sucesso")

        # ==========================================
        # EXTRAI SIGNATURE
        # ==========================================
        signature = signed_infNFe.find(
            ".//{http://www.w3.org/2000/09/xmldsig#}Signature"
        )

        if signature is None:

            raise Exception(
                "Signature não encontrada"
            )

        # ==========================================
        # REMOVE SIGNATURE DO infNFe
        # ==========================================
        signature.getparent().remove(
            signature
        )

        log(
            "Signature removida "
            "de dentro do infNFe"
        )

        # ==========================================
        # SUBSTITUI infNFe ORIGINAL
        # ==========================================
        parent = infNFe.getparent()

        parent.replace(
            infNFe,
            signed_infNFe
        )

        log(
            "infNFe original substituído "
            "pelo assinado"
        )

        # ==========================================
        # INSERE SIGNATURE FORA DO infNFe
        # ==========================================
        parent.append(
            signature
        )

        log(
            "Signature movida para fora "
            "do infNFe"
        )

        # ==========================================
        # XML FINAL
        # ==========================================
        xml_final = etree.tostring(

            xml,

            encoding="utf-8",

            xml_declaration=True
        )

        log("===== FIM ASSINATURA XML =====")

        return xml_final

    except Exception as e:

        log("===== ERRO ASSINATURA XML =====")

        log(str(e))

        raise