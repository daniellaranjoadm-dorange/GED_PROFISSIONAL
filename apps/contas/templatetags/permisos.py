from django import template
from apps.contas.permissions import usuario_tem_permissao

register = template.Library()

@register.filter
def has_perm(usuario, perm):
    return usuario_tem_permissao(usuario, perm)




