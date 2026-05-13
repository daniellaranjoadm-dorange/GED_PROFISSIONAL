import re


LD_TIPOS_DOCUMENTAIS_VALIDOS = {
    "AC", "AF", "AP", "AR", "AV", "BM", "BS", "CA", "CC", "CE", "CF", "CG",
    "CI", "CL", "CM", "CO", "CP", "CQ", "CR", "CT", "CV", "DB", "DC", "DE",
    "DF", "DI", "DL", "DO", "DR", "DT", "DU", "EE", "EC", "EM", "ES", "ET",
    "EQ", "FD", "GE", "GI", "ID", "IT", "IS", "LA", "LC", "LD", "LE", "LI",
    "LM", "LP", "LO", "LV", "LT", "MA", "MC", "MD", "MG", "MI", "ML", "MM",
    "MO", "NA", "NC", "NF", "NP", "NQ", "NT", "OA", "OC", "OG", "OS", "PC",
    "PE", "PG", "PI", "PJ", "PL", "PM", "PO", "PP", "PQ", "PR", "PT", "QT",
    "RA", "RC", "RD", "RE", "RH", "RL", "RM", "RV", "SC", "SM", "SP", "TF",
    "TI", "TP", "TR",
}


def _texto(valor):
    return str(valor or "").strip()


def extrair_tipo_documental(documento):
    """
    Extrai o tipo documental real do número do documento.

    Exemplos:
    24-7141-00-MA-001 -> MA
    I-PR-4880.00-9311-100-CZ1-001 -> PR
    """
    texto = _texto(documento).upper()
    if not texto:
        return ""

    for parte in re.split(r"[^A-Z0-9]+", texto):
        if parte in LD_TIPOS_DOCUMENTAIS_VALIDOS:
            return parte

    return ""
