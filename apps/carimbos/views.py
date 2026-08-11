from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from urllib.parse import urlencode

from .forms import CopiaControladaForm
from .models import DistribuicaoCopia
from .services.guia_parser import GuiaParseError
from .services.guia_processor import (
    carregar_previa,
    listar_guias,
    processar_guia,
    raiz_guias,
)
from .services.pdf_stamper import PdfStampError, gerar_copia_controlada
from .services.revision_control import analisar_revisoes


def _nome_usuario(request):
    nome = request.user.get_full_name().strip()
    return nome or request.user.get_username()


@login_required
def criar_copia_controlada(request):
    if request.method == "POST":
        form = CopiaControladaForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = form.cleaned_data["arquivo_pdf"]
            try:
                resultado = gerar_copia_controlada(
                    arquivo.read(),
                    nome_original=arquivo.name,
                    numero_gi=form.cleaned_data["numero_gi"],
                    usuario=form.cleaned_data["usuario"],
                    emitido_em=timezone.localtime(),
                )
            except PdfStampError as exc:
                form.add_error("arquivo_pdf", str(exc))
            else:
                response = HttpResponse(
                    resultado.conteudo,
                    content_type="application/pdf",
                )
                response["Content-Disposition"] = (
                    f'attachment; filename="{resultado.nome_arquivo}"'
                )
                response["X-Content-Type-Options"] = "nosniff"
                return response
    else:
        form = CopiaControladaForm(initial={"usuario": _nome_usuario(request)})

    return render(
        request,
        "carimbos/criar_copia_controlada.html",
        {"form": form},
    )


@login_required
def guias_emissao(request):
    numero = request.GET.get("guia", "").strip()
    previa = None
    analise_revisoes = None
    destinatarios_exibicao = []
    erro = ""
    if numero:
        try:
            previa = carregar_previa(numero)
            analise_revisoes = analisar_revisoes(previa)
            destinatarios_exibicao = list(previa.destinatarios)
            existentes = {item.nome.casefold() for item in destinatarios_exibicao}
            from .services.guia_parser import DestinatarioGuia

            for impacto in analise_revisoes.impactos:
                if impacto.destinatario.casefold() not in existentes:
                    destinatarios_exibicao.append(
                        DestinatarioGuia(
                            impacto.destinatario,
                            impacto.email_destinatario,
                            na_guia=False,
                        )
                    )
                    existentes.add(impacto.destinatario.casefold())
        except GuiaParseError as exc:
            erro = str(exc)
    try:
        guias = listar_guias()
    except OSError as exc:
        guias = []
        erro = f"Não foi possível acessar a pasta oficial de GIs/GEs: {exc}"
    return render(
        request,
        "carimbos/guias_emissao.html",
        {
            "raiz_guias": raiz_guias(),
            "guias": guias,
            "numero_selecionado": numero,
            "previa": previa,
            "analise_revisoes": analise_revisoes,
            "destinatarios_exibicao": destinatarios_exibicao,
            "erro": erro,
        },
    )


@login_required
def processar_guia_emissao(request):
    if request.method != "POST":
        return redirect("carimbos:guias")
    numero = request.POST.get("guia", "").strip()
    destinatarios = request.POST.getlist("destinatarios")
    nomes_carimbo = {}
    for indice, nome_original in enumerate(request.POST.getlist("destinatarios_originais")):
        nomes_carimbo[nome_original] = request.POST.getlist("nomes_carimbo")[indice] if indice < len(request.POST.getlist("nomes_carimbo")) else nome_original
    try:
        resultado = processar_guia(
            numero,
            destinatarios_selecionados=destinatarios,
            nomes_carimbo=nomes_carimbo,
            corrigir_orientacao_paisagem=request.POST.get("corrigir_orientacao_paisagem") == "1",
            posicionar_em_espaco_livre=request.POST.get("posicionar_em_espaco_livre") == "1",
            usar_folha_controle=request.POST.get("usar_folha_controle") == "1",
            usuario=request.user,
        )
    except (GuiaParseError, PdfStampError, OSError) as exc:
        messages.error(request, f"GI/GE não processada: {exc}")
        return redirect(f"{reverse('carimbos:guias')}?{urlencode({'guia': numero})}")

    messages.success(
        request,
        (
            f"GI/GE {resultado.guia.numero} processada: "
            f"{resultado.copias_geradas} novas cópias, "
            f"{resultado.copias_atualizadas} cópias atualizadas e "
            f"{resultado.recolhimentos_abertos} recolhimentos abertos."
        ),
    )
    return redirect(f"{reverse('carimbos:guias')}?{urlencode({'guia': numero})}")


@login_required
def rastreabilidade(request):
    termo = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    registros = DistribuicaoCopia.objects.select_related("guia")
    if termo:
        registros = registros.filter(
            Q(documento__icontains=termo)
            | Q(guia__numero__icontains=termo)
            | Q(destinatario__icontains=termo)
        )
    if status:
        registros = registros.filter(status=status)
    return render(
        request,
        "carimbos/rastreabilidade.html",
        {
            "registros": registros[:500],
            "termo": termo,
            "status_selecionado": status,
            "status_choices": DistribuicaoCopia.STATUS_CHOICES,
            "pendentes": DistribuicaoCopia.objects.filter(
                status=DistribuicaoCopia.STATUS_RECOLHIMENTO_PENDENTE
            ).count(),
        },
    )


@login_required
def confirmar_recolhimento(request, pk):
    if request.method != "POST":
        return redirect("carimbos:rastreabilidade")
    registro = get_object_or_404(DistribuicaoCopia, pk=pk)
    registro.status = DistribuicaoCopia.STATUS_RECOLHIDA
    registro.recolhida_em = timezone.now()
    registro.recolhida_por = request.user
    registro.observacao = request.POST.get("observacao", "").strip()
    registro.save(
        update_fields=[
            "status",
            "recolhida_em",
            "recolhida_por",
            "observacao",
            "atualizado_em",
        ]
    )
    messages.success(request, "Recolhimento confirmado e registrado.")
    return redirect("carimbos:rastreabilidade")
