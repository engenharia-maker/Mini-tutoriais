# HNL MiniTutoriais — GitHub Actions, sem Render e sem Drive

**Esta versão é a adaptação para o mesmo modo de execução dos vídeos das novelas: o GitHub Actions processa e você baixa em `Artifacts`.** O editor começa pela tela de login `index.html`, que abre no navegador, sem instalar Python ou Codespaces. O projeto e os vídeos ficam em um **repositório privado** e nas suas Releases privadas.

Não é um site permanente hospedado em endereço privado. No GitHub Pages comum, a página seria pública, por isso **não ative GitHub Pages**. A página de revisão `index.html` é aberta como arquivo no navegador do celular ou computador; nenhum vídeo é enviado a essa página. Sua edição é feita localmente.

## Antes de começar — uma única vez

1. Crie um repositório **Private** (privado), por exemplo, `HNL-MiniTutoriais`.
2. Extraia o ZIP e envie **todos os arquivos e pastas que estão dentro dele** ao repositório (inclusive `.github/workflows` e `scripts`). Não envie apenas o ZIP.
3. Vá a **Settings → Actions → General**, confira se Actions está habilitado. Não é necessário adicionar chaves, senhas ou tokens. `GITHUB_TOKEN` é disponibilizado automaticamente em cada execução.
4. Não ative GitHub Pages: páginas comuns são públicas, mesmo que o repositório privado seja permitido pelo plano.

## Como fazer cada vídeo (duas execuções no GitHub)

### Passo 1 — Enviar o vídeo

1. No GitHub, abra o repositório e entre em **Releases → Draft a new release** (Nova release).
2. Clique em **Choose a tag** e crie uma tag única, por exemplo `tutorial-001`.
3. Informe um título identificável; em **Attach binaries** / **Attach files**, selecione **um único vídeo** MP4, MOV, M4V ou WEBM com duração até **3 minutos**.
4. Clique em **Publish release**. Uma Release aceita um arquivo de até **2 GiB**; para tutoriais, recomenda-se manter vídeos menores para processamento mais ágil.
5. Se o repositório for privado, vídeos e Releases não ficam públicos para quem não tem acesso.

### Passo 2 — Gerar legendas automaticamente

1. Vá a **Actions → 01 - Gerar legendas (Whisper) → Run workflow**.
2. Digite a **mesma tag** (ex.: `tutorial-001`). Modelo recomendado: **large-v3-turbo**; `medium` é alternativa se o consumo de recursos for alto.
3. Depois que a execução terminar com sucesso, abra essa execução e vá a **Artifacts → HNL-legendas-para-revisar**.
4. Baixe e extraia o ZIP. O arquivo `legendas_automaticas.srt` contém as falas e `index.html` é sua página de revisão.

### Passo 3 — Assistir e revisar na página HTML

1. Abra `index.html` com Chrome/Edge no computador ou navegador do celular. **Entre com o usuário e a senha definidos para o projeto.** A senha não fica gravada em texto aberto dentro do HTML; o editor só pode ser decifrado com as credenciais corretas.
2. Escolha o **mesmo vídeo original** que foi enviado à Release. Ele é aberto **somente no seu navegador**.
3. Importe `legendas_automaticas.srt`. Dê Play. A legenda aparece **em cima do vídeo**, sincronizada com cada frase.
4. Toque numa frase para ir ao trecho; corrija o texto, o início ou o fim. Confira na reprodução. O botão **Baixar legenda revisada** gera `legendas_revisadas.srt`.
5. Guarde o SRT. As alterações podem ser salvas no navegador como rascunho, mas baixar o SRT é a forma mais segura de não perder as correções.

### Passo 4 — Enviar a legenda revisada

1. Volte à **mesma Release** no GitHub e clique em **Edit release**.
2. Anexe `legendas_revisadas.srt` **com esse nome exato** e salve a Release.

### Passo 5 — Gerar o vídeo final

1. Vá em **Actions → 02 - Gerar vídeo institucional MP4 → Run workflow**.
2. Preencha a mesma **tag**, o **equipamento** e o **tema** da capa.
3. Ao concluir, abra a execução → **Artifacts → HNL-video-final**. Baixe o ZIP com `minitutorial_institucional.mp4`.
4. O MP4 terá **capa 2 segundos → vídeo Full HD com logo e legendas revisadas → encerramento 2 segundos**.

## Estrutura — envie exatamente assim

```text
HNL-MiniTutoriais/
├── .github/
│   └── workflows/
│       ├── 01-transcrever.yml
│       └── 02-gerar-video.yml
├── assets/
│   └── logo_hnl.png
├── scripts/
│   ├── baixar_release.py
│   └── processar.py
├── index.html
├── requirements.txt
├── .gitignore
└── README.md
```

## Sobre custo, privacidade e limitações

- **Sem Render, Apps Script, Codespaces ou Google Drive.** Os vídeos são anexados diretamente à Release do GitHub privado. O Whisper é executado no GitHub Actions.
- **Sem assinatura de hospedagem** para o projeto. GitHub Actions em repositórios privados inclui uma franquia mensal de minutos e armazenamento; ao ultrapassar a franquia, a execução pode ser bloqueada ou cobrada conforme a configuração de faturamento. Confira **Settings → Billing**.
- Esta solução **não cria um link privado único** onde se faz upload, edita e baixa sem sair da página. Para isso seria necessário um serviço de autenticação, armazenamento e processamento além do GitHub Pages. A revisão aqui é realmente visual, mas **local no navegador**.
- Não é necessário subir os MP4/SRT para `Code`; os arquivos originais vão em **Releases**, as versões processadas vêm por **Artifacts**.
- Artifacts são temporários (7 dias nesta configuração). Baixe os resultados; você poderá executar novamente enquanto mantiver os arquivos da Release.
- Com conteúdo institucional, evite vídeos que revelem pacientes, telas com nomes, prontuários ou outros dados sensíveis sem autorização e validação de segurança.
- Se o vídeo estiver em um codec que o navegador não reproduz (ex.: alguns MOV/HEVC), converta-o para MP4 H.264 antes de revisar; o GitHub Actions pode transcrever muitos formatos que o navegador não reproduz.
- O fluxo completo depende de suas permissões de escrita no repositório privado. Nem a transcrição Whisper nem a renderização foram executadas ainda na sua conta do GitHub.

## Acesso do editor e limite importante de segurança

A abertura do `index.html` mostra uma tela de usuário e senha. A página do editor foi **cifrada com AES-GCM e chave derivada da senha**: seu conteúdo não fica visível como HTML aberto. Isso permite um bloqueio local real do conteúdo do editor, sem colocar a senha literal no JavaScript. **Não é login de servidor** nem autenticação do GitHub: o arquivo HTML ainda pode ser copiado e atacado offline por quem o obtiver. A senha escolhida deve ser forte e não deve ser reutilizada em outras contas.

- Mantenha o **repositório privado**. Não publique `index.html` via GitHub Pages nem disponibilize o pacote publicamente.
- Esse bloqueio protege **a abertura do editor**, não substitui as permissões do GitHub para Releases/Actions, nem protege automaticamente arquivos SRT e MP4 que você distribuir.
- Para alterar a senha futuramente será necessário **gerar novamente** o `index.html` cifrado; mudar só o texto do login não funciona.
- O arquivo `index.html` precisa ser mantido com esse nome para a execução de transcrição distribuí-lo junto do SRT.
