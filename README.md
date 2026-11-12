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


## English welcome, onboarding and Loritta (Nov 2026)

### Critical: choose APPLY, not preview

The Nov 12 workflow run was in **preview** mode even though the
confirmation said APLICAR. The log printed "PREVIEW ONLY: no Discord changes"
and "Community enabled: False". So the choices and auto-role were not active.

To actually change Discord, open [Join Roles and Onboarding](https://github.com/hshsagaga1-commits/-wired-paradise-setup/actions/workflows/join-roles.yml),
choose **modo = apply**, enter **confirmar = APLICAR**, and press
Run workflow. Both fields must match. Afterward, run **modo = audit**;
audit is read-only and will fail if Community, roles, questions or
welcome notifications are not configured. The setup workflow is one-shot:
it has no 24/7 background runtime.

### What apply changes

- Renames **Membro** to **Member**, preserving its existing assignments.
- Creates **Male, Female, PC, Mobile, Console, Notifications** roles.
- Creates a **WELCOME** category with **#welcome** and **#rules**,
  plus useful public channels **#introductions, #gaming-chat, #off-topic**.
- Enables native **Discord system join messages** in #welcome. These are
  automatic without a bot, but are not customizable, guaranteed pings.
- Enables **Discord Community**, if required and if the setup bot has
  Administrator permission. Uses #rules and the existing private
  #logs-de-seguranca channel as Community setup requirements.
  This does NOT enable public Server Discovery.
- Configures 7 useful default channels with 5 writable channels, and
  activates the English Onboarding questions. The #spam trap and
  private channels are NEVER included in the default channels.
- Updates the AutoMod spam-trap exemptions to cover new channels.

These questions appear during Community Onboarding:
- **How do you identify?** Male / Female / Prefer not to say.
- **What do you play on?** PC / Mobile / Console (multiple allowed).
- **Would you like notifications?** Yes, notify me / No, thanks.

All questions are optional. Prefer not to say assigns no gender role;
No, thanks assigns no notifications role. Existing prompts unrelated to
these titles are preserved. Check via Server Settings > Onboarding >
Preview; use a desktop browser view on iPhone if mobile settings hide it.

### Automatic Member role requires Loritta

GitHub Actions only configures the server once. It cannot respond to
member joins after the workflow finishes. Loritta must be invited and
configured in the [Loritta dashboard](https://loritta.website/dashboard):

1. Add Loritta to Wired Paradise via its official dashboard.
2. Place Loritta's bot role **above Member** under Server Settings > Roles.
3. Grant **Manage Roles** but not Administrator.
4. Enable Loritta **AutoRole / Autorole**, set its role to **Member**,
   turn off any "only after sending a message" condition, use zero delay,
   and save.
5. Enable Loritta **Welcome / Mensagens de Boas-Vindas**, choose #welcome
   as the channel and configure a personalized English message.
   Choose Loritta's own **mention member variable** from its variable
   list/picker; variable syntax differs across Discord bots.
6. #welcome is read-only to ordinary users. Add an explicit channel
   permission overwrite allowing the Loritta bot role View Channel,
   Send Messages and Read Message History.
7. Test with a normal account. If it works, optionally disable native
   Discord system join notifications to avoid duplicate welcomes.

**Suggested English custom welcome message**:

> Welcome to Wired Paradise! Please read #rules, pick your roles using
> Channels & Roles, and introduce yourself in #introductions.

Insert the bot's member mention at the beginning of that message via its
variable picker, then use its built-in preview/test if available.

Native Discord join messages will appear in #welcome even if Loritta
is not installed, but explicit personalized mentions and new-member
auto-role require Loritta to be online and configured.

This action does not start or host the optional live_bot.py security
guardian, and never removes security rules or disables the #spam trap.


## Limpeza manual do #chat-geral (sem recriar o canal)

O workflow [Limpar chat-geral](https://github.com/hshsagaga1-commits/-wired-paradise-setup/actions/workflows/limpar-chat-geral.yml)
apaga somente mensagens do canal de texto COMUNIDADE/#chat-geral do servidor
autorizado. Ele nao remove canais, categorias, cargos ou membros. O canal e
suas permissoes continuam intactos. O #spam nao e alterado.

1. Abra GitHub Actions > Limpar chat-geral (Wired Paradise) > Run workflow.
2. Deixe **modo = preview** para contar ate o limite escolhido sem apagar nada.
3. Para realmente apagar, escolha **modo = apply**, defina o limite de 100,
   500 ou 2000 mensagens, e escreva **APAGAR CHAT-GERAL** no campo confirmar.
   Escrever a confirmacao sem selecionar apply nao apaga nada.
4. Leia o log para conferir quantas mensagens foram removidas. Se houver
   mais mensagens do que o limite, repita o workflow.
5. Rode preview novamente para conferir que zerou.

**ATENCAO:** a exclusao e PERMANENTE, inclui mensagens e anexos fixados
(pins), e NAO pode ser desfeita. Discord permite bulk-delete de 2 a 100
mensagens por requisicao, somente com menos de 14 dias. Mensagens mais antigas
sao apagadas individualmente e podem levar tempo. A rotina processa no maximo
2000 mensagens por execucao.

O bot deve ter permissao para Ver Canal, Ler Historico e Gerenciar Mensagens.
As credenciais ficam em Actions Secrets. O workflow nao roda automaticamente
e nao apaga nada a menos que o proprietario escolha apply e confirme.


## Somente o dono pode gerenciar bots, AutoMod e automações

**Novo workflow manual**:
[Somente dono — segurança das automações](https://github.com/hshsagaga1-commits/-wired-paradise-setup/actions/workflows/somente-dono-seguranca.yml)

**O que ele faz:** fiscaliza todas as permissões de cargos *editáveis*
(incluindo @everyone, Member, Moderação e cargos antigos) e as permissões
específicas de canais, para impedir que não proprietários recebam:

- Administrator
- Manage Server (Gerenciar servidor, necessário para alterar AutoMod)
- Manage Roles
- Manage Channels
- Manage Webhooks

A permissão do proprietário real do servidor é automática no Discord;
ele não perde acesso ao fazer a limpeza. Os cargos gerenciados pelo Discord
para bots e integrações **não são alterados** (incluindo Loritta). Os
IDs identificados de bots ficam protegidos das alterações de permissões
de canal. Direitos de moderadores para Manage Messages, timeout e mensagens
não são eliminados automaticamente.

### Executar no iPhone

1. No workflow, rode **modo = preview**; o log mostra os nomes dos
   cargos que ainda têm permissões de configuração perigosas. Nada é alterado.
2. Se aceitar que também cargos administrativos antigos sejam restringidos,
   rode **modo = apply** e **confirmar = SOMENTE DONO**.
3. Rode **modo = audit** para ler e validar tudo novamente sem mudanças.

**Atenção:** "apply" modifica permissões de todos os cargos humanos
que ainda possuam tais capacidades, incluindo possíveis cargos de
administração de outros usuários. Isso é intencional para garantir que só
o proprietário real administre bots e AutoMod. Se bots de terceiros também
receberam papéis comuns editáveis para acessar funções, revendo antes
a prévia evita quebrar uma integração. O projeto não modifica as permissões
das roles gerenciadas por bots.

### Passo complementar importante para Loritta

O script **não acessa o painel privado da Loritta** e não consegue alterar
automaticamente suas regras internas. O Discord determina que usuários com
Gerenciar servidor ou Administrador podem gerenciar apps e AutoMod.
Para comandos individuais da Loritta, navegue em:

Discord -> Configurações do servidor -> Integrações -> Loritta -> Gerenciar

Revise **cada comando de moderação/administração** e permita somente
o proprietário do servidor; deixe comandos de diversão abertos conforme
sua preferência. Configure as permissões por comando em Integrações, em
vez de bloquear todos os comandos da Loritta (isso impediria os membros
de usar comandos normais). Não se esqueça de revisar o painel da Loritta
para permissões próprias de administração delegada, se houver.

A API de permissões de comandos requer OAuth de usuário com escopo
applications.commands.permissions.update; **um token de bot do GitHub não
é suficiente para editar essas permissões**, portanto este workflow não
afirma que elas foram modificadas.

Se conceder novamente Gerenciar servidor ou Administrador a qualquer
outro cargo no futuro, repita o audit para ver se a restrição foi perdida.

Referências:
- Discord AutoMod FAQ: https://support.discord.com/hc/pt-br/articles/4421269296535-FAQ-do-AutoMod
- Discord Application Commands: https://docs.discord.com/developers/docs/interactions/slash-commands
