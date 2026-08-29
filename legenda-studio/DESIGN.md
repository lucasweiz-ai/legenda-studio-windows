# Glimo Editor Design System

## Overview

Interface de produto para Windows 11. A composição é densa o suficiente para edição de vídeo, mas mantém ações primárias reconhecíveis e uma linha do tempo visualmente dominante.

## Color

- Brand yellow: `#F7C600` — ações primárias, seleção e playhead.
- Brand yellow hover: `#E4B700`.
- Ink: `#111111`.
- Light background: `#F3F4F6`.
- Light surface: `#FFFFFF`.
- Dark background: `#151515`.
- Dark surface: `#202020`.
- Destructive/cut: `#DC3B3B`.
- Success: `#27864A`.

O amarelo nunca é usado como cor de texto corrido. Seleções e cortes também usam forma, rótulo ou padrão, não somente cor.

## Typography

Usar `Segoe UI` para toda a interface. Títulos e rótulos importantes usam peso 600–700; controles e tabelas usam 13–14 px. Timecodes usam fonte monoespaçada do sistema.

## Shape and Spacing

- Sem cantos arredondados, conforme a convenção visual do projeto.
- Bordas de 1 px e foco amarelo de 2 px.
- Escala de espaçamento: 4, 8, 12, 16 e 24 px.
- Botões têm altura mínima de 36 px; ações primárias usam fundo amarelo e texto preto.

## Components

### Application header

Ícone amarelo e preto, nome “Glimo Editor”, ações de arquivo, ações de processamento e seletor de tema. A ação principal atual recebe maior contraste.

### Timeline

Altura mínima de 150 px, régua temporal, faixa de vídeo, faixa de áudio simplificada, playhead de alto contraste, seleção com alças visíveis e trechos removidos com padrão vermelho. Uma legenda permanente explica arrastar, selecionar e excluir.

### Progress area

Barra de progresso real quando a tarefa fornece percentual. Quando não fornece, usar estado indeterminado e, após três segundos, informar que a operação pode levar vários minutos.

### Recovery list

Ao iniciar, apresentar projetos e vídeos recentes com caminho, última edição e ação “Continuar”. Arquivos ausentes permanecem identificáveis, mas não podem ser abertos.

## Themes

Três modos: Automático (Windows), Claro e Escuro. Automático consulta o tema de aplicativos do Windows e reage a mudanças enquanto o programa está aberto.

## Motion

Somente feedback de estado. Evitar animações decorativas; respeitar a configuração de movimento reduzido do sistema.

