from django.core.management.base import BaseCommand
from apps.documentos.models import WorkflowEtapa


class Command(BaseCommand):
    help = "Cria/atualiza as etapas padrão do Workflow Enterprise Naval"

    def handle(self, *args, **kwargs):

        etapas = [
            (1, "Documento em Elaboração", 0),
            (2, "Revisão Interna", 5),
            (3, "Aprovação Técnica", 3),
            (4, "Doc Control", 2),
            (5, "Enviado ao Cliente", 0),
            (6, "Aprovação Cliente", 7),
            (7, "Emissão Final", 0),
        ]

        nomes_validos = []

        for ordem, nome, prazo in etapas:
            etapa, created = WorkflowEtapa.objects.update_or_create(
                ordem=ordem,
                defaults={
                    "nome": nome,
                    "prazo_dias": prazo,
                    "ativa": True,
                },
            )
            nomes_validos.append(nome)

            if created:
                self.stdout.write(self.style.SUCCESS(f"Etapa criada: {nome}"))
            else:
                self.stdout.write(self.style.WARNING(f"Etapa atualizada: {nome}"))

        # Opcional: desativar etapas antigas que não fazem mais parte do fluxo oficial
        WorkflowEtapa.objects.exclude(nome__in=nomes_validos).update(ativa=False)

        self.stdout.write(self.style.SUCCESS("Workflow Enterprise Naval configurado com sucesso!"))
