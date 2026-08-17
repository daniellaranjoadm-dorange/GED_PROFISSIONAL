from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from apps.carimbos.models import DistribuicaoCopia, GuiaEmissao

from .guia_parser import (
    DadosGuia,
    GuiaParseError,
    ler_guia,
    normalizar_documento,
)
from .pdf_stamper import gerar_copia_controlada
from .revision_control import REVISAO_SUPERIOR, comparar_revisoes


@dataclass(frozen=True)
class ResultadoProcessamento:
    guia: GuiaEmissao
    copias_geradas: int
    copias_atualizadas: int
    recolhimentos_abertos: int


def raiz_guias() -> Path:
    return Path(settings.GUIAS_EMISSAO_ROOT)


def listar_guias() -> list[str]:
    raiz = raiz_guias()
    if not raiz.exists():
        return []
    guias = {
        arquivo.stem
        for arquivo in raiz.glob("*.pdf")
        if any(tipo in arquivo.stem.upper() for tipo in ("-GI-", "-GE-"))
    }
    # Algumas GEs armazenam o PDF da própria guia dentro da subpasta homônima,
    # junto dos documentos técnicos.
    for pasta in raiz.iterdir():
        if not pasta.is_dir() or not any(tipo in pasta.name.upper() for tipo in ("-GI-", "-GE-")):
            continue
        guia_interna = pasta / f"{pasta.name}.pdf"
        if guia_interna.is_file():
            guias.add(pasta.name)
    return sorted(guias, reverse=True)


def resolver_guia(numero: str) -> tuple[Path, Path]:
    nome = Path(numero.strip()).stem
    if not nome or nome in {".", ".."} or any(c in nome for c in ("/", "\\", ":")):
        raise GuiaParseError("Número de guia inválido.")
    raiz = raiz_guias().resolve()
    pasta = (raiz / nome).resolve()
    caminho_raiz = (raiz / f"{nome}.pdf").resolve()
    caminho_interno = (pasta / f"{nome}.pdf").resolve()
    if caminho_raiz.parent != raiz or pasta.parent != raiz or caminho_interno.parent != pasta:
        raise GuiaParseError("A guia deve estar dentro da pasta oficial de emissão.")
    caminho = caminho_raiz if caminho_raiz.is_file() else caminho_interno
    if not caminho.is_file():
        raise GuiaParseError(f"Guia não encontrada: {nome}.pdf")
    if not pasta.is_dir():
        raise GuiaParseError(f"A pasta de documentos da guia não foi encontrada: {nome}")
    return caminho, pasta


def carregar_previa(numero: str) -> DadosGuia:
    caminho, pasta = resolver_guia(numero)
    return ler_guia(caminho, pasta)


def _nome_pasta(nome: str) -> str:
    seguro = re.sub(r"[^A-Za-z0-9_-]+", "_", nome).strip("_")
    return seguro.upper() or "DESTINATARIO"


def _arquivos_documentos(dados: DadosGuia) -> list[tuple[Path, str, str]]:
    candidatos = [
        item
        for item in dados.pasta_documentos.glob("*.pdf")
        if "COPIA_CONTROLADA" not in item.name.upper()
        and item.stem.upper() != dados.caminho.stem.upper()
    ]
    encontrados = []
    usados = set()
    for documento in dados.documentos:
        alvo = normalizar_documento(documento.numero)
        for arquivo in candidatos:
            chave = normalizar_documento(arquivo.stem)
            if alvo in chave or chave in alvo:
                if arquivo not in usados:
                    encontrados.append((arquivo, documento.numero, documento.revisao))
                    usados.add(arquivo)
                break
    if not encontrados and len(dados.documentos) == 1 and len(candidatos) == 1:
        doc = dados.documentos[0]
        encontrados.append((candidatos[0], doc.numero, doc.revisao))
    if len(encontrados) != len(dados.documentos):
        raise GuiaParseError(
            "Nem todos os documentos relacionados na guia foram encontrados na subpasta."
        )
    return encontrados


def processar_guia(
    numero: str,
    *,
    destinatarios_selecionados: list[str],
    nomes_carimbo: dict[str, str] | None = None,
    meios_distribuicao: dict[str, str] | None = None,
    quantidades: dict[str, int] | None = None,
    corrigir_orientacao_paisagem: bool = False,
    posicionar_em_espaco_livre: bool = False,
    usar_folha_controle: bool = False,
    usuario,
) -> ResultadoProcessamento:
    dados = carregar_previa(numero)
    selecionados = {nome.casefold() for nome in destinatarios_selecionados}
    destinatarios = [
        item for item in dados.destinatarios if item.nome.casefold() in selecionados
    ]
    nomes_encontrados = {item.nome.casefold() for item in destinatarios}
    if selecionados - nomes_encontrados:
        anteriores_por_nome = {
            item.destinatario.casefold(): item
            for item in DistribuicaoCopia.objects.filter(
                destinatario__isnull=False
            ).order_by("destinatario", "-emitida_em")
            if item.destinatario.casefold() in selecionados - nomes_encontrados
        }
        from .guia_parser import DestinatarioGuia

        destinatarios.extend(
            DestinatarioGuia(item.destinatario, item.email_destinatario, na_guia=False)
            for item in anteriores_por_nome.values()
        )
    if not destinatarios:
        raise GuiaParseError("Selecione pelo menos um destinatário.")
    nomes_carimbo = {
        str(chave).casefold(): str(valor).strip()
        for chave, valor in (nomes_carimbo or {}).items()
        if str(valor).strip()
    }
    meios_validos = {valor for valor, _ in DistribuicaoCopia.MEIO_CHOICES}
    meios_distribuicao = {
        str(chave).casefold(): str(valor).strip().upper()
        for chave, valor in (meios_distribuicao or {}).items()
        if str(valor).strip().upper() in meios_validos
    }
    quantidades = {
        str(chave).casefold(): max(1, min(99, int(valor)))
        for chave, valor in (quantidades or {}).items()
        if str(valor).strip().isdigit()
    }
    arquivos = _arquivos_documentos(dados)

    guia, _ = GuiaEmissao.objects.update_or_create(
        numero=dados.numero,
        defaults={
            "caminho_guia": str(dados.caminho),
            "pasta_documentos": str(dados.pasta_documentos),
            "data_emissao": dados.data_emissao,
            "remetente": dados.remetente,
            "email_remetente": dados.email_remetente,
            "processada_por": usuario,
        },
    )
    copias = 0
    atualizadas = 0
    recolhimentos = 0

    for arquivo, documento, revisao in arquivos:
        normalizado = normalizar_documento(documento)
        anteriores = DistribuicaoCopia.objects.filter(
            documento_normalizado=normalizado,
            status__in=(
                DistribuicaoCopia.STATUS_EMITIDA,
                DistribuicaoCopia.STATUS_ENTREGUE,
            ),
        )
        ids_obsoletos = [
            item.pk
            for item in anteriores.only("pk", "revisao")
            if comparar_revisoes(revisao, item.revisao) == REVISAO_SUPERIOR
        ]
        recolhimentos += anteriores.filter(pk__in=ids_obsoletos).update(
            status=DistribuicaoCopia.STATUS_RECOLHIMENTO_PENDENTE
        )

        for destinatario in destinatarios:
            chave_destinatario = destinatario.nome.casefold()
            nome_carimbo = nomes_carimbo.get(chave_destinatario, destinatario.nome)
            pasta_saida = (
                dados.pasta_documentos
                / "COPIAS_CONTROLADAS"
                / _nome_pasta(destinatario.nome)
            )
            pasta_saida.mkdir(parents=True, exist_ok=True)
            existente = DistribuicaoCopia.objects.filter(
                guia=guia,
                documento_normalizado=normalizado,
                revisao=revisao,
                destinatario=destinatario.nome,
            ).first()
            resultado_pdf = gerar_copia_controlada(
                arquivo.read_bytes(),
                nome_original=arquivo.name,
                numero_gi=dados.numero,
                usuario=nome_carimbo,
                emitido_por=dados.remetente,
                emitido_em=dados.data_emissao,
                corrigir_orientacao_paisagem=corrigir_orientacao_paisagem,
                posicionar_em_espaco_livre=posicionar_em_espaco_livre,
                usar_folha_controle=usar_folha_controle,
            )
            destino = pasta_saida / resultado_pdf.nome_arquivo
            temporario = destino.with_suffix(".tmp")
            temporario.write_bytes(resultado_pdf.conteudo)
            temporario.replace(destino)

            _, criado = DistribuicaoCopia.objects.update_or_create(
                guia=guia,
                documento_normalizado=normalizado,
                revisao=revisao,
                destinatario=destinatario.nome,
                defaults={
                    "documento": documento,
                    "arquivo_origem": str(arquivo),
                    "email_destinatario": destinatario.email,
                    "recebedor_carimbo": nome_carimbo,
                    "meio_distribuicao": meios_distribuicao.get(
                        chave_destinatario,
                        DistribuicaoCopia.MEIO_NAO_INFORMADO,
                    ),
                    "quantidade": quantidades.get(chave_destinatario, 1),
                    "caminho_copia": str(destino),
                    "emitida_em": dados.data_emissao,
                },
            )
            copias += int(criado)
            atualizadas += int(not criado)

    return ResultadoProcessamento(
        guia=guia,
        copias_geradas=copias,
        copias_atualizadas=atualizadas,
        recolhimentos_abertos=recolhimentos,
    )
