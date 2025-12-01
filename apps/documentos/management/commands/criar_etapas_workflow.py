from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from backend.apps.apps.documentos.models import WorkflowEtapa

class Command(BaseCommand):
    help = "Cria as etapas padrão do Workflow Enterprise"

    def handle(self, *args, **kwargs):
        
        etapas = [
            (1, "Revisão Interna – Disciplina", 5),
            (2, "Aprovação Técnica – Coordenador", 3),
            (3, "Envio ao Cliente", 0),
            (4, "Aprovação do Cliente", 7),
            (5, "Emissão Final", 0),
        ]

        for ordem, nome, prazo in etapas:
            etapa, created = WorkflowEtapa.objects.get_or_create(
                ordem=ordem,
                defaults={
                    "nome": nome,
                    "prazo_dias": prazo,
                    "ativa": True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Etapa criada: {nome}"))
            else:
                self.stdout.write(self.style.WARNING(f"Etapa já existe: {nome}"))
        
        self.stdout.write(self.style.SUCCESS("Workflow Enterprise configurado!"))
