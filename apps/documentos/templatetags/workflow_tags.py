from django import template
from django.utils.text import slugify

register = template.Library()

@register.filter
def wf_badge_class(etapa):
    """
    Retorna a classe CSS correta para a etapa do workflow.
    """

    if not etapa:
        return "wf-badge-default"

    etapa_slug = slugify(etapa)

    # MAPEAMENTO REAL DAS ETAPAS DO SEU WORKFLOW
    mapping = {
        "revisao-interna-disciplina": "wf-badge-revisao",
        "aprovacao-tecnica-coordenador": "wf-badge-aprovacao",
        "envio-ao-cliente": "wf-badge-envio",
        "aprovacao-do-cliente": "wf-badge-cliente",
        "emissao-final": "wf-badge-emissao",
    }

    # fallback
    return mapping.get(etapa_slug, "wf-badge-default")
