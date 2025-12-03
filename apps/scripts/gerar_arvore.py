import os

def listar_arvore(caminho, prefixo="", arquivo=None):
    itens = sorted(os.listdir(caminho))
    total = len(itens)

    for i, nome in enumerate(itens):
        caminho_completo = os.path.join(caminho, nome)
        conector = "└── " if i == total - 1 else "├── "

        linha = prefixo + conector + nome + "\n"
        arquivo.write(linha)

        if os.path.isdir(caminho_completo):
            extensao = "    " if i == total - 1 else "│   "
            listar_arvore(caminho_completo, prefixo + extensao, arquivo)


if __name__ == "__main__":
    # 📌 ALTERE AQUI PARA O CAMINHO DO SEU PROJETO
    raiz = r"D:\GED_PROFISSIONAL"

    saida = os.path.join(raiz, "tree.txt")

    with open(saida, "w", encoding="utf-8") as f:
        f.write(f"Árvore de diretórios de: {raiz}\n\n")
        listar_arvore(raiz, arquivo=f)

    print(f"Arquivo gerado com sucesso: {saida}")
