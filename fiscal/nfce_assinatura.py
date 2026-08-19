from datetime import datetime
import base64
import hashlib

from lxml import etree

from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding,
)

from cryptography.hazmat.primitives import hashes

from cryptography.hazmat.primitives.asymmetric import (
    padding,
)


# ============================================================
# CONSTANTES
# ============================================================

NAMESPACE_NFE = "http://www.portalfiscal.inf.br/nfe"

NAMESPACE_DS = "http://www.w3.org/2000/09/xmldsig#"

C14N_ALGORITHM = (
    "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
)

SIGNATURE_ALGORITHM = (
    "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
)

DIGEST_ALGORITHM = (
    "http://www.w3.org/2000/09/xmldsig#sha1"
)

TRANSFORM_ENVELOPED = (
    "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
)


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
# CANONICALIZAÇÃO C14N
# ============================================================

def canonicalizar(elemento):

    return etree.tostring(
        elemento,
        method="c14n",
        exclusive=False,
        with_comments=False
    )


# ============================================================
# LOCALIZAR ELEMENTO
# ============================================================

def localizar(
    elemento,
    nome
):

    return elemento.find(
        f"./{{{NAMESPACE_DS}}}{nome}"
    )


# ============================================================
# VALIDAR DIGEST
# ============================================================

def validar_digest(
    infNFe,
    digest_esperado
):

    log(
        "VALIDAÇÃO: Recalculando DigestValue"
    )

    inf_c14n = canonicalizar(
        infNFe
    )

    digest_bytes = hashlib.sha1(
        inf_c14n
    ).digest()

    digest_calculado = base64.b64encode(
        digest_bytes
    ).decode("ascii")

    log(
        f"Digest esperado: {digest_esperado}"
    )

    log(
        f"Digest calculado: {digest_calculado}"
    )

    if digest_calculado != digest_esperado:

        raise Exception(
            "DigestValue inválido após assinatura. "
            f"Esperado: {digest_esperado} | "
            f"Calculado: {digest_calculado}"
        )

    log(
        "DigestValue validado com sucesso"
    )


# ============================================================
# VALIDAR SIGNATUREVALUE
# ============================================================

def validar_signature_value(
    signed_info,
    signature_value_base64,
    certificate
):

    log(
        "VALIDAÇÃO: Verificando SignatureValue"
    )

    signed_info_c14n = canonicalizar(
        signed_info
    )

    signature_bytes = base64.b64decode(
        signature_value_base64
    )

    public_key = certificate.public_key()

    public_key.verify(
        signature_bytes,
        signed_info_c14n,
        padding.PKCS1v15(),
        hashes.SHA1()
    )

    log(
        "SignatureValue RSA-SHA1 validado com sucesso"
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
    Assina XML NFC-e 4.00.

    Estrutura inicial:

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

    Algoritmos:

    Canonicalização:
        C14N 1.0

    Digest:
        SHA1

    Assinatura:
        RSA-SHA1
    """

    log(
        "===== INÍCIO ASSINATURA XML ====="
    )

    try:

        # ====================================================
        # 1. NORMALIZAR XML
        # ====================================================

        log(
            "ETAPA 1: Preparando XML"
        )

        if isinstance(
            xml_bytes,
            str
        ):

            xml_bytes = xml_bytes.encode(
                "utf-8"
            )

        if not xml_bytes:

            raise Exception(
                "XML da NFC-e está vazio"
            )

        # ====================================================
        # 2. CARREGAR CERTIFICADO
        # ====================================================

        log(
            "ETAPA 2: Lendo certificado PFX"
        )

        if not certificado_path:

            raise Exception(
                "Caminho do certificado não informado"
            )

        with open(
            certificado_path,
            "rb"
        ) as arquivo:

            pfx_data = arquivo.read()

        log(
            f"Certificado PFX carregado: "
            f"{len(pfx_data)} bytes"
        )

        # ====================================================
        # 3. ABRIR PFX
        # ====================================================

        log(
            "ETAPA 3: Abrindo PFX"
        )

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

        log(
            "Chave privada encontrada"
        )

        log(
            "Certificado encontrado"
        )

        # ====================================================
        # 4. INFORMAÇÕES CERTIFICADO
        # ====================================================

        log(
            "===== CERTIFICADO ====="
        )

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
            f"{certificate.not_valid_before}"
        )

        log(
            f"VALIDADE FIM: "
            f"{certificate.not_valid_after}"
        )

        log(
            f"CERTIFICADOS ADICIONAIS: "
            f"{len(additional_certificates or [])}"
        )

        # ====================================================
        # 5. CERTIFICADO DER
        # ====================================================

        log(
            "ETAPA 4: Preparando certificado DER"
        )

        certificate_der = (
            certificate.public_bytes(
                Encoding.DER
            )
        )

        certificate_base64 = (
            base64.b64encode(
                certificate_der
            ).decode("ascii")
        )

        log(
            f"Certificado DER: "
            f"{len(certificate_der)} bytes"
        )

        log(
            f"Certificado Base64: "
            f"{len(certificate_base64)} caracteres"
        )

        # ====================================================
        # 6. PARSE XML
        # ====================================================

        log(
            "ETAPA 5: Interpretando XML"
        )

        parser = etree.XMLParser(
            remove_blank_text=True,
            resolve_entities=False
        )

        xml = etree.fromstring(
            xml_bytes,
            parser=parser
        )

        raiz = etree.QName(
            xml
        ).localname

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

        log(
            "ETAPA 6: Localizando infNFe"
        )

        infNFe = xml.find(
            f"./{{{NAMESPACE_NFE}}}infNFe"
        )

        if infNFe is None:

            raise Exception(
                "infNFe não encontrado"
            )

        infNFe_id = infNFe.get(
            "Id"
        )

        if not infNFe_id:

            raise Exception(
                "Id do infNFe não encontrado"
            )

        if not infNFe_id.startswith(
            "NFe"
        ):

            raise Exception(
                f"Id do infNFe inválido: "
                f"{infNFe_id}"
            )

        log(
            f"Id encontrado: {infNFe_id}"
        )

        # ====================================================
        # 8. VERIFICAR ASSINATURA EXISTENTE
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
        # 9. CALCULAR DIGEST DO infNFe
        # ====================================================

        log(
            "ETAPA 8: Canonicalizando infNFe"
        )

        infNFe_c14n = canonicalizar(
            infNFe
        )

        log(
            f"infNFe C14N: "
            f"{len(infNFe_c14n)} bytes"
        )

        digest_bytes = hashlib.sha1(
            infNFe_c14n
        ).digest()

        digest_value = base64.b64encode(
            digest_bytes
        ).decode("ascii")

        log(
            f"DigestValue: {digest_value}"
        )

        # ====================================================
        # 10. CRIAR SIGNATURE
        # ====================================================

        log(
            "ETAPA 9: Criando Signature"
        )

        signature = etree.Element(
            etree.QName(
                NAMESPACE_DS,
                "Signature"
            ),
            nsmap={
                "ds": NAMESPACE_DS
            }
        )

        # ====================================================
        # SIGNEDINFO
        # ====================================================

        signed_info = etree.SubElement(
            signature,
            etree.QName(
                NAMESPACE_DS,
                "SignedInfo"
            )
        )

        # ====================================================
        # CANONICALIZATION METHOD
        # ====================================================

        canonicalization_method = (
            etree.SubElement(
                signed_info,
                etree.QName(
                    NAMESPACE_DS,
                    "CanonicalizationMethod"
                )
            )
        )

        canonicalization_method.set(
            "Algorithm",
            C14N_ALGORITHM
        )

        # ====================================================
        # SIGNATURE METHOD
        # ====================================================

        signature_method = etree.SubElement(
            signed_info,
            etree.QName(
                NAMESPACE_DS,
                "SignatureMethod"
            )
        )

        signature_method.set(
            "Algorithm",
            SIGNATURE_ALGORITHM
        )

        # ====================================================
        # REFERENCE
        # ====================================================

        reference = etree.SubElement(
            signed_info,
            etree.QName(
                NAMESPACE_DS,
                "Reference"
            )
        )

        reference.set(
            "URI",
            f"#{infNFe_id}"
        )

        # ====================================================
        # TRANSFORMS
        # ====================================================

        transforms = etree.SubElement(
            reference,
            etree.QName(
                NAMESPACE_DS,
                "Transforms"
            )
        )

        transform_enveloped = etree.SubElement(
            transforms,
            etree.QName(
                NAMESPACE_DS,
                "Transform"
            )
        )

        transform_enveloped.set(
            "Algorithm",
            TRANSFORM_ENVELOPED
        )

        transform_c14n = etree.SubElement(
            transforms,
            etree.QName(
                NAMESPACE_DS,
                "Transform"
            )
        )

        transform_c14n.set(
            "Algorithm",
            C14N_ALGORITHM
        )

        # ====================================================
        # DIGEST METHOD
        # ====================================================

        digest_method = etree.SubElement(
            reference,
            etree.QName(
                NAMESPACE_DS,
                "DigestMethod"
            )
        )

        digest_method.set(
            "Algorithm",
            DIGEST_ALGORITHM
        )

        # ====================================================
        # DIGEST VALUE
        # ====================================================

        digest_element = etree.SubElement(
            reference,
            etree.QName(
                NAMESPACE_DS,
                "DigestValue"
            )
        )

        digest_element.text = (
            digest_value
        )

        # ====================================================
        # 11. INSERIR SIGNATURE NA NFe
        # ====================================================

        log(
            "ETAPA 10: Inserindo Signature na NFe"
        )

        xml.append(
            signature
        )

        filhos = [
            etree.QName(
                elemento
            ).localname
            for elemento in xml
        ]

        log(
            f"Filhos da NFe: {filhos}"
        )

        if filhos != [
            "infNFe",
            "Signature"
        ]:

            raise Exception(
                "Estrutura da NFe incorreta após "
                f"inserir Signature: {filhos}"
            )

        # ====================================================
        # 12. CANONICALIZAR SIGNEDINFO NO CONTEXTO FINAL
        # ====================================================

        log(
            "ETAPA 11: Canonicalizando SignedInfo"
        )

        signed_info_c14n = canonicalizar(
            signed_info
        )

        log(
            f"SignedInfo C14N: "
            f"{len(signed_info_c14n)} bytes"
        )

        # ====================================================
        # 13. ASSINAR SIGNEDINFO
        # ====================================================

        log(
            "ETAPA 12: Assinando SignedInfo com RSA-SHA1"
        )

        assinatura_bytes = (
            private_key.sign(
                signed_info_c14n,
                padding.PKCS1v15(),
                hashes.SHA1()
            )
        )

        assinatura_base64 = (
            base64.b64encode(
                assinatura_bytes
            ).decode("ascii")
        )

        # ====================================================
        # SIGNATURE VALUE
        # ====================================================

        signature_value = etree.SubElement(
            signature,
            etree.QName(
                NAMESPACE_DS,
                "SignatureValue"
            )
        )

        signature_value.text = (
            assinatura_base64
        )

        log(
            "SignatureValue criado"
        )

        # ====================================================
        # 14. KEYINFO
        # ====================================================

        log(
            "ETAPA 13: Inserindo X509Certificate"
        )

        key_info = etree.SubElement(
            signature,
            etree.QName(
                NAMESPACE_DS,
                "KeyInfo"
            )
        )

        x509_data = etree.SubElement(
            key_info,
            etree.QName(
                NAMESPACE_DS,
                "X509Data"
            )
        )

        x509_certificate = etree.SubElement(
            x509_data,
            etree.QName(
                NAMESPACE_DS,
                "X509Certificate"
            )
        )

        x509_certificate.text = (
            certificate_base64
        )

        # ====================================================
        # 15. VALIDAR CERTIFICADO XML
        # ====================================================

        log(
            "ETAPA 14: Validando X509Certificate"
        )

        cert_xml_der = base64.b64decode(
            x509_certificate.text
        )

        if cert_xml_der != certificate_der:

            raise Exception(
                "Certificado inserido no XML "
                "é diferente do PFX"
            )

        log(
            "Certificado do XML é idêntico ao PFX"
        )

        # ====================================================
        # 16. VALIDAR SIGNATUREVALUE
        # ====================================================

        log(
            "ETAPA 15: Validando assinatura RSA"
        )

        validar_signature_value(
            signed_info,
            assinatura_base64,
            certificate
        )

        # ====================================================
        # 17. VALIDAR DIGEST
        # ====================================================

        log(
            "ETAPA 16: Validando DigestValue"
        )

        validar_digest(
            infNFe,
            digest_value
        )

        # ====================================================
        # 18. SERIALIZAR
        # ====================================================

        log(
            "ETAPA 17: Serializando XML final"
        )

        xml_final = etree.tostring(
            xml,
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=False
        )

        # ====================================================
        # 19. REABRIR XML
        # ====================================================

        log(
            "ETAPA 18: Reabrindo XML final"
        )

        parser_final = etree.XMLParser(
            remove_blank_text=True,
            resolve_entities=False
        )

        xml_check = etree.fromstring(
            xml_final,
            parser=parser_final
        )

        infNFe_check = xml_check.find(
            f"./{{{NAMESPACE_NFE}}}infNFe"
        )

        signature_check = xml_check.find(
            f"./{{{NAMESPACE_DS}}}Signature"
        )

        if infNFe_check is None:

            raise Exception(
                "infNFe desapareceu após serialização"
            )

        if signature_check is None:

            raise Exception(
                "Signature desapareceu após serialização"
            )

        # ====================================================
        # 20. VALIDAR ESTRUTURA FINAL
        # ====================================================

        log(
            "ETAPA 19: Validando estrutura final"
        )

        filhos_finais = [
            etree.QName(
                elemento
            ).localname
            for elemento in xml_check
        ]

        log(
            f"Filhos finais da NFe: "
            f"{filhos_finais}"
        )

        if filhos_finais != [
            "infNFe",
            "Signature"
        ]:

            raise Exception(
                "Estrutura final inválida: "
                f"{filhos_finais}"
            )

        # ====================================================
        # 21. VALIDAR DIGEST DEPOIS DA SERIALIZAÇÃO
        # ====================================================

        log(
            "ETAPA 20: Validando Digest após serialização"
        )

        validar_digest(
            infNFe_check,
            digest_value
        )

        # ====================================================
        # 22. VALIDAR ASSINATURA DEPOIS DA SERIALIZAÇÃO
        # ====================================================

        log(
            "ETAPA 21: Validando SignatureValue "
            "após serialização"
        )

        signed_info_check = signature_check.find(
            f"./{{{NAMESPACE_DS}}}SignedInfo"
        )

        signature_value_check = signature_check.find(
            f"./{{{NAMESPACE_DS}}}SignatureValue"
        )

        if signed_info_check is None:

            raise Exception(
                "SignedInfo não encontrado "
                "após serialização"
            )

        if signature_value_check is None:

            raise Exception(
                "SignatureValue não encontrado "
                "após serialização"
            )

        if not signature_value_check.text:

            raise Exception(
                "SignatureValue vazio "
                "após serialização"
            )

        validar_signature_value(
            signed_info_check,
            signature_value_check.text.strip(),
            certificate
        )

        # ====================================================
        # 23. CONFERIR REFERENCE
        # ====================================================

        reference_check = signed_info_check.find(
            f"./{{{NAMESPACE_DS}}}Reference"
        )

        if reference_check is None:

            raise Exception(
                "Reference não encontrado"
            )

        reference_uri = reference_check.get(
            "URI"
        )

        esperado = (
            f"#{infNFe_id}"
        )

        log(
            f"Reference URI final: "
            f"{reference_uri}"
        )

        if reference_uri != esperado:

            raise Exception(
                "Reference URI incorreto. "
                f"Esperado: {esperado} | "
                f"Recebido: {reference_uri}"
            )

        # ====================================================
        # 24. CONFERIR CERTIFICADO FINAL
        # ====================================================

        x509_check = signature_check.find(
            f".//{{{NAMESPACE_DS}}}X509Certificate"
        )

        if x509_check is None:

            raise Exception(
                "X509Certificate não encontrado "
                "no XML final"
            )

        cert_final_base64 = (
            x509_check.text or ""
        ).strip()

        if not cert_final_base64:

            raise Exception(
                "X509Certificate vazio "
                "no XML final"
            )

        cert_final_der = base64.b64decode(
            cert_final_base64
        )

        if cert_final_der != certificate_der:

            raise Exception(
                "Certificado do XML final "
                "é diferente do PFX"
            )

        log(
            "X509Certificate final validado"
        )

        # ====================================================
        # DEBUG FINAL
        # ====================================================

        print()
        print("=" * 100)

        print(
            "=============== XML NFC-e "
            "ASSINADO ==============="
        )

        print("=" * 100)

        print(
            xml_final.decode(
                "utf-8"
            )
        )

        print("=" * 100)

        print(
            "=============== FIM XML NFC-e "
            "ASSINADO ==============="
        )

        print("=" * 100)

        print()

        log(
            f"DIGEST FINAL: {digest_value}"
        )

        log(
            "ASSINATURA RSA-SHA1 "
            "VALIDADA LOCALMENTE"
        )

        log(
            "CERTIFICADO DO XML "
            "CONFERE COM O PFX"
        )

        log(
            "===== ASSINATURA NFC-e "
            "CONCLUÍDA COM SUCESSO ====="
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