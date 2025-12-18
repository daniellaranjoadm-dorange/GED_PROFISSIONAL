from django.core.management.base import BaseCommand
from apps.documentos.models import WorkflowEtapa


class Command(BaseCommand):
    help = "Cria ou atualiza as etapas oficiais do Workflow Enterprise D'ORANGE Naval"

    def handle(self, *args, **kwargs):

        # DEFINIÇÃO OFICIAL DAS ETAPAS S7 ENTERPRISE
        etapas = [
            ("ELABORACAO",         1, "Documento em Elaboração"),
            ("REVISAO_INTERNA",    2, "Revisão Interna"),
            ("APROVACAO_TECNICA",  3, "Aprovação Técnica"),
            ("DOC_CONTROL",        4, "Doc Control"),
            ("ENVIADO_CLIENTE",    5, "Enviado ao Cliente"),
            ("APROVACAO_CLIENTE",  6, "Aprovação Cliente"),
            ("EMISSAO_FINAL",      7, "Emissão Final"),
        ]

        self.stdout.write(self.style.WARNING("Configurando Workflow Enterprise Naval…"))

        # 1) Criar ou atualizar cada etapa
        etapas_criadas = []
        for codigo, ordem, nome in etapas:
            etapa, created = WorkflowEtapa.objects.update_or_create(
                codigo=codigo,
                defaults={
                    "nome": nome,
                    "ordem": ordem,
                    "prazo_dias": 15,       # conforme sua escolha
                    "ativa": True,
                },
            )
            etapas_criadas.append(etapa)

            if created:
                self.stdout.write(self.style.SUCCESS(f"Etapa criada: {ordem} - {nome}"))
            else:
                self.stdout.write(self.style.WARNING(f"Etapa atualizada: {ordem} - {nome}"))

        # 2) Configurar automaticamente as próximas etapas
        for i, etapa in enumerate(etapas_criadas):
            if i < len(etapas_criadas) - 1:
                etapa.proxima_etapa = etapas_criadas[i + 1]
            else:
                etapa.proxima_etapa = None  # Emissão Final não tem próxima etapa
            etapa.save()

        self.stdout.write(self.style.SUCCESS("Próximas etapas configuradas com sucesso."))

        # 3) Desativar qualquer etapa antiga
        WorkflowEtapa.objects.exclude(codigo__in=[e[0] for e in etapas]).update(ativa=False)

        self.stdout.write(self.style.SUCCESS("Workflow Enterprise Naval configurado com sucesso!"))
