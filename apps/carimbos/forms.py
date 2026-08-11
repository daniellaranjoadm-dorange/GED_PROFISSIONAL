from pathlib import Path

from django import forms
from django.conf import settings


class CopiaControladaForm(forms.Form):
    arquivo_pdf = forms.FileField(
        label="Documento PDF",
        help_text="O arquivo original não será alterado.",
        widget=forms.ClearableFileInput(
            attrs={"accept": "application/pdf,.pdf", "class": "form-control"}
        ),
    )
    numero_gi = forms.CharField(
        label="Número da GI",
        max_length=80,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ex.: GI-2026-001",
                "autocomplete": "off",
            }
        ),
    )
    usuario = forms.CharField(
        label="Usuário da cópia",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nome de quem receberá a cópia",
                "autocomplete": "off",
            }
        ),
    )

    def clean_arquivo_pdf(self):
        arquivo = self.cleaned_data["arquivo_pdf"]
        limite_mb = getattr(settings, "CONTROLLED_COPY_MAX_UPLOAD_MB", 100)

        if Path(arquivo.name).suffix.lower() != ".pdf":
            raise forms.ValidationError("Selecione um arquivo com extensão .pdf.")
        if arquivo.size > limite_mb * 1024 * 1024:
            raise forms.ValidationError(
                f"O PDF excede o limite permitido de {limite_mb} MB."
            )

        assinatura = arquivo.read(5)
        arquivo.seek(0)
        if assinatura != b"%PDF-":
            raise forms.ValidationError("O arquivo selecionado não é um PDF válido.")
        return arquivo
