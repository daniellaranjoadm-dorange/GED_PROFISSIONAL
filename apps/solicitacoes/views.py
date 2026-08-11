from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import FieldError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods

from apps.contas.models import Role
from apps.contas.permissions import has_perm
from apps.contas.rbac_catalog import PERFIS_OPERACIONAIS
from .forms import SolicitarAcessoForm
from .models import SolicitarAcesso
from .services import (
    criar_usuario_para_solicitacao, notificar_decisao_solicitacao,
    notificar_nova_solicitacao, registrar_auditoria_solicitacao,
)


@require_http_methods(["GET", "POST"])
def solicitar_acesso_view(request):
    form = SolicitarAcessoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        instancia = form.save()
        notificar_nova_solicitacao(instancia)
        messages.success(request, "Solicitação enviada. O Master Admin fará a análise.")
        return redirect("solicitacoes:solicitar_acesso_sucesso")
    return render(request, "solicitar_acesso/form.html", {"form": form})


def solicitar_acesso_sucesso(request):
    return render(request, "solicitar_acesso/sucesso.html")


@has_perm("administracao.gerenciar")
def listar_solicitacoes(request):
    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao == "arquivar_concluidas":
            atualizadas = SolicitarAcesso.objects.filter(
                arquivada=False, status__in=[SolicitarAcesso.STATUS_APROVADO, SolicitarAcesso.STATUS_NEGADO]
            ).update(arquivada=True, data_arquivamento=timezone.now(), arquivada_por=request.user)
            messages.success(request, f"{atualizadas} solicitação(ões) concluída(s) arquivada(s).")
        elif acao == "restaurar_todas":
            atualizadas = SolicitarAcesso.objects.filter(arquivada=True).update(
                arquivada=False, data_arquivamento=None, arquivada_por=None
            )
            messages.success(request, f"{atualizadas} solicitação(ões) restaurada(s).")
        return redirect("solicitacoes:listar_solicitacoes")

    visualizacao = request.GET.get("visualizacao", "ativas")
    qs = SolicitarAcesso.objects.select_related("perfil_solicitado", "perfil_concedido")
    if visualizacao == "arquivadas":
        qs = qs.filter(arquivada=True)
    elif visualizacao == "todas":
        pass
    else:
        visualizacao = "ativas"
        qs = qs.filter(arquivada=False)
    try:
        qs = qs.order_by("-data_solicitacao", "-id")
    except FieldError:
        qs = qs.order_by("-id")
    return render(request, "solicitar_acesso/lista.html", {
        "solicitacoes": qs, "visualizacao": visualizacao,
        "total_pendentes": SolicitarAcesso.objects.filter(arquivada=False, status=SolicitarAcesso.STATUS_PENDENTE).count(),
        "total_arquivadas": SolicitarAcesso.objects.filter(arquivada=True).count(),
        "total_concluidas_ativas": SolicitarAcesso.objects.filter(arquivada=False, status__in=[SolicitarAcesso.STATUS_APROVADO, SolicitarAcesso.STATUS_NEGADO]).count(),
    })


@has_perm("administracao.gerenciar")
@require_http_methods(["GET", "POST"])
def detalhe_solicitacao(request, id):
    solicitacao = get_object_or_404(SolicitarAcesso, id=id)
    if request.method == "POST":
        acao = (request.POST.get("acao") or "").strip().lower()
        observacao = (request.POST.get("observacao") or "").strip()
        status_anterior = solicitacao.status
        ip = request.META.get("REMOTE_ADDR")

        if solicitacao.status != SolicitarAcesso.STATUS_PENDENTE:
            messages.warning(request, "Esta solicitação já foi analisada.")
            return redirect("solicitacoes:listar_solicitacoes")

        if acao == "aprovar":
            role = Role.objects.filter(pk=request.POST.get("perfil_concedido"), nome__in=PERFIS_OPERACIONAIS).first()
            if not role:
                messages.error(request, "Selecione um perfil operacional válido antes de aprovar.")
                return redirect("solicitacoes:detalhe_solicitacao", id=id)

            with transaction.atomic():
                usuario, _created = criar_usuario_para_solicitacao(solicitacao, role)
                solicitacao.status = SolicitarAcesso.STATUS_APROVADO
                solicitacao.perfil_concedido = role
                solicitacao.data_decisao = timezone.now()
                solicitacao.observacao_admin = observacao
                solicitacao.save()
                registrar_auditoria_solicitacao(
                    solicitacao, request.user, status_anterior, solicitacao.status, ip,
                    f"{observacao}\nPerfil concedido: {role.nome}".strip(), usuario,
                )

            uid = urlsafe_base64_encode(force_bytes(usuario.pk))
            token = default_token_generator.make_token(usuario)
            convite_url = request.build_absolute_uri(
                reverse("solicitacoes:aceitar_convite", kwargs={"uidb64": uid, "token": token})
            )
            notificar_decisao_solicitacao(solicitacao, convite_url)
            messages.success(request, "Solicitação aprovada. Convite seguro enviado ao colaborador.")

        elif acao == "negar":
            solicitacao.status = SolicitarAcesso.STATUS_NEGADO
            solicitacao.data_decisao = timezone.now()
            solicitacao.observacao_admin = observacao
            solicitacao.save()
            registrar_auditoria_solicitacao(
                solicitacao, request.user, status_anterior, solicitacao.status, ip, observacao, None,
            )
            notificar_decisao_solicitacao(solicitacao)
            messages.warning(request, "Solicitação recusada.")
        else:
            messages.error(request, "Ação inválida.")
            return redirect("solicitacoes:detalhe_solicitacao", id=id)
        return redirect("solicitacoes:listar_solicitacoes")

    roles = Role.objects.filter(nome__in=PERFIS_OPERACIONAIS).order_by("nome")
    return render(request, "solicitar_acesso/detalhe.html", {"solicitacao": solicitacao, "roles": roles})


@require_http_methods(["GET", "POST"])
def aceitar_convite(request, uidb64, token):
    User = get_user_model()
    try:
        usuario = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        usuario = None
    if usuario is None or not default_token_generator.check_token(usuario, token):
        return render(request, "solicitar_acesso/convite_invalido.html", status=400)

    form = SetPasswordForm(usuario, request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save(commit=False)
        usuario.is_active = True
        usuario.save(update_fields=["password", "is_active"])
        messages.success(request, "Senha criada com sucesso. Sua conta está ativa.")
        return redirect("contas:login")
    return render(request, "solicitar_acesso/aceitar_convite.html", {"form": form, "usuario": usuario})
