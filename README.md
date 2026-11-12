# Wired Paradise — montador Discord

Cria a estrutura básica de um servidor Discord pelo **GitHub Actions**, uma única vez, sem deixar um bot hospedado 24h. Roda no iPhone.

## O que faz

- **COMUNIDADE:** `anuncios` (só proprietário publica), `chat-geral` (texto, sem anexos nem prévias de link), `midias` (texto, imagem, vídeo e arquivos), `spam` (**canal-armadilha**: qualquer mensagem pode resultar em ban permanente quando o guardião estiver online), `cargos` (guia de cargos somente leitura).
- **MEUS PROJETOS:** `meus-scripts` e `metodos-de-qualidade` (só proprietário publica).
- **VOZ:** `Call Geral`.
- **SEGURANÇA:** `logs-de-seguranca` (alertas do AutoMod, visível para dono e Moderação).
- **Cargos:** `👑 Dono` (vermelho), `Moderação` (azul), `Member` (branco), `Cargo Boost` (rosa) e `Sigma 67` (roxo). Dono e Sigma 67 são atribuídos apenas ao proprietário identificado pelo Discord. A coroa aparece no nome; ícone real de cargo depende do recurso `ROLE_ICONS` no servidor.
- Se existir o cargo **Server Booster nativo**, ele é aproveitado porque o Discord o atribui automaticamente; se não existir, o cargo personalizado Cargo Boost **não é atribuído automaticamente**.
- **Armadilha no `spam`:** o AutoMod bloqueia **qualquer mensagem com texto**, aplica timeout de 60 segundos e registra alerta. O `live_bot.py`, quando hospedado 24h, também detecta tentativas de texto barradas pelo AutoMod e **qualquer mensagem efetivamente publicada**, inclusive anexos sem texto, para banir permanentemente o autor. O Discord não oferece ban automático direto pelo AutoMod. **Sem bot online, anexos sem texto podem passar e ninguém é banido.**
- Proteções adicionais contra spam, excesso de menções, convites de membros comuns e verificação elevada.

**Limites importantes:** o Discord permite que administradores ignorem bloqueios de canal. No `chat-geral`, bloquear anexos e embeds não impede a pessoa de escrever um URL de imagem como texto. Criar o cargo `Member` não o atribui automaticamente aos próximos participantes: configure o módulo AutoRole da Loritta para isso.

**O script não apaga canais, cargos, mensagens ou membros existentes.** Cada aplicação é idempotente para os canais e cargos de mesmo nome nas categorias previstas. O texto informativo do canal `cargos` só é publicado quando esse canal é criado pela primeira vez; mensagens antigas não são apagadas ou editadas.

## Configurar pelo iPhone
1. No Discord: **Configurações → Avançado → Modo desenvolvedor**, depois copie o **ID do servidor Wired Paradise**. É o ID numérico, não um convite.
2. No [Portal de Desenvolvedores do Discord](https://discord.com/developers/applications), abra seu aplicativo → **Bot**. Obtenha o token do bot. **Nunca envie token por chat, print, commit, issues ou nos campos de execução.**
3. Neste GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Cadastre:
   - `DISCORD_BOT_TOKEN`: token do bot;
   - `DISCORD_GUILD_ID`: ID numérico do seu servidor.
4. Vá a **Actions → Configurar Wired Paradise → Run workflow** e execute `preview` para ver o plano sem alterar nada.
5. Se estiver certo, escolha `apply` e digite **APLICAR** no campo `confirmar`. A alteração real só ocorre agora.
6. Execute `audit` para verificar categorias, canais, cargos, permissões e AutoMod. Este modo usa apenas consultas GET, sem modificar o Discord.
7. Teste com uma conta normal (não Admin), pois quem tem Administrador pode ignorar restrições: no `chat-geral` enviar texto e tentar um arquivo; no `midias` enviar texto e anexo; nos canais de anúncio/projetos tentar escrever; no `spam` enviar uma mensagem de teste com o guardião **desligado** e verificar se o texto é bloqueado; não tente com o guardião de ban ativo. Verifique os avisos em `logs-de-seguranca`.
8. Retire a permissão de **Administrador** ou remova o bot quando terminar, conforme o uso futuro.

> Se a aba **Actions** não mostrar o fluxo, talvez seja preciso habilitar ações nas configurações do repositório. O fluxo só é executado quando você iniciar manualmente.

## Armadilha: ban por qualquer mensagem (opcional, exige bot online)

O `#spam` **não é um chat para conversa**: é uma isca para contas comprometidas que publicam golpes em todos os canais. O tópico avisa os membros honestos para não escreverem lá. **Qualquer publicação aciona ban permanente**, se o guardião estiver online. Isso inclui texto, GIF, imagem, vídeo, arquivo e sticker. O bot **não verifica se a publicação é golpe**; também pode banir um membro legítimo que escrever por engano. A conta dona do servidor é protegida da automação.

O arquivo `live_bot.py` **foi implementado, mas não está hospedado e não está ativo**. O GitHub Actions não executa o guardião. Ele usa dois caminhos:
- AutoMod `WP | Armadilha spam` bloqueia texto e o bot online recebe o evento para banir o autor;
- Evento de mensagem cobre publicações que o AutoMod não bloqueou, inclusive **anexos sem texto**.

Para ativar futuramente, hospede o processo Python continuamente, instale `discord.py>=2.4,<3`, configure `DISCORD_BOT_TOKEN` como **Secret da hospedagem** e execute `python live_bot.py`. O bot precisa de **Gerenciar Servidor**, **Banir Membros** e, para retirar mensagens de webhooks, **Gerenciar Mensagens**. A hierarquia do cargo do bot também importa. Ele não precisa do intent privilegiado Message Content, porque usa somente canal e autor.

**Modo de teste seguro:** configure `WP_DRY_RUN=1` na hospedagem para registrar eventos sem banir. Com `WP_DRY_RUN` desativado, o bot tentará banir permanentemente o autor e solicitar exclusão de até 24 horas de mensagens anteriores dessa conta no servidor. Não faça testes com sua conta alternativa enquanto o ban estiver ativo.

**Limites:** o ban não acontece se o bot cair, estiver desconectado ou não tiver permissão. Uma conta hackeada pode publicar golpes em outros canais **antes** de atingir o spam; por isso, use AutoMod anti-spam, verificação de entrada e limites de anexos/convites em paralelo. Banir a conta comprometida não identifica o invasor.

## Anti-raid — limites

O AutoMod bloqueia texto e registra alertas. O teste `audit` verifica **configurações**, não simula raids, não confirma acesso real de todos os membros nem verifica se o guardião de ban está hospedado. O montador é uma execução pontual, sem serviço online 24h. Revise verificação, moderação e segurança diretamente no Discord.

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


## English member roles + Loritta commands (Nov 2026)

The server is **Wired Paradise**. The old `Membro` role will be renamed
**Member** without removing it from existing users. This keeps old assignments.
All **new prompts and role names** are in English; older channels keep their
current names and permissions. Nothing in the join-role workflow deletes
channels, messages or other roles.

**Member is NOT assigned to future joins by GitHub Actions.** GitHub Actions
is a one-time setup, not a persistent Discord bot. Use **Loritta AutoRole**:

1. Open [Loritta's official dashboard](https://loritta.website/dashboard)
   and authorize adding Loritta to Wired Paradise. Discord will ask you
   to approve access (this cannot be done by this GitHub repository).
2. In Discord > **Server Settings > Roles**, place Loritta's highest role
   **above Member**, but **below Owner/Moderation**. Grant **Manage Roles**,
   but avoid Administrator unless absolutely necessary.
3. In Loritta's dashboard, enable **Auto Role / Autorole**, choose **Member**,
   set the delay to **0** and disable "only when user sends a message" if
   available. Save.
4. Loritta's slash commands are available after you authorize the app with
   its command permissions. Configure which commands are available under
   Discord > **Server Settings > Integrations > Loritta**.
5. Test by joining with a normal account (not the server owner's account),
   and check the Member role is granted automatically.

The separate `join_roles.py` script handles English **Discord-native
Community Onboarding questions**. These prompts are not Loritta commands.

| Onboarding question | Options | Role behavior |
| --- | --- | --- |
| How do you identify? | Male / Female / Prefer not to say | Male or Female adds that role; privacy option adds **no gender role** |
| What do you play on? | PC / Mobile / Console | Multiple selections allowed, each adds its matching role |
| Would you like notifications? | Yes, notify me / No, thanks | Yes adds Notifications; No adds **no notification role** |

Questions are optional. People can skip questions instead of disclosing
personal details. The privacy/no-notification options use a normal public
text channel as an onboarding selection target, without adding a role.
Use `@Notifications` for optional announcements instead of `@everyone`.

### Run the new workflow on iPhone

1. Open **Actions > Join Roles and Onboarding (Wired Paradise)**.
2. Run **preview** to inspect the changes without modifying anything.
3. Run **apply**, enter `APLICAR` as confirmation. This only adds/renames
   the requested roles and configures the three English onboarding questions.
4. Run **audit** to verify the onboarding questions are active.
5. From Discord, open **Server Settings > Onboarding** and use **Preview**
   to test the actual newcomer experience.

If the server does not have **Community** enabled, the workflow creates
the roles but cannot activate Onboarding. Enable Community from Discord.
Discord also requires **at least seven default channels**, of which **five
must allow @everyone to send messages**, to enable Onboarding. The workflow
**will not** create unwanted channels or turn the `#spam` trap into a
writable welcome channel. It retains existing default channel settings and
stages the questions if requirements are not met. After configuring
suitable default channels in the Discord interface, rerun `apply`.

Existing security / anti-spam rules and `live_bot.py` are kept separate
from Loritta. The guard bot remains **not hosted**, and the `#spam` ban
trap is **not** made active by installing Loritta.

**Security:** never share Discord tokens or put them in GitHub files.
Continue using the existing `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID`
repository secrets, and consider making this repository private.

