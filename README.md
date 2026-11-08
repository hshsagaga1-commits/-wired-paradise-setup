# Wired Paradise — montador Discord

Cria a estrutura básica de um servidor Discord pelo **GitHub Actions**, uma única vez, sem deixar um bot hospedado 24h. Roda no iPhone.

## O que faz

- **COMUNIDADE:** `anuncios` (só proprietário publica), `chat-geral` (texto, sem anexos nem prévias de link), `midias` (texto, imagem, vídeo e arquivos), `spam` (texto), `cargos` (guia de cargos somente leitura).
- **MEUS PROJETOS:** `meus-scripts` e `metodos-de-qualidade` (só proprietário publica).
- **VOZ:** `Call Geral`.
- **SEGURANÇA:** `logs-de-seguranca` (alertas do AutoMod, visível para dono e Moderação).
- **Cargos:** `👑 Dono` (vermelho), `Moderação` (azul), `Membro` (branco), `Cargo Boost` (rosa) e `Sigma 67` (roxo). Dono e Sigma 67 são atribuídos apenas ao proprietário identificado pelo Discord. A coroa aparece no nome; ícone real de cargo depende do recurso `ROLE_ICONS` no servidor.
- Se existir o cargo **Server Booster nativo**, ele é aproveitado porque o Discord o atribui automaticamente; se não existir, o cargo personalizado Cargo Boost **não é atribuído automaticamente**.
- **Filtro do `.` no `spam`:** o AutoMod bloqueia a mensagem que contém **exatamente um ponto** e aplica 60 segundos de timeout, além de gerar alerta. Ele não dá ban. Para banir imediatamente alguém que enviou apenas `.`, é necessário hospedar um bot com eventos em tempo real e permissão de banir. Não há mecanismo de banimento permanente em uma configuração pontual do GitHub Actions.
- Proteções adicionais contra spam, excesso de menções, convites de membros comuns e verificação elevada.

**Limites importantes:** o Discord permite que administradores ignorem bloqueios de canal. No `chat-geral`, bloquear anexos e embeds não impede a pessoa de escrever um URL de imagem como texto. Criar o cargo `Membro` não o atribui automaticamente aos próximos participantes: é preciso atribuir manualmente, por Onboarding apropriado ou com um bot online.

**O script não apaga canais, cargos, mensagens ou membros existentes.** Cada aplicação é idempotente para os canais e cargos de mesmo nome nas categorias previstas. O texto informativo do canal `cargos` só é publicado quando esse canal é criado pela primeira vez.

## Configurar pelo iPhone
1. No Discord: **Configurações → Avançado → Modo desenvolvedor**, depois copie o **ID do servidor Wired Paradise**. É o ID numérico, não um convite.
2. No [Portal de Desenvolvedores do Discord](https://discord.com/developers/applications), abra seu aplicativo → **Bot**. Obtenha o token do bot. **Nunca envie token por chat, print, commit, issues ou nos campos de execução.**
3. Neste GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Cadastre:
   - `DISCORD_BOT_TOKEN`: token do bot;
   - `DISCORD_GUILD_ID`: ID numérico do seu servidor.
4. Vá a **Actions → Configurar Wired Paradise → Run workflow** e execute `preview` para ver o plano sem alterar nada.
5. Se estiver certo, escolha `apply` e digite **APLICAR** no campo `confirmar`. A alteração real só ocorre agora.
6. Execute `audit` para verificar categorias, canais, cargos, permissões e AutoMod. Este modo usa apenas consultas GET, sem modificar o Discord.
7. Teste com uma conta normal (não Admin), pois quem tem Administrador pode ignorar restrições: no `chat-geral` enviar texto e tentar um arquivo; no `midias` enviar texto e anexo; nos canais de anúncio/projetos tentar escrever; no `spam` enviar uma mensagem contendo somente `.` e confirmar se foi bloqueada. Verifique os avisos em `logs-de-seguranca`.
8. Retire a permissão de **Administrador** ou remova o bot quando terminar, conforme o uso futuro.

> Se a aba **Actions** não mostrar o fluxo, talvez seja preciso habilitar ações nas configurações do repositório. O fluxo só é executado quando você iniciar manualmente.

## Ban instantâneo pelo ponto (opcional, exige bot online)

O arquivo `live_bot.py` é um **guardião separado**, implementado mas **NÃO está hospedado nem ativo**. O GitHub Actions não o executa. Ele escuta o evento do AutoMod `WP | Ponto no spam` e só bane se a regra ainda usa a regex do ponto isolado, se o evento veio do `#spam` da categoria COMUNIDADE e se o autor não é o proprietário.

Para utilizá-lo no futuro, escolha uma hospedagem confiável que mantenha um processo Python online; instale `discord.py>=2.4,<3`, configure `DISCORD_BOT_TOKEN` como variável **secreta** do host e execute `python live_bot.py`. O bot precisa de **Gerenciar Servidor** (para receber a execução do AutoMod) e **Banir Membros** com hierarquia de cargo suficiente. A alternativa nativa continua funcionando mesmo com o guardião offline: bloqueio e timeout, **sem ban**.

**Não rode o guardião antes de testar o filtro e confirmar que quer banimentos automáticos definitivos.** Um usuário de teste real não deve enviar `.` com o guardião ativo se você não quiser que a conta seja banida. O arquivo foi revisado estaticamente, mas ainda não foi testado em um Discord real.

## Anti-raid — limites

O AutoMod bloqueia mensagens e registra alertas. O teste `audit` verifica **configurações**, não simula raids, não confirma acesso real de todos os membros e não configura banimento por ponto. O montador é uma execução pontual, sem serviço online 24h. Revise verificação, moderação e segurança diretamente no Discord.

O canal `logs-de-seguranca` é um registro privado de alertas: **não é um chat público**. O bot pode adicionar avisos quando regras do AutoMod são acionadas.

## Segurança do GitHub e do token

- O repositório **deve ficar privado**. Nas configurações: **Settings → General → Danger Zone → Change repository visibility → Private**. O histórico público anterior não é apagado de cópias já feitas.
- **GitHub Actions Secrets** são adequados para guardar o token do Discord. Não há necessidade de ofuscar ou decodificar o token; ele não deve aparecer no código, em Issues, prints ou logs.
- O workflow usa apenas **execução manual** autorizada, somente a branch `main` e a conta proprietária, com permissão do GitHub limitada a leitura e ações fixadas por hash.
- O ID do servidor é **identificador, não senha**. O código atual contém apenas uma impressão digital SHA-256, mas o ID aparecia em commits antigos. Não confunda fingerprint com criptografia.
- Ative **2FA/passkey** na conta do GitHub e revise quem tem permissão para editar a branch principal. Qualquer pessoa que possa alterar o workflow/código executado com Secrets representa um risco.
- Se não vai usar o montador novamente, **retire a permissão Administrador do bot** ou remova o bot do servidor. Para revogar o token atual, use **Reset Token** no Portal de Desenvolvedores do Discord e remova o Secret antigo do GitHub. Se desejar reutilizar o montador depois, cadastre o novo token no Secret.
- Atenção: quem tem o token pode controlar o bot enquanto ele for válido, mesmo que você apague o Secret. **Reset Token** é o que invalida a credencial anterior.

## Permissões
O bot precisa ter as permissões necessárias para administrar categorias, cargos, AutoMod e configurações; Administrador **somente temporariamente**. O código não faz vigilância contínua.

**Importante:** não cole o token no campo `confirmar`. Nele vai só a palavra `APLICAR`.
