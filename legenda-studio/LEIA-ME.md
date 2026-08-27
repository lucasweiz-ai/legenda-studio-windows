# Legenda Studio

## Uso rápido

1. Abra o `LegendaStudio.exe`.
2. Clique em **Abrir vídeo** e escolha um arquivo.
3. Clique em **Gerar legenda**. A primeira execução pode baixar o modelo de transcrição.
4. Revise as palavras e os horários na tabela à direita. Clique em uma palavra para ir até ela.
5. Para cortar, arraste no timeline, confira a área selecionada e clique em **Excluir trecho**.
6. Escolha **Exportar MP4** para salvar o resultado em um novo arquivo.

Os atalhos são `Espaço` para reproduzir/pausar, `Ctrl+O` para abrir, `Ctrl+E` para exportar e `Ctrl+Z` para desfazer o último corte.

O vídeo original permanece intacto. O exportador recusa o mesmo caminho do arquivo de origem e remove arquivos incompletos quando a operação é cancelada ou falha.

## Requisitos

O pacote portátil inclui Python, FFmpeg e a fonte usada nas legendas. Não é necessário instalar Python no computador que executará o `.exe`.

Arquivos sem áudio podem ser abertos e exportados normalmente; nesse caso não há transcrição disponível e a interface informa o motivo.