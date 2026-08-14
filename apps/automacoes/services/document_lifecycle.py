import re
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.automacoes.models import (
    DocumentoLD,
    PCFTimeline,
    PendenciaDocumental,
    TransmittalKM,
)
from apps.automacoes.services.document_registry_sync import (
    cadastrar_documentos_ausentes_da_ld,
    normalizar_identificador,
    normalizar_revisao,
    sincronizar_documentos_ld_com_ged,
)
from apps.documentos.models import (
    Documento,
    DocumentoMestre,
    DocumentoReferenciaExterna,
    DocumentoWorkflowHistorico,
    WorkflowEtapa,
)


ETAPAS = (
    ("ELABORACAO", "Documento em Elaboração", 1, 15),
    ("REVISAO_INTERNA", "Revisão Interna", 2, 10),
    ("APROVACAO_TECNICA", "Aprovação Técnica", 3, 7),
    ("DOC_CONTROL", "Doc Control", 4, 5),
    ("ENVIADO_CLIENTE", "Enviado ao Cliente", 5, 15),
    ("APROVACAO_CLIENTE", "Aprovação Cliente (PCF)", 6, 15),
    ("EMISSAO_FINAL", "Emissão Final", 7, 3),
)


def _peso_revisao(valor):
    texto = normalizar_revisao(valor)
    return (0, int(texto)) if texto.isdigit() else (1, texto)


def garantir_mestres_documentais():
    criados = vinculados = atualizados = 0
    grupos = {}
    for documento in Documento.objects.all().order_by("id"):
        chave = normalizar_identificador(documento.codigo)
        if not chave:
            continue
        mestre, criado = DocumentoMestre.objects.get_or_create(
            codigo_normalizado=chave,
            defaults={
                "codigo": documento.codigo,
                "titulo": documento.titulo or "",
                "disciplina": documento.disciplina or "",
            },
        )
        criados += int(criado)
        if documento.mestre_id != mestre.id:
            Documento.objects.filter(pk=documento.pk).update(mestre=mestre)
            vinculados += 1
        grupos.setdefault(mestre.id, []).append(documento)

    for mestre_id, revisoes in grupos.items():
        ativas = [d for d in revisoes if d.ativo and d.deletado_em is None]
        candidatas = ativas or revisoes
        atual = max(candidatas, key=lambda d: (_peso_revisao(d.revisao), d.id))
        mestre = DocumentoMestre.objects.get(pk=mestre_id)
        if mestre.revisao_atual_id != atual.id:
            mestre.revisao_atual = atual
            mestre.titulo = atual.titulo or mestre.titulo
            mestre.disciplina = atual.disciplina or mestre.disciplina
            mestre.save(update_fields=["revisao_atual", "titulo", "disciplina", "atualizado_em"])
            atualizados += 1
    return {"criados": criados, "vinculados": vinculados, "atuais": atualizados}


def enriquecer_documentos_pela_ld():
    atualizados = 0
    for documento in Documento.objects.filter(ativo=True, deletado_em__isnull=True).prefetch_related("registros_ld"):
        registros = list(documento.registros_ld.all())
        if not registros:
            continue
        principal = registros[0]
        campos = {
            "titulo": principal.titulo or documento.titulo,
            "disciplina": principal.disciplina or documento.disciplina,
            "status_documento": principal.status_documento or documento.status_documento,
            "status_emissao": principal.status_grd or documento.status_emissao,
        }
        alterados = [campo for campo, valor in campos.items() if getattr(documento, campo) != valor]
        if alterados:
            for campo in alterados:
                setattr(documento, campo, campos[campo])
            documento.save(update_fields=alterados)
            atualizados += 1
    return atualizados


def vincular_pcfs_revisoes():
    documentos_por_codigo = {}
    for documento in Documento.objects.filter(ativo=True, deletado_em__isnull=True):
        documentos_por_codigo.setdefault(normalizar_identificador(documento.codigo), []).append(documento)
    vinculados = ambiguos = 0
    for pcf in PCFTimeline.objects.all():
        candidatos = documentos_por_codigo.get(normalizar_identificador(pcf.numero_documento), [])
        if not candidatos:
            continue
        revisao = normalizar_revisao(pcf.revisao_pcf)
        exatos = [d for d in candidatos if normalizar_revisao(d.revisao) == revisao]
        escolhido = exatos[0] if len(exatos) == 1 else candidatos[0] if len(candidatos) == 1 else None
        if escolhido:
            if pcf.documento_ged_id != escolhido.id:
                PCFTimeline.objects.filter(pk=pcf.pk).update(documento_ged=escolhido)
            vinculados += 1
        else:
            ambiguos += 1
    return {"vinculados": vinculados, "ambiguos": ambiguos}


def vincular_transmittals_revisoes():
    indice = {}
    for ld in DocumentoLD.objects.exclude(numero_documento_km="").exclude(documento_ged=None):
        for numero in re.split(r"[|;,]", ld.numero_documento_km):
            chave = normalizar_identificador(numero)
            if chave:
                indice.setdefault(chave, set()).add(ld.documento_ged_id)
    vinculados = ambiguos = 0
    for evento in TransmittalKM.objects.all():
        candidatos = indice.get(normalizar_identificador(evento.documento), set())
        if len(candidatos) == 1:
            documento_id = next(iter(candidatos))
            if evento.documento_ged_id != documento_id:
                TransmittalKM.objects.filter(pk=evento.pk).update(documento_ged_id=documento_id)
            vinculados += 1
        elif len(candidatos) > 1:
            ambiguos += 1
    return {"vinculados": vinculados, "ambiguos": ambiguos}


def sincronizar_referencias_dox():
    criadas = atualizadas = 0
    for ld in DocumentoLD.objects.exclude(numero_interno="").exclude(documento_ged=None):
        referencia, criada = DocumentoReferenciaExterna.objects.get_or_create(
            sistema=DocumentoReferenciaExterna.SISTEMA_DOX,
            identificador_externo=ld.numero_interno.strip(),
            defaults={"documento_id": ld.documento_ged_id},
        )
        divergencias = []
        if referencia.documento_id != ld.documento_ged_id:
            divergencias.append("Identificador DOX relacionado a outro documento GED")
        status_externo = ld.status or ""
        referencia.status_externo = status_externo
        referencia.divergente = bool(divergencias)
        referencia.divergencias = divergencias
        referencia.conferido_em = timezone.now()
        referencia.sincronizado_em = timezone.now()
        referencia.metadados = {
            **(referencia.metadados or {}),
            "origem_ld": ld.origem_aba,
            "status_ld": ld.status_documento,
            "guia_emissao": ld.grd,
        }
        referencia.save()
        criadas += int(criada)
        atualizadas += int(not criada)
    return {"criadas": criadas, "atualizadas": atualizadas}


def _etapa_documento(registros):
    status_pcf = " ".join((r.status_final_pcf or "").upper() for r in registros)
    if "RELEASED" in status_pcf and "NOT RELEASED" not in status_pcf:
        return "EMISSAO_FINAL"
    if any(r.pcf for r in registros):
        return "APROVACAO_CLIENTE"
    if any((r.status_grd or "").upper() == "EMITIDO" for r in registros):
        return "ENVIADO_CLIENTE"
    if any("RECEB" in (r.status_documento or "").upper() for r in registros):
        return "DOC_CONTROL"
    return "ELABORACAO"


def sincronizar_workflow_documental():
    etapas = {}
    for codigo, nome, ordem, prazo in ETAPAS:
        etapa, _ = WorkflowEtapa.objects.update_or_create(
            codigo=codigo, defaults={"nome": nome, "ordem": ordem, "prazo_dias": prazo, "ativa": True}
        )
        etapas[codigo] = etapa
    atualizados = 0
    for documento in Documento.objects.filter(ativo=True, deletado_em__isnull=True).prefetch_related("registros_ld"):
        registros = list(documento.registros_ld.all())
        if not registros:
            continue
        codigo = _etapa_documento(registros)
        etapa = etapas[codigo]
        if documento.etapa_id != etapa.id:
            documento.etapa = etapa
            documento.etapa_atual = codigo
            documento.save(update_fields=["etapa", "etapa_atual"])
            documento._atualizar_status_workflow(etapa)
            DocumentoWorkflowHistorico.objects.create(
                documento=documento,
                etapa=etapa,
                usuario=None,
                acao="AJUSTE_MANUAL",
                observacao="Etapa sincronizada automaticamente pelos eventos documentais.",
                data=timezone.now(),
            )
            atualizados += 1
    return atualizados


def _abrir_pendencia(documento, ld, tipo, titulo, descricao, acao, severidade="ATENCAO", prazo_dias=None, metadados=None):
    chave = f"{documento.id}:{ld.id if ld else 0}:{tipo}"
    prazo = timezone.localdate() + timedelta(days=prazo_dias) if prazo_dias is not None else None
    pendencia, _ = PendenciaDocumental.objects.update_or_create(
        chave=chave,
        defaults={
            "documento": documento,
            "registro_ld": ld,
            "tipo": tipo,
            "titulo": titulo,
            "descricao": descricao,
            "acao_recomendada": acao,
            "origem": ld.origem_aba if ld else "GED",
            "severidade": severidade,
            "status": PendenciaDocumental.STATUS_ABERTA,
            "responsavel_texto": ld.resp_for_issue if ld else "",
            "prazo": prazo,
            "resolvida_em": None,
            "metadados": metadados or {},
        },
    )
    return pendencia.chave


def recalcular_pendencias_documentais():
    chaves_ativas = set()
    for ld in DocumentoLD.objects.select_related("documento_ged").exclude(documento_ged=None):
        documento = ld.documento_ged
        if not ld.caminho_documento:
            chaves_ativas.add(_abrir_pendencia(documento, ld, "ARQUIVO_AUSENTE", "Documento sem arquivo", "A LD não possui caminho de arquivo oficial.", "Localizar e vincular o arquivo oficial.", prazo_dias=3))
        if "RECEB" in (ld.status_documento or "").upper() and (ld.status_grd or "").upper() != "EMITIDO":
            chaves_ativas.add(_abrir_pendencia(documento, ld, "RECEBIDO_NAO_EMITIDO", "Recebido e não emitido", "Documento recebido ainda sem emissão por GRD.", "Preparar emissão e registrar a GRD.", severidade="CRITICA", prazo_dias=2))
        status_pcf = (ld.status_final_pcf or "").upper()
        if ld.pcf and (not status_pcf or "NOT RELEASED" in status_pcf):
            chaves_ativas.add(_abrir_pendencia(documento, ld, "PCF_NAO_LIBERADA", "PCF não liberada", f"Status atual: {ld.status_final_pcf or 'não informado'}.", "Tratar comentários e preparar resposta da PCF.", severidade="CRITICA", prazo_dias=5))
        try:
            abertos = int(float(str(ld.open_comments or "0").replace(",", ".")))
        except ValueError:
            abertos = 0
        if abertos > 0:
            chaves_ativas.add(_abrir_pendencia(documento, ld, "COMENTARIOS_ABERTOS", "Comentários em aberto", f"{abertos} comentário(s) ainda aberto(s).", "Atribuir responsáveis e concluir as tratativas.", severidade="CRITICA" if abertos >= 10 else "ATENCAO", prazo_dias=5, metadados={"open": abertos}))
        if ld.status_revisao_km == DocumentoLD.STATUS_REVISAO_KM_DIVERGENTE:
            chaves_ativas.add(_abrir_pendencia(documento, ld, "REVISAO_DIVERGENTE", "Revisão KM divergente", ld.observacao_revisao_km, "Conferir a revisão recebida e atualizar o vínculo.", severidade="CRITICA", prazo_dias=1))

    resolvidas = PendenciaDocumental.objects.filter(status__in=["ABERTA", "EM_TRATAMENTO"]).exclude(chave__in=chaves_ativas).update(status="RESOLVIDA", resolvida_em=timezone.now())
    return {"abertas": len(chaves_ativas), "resolvidas": resolvidas}


@transaction.atomic
def executar_ciclo_documental(*, usuario=None):
    cadastro = cadastrar_documentos_ausentes_da_ld(usuario=usuario)
    vinculos = sincronizar_documentos_ld_com_ged()
    return {
        "cadastro": cadastro,
        "vinculos_ld": vinculos,
        "mestres": garantir_mestres_documentais(),
        "documentos_enriquecidos": enriquecer_documentos_pela_ld(),
        "pcfs": vincular_pcfs_revisoes(),
        "transmittals": vincular_transmittals_revisoes(),
        "dox": sincronizar_referencias_dox(),
        "workflow": sincronizar_workflow_documental(),
        "pendencias": recalcular_pendencias_documentais(),
    }
