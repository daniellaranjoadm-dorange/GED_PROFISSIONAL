from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.template import TemplateDoesNotExist
from django.http import HttpResponse
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import transaction
from django.db.models import Q
import logging

from .models import Role, UserConfig, UserRole, Usuario
from .forms import UserConfigForm
from .permissions import has_perm

logger = logging.getLogger(__name__)


def landing(request):
    """
    Entrada principal do sistema.

    A landing institucional antiga foi descontinuada do fluxo operacional.
    Usuários autenticados e visitantes são direcionados ao painel enterprise.
    O login_required da rota de destino cuida do redirecionamento para login.
    """
    return redirect("automacoes:painel")


def login_view(request):
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        try:
            user = authenticate(request, username=username, password=password)
        except Exception:
            logger.exception("Erro no authenticate() dentro do login_view")
            messages.error(request, "Erro interno ao validar suas credenciais.")
            return render(request, "contas/login.html")

        if user:
            login(request, user)

            # next seguro (evita open-redirect)
            next_url = (
                request.POST.get("next")
                or request.GET.get("next")
                or reverse("automacoes:painel")
            )

            if not url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                next_url = reverse("automacoes:painel")

            return redirect(next_url)

        messages.error(request, "Usuário ou senha incorretos!")

    return render(request, "contas/login.html")


def logout_view(request):
    logout(request)
    return redirect("contas:login")


@login_required
def minhas_configuracoes(request):
    try:
        config, _ = UserConfig.objects.get_or_create(user=request.user)
    except Exception:
        logger.exception("Falha ao carregar/criar UserConfig")
        return HttpResponse("Erro ao carregar configurações do usuário.", status=500)

    try:
        if request.method == "POST":
            form = UserConfigForm(request.POST, instance=config)
            if form.is_valid():
                form.save()
                messages.success(request, "Configurações atualizadas com sucesso!")
                return redirect("contas:minhas_configuracoes")
        else:
            form = UserConfigForm(instance=config)
    except Exception:
        logger.exception("Falha ao processar UserConfigForm")
        return HttpResponse("Erro ao processar formulário.", status=500)

    try:
        return render(request, "contas/minhas_configuracoes.html", {"form": form})
    except TemplateDoesNotExist:
        # fallback simples (não quebra)
        return HttpResponse(form.as_p())


def is_master(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, "is_master", False))


# ✅ Compatibilidade:
# tudo que for "Solicitação de Acesso" fica no app solicitacoes.
# aqui no contas a gente só redireciona (compatibilidade com links antigos)
def solicitar_acesso(request):
    return redirect("solicitacoes:solicitar_acesso")


@login_required
@user_passes_test(is_master)
def painel_solicitacoes(request):
    return redirect("solicitacoes:listar_solicitacoes")


@login_required
@user_passes_test(is_master)
def aprovar_solicitacao(request, id):
    # fluxo oficial de aprovar/negar é no detalhe (POST).
    return redirect("solicitacoes:detalhe_solicitacao", id=id)


@login_required
@user_passes_test(is_master)
def negar_solicitacao(request, id):
    # fluxo oficial de aprovar/negar é no detalhe (POST).
    return redirect("solicitacoes:detalhe_solicitacao", id=id)


@login_required
@user_passes_test(is_master)
def usuarios_permissoes_admin_legacy(request):
    """
    Vai para o Django Admin do seu User customizado (contas.Usuario).
    (O /admin/auth/user/ dá 404 porque você não usa o User padrão do Django.)
    """
    try:
        return redirect(reverse("admin:contas_usuario_changelist"))
    except NoReverseMatch:
        # fallback garantido
        return redirect("/admin/contas/usuario/")


@has_perm("administracao.gerenciar")
def usuarios_permissoes(request):
    """Central segura para atribuição dos papéis operacionais do GED."""
    if request.method == "POST":
        usuario_id = request.POST.get("usuario_id")
        role_ids = request.POST.getlist("roles")
        try:
            alvo = Usuario.objects.get(pk=usuario_id)
        except (Usuario.DoesNotExist, ValueError, TypeError):
            messages.error(request, "Usuário não localizado.")
            return redirect("contas:usuarios_permissoes")

        if alvo.pk == request.user.pk:
            messages.error(request, "Seu próprio acesso não pode ser alterado nesta tela.")
            return redirect("contas:usuarios_permissoes")
        if alvo.is_superuser or alvo.is_master:
            messages.error(request, "Contas Master são protegidas contra alteração por esta tela.")
            return redirect("contas:usuarios_permissoes")

        roles_permitidos = Role.objects.filter(pk__in=role_ids)
        if not request.user.is_superuser:
            roles_permitidos = roles_permitidos.exclude(nome="MASTER")
        roles_validos = list(roles_permitidos.order_by("nome"))
        if len(roles_validos) != len(set(role_ids)):
            messages.error(request, "Um dos perfis selecionados não é válido.")
            return redirect("contas:usuarios_permissoes")

        with transaction.atomic():
            ids_validos = [role.pk for role in roles_validos]
            UserRole.objects.filter(user=alvo).exclude(role_id__in=ids_validos).delete()
            for role in roles_validos:
                UserRole.objects.get_or_create(user=alvo, role=role)

        nomes = ", ".join(role.nome for role in roles_validos) or "SEM PERFIL"
        messages.success(request, f"Acessos de {alvo.username} atualizados: {nomes}.")
        return redirect(f"{reverse('contas:usuarios_permissoes')}?q={alvo.username}")

    busca = (request.GET.get("q") or "").strip()
    usuarios = Usuario.objects.all().order_by("first_name", "username")
    if busca:
        usuarios = usuarios.filter(
            Q(username__icontains=busca) | Q(first_name__icontains=busca)
            | Q(last_name__icontains=busca) | Q(email__icontains=busca)
        )

    roles_catalogo = Role.objects.prefetch_related("permissoes").order_by("nome")
    roles = list(roles_catalogo if request.user.is_superuser else roles_catalogo.exclude(nome="MASTER"))
    vinculos = UserRole.objects.filter(user__in=usuarios).select_related("role")
    roles_por_usuario = {}
    for vinculo in vinculos:
        roles_por_usuario.setdefault(vinculo.user_id, []).append(vinculo.role)

    usuarios_cards = []
    for usuario in usuarios:
        papeis = roles_por_usuario.get(usuario.pk, [])
        codigos = sorted({
            codigo for papel in papeis
            for codigo in papel.permissoes.values_list("codigo", flat=True)
        })
        usuarios_cards.append({
            "usuario": usuario, "roles": papeis,
            "role_ids": [papel.pk for papel in papeis], "permissoes": codigos,
            "protegido": usuario.pk == request.user.pk or usuario.is_superuser or usuario.is_master,
        })

    return render(request, "contas/usuarios_permissoes.html", {
        "usuarios_cards": usuarios_cards, "roles": roles, "busca": busca,
        "total_usuarios": Usuario.objects.count(),
        "total_ativos": Usuario.objects.filter(is_active=True).count(),
        "total_sem_perfil": Usuario.objects.exclude(
            pk__in=UserRole.objects.values_list("user_id", flat=True)
        ).filter(is_superuser=False, is_master=False).count(),
    })
