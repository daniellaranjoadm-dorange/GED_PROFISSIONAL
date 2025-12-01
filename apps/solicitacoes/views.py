from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone

# Caminhos corrigidos para os apps locais
from apps.solicitacoes.forms import SolicitarAcessoForm
from apps.solicitacoes.models import SolicitarAcesso
from apps.solicitacoes.services import (
    notificar_nova_solicitacao,
    notificar_decisao_solicitacao,
    criar_usuario_para_solicitacao,
    registrar_auditoria_solicitacao,
)


@require_http_methods(["GET", "POST"])
def solicitar_acesso_view(request):
    """View pública para que qualquer usuário (logado ou não) solicite acesso."""
    if request.method == "POST":
        form = SolicitarAcessoForm(request.POST)
        if form.is_valid():
            instancia = form.save()

            # Notifica administradores sobre a nova solicitação
            notificar_nova_solicitacao(instancia)

            messages.success(
                request,
                "Sua solicitação foi enviada com sucesso. Em breve o setor responsável responderá.",
            )
            return redirect("solicitar_acesso_sucesso")
    else:
        form = SolicitarAcessoForm()

    return render(request, "solicitar_acesso/form.html", {"form": form})


def solicitar_acesso_sucesso(request):
    """Exibe a página de sucesso após o envio da solicitação."""
    return render(request, "solicitar_acesso/sucesso.html")


@staff_member_required
def listar_solicitacoes(request):
    """Lista somente para administradores / usuários staff."""
    solicitacoes = SolicitarAcesso.objects.all()
    return render(request, "solicitar_acesso/lista.html", {"solicitacoes": solicitacoes})


@staff_member_required
@require_http_methods(["GET", "POST"])
def detalhe_solicitacao(request, id):
    """Detalhamento da solicitação, permitindo aprovação ou rejeição."""
    solicitacao = get_object_or_404(SolicitarAcesso, id=id)

    if request.method == "POST":
        acao = request.POST.get("acao")
        observacao = request.POST.get("observacao", "")

        # Para auditoria
        status_anterior = solicitacao.status
        ip = request.META.get("REMOTE_ADDR")

        senha_temporaria = None
        usuario_criado = None

        if acao == "aprovar":
            usuario_criado, senha_temporaria, created = criar_usuario_para_solicitacao(
                solicitacao
            )

            solicitacao.status = SolicitarAcesso.STATUS_APROVADO
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

            notificar_decisao_solicitacao(
                solicitacao,
                senha_temporaria=senha_temporaria,
            )

            messages.success(request, "Solicitação aprovada com sucesso.")

        elif acao == "negar":
            solicitacao.status = SolicitarAcesso.STATUS_NEGADO
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

            notificar_decisao_solicitacao(
                solicitacao,
                senha_temporaria=None,
            )

            messages.warning(request, "Solicitação recusada.")

        return redirect("listar_solicitacoes")

    return render(
        request,
        "solicitar_acesso/detalhe.html",
        {"solicitacao": solicitacao},
    )
