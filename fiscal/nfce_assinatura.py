from datetime import datetime
import base64

from lxml import etree

from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding,
    PrivateFormat,
    NoEncryption,
)

from signxml import (
    XMLSigner,
    XMLVerifier,
    methods,
)


# ============================================================
# CONSTANTES
# ============================================================

NAMESPACE_NFE = "http://www.portalfiscal.inf.br/nfe"

NAMESPACE_DS = "http://www.w3.org/2000/09/xmldsig#"

C14N_ALGORITHM = (
    "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
)

SIGNATURE_ALGORITHM = "rsa-sha1"

DIGEST_ALGORITHM = "sha1"


# ============================================================
# LOG
# ============================================================

def log(msg):
    print(
        f"[NFCe-ASSINATURA]"
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"{msg}"
    )


# ============================================================
# ASSINAR XML NFC-e
# ============================================================

def assinar_xml(
    xml_bytes,
    certificado_path,
    senha
):
    """
    Assina o XML da NFC-e usando XMLDSig.

    Estrutura esperada:

    <NFe>
        <infNFe Id="NFe...">
            ...
        </infNFe>
    </NFe>

    Estrutura final:

    <NFe>
        <infNFe Id="NFe...">
            ...
        </infNFe>

        <Signature>
            ...
        </Signature>
    </NFe>

    Algoritmos utilizados pela NFC-e:

    Canonicalização:
        C14N 1.0

    Digest:
        SHA1

    Assinatura:
        RSA-SHA1
    """

    log("===== INÍCIO ASSINATURA XML =====")

    try:

        # ====================================================
        # 1. NORMALIZAR XML
        # ====================================================

        log("ETAPA 1: Preparando XML")

        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode("utf-8")

        if not xml_bytes:
            raise Exception(
                "XML da NFC-e está vazio"
            )

        # ====================================================
        # 2. CARREGAR CERTIFICADO PFX
        # ====================================================

        log("ETAPA 2: Lendo certificado PFX")

        if not certificado_path:
            raise Exception(
                "Caminho do certificado não informado"
            )

        with open(certificado_path, "rb") as arquivo:
            pfx_data = arquivo.read()

        log(
            f"Certificado PFX carregado: "
            f"{len(pfx_data)} bytes"
        )

        # ====================================================
        # 3. ABRIR PFX
        # ====================================================

        log("ETAPA 3: Abrindo PFX")

        (
            private_key,
            certificate,
            additional_certificates
        ) = pkcs12.load_key_and_certificates(
            pfx_data,
            senha.encode("utf-8")
        )

        if private_key is None:
            raise Exception(
                "Chave privada não encontrada no PFX"
            )

        if certificate is None:
            raise Exception(
                "Certificado não encontrado no PFX"
            )

        log("Chave privada encontrada")
        log("Certificado encontrado")

        # ====================================================
        # 4. INFORMAÇÕES DO CERTIFICADO
        # ====================================================

        log("===== CERTIFICADO =====")

        log(
            f"SUBJECT: "
            f"{certificate.subject.rfc4514_string()}"
        )

        log(
            f"ISSUER: "
            f"{certificate.issuer.rfc4514_string()}"
        )

        log(
            f"SERIAL: "
            f"{certificate.serial_number}"
        )

        log(
            f"VALIDADE INÍCIO: "
            f"{certificate.not_valid_before_utc}"
        )

        log(
            f"VALIDADE FIM: "
            f"{certificate.not_valid_after_utc}"
        )

        log(
            f"CERTIFICADOS ADICIONAIS: "
            f"{len(additional_certificates or [])}"
        )

        # ====================================================
        # 5. CONVERTER CHAVE PARA PEM
        # ====================================================

        log("ETAPA 4: Convertendo chave privada para PEM")

        private_key_pem = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption()
        )

        certificate_pem = certificate.public_bytes(
            Encoding.PEM
        )

        certificate_der = certificate.public_bytes(
            Encoding.DER
        )

        log(
            f"Certificado DER: "
            f"{len(certificate_der)} bytes"
        )

        # ====================================================
        # 6. PARSE DO XML
        # ====================================================

        log("ETAPA 5: Interpretando XML")

        parser = etree.XMLParser(
            remove_blank_text=True,
            resolve_entities=False
        )

        xml = etree.fromstring(
            xml_bytes,
            parser=parser
        )

        raiz = etree.QName(xml).localname

        log(
            f"Elemento raiz: {raiz}"
        )

        if raiz != "NFe":
            raise Exception(
                f"Elemento raiz inválido: {raiz}"
            )

        # ====================================================
        # 7. LOCALIZAR infNFe
        # ====================================================

        log("ETAPA 6: Localizando infNFe")

        infNFe = xml.find(
            f"./{{{NAMESPACE_NFE}}}infNFe"
        )

        if infNFe is None:
            raise Exception(
                "infNFe não encontrado"
            )

        infNFe_id = infNFe.get("Id")

        if not infNFe_id:
            raise Exception(
                "Id do infNFe não encontrado"
            )

        if not infNFe_id.startswith("NFe"):
            raise Exception(
                f"Id do infNFe inválido: "
                f"{infNFe_id}"
            )

        log(
            f"Id encontrado: {infNFe_id}"
        )

        # ====================================================
        # 8. GARANTIR QUE NÃO EXISTE ASSINATURA
        # ====================================================

        log(
            "ETAPA 7: Verificando assinatura existente"
        )

        signature_existente = xml.find(
            f"./{{{NAMESPACE_DS}}}Signature"
        )

        if signature_existente is not None:
            raise Exception(
                "XML já possui Signature"
            )

        # ====================================================
        # 9. CRIAR ASSINADOR
        # ====================================================

        log(
            "ETAPA 8: Criando XMLSigner"
        )

        signer = XMLSigner(
            method=methods.enveloped,
            signature_algorithm=SIGNATURE_ALGORITHM,
            digest_algorithm=DIGEST_ALGORITHM,
            c14n_algorithm=C14N_ALGORITHM
        )

        # ====================================================
        # 10. ASSINAR
        # ====================================================

        log(
            "ETAPA 9: Assinando infNFe"
        )

        xml_assinado = signer.sign(
            xml,
            key=private_key_pem,
            cert=certificate_pem,
            reference_uri=f"#{infNFe_id}",
            id_attribute="Id",
            always_add_key_value=False
        )

        log(
            "XMLSigner concluiu a assinatura"
        )

        # ====================================================
        # 11. LOCALIZAR SIGNATURE
        # ====================================================

        log(
            "ETAPA 10: Conferindo Signature"
        )

        signature = xml_assinado.find(
            f"./{{{NAMESPACE_DS}}}Signature"
        )

        if signature is None:
            raise Exception(
                "Signature não foi gerada"
            )

        signed_info = signature.find(
            f"./{{{NAMESPACE_DS}}}SignedInfo"
        )

        signature_value = signature.find(
            f"./{{{NAMESPACE_DS}}}SignatureValue"
        )

        key_info = signature.find(
            f"./{{{NAMESPACE_DS}}}KeyInfo"
        )

        if signed_info is None:
            raise Exception(
                "SignedInfo não encontrado"
            )

        if signature_value is None:
            raise Exception(
                "SignatureValue não encontrado"
            )

        if key_info is None:
            raise Exception(
                "KeyInfo não encontrado"
            )

        # ====================================================
        # 12. CONFERIR REFERENCE
        # ====================================================

        reference = signed_info.find(
            f"./{{{NAMESPACE_DS}}}Reference"
        )

        if reference is None:
            raise Exception(
                "Reference não encontrado"
            )

        reference_uri = reference.get("URI")

        log(
            f"Reference URI: {reference_uri}"
        )

        esperado = f"#{infNFe_id}"

        if reference_uri != esperado:
            raise Exception(
                "Reference URI incorreto. "
                f"Esperado: {esperado} | "
                f"Recebido: {reference_uri}"
            )

        # ====================================================
        # 13. CONFERIR DIGEST
        # ====================================================

        digest_value = reference.find(
            f"./{{{NAMESPACE_DS}}}DigestValue"
        )

        if digest_value is None:
            raise Exception(
                "DigestValue não encontrado"
            )

        if not digest_value.text:
            raise Exception(
                "DigestValue vazio"
            )

        log(
            f"DigestValue: {digest_value.text}"
        )

        # ====================================================
        # 14. CONFERIR CERTIFICADO NO XML
        # ====================================================

        log(
            "ETAPA 11: Conferindo X509Certificate"
        )

        x509_certificate = signature.find(
            f".//{{{NAMESPACE_DS}}}X509Certificate"
        )

        if x509_certificate is None:
            raise Exception(
                "X509Certificate não encontrado"
            )

        cert_xml_base64 = (
            x509_certificate.text or ""
        ).strip()

        if not cert_xml_base64:
            raise Exception(
                "X509Certificate vazio"
            )

        cert_xml_der = base64.b64decode(
            cert_xml_base64
        )

        if cert_xml_der != certificate_der:
            raise Exception(
                "Certificado inserido no XML "
                "é diferente do certificado PFX"
            )

        log(
            "Certificado do XML é idêntico ao PFX"
        )

        # ====================================================
        # 15. SERIALIZAR
        # ====================================================

        log(
            "ETAPA 12: Serializando XML assinado"
        )

        xml_final = etree.tostring(
            xml_assinado,
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=False
        )

        # ====================================================
        # 16. REABRIR XML
        # ====================================================

        log(
            "ETAPA 13: Reabrindo XML final"
        )

        xml_check = etree.fromstring(
            xml_final
        )

        signature_check = xml_check.find(
            f"./{{{NAMESPACE_DS}}}Signature"
        )

        if signature_check is None:
            raise Exception(
                "Signature desapareceu após serialização"
            )

        # ====================================================
        # 17. VERIFICAÇÃO CRIPTOGRÁFICA INDEPENDENTE
        # ====================================================

        log(
            "ETAPA 14: Verificando XMLDSig"
        )

        try:

            XMLVerifier().verify(
                xml_check,
                x509_cert=certificate_pem,
                id_attribute="Id"
            )

            log(
                "ASSINATURA XMLDSig VALIDADA COM SUCESSO"
            )

        except Exception as verify_error:

            log(
                "ERRO NA VERIFICAÇÃO XMLDSig"
            )

            log(
                f"{type(verify_error).__name__}: "
                f"{verify_error}"
            )

            raise Exception(
                "A assinatura XML foi criada, "
                "mas falhou na validação XMLDSig: "
                f"{verify_error}"
            )

        # ====================================================
        # 18. CONFERIR ESTRUTURA FINAL
        # ====================================================

        filhos = [
            etree.QName(elemento).localname
            for elemento in xml_check
        ]

        log(
            f"Filhos da NFe: {filhos}"
        )

        if not filhos:
            raise Exception(
                "NFe sem elementos internos"
            )

        if filhos[0] != "infNFe":
            raise Exception(
                "infNFe não é o primeiro elemento da NFe"
            )

        if len(filhos) < 2:
            raise Exception(
                "Signature não encontrada após infNFe"
            )

        if filhos[1] != "Signature":
            raise Exception(
                "Signature não está imediatamente "
                "depois do infNFe"
            )

        # ====================================================
        # 19. DEBUG FINAL
        # ====================================================

        print()
        print("=" * 100)
        print(
            "=============== XML NFC-e "
            "ASSINADO ==============="
        )
        print("=" * 100)

        print(
            xml_final.decode("utf-8")
        )

        print("=" * 100)
        print(
            "=============== FIM XML NFC-e "
            "ASSINADO ==============="
        )
        print("=" * 100)
        print()

        log(
            "===== ASSINATURA NFC-e CONCLUÍDA ====="
        )

        return xml_final

    except Exception as e:

        print()
        print("!" * 100)
        print(
            "=============== ERRO NA "
            "ASSINATURA NFC-e ==============="
        )
        print("!" * 100)

        print(
            f"TIPO: {type(e).__name__}"
        )

        print(
            f"MENSAGEM: {str(e)}"
        )

        print(
            f"REPR: {repr(e)}"
        )

        print("!" * 100)
        print()

        log(
            "===== ERRO ASSINATURA XML ====="
        )

        log(
            str(e)
        )

        raise