from django.core.management.base import BaseCommand
from apps.documentos.models import Documento


MAPEAMENTO = {
    "Revisão Interna – Disciplina": "REVISAO_INTERNA",
    "Aprovação Técnica – Coordenador": "APROVACAO_TECNICA",
    "Aprovação Técnica": "APROVACAO_TECNICA",
    "Doc Control": "DOC_CONTROL",
    "Enviado Cliente": "ENVIADO_CLIENTE",
    "Enviado ao Cliente": "ENVIADO_CLIENTE",
    "Aprovação Cliente": "APROVACAO_CLIENTE",
    "Emissão Final": "EMISSAO_FINAL",
}


class Command(BaseCommand):
    help = "Mapeia estados antigos para o novo workflow, sem perder dados."

    def handle(self, *args, **kwargs):
        documentos = Documento.objects.all()
        alterados = 0

        for doc in documentos:
            etapa_antiga = doc.etapa_atual

            if etapa_antiga in MAPEAMENTO:
                nova = MAPEAMENTO[etapa_antiga]
                doc.etapa_atual = nova
                doc.save(update_fields=["etapa_atual"])
                self.stdout.write(self.style.SUCCESS(f"{etapa_antiga} → {nova}"))
                alterados += 1

        self.stdout.write(self.style.WARNING(f"\nTotal de documentos ajustados: {alterados}"))
        self.stdout.write(self.style.SUCCESS("Mapeamento concluído!"))
