import os
import re
import ssl
import sys
import base64
import hashlib
import tempfile
import traceback
from datetime import datetime, timezone

import requests
import urllib3

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, ec, dsa, padding
from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding,
    PrivateFormat,
    NoEncryption,
)
from cryptography.x509.oid import ExtensionOID, ObjectIdentifier


# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PFX_PATH = os.path.join(BASE_DIR, "enya.pfx")
SENHA_PFX = "12345678"

# CNPJ que aparece no <emit><CNPJ> da NFC-e
CNPJ_EMITENTE_ESPERADO = "62712093000134"

# Opcional:
# Se você salvar o XML assinado ao lado deste script como nfce_assinada.xml,
# o diagnóstico também compara o X509Certificate do XML com o PFX.
XML_ASSINADO_PATH = os.path.join(BASE_DIR, "nfce_assinada.xml")

# OID ICP-Brasil de CNPJ em subjectAltName / otherName
OID_CNPJ_ICP_BRASIL = ObjectIdentifier("2.16.76.1.3.3")

URL_STATUS_SEFAZ = (
    "https://homologacao.nfce.fazenda.sp.gov.br/"
    "ws/NFeStatusServico4.asmx"
)

SOAP_STATUS = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<soap12:Envelope '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
    'xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">'
    '<soap12:Header>'
    '<nfeCabecMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeStatusServico4">'
    '<cUF>35</cUF>'
    '<versaoDados>4.00</versaoDados>'
    '</nfeCabecMsg>'
    '</soap12:Header>'
    '<soap12:Body>'
    '<nfeDadosMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeStatusServico4">'
    '<consStatServ xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
    '<tpAmb>2</tpAmb>'
    '<cUF>35</cUF>'
    '<xServ>STATUS</xServ>'
    '</consStatServ>'
    '</nfeDadosMsg>'
    '</soap12:Body>'
    '</soap12:Envelope>'
)


# ============================================================
# UTILITÁRIOS
# ============================================================

def titulo(texto):
    print()
    print("=" * 100)
    print(texto)
    print("=" * 100)


def ok(texto):
    print(f"[OK] {texto}")


def alerta(texto):
    print(f"[ATENÇÃO] {texto}")


def erro(texto):
    print(f"[ERRO] {texto}")


def somente_digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def fingerprint(certificado, algoritmo):
    return certificado.fingerprint(algoritmo).hex().upper()


def formatar_hex(valor):
    return ":".join(
        valor[i:i + 2]
        for i in range(0, len(valor), 2)
    )


def cert_datetime_utc(certificado, inicio=True):
    if inicio:
        valor = getattr(certificado, "not_valid_before_utc", None)
        if valor is None:
            valor = certificado.not_valid_before.replace(tzinfo=timezone.utc)
    else:
        valor = getattr(certificado, "not_valid_after_utc", None)
        if valor is None:
            valor = certificado.not_valid_after.replace(tzinfo=timezone.utc)

    return valor


def imprimir_extensoes(certificado):
    titulo("[7] EXTENSÕES X.509")

    for ext in certificado.extensions:
        print()
        print(f"OID: {ext.oid.dotted_string}")
        print(f"NOME: {ext.oid._name}")
        print(f"CRITICAL: {ext.critical}")
        print(f"VALOR: {ext.value}")


def extrair_cnpj_othername(certificado):
    """
    Procura o OID 2.16.76.1.3.3 no SubjectAlternativeName.

    O valor de OtherName vem codificado em ASN.1 DER. Para diagnóstico,
    procuramos sequências ASCII numéricas no payload e priorizamos 14 dígitos.
    """

    try:
        san = certificado.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        ).value
    except x509.ExtensionNotFound:
        return None, "SubjectAlternativeName ausente"

    encontrados = []

    for nome in san:
        if isinstance(nome, x509.OtherName):
            if nome.type_id == OID_CNPJ_ICP_BRASIL:
                bruto = nome.value

                # DER normalmente contém tag + tamanho + conteúdo.
                # Procuramos os dígitos para não depender de asn1crypto.
                ascii_text = bruto.decode("latin1", errors="ignore")
                candidatos = re.findall(r"\d{14}", ascii_text)

                if candidatos:
                    return candidatos[0], "OID 2.16.76.1.3.3"

                # Fallback por inspeção hexadecimal/ASCII.
                encontrados.append(bruto)

    if encontrados:
        return None, (
            "OID de CNPJ encontrado, mas não foi possível "
            "decodificar automaticamente o conteúdo"
        )

    return None, "OID 2.16.76.1.3.3 não encontrado"


def extrair_cnpj_subject(certificado):
    """
    Extrai somente o CNPJ que aparece no CN no formato:
    NOME:12345678000199

    Não usa qualquer número de 14 dígitos encontrado nos OUs,
    pois isso gerava falso positivo no diagnóstico anterior.
    """
    texto = certificado.subject.rfc4514_string()

    match = re.search(
        r"CN=[^,]*:(\d{14})(?:,|$)",
        texto,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None


def testar_correspondencia_chave(private_key, certificate):
    titulo("[4] CHAVE PRIVADA x CERTIFICADO")

    mensagem = b"IRON-NFCE-DIAGNOSTICO-CHAVE"

    public_key = certificate.public_key()

    if isinstance(private_key, rsa.RSAPrivateKey):
        assinatura = private_key.sign(
            mensagem,
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        public_key.verify(
            assinatura,
            mensagem,
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        ok("A chave privada do PFX corresponde à chave pública do certificado.")
        print(f"Tipo: RSA")
        print(f"Tamanho: {private_key.key_size} bits")
        return

    if isinstance(private_key, ec.EllipticCurvePrivateKey):
        assinatura = private_key.sign(
            mensagem,
            ec.ECDSA(hashes.SHA256())
        )

        public_key.verify(
            assinatura,
            mensagem,
            ec.ECDSA(hashes.SHA256())
        )

        ok("A chave privada EC corresponde à chave pública do certificado.")
        print(f"Curva: {private_key.curve.name}")
        return

    if isinstance(private_key, dsa.DSAPrivateKey):
        assinatura = private_key.sign(
            mensagem,
            hashes.SHA256()
        )

        public_key.verify(
            assinatura,
            mensagem,
            hashes.SHA256()
        )

        ok("A chave privada DSA corresponde à chave pública do certificado.")
        return

    alerta(
        f"Tipo de chave não tratado automaticamente: "
        f"{type(private_key).__name__}"
    )


def diagnosticar_regra_290(certificado):
    titulo("[5] TESTES DIRETAMENTE RELACIONADOS AO cStat 290")

    falhas_290 = []

    # --------------------------------------------------------
    # X.509 v3
    # --------------------------------------------------------
    print()
    print("5.1 VERSÃO X.509")

    print(f"Versão encontrada: {certificado.version}")

    if certificado.version == x509.Version.v3:
        ok("Certificado é X.509 v3.")
    else:
        erro("Certificado não é X.509 v3.")
        falhas_290.append("Versão X.509 diferente de v3")

    # --------------------------------------------------------
    # Basic Constraints
    # --------------------------------------------------------
    print()
    print("5.2 BASIC CONSTRAINTS")

    try:
        bc = certificado.extensions.get_extension_for_oid(
            ExtensionOID.BASIC_CONSTRAINTS
        ).value

        print(f"CA: {bc.ca}")
        print(f"path_length: {bc.path_length}")

        if bc.ca is False:
            ok("Certificado é certificado final, não é certificado de AC.")
        else:
            erro("BasicConstraints indica CA=True.")
            falhas_290.append("BasicConstraints CA=True")

    except x509.ExtensionNotFound:
        alerta(
            "Extensão BasicConstraints não está presente. "
            "A regra oficial trata essa extensão quando informada."
        )

    # --------------------------------------------------------
    # Key Usage
    # --------------------------------------------------------
    print()
    print("5.3 KEY USAGE")

    try:
        ku = certificado.extensions.get_extension_for_oid(
            ExtensionOID.KEY_USAGE
        ).value

        print(f"digital_signature: {ku.digital_signature}")
        print(f"content_commitment / non_repudiation: {ku.content_commitment}")
        print(f"key_encipherment: {ku.key_encipherment}")
        print(f"data_encipherment: {ku.data_encipherment}")
        print(f"key_agreement: {ku.key_agreement}")
        print(f"key_cert_sign: {ku.key_cert_sign}")
        print(f"crl_sign: {ku.crl_sign}")

        if ku.digital_signature:
            ok("KeyUsage permite Digital Signature.")
        else:
            erro("KeyUsage NÃO permite Digital Signature.")
            falhas_290.append("KeyUsage sem Digital Signature")

        if ku.content_commitment:
            ok("KeyUsage permite Non Repudiation / Content Commitment.")
        else:
            erro(
                "KeyUsage NÃO permite Non Repudiation / "
                "Content Commitment."
            )
            falhas_290.append(
                "KeyUsage sem Non Repudiation/Content Commitment"
            )

    except x509.ExtensionNotFound:
        erro("Extensão KeyUsage não encontrada.")
        falhas_290.append("Extensão KeyUsage ausente")

    # --------------------------------------------------------
    # Extended Key Usage
    # --------------------------------------------------------
    print()
    print("5.4 EXTENDED KEY USAGE")

    try:
        eku = certificado.extensions.get_extension_for_oid(
            ExtensionOID.EXTENDED_KEY_USAGE
        ).value

        for oid in eku:
            print(f"{oid.dotted_string} | {oid._name}")

    except x509.ExtensionNotFound:
        print("ExtendedKeyUsage não informado.")

    return falhas_290


def diagnosticar_validade(certificado):
    titulo("[6] VALIDADE DO CERTIFICADO")

    inicio = cert_datetime_utc(certificado, True)
    fim = cert_datetime_utc(certificado, False)
    agora = datetime.now(timezone.utc)

    print(f"Agora UTC: {agora}")
    print(f"Início:    {inicio}")
    print(f"Fim:       {fim}")

    if agora < inicio:
        erro("Certificado ainda não está válido.")
        return False

    if agora > fim:
        erro("Certificado expirado.")
        return False

    ok("Certificado está dentro do período de validade.")
    return True


def diagnosticar_cnpj(certificado):
    titulo("[8] CNPJ DO CERTIFICADO")

    esperado = somente_digitos(CNPJ_EMITENTE_ESPERADO)

    print(f"CNPJ esperado no emitente: {esperado}")

    cnpj_oid, origem_oid = extrair_cnpj_othername(certificado)
    cnpj_subject = extrair_cnpj_subject(certificado)

    print()
    print(f"CNPJ via OID ICP-Brasil: {cnpj_oid}")
    print(f"Resultado OID: {origem_oid}")

    print()
    print(f"CNPJ localizado no Subject/CN: {cnpj_subject}")

    if cnpj_oid:
        if somente_digitos(cnpj_oid) == esperado:
            ok("CNPJ do OID ICP-Brasil coincide com o emitente.")
        else:
            erro(
                "CNPJ do OID ICP-Brasil NÃO coincide com o emitente."
            )
    else:
        alerta(
            "Não consegui confirmar automaticamente o CNPJ "
            "pelo OID 2.16.76.1.3.3."
        )

    if cnpj_subject:
        if somente_digitos(cnpj_subject) == esperado:
            ok("CNPJ visível no Subject coincide com o emitente.")
        else:
            erro("CNPJ visível no Subject difere do emitente.")


def diagnosticar_aia_crl(certificado):
    titulo("[9] CADEIA, AIA E LCR INFORMADAS PELO CERTIFICADO")

    print("ISSUER:")
    print(certificado.issuer.rfc4514_string())

    print()
    print("Authority Information Access:")

    try:
        aia = certificado.extensions.get_extension_for_oid(
            ExtensionOID.AUTHORITY_INFORMATION_ACCESS
        ).value

        for item in aia:
            print(
                f"  Método: {item.access_method.dotted_string} "
                f"({item.access_method._name})"
            )
            print(f"  Local:  {item.access_location}")

    except x509.ExtensionNotFound:
        alerta("Authority Information Access não encontrado.")

    print()
    print("CRL Distribution Points:")

    try:
        crl = certificado.extensions.get_extension_for_oid(
            ExtensionOID.CRL_DISTRIBUTION_POINTS
        ).value

        for i, ponto in enumerate(crl, 1):
            print(f"  Ponto {i}:")

            if ponto.full_name:
                for nome in ponto.full_name:
                    print(f"    {nome}")

    except x509.ExtensionNotFound:
        alerta("CRL Distribution Points não encontrado.")


def gerar_pem_temporario(private_key, certificate, adicionais):
    cert_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pem"
    )

    key_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pem"
    )

    cert_path = cert_file.name
    key_path = key_file.name

    # Para TLS enviamos o certificado final e, se o PFX tiver,
    # certificados adicionais da cadeia.
    cert_file.write(
        certificate.public_bytes(Encoding.PEM)
    )

    for adicional in adicionais or []:
        cert_file.write(
            adicional.public_bytes(Encoding.PEM)
        )

    key_file.write(
        private_key.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            NoEncryption()
        )
    )

    cert_file.close()
    key_file.close()

    return cert_path, key_path


def testar_tls_sefaz(private_key, certificate, adicionais):
    titulo("[10] TESTE mTLS COM SEFAZ-SP")

    cert_path = None
    key_path = None

    try:
        cert_path, key_path = gerar_pem_temporario(
            private_key,
            certificate,
            adicionais
        )

        print(URL_STATUS_SEFAZ)
        print()
        print(
            "Primeiro teste: validação TLS normal do servidor "
            "(verify=True)."
        )

        headers = {
            "Content-Type": "application/soap+xml; charset=utf-8"
        }

        try:
            response = requests.post(
                URL_STATUS_SEFAZ,
                data=SOAP_STATUS.encode("utf-8"),
                headers=headers,
                cert=(cert_path, key_path),
                timeout=30
            )

            ok("Handshake TLS com validação do servidor concluído.")
            print(f"HTTP: {response.status_code}")
            print(response.text[:2500])

            return response

        except requests.exceptions.SSLError as exc:
            alerta(
                "O Windows/Python não conseguiu validar a cadeia TLS "
                "do servidor da SEFAZ."
            )
            print(str(exc))
            print()
            print(
                "Isso é diferente da validação do certificado de "
                "assinatura da NFC-e."
            )
            print()
            print(
                "Executando segundo teste SOMENTE diagnóstico "
                "com verify=False..."
            )

            urllib3.disable_warnings(
                urllib3.exceptions.InsecureRequestWarning
            )

            response = requests.post(
                URL_STATUS_SEFAZ,
                data=SOAP_STATUS.encode("utf-8"),
                headers=headers,
                cert=(cert_path, key_path),
                verify=False,
                timeout=30
            )

            print(f"HTTP: {response.status_code}")
            print(response.text[:2500])

            if "<cStat>107</cStat>" in response.text:
                ok(
                    "SEFAZ aceitou o certificado para autenticação "
                    "mTLS e retornou 107."
                )

            return response

    finally:
        for caminho in (cert_path, key_path):
            if caminho and os.path.exists(caminho):
                os.remove(caminho)



def gerar_xml_teste_para_assinatura():
    """
    XML mínimo apenas para testar a camada XMLDSig do projeto.
    Não é enviado à SEFAZ como NFC-e.
    """
    chave = "35260862712093000134650010000000011000000010"

    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
        f'<infNFe Id="NFe{chave}" versao="4.00">'
        '<ide>'
        '<cUF>35</cUF>'
        '<cNF>00000001</cNF>'
        '<natOp>TESTE</natOp>'
        '<mod>65</mod>'
        '<serie>1</serie>'
        '<nNF>1</nNF>'
        '</ide>'
        '</infNFe>'
        '</NFe>'
    )


def diagnosticar_assinador_real_do_projeto(certificado_pfx):
    titulo("[11] TESTE DO nfce_assinatura.py REAL DO PROJETO")

    try:
        from ..nfce_assinatura import assinar_xml
    except Exception as exc:
        alerta(
            "Não foi possível importar nfce_assinatura.assinar_xml. "
            "Coloque este diagnóstico na mesma pasta do módulo "
            "nfce_assinatura.py ou mantenha o teste por arquivo."
        )
        print(f"Detalhe: {type(exc).__name__}: {exc}")
        return None

    xml_teste = gerar_xml_teste_para_assinatura()

    try:
        xml_assinado = assinar_xml(
            xml_teste,
            PFX_PATH,
            SENHA_PFX
        )
    except Exception as exc:
        erro("A função real assinar_xml falhou.")
        print(f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False

    if isinstance(xml_assinado, bytes):
        xml_bytes = xml_assinado
        xml_texto = xml_assinado.decode("utf-8")
    else:
        xml_texto = str(xml_assinado)
        xml_bytes = xml_texto.encode("utf-8")

    saida = os.path.join(
        BASE_DIR,
        "nfce_assinada_diagnostico.xml"
    )

    with open(saida, "wb") as arquivo:
        arquivo.write(xml_bytes)

    ok(f"XML assinado pelo módulo real foi salvo em: {saida}")

    match = re.search(
        r"<(?:ds:)?X509Certificate[^>]*>\\s*"
        r"([^<]+?)"
        r"\\s*</(?:ds:)?X509Certificate>",
        xml_texto,
        re.DOTALL
    )

    if not match:
        erro("O assinar_xml não colocou X509Certificate no XML.")
        return False

    b64 = re.sub(r"\\s+", "", match.group(1))

    try:
        der = base64.b64decode(b64, validate=True)
        cert_xml = x509.load_der_x509_certificate(der)
    except Exception as exc:
        erro(f"X509Certificate produzido é inválido: {exc}")
        return False

    fp_pfx = fingerprint(certificado_pfx, hashes.SHA256())
    fp_xml = fingerprint(cert_xml, hashes.SHA256())

    print()
    print("SHA256 PFX:")
    print(formatar_hex(fp_pfx))

    print()
    print("SHA256 XML:")
    print(formatar_hex(fp_xml))

    if fp_pfx == fp_xml:
        ok("O nfce_assinatura.py REAL coloca exatamente o certificado do PFX no XML.")
    else:
        erro("O nfce_assinatura.py REAL colocou um certificado diferente no XML.")
        return False

    # Confere presença dos componentes essenciais da XMLDSig.
    componentes = [
        "Signature",
        "SignedInfo",
        "CanonicalizationMethod",
        "SignatureMethod",
        "Reference",
        "Transforms",
        "DigestMethod",
        "DigestValue",
        "SignatureValue",
        "KeyInfo",
        "X509Data",
        "X509Certificate",
    ]

    ausentes = []

    for nome in componentes:
        if re.search(rf"<(?:ds:)?{nome}\\b", xml_texto):
            ok(f"XMLDSig contém {nome}.")
        else:
            erro(f"XMLDSig NÃO contém {nome}.")
            ausentes.append(nome)

    if ausentes:
        return False

    ok("Estrutura básica XMLDSig produzida pelo módulo real está presente.")
    return True


def comparar_certificado_xml(certificado_pfx):
    titulo("[12] COMPARAÇÃO COM XML REAL DE UMA EMISSÃO, OPCIONAL")

    if not os.path.exists(XML_ASSINADO_PATH):
        alerta(
            "nfce_assinada.xml não existe ao lado do script. "
            "Teste opcional ignorado."
        )
        print()
        print(
            "Se quiser testar exatamente o certificado enviado no XML, "
            "salve a NFC-e assinada como:"
        )
        print(XML_ASSINADO_PATH)
        return None

    xml = open(
        XML_ASSINADO_PATH,
        "r",
        encoding="utf-8"
    ).read()

    match = re.search(
        r"<(?:ds:)?X509Certificate[^>]*>\s*"
        r"([^<]+?)"
        r"\s*</(?:ds:)?X509Certificate>",
        xml,
        re.DOTALL
    )

    if not match:
        erro("X509Certificate não encontrado no XML.")
        return False

    b64 = re.sub(r"\s+", "", match.group(1))

    try:
        der = base64.b64decode(
            b64,
            validate=True
        )
    except Exception as exc:
        erro(f"Base64 do X509Certificate inválido: {exc}")
        return False

    cert_xml = x509.load_der_x509_certificate(der)

    sha256_pfx = fingerprint(
        certificado_pfx,
        hashes.SHA256()
    )

    sha256_xml = fingerprint(
        cert_xml,
        hashes.SHA256()
    )

    print(
        "PFX SHA256:",
        formatar_hex(sha256_pfx)
    )

    print(
        "XML SHA256:",
        formatar_hex(sha256_xml)
    )

    print()
    print("SUBJECT XML:")
    print(cert_xml.subject.rfc4514_string())

    print()
    print("ISSUER XML:")
    print(cert_xml.issuer.rfc4514_string())

    if sha256_pfx == sha256_xml:
        ok(
            "O X509Certificate dentro do XML é exatamente "
            "o certificado carregado do PFX."
        )
        return True

    erro(
        "O certificado dentro do XML é DIFERENTE "
        "do certificado carregado do PFX."
    )

    return False


def resumo(
    falhas_290,
    validade_ok,
    tls_response,
    adicionais
):
    titulo("RESUMO FINAL")

    print(
        f"Certificados adicionais presentes no PFX: "
        f"{len(adicionais or [])}"
    )

    if not adicionais:
        alerta(
            "O PFX não contém certificados intermediários adicionais. "
            "Isso não significa automaticamente erro 290, porque a "
            "cadeia é uma validação separada e normalmente produziria "
            "cStat 293 se fosse o problema."
        )

    print()

    if falhas_290:
        erro("ENCONTRAMOS REQUISITOS DA REGRA 290 QUE NÃO PASSARAM:")
        for item in falhas_290:
            print(f"  * {item}")

        print()
        print(
            "Esse é o ponto mais importante do diagnóstico. "
            "Não altere DigestValue ou SignatureValue antes de resolver "
            "essas falhas do certificado."
        )
    else:
        ok(
            "Os requisitos locais que conseguimos testar diretamente "
            "para a regra 290 passaram."
        )

    print()

    if validade_ok:
        ok("Validade temporal passou.")
    else:
        erro(
            "Validade temporal falhou. Normalmente a SEFAZ possui "
            "rejeição específica 291 para esse caso."
        )

    print()

    if tls_response is not None:
        if "<cStat>107</cStat>" in tls_response.text:
            ok(
                "mTLS com SEFAZ-SP passou e o serviço respondeu 107."
            )
        else:
            alerta(
                "SEFAZ respondeu ao teste TLS, mas não retornou cStat 107."
            )

    print()
    print(
        "INTERPRETAÇÃO DOS CÓDIGOS MAIS IMPORTANTES:"
    )
    print("290 = certificado de assinatura inválido")
    print("291 = validade do certificado de assinatura")
    print("292 = certificado de assinatura sem CNPJ")
    print("293 = erro na cadeia de certificação")
    print("294 = certificado de assinatura revogado")
    print("295 = certificado difere ICP-Brasil")
    print("296 = erro de acesso à LCR")
    print("297 = assinatura difere do valor calculado")
    print("298 = assinatura difere do padrão do projeto")

    print()
    print(
        "Se este script apontar digital_signature=True, "
        "content_commitment=False, esse resultado merece atenção "
        "imediata porque a regra E01 do MOC associa Digital Signature "
        "e Não Recusa à validação que gera o cStat 290."
    )


def main():
    titulo("DIAGNÓSTICO COMPLETO DO CERTIFICADO NFC-e")

    cert_path = None
    key_path = None

    try:
        # ====================================================
        # 1. ARQUIVO
        # ====================================================

        titulo("[1] ARQUIVO PFX")

        print(f"Caminho: {PFX_PATH}")

        if not os.path.exists(PFX_PATH):
            raise FileNotFoundError(
                f"PFX não encontrado: {PFX_PATH}"
            )

        tamanho = os.path.getsize(PFX_PATH)
        print(f"Tamanho: {tamanho} bytes")

        sha256_arquivo = hashlib.sha256(
            open(PFX_PATH, "rb").read()
        ).hexdigest().upper()

        print(f"SHA256 arquivo: {sha256_arquivo}")

        ok("Arquivo PFX encontrado.")

        # ====================================================
        # 2. ABRIR PFX
        # ====================================================

        titulo("[2] ABERTURA DO PFX")

        with open(PFX_PATH, "rb") as arquivo:
            pfx_data = arquivo.read()

        private_key, certificate, adicionais = (
            pkcs12.load_key_and_certificates(
                pfx_data,
                SENHA_PFX.encode("utf-8")
            )
        )

        if private_key is None:
            raise Exception(
                "PFX abriu, mas não possui chave privada."
            )

        if certificate is None:
            raise Exception(
                "PFX abriu, mas não possui certificado final."
            )

        ok("PFX aberto com sucesso.")
        ok("Chave privada encontrada.")
        ok("Certificado encontrado.")

        print(
            f"Certificados adicionais: "
            f"{len(adicionais or [])}"
        )

        # ====================================================
        # 3. IDENTIDADE
        # ====================================================

        titulo("[3] IDENTIDADE DO CERTIFICADO")

        print("SUBJECT:")
        print(certificate.subject.rfc4514_string())

        print()
        print("ISSUER:")
        print(certificate.issuer.rfc4514_string())

        print()
        print(f"SERIAL: {certificate.serial_number}")

        print()
        print(
            "SHA1:",
            formatar_hex(
                fingerprint(
                    certificate,
                    hashes.SHA1()
                )
            )
        )

        print(
            "SHA256:",
            formatar_hex(
                fingerprint(
                    certificate,
                    hashes.SHA256()
                )
            )
        )

        # ====================================================
        # 4. CHAVE
        # ====================================================

        testar_correspondencia_chave(
            private_key,
            certificate
        )

        # ====================================================
        # 5. REGRA 290
        # ====================================================

        falhas_290 = diagnosticar_regra_290(
            certificate
        )

        # ====================================================
        # 6. VALIDADE
        # ====================================================

        validade_ok = diagnosticar_validade(
            certificate
        )

        # ====================================================
        # 7. EXTENSÕES
        # ====================================================

        imprimir_extensoes(
            certificate
        )

        # ====================================================
        # 8. CNPJ
        # ====================================================

        diagnosticar_cnpj(
            certificate
        )

        # ====================================================
        # 9. CADEIA / LCR
        # ====================================================

        diagnosticar_aia_crl(
            certificate
        )

        # ====================================================
        # 10. TLS
        # ====================================================

        tls_response = testar_tls_sefaz(
            private_key,
            certificate,
            adicionais
        )

        # ====================================================
        # 11. ASSINADOR REAL DO PROJETO
        # ====================================================

        diagnosticar_assinador_real_do_projeto(
            certificate
        )

        # ====================================================
        # 12. XML REAL DE UMA EMISSÃO, SE EXISTIR
        # ====================================================

        comparar_certificado_xml(
            certificate
        )

        # ====================================================
        # 13. RESUMO
        # ====================================================

        resumo(
            falhas_290,
            validade_ok,
            tls_response,
            adicionais
        )

    except Exception as exc:
        titulo("ERRO FATAL NO DIAGNÓSTICO")

        print(type(exc).__name__)
        print(str(exc))
        print()
        traceback.print_exc()

    finally:
        titulo("FIM DO DIAGNÓSTICO")


if __name__ == "__main__":
    main()