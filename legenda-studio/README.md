# Glimo Editor

Editor local de vídeo para Windows 11, com cortes manuais e automáticos, projetos recuperáveis e transcrição em português brasileiro.

## Recursos

- Interface PySide6 em português brasileiro com temas Automático, Claro e Escuro.
- O modo Automático acompanha o tema de aplicativos do Windows.
- Abertura de MP4, MOV, MKV, AVI, WEBM e M4V.
- Linha do tempo ampliada com régua, playhead, seleção ajustável e cortes claramente marcados.
- Corte automático de silêncios com FFmpeg e revisão não destrutiva antes da exportação.
- Salvamento de projetos `.glimo` com vídeo, posição, cortes e legendas.
- Recuperação automática dos vídeos recentes ao reabrir o aplicativo.
- Indicador de atividade e porcentagem para transcrição, análise de silêncio e exportação.
- Transcrição com `faster-whisper`, `large-v3-turbo`, CPU e INT8.
- Exportação H.264 MP4 com CRF 18, `yuv420p`, AAC 256 kbps e fast-start.
- Ícone amarelo e preto integrado à janela, executável e barra de tarefas.

O vídeo original nunca é alterado. Os cortes somente são aplicados ao MP4 exportado.

## Desenvolvimento local

Requer Python 3.11+ e FFmpeg disponível no `PATH`.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

O modelo `large-v3-turbo` é baixado pelo faster-whisper na primeira transcrição.

## Gerar o aplicativo Windows

O workflow GitHub Actions e o script local publicam:

- uma pasta portátil `dist/GlimoEditor/`;
- `GlimoEditor-windows-x64.zip`.

```powershell
python scripts\fetch_runtime.py
python scripts\build_windows.py
```

## Testes

```powershell
python -m unittest discover -s tests -v
python -m scripts.e2e_smoke
```

