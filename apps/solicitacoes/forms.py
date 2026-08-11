from django import forms
from .models import SolicitarAcesso
from apps.contas.models import Role, Usuario
from apps.contas.rbac_catalog import PERFIS_OPERACIONAIS

class SolicitarAcessoForm(forms.ModelForm):
    class Meta:
        model = SolicitarAcesso
        fields = ["nome", "email", "setor", "projeto_empresa", "perfil_solicitado", "motivo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Seu nome completo"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Seu e-mail"}),
            "setor": forms.TextInput(attrs={"class": "form-control", "placeholder": "Seu setor / departamento"}),
            "projeto_empresa": forms.TextInput(attrs={"class": "form-control", "placeholder": "Projeto, empresa ou contrato"}),
            "perfil_solicitado": forms.Select(attrs={"class": "form-select"}),
            "motivo": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Explique brevemente o motivo da solicitação"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["perfil_solicitado"].queryset = Role.objects.filter(nome__in=PERFIS_OPERACIONAIS).order_by("nome")
        self.fields["perfil_solicitado"].required = True
        self.fields["perfil_solicitado"].empty_label = "Selecione o perfil necessário"

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta cadastrada com este e-mail.")
        if SolicitarAcesso.objects.filter(email__iexact=email, status=SolicitarAcesso.STATUS_PENDENTE).exists():
            raise forms.ValidationError("Já existe uma solicitação pendente para este e-mail.")
        return email

    def clean_motivo(self):
        motivo = (self.cleaned_data.get("motivo") or "").strip()
        if len(motivo) < 10:
            raise forms.ValidationError("O motivo deve ter ao menos 10 caracteres.")
        return motivo
