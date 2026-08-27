# Legenda Studio

Editor local de vídeo para Windows 11, com transcrição em português brasileiro e legendas de uma palavra por vez.

## O que já está incluído

- Interface PySide6 em português brasileiro.
- Abertura de MP4, MOV, MKV, AVI, WEBM e M4V.
- Reprodução com busca, volume e pré-visualização da legenda.
- Tabela com edição de cada palavra, início e fim.
- Cortes não destrutivos com seleção no timeline, normalização de trechos sobrepostos e desfazer.
- Transcrição com `faster-whisper`, `large-v3-turbo`, CPU e INT8.
- Exportação H.264 MP4 com CRF 18, `yuv420p`, AAC 256 kbps e fast-start.
- Testes unitários para timecodes, cortes, remapeamento e ASS.
- Workflow GitHub Actions que monta o aplicativo portátil Windows x64.

## Desenvolvimento local

Requer Python 3.11+ e FFmpeg disponível no `PATH`.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

O modelo `large-v3-turbo` é baixado pelo faster-whisper na primeira transcrição. O vídeo original nunca é alterado.

## Gerar o aplicativo Windows

O workflow `.github/workflows/build-windows.yml` instala FFmpeg e a fonte Poppins ExtraBold, cria `LegendaStudio.exe` com PyInstaller e publica:

- uma pasta portátil `dist/LegendaStudio/`;
- `LegendaStudio-windows-x64.zip`.

Para uma montagem manual, execute no Windows:

```powershell
python scripts\fetch_runtime.py
pyinstaller --noconfirm --clean --onedir --windowed --name LegendaStudio `
  --add-data "assets;assets" app.py
```

## Testes

```bash
python -m unittest discover -s tests -v
```

O teste ponta a ponta com vídeo real e o empacotamento Windows devem ser executados em um runner Windows, pois PySide6 e o binário final são específicos da plataforma.