from __future__ import annotations

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.exceptions import FieldError

from .forms import SolicitarAcessoForm
from .models import SolicitarAcesso

# Services (se existir). Se não existir no deploy, vira no-op e não quebra.
try:
    from .services import (
        notificar_nova_solicitacao,
        notificar_decisao_solicitacao,
        criar_usuario_para_solicitacao,
        registrar_auditoria_solicitacao,
    )
except Exception:
    def notificar_nova_solicitacao(*args, **kwargs):  # type: ignore
        return None

    def notificar_decisao_solicitacao(*args, **kwargs):  # type: ignore
        return None

    def criar_usuario_para_solicitacao(*args, **kwargs):  # type: ignore
        return (None, None, False)

    def registrar_auditoria_solicitacao(*args, **kwargs):  # type: ignore
        return None


@require_http_methods(["GET", "POST"])
def solicitar_acesso_view(request):
    """Form público (logado ou não) para solicitar acesso."""
    if request.method == "POST":
        form = SolicitarAcessoForm(request.POST)
        if form.is_valid():
            instancia = form.save()
            notificar_nova_solicitacao(instancia)

            messages.success(
                request,
                "Sua solicitação foi enviada com sucesso. Em breve o responsável responderá.",
            )
            return redirect("solicitacoes:solicitar_acesso_sucesso")
    else:
        form = SolicitarAcessoForm()

    return render(request, "solicitar_acesso/form.html", {"form": form})


def solicitar_acesso_sucesso(request):
    return render(request, "solicitar_acesso/sucesso.html")


@staff_member_required
def listar_solicitacoes(request):
    qs = SolicitarAcesso.objects.all()

    # Ordenação resiliente (depende dos campos reais do model)
    try:
        qs = qs.order_by("-data_solicitacao", "-id")
    except FieldError:
        try:
            qs = qs.order_by("-data", "-id")
        except FieldError:
            qs = qs.order_by("-id")

    return render(request, "solicitar_acesso/lista.html", {"solicitacoes": qs})


@staff_member_required
@require_http_methods(["GET", "POST"])
def detalhe_solicitacao(request, id: int):
    solicitacao = get_object_or_404(SolicitarAcesso, id=id)

    STATUS_APROVADO = getattr(SolicitarAcesso, "STATUS_APROVADO", "aprovado")
    STATUS_NEGADO = getattr(SolicitarAcesso, "STATUS_NEGADO", "negado")

    if request.method == "POST":
        acao = (request.POST.get("acao") or "").strip().lower()
        observacao = request.POST.get("observacao", "").strip()

        status_anterior = getattr(solicitacao, "status", None)
        ip = request.META.get("REMOTE_ADDR")

        senha_temporaria = None
        usuario_criado = None

        if acao == "aprovar":
            usuario_criado, senha_temporaria, _created = criar_usuario_para_solicitacao(solicitacao)

            solicitacao.status = STATUS_APROVADO
            solicitacao.data_decisao = timezone.now()
            solicitacao.observacao_admin = observacao
            solicitacao.save()

            registrar_auditoria_solicitacao(
                instancia=solicitacao,
                usuario_responsavel=request.user,
                status_anterior=status_anterior,
                status_novo=solicitacao.status,
                ip=ip,
                observacao=observacao,
                usuario_criado=usuario_criado,
            )

            notificar_decisao_solicitacao(solicitacao, senha_temporaria=senha_temporaria)
            messages.success(request, "Solicitação aprovada com sucesso.")

        elif acao == "negar":
            solicitacao.status = STATUS_NEGADO
            solicitacao.data_decisao = timezone.now()
            solicitacao.observacao_admin = observacao
            solicitacao.save()

            registrar_auditoria_solicitacao(
                instancia=solicitacao,
                usuario_responsavel=request.user,
                status_anterior=status_anterior,
                status_novo=solicitacao.status,
                ip=ip,
                observacao=observacao,
                usuario_criado=None,
            )

            notificar_decisao_solicitacao(solicitacao, senha_temporaria=None)
            messages.warning(request, "Solicitação recusada.")

        return redirect("solicitacoes:listar_solicitacoes")

    return render(request, "solicitar_acesso/detalhe.html", {"solicitacao": solicitacao})
