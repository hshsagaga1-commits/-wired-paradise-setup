# Wired Paradise — montador Discord

Cria a estrutura básica de um servidor Discord pelo **GitHub Actions**, uma única vez, sem deixar um bot hospedado 24h. Roda no iPhone.

## O que faz
- **COMUNIDADE:** `chat-geral`, `midias`, `spam`
- **MEUS PROJETOS:** `meus-scripts`, `metodos-de-qualidade` (publicação só pela equipe)
- **VOZ:** `Call Geral`
- **SEGURANÇA:** `logs-de-seguranca` privado
- Slowmode no chat/mídias; limita convites e menções a todos; aumenta nível de verificação e filtro de conteúdo; tenta criar AutoMod anti-spam e contra menções em massa.

Nada é apagado. Execute primeiro em **prévia**, depois **aplicar** para gravar as alterações. Executar novamente evita duplicatas nas categorias correspondentes.

## Configurar pelo iPhone
1. No Discord: **Configurações → Avançado → Modo desenvolvedor**, depois copie o **ID do servidor Wired Paradise**. É o ID numérico, não um convite.
2. No [Portal de Desenvolvedores do Discord](https://discord.com/developers/applications), abra seu aplicativo → **Bot**. Obtenha o token do bot. **Nunca envie token por chat, print, commit, issues ou nos campos de execução.**
3. Neste GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Cadastre:
   - `DISCORD_BOT_TOKEN`: token do bot;
   - `DISCORD_GUILD_ID`: ID numérico do seu servidor.
4. Vá a **Actions → Configurar Wired Paradise → Run workflow**. Escolha `preview` e execute. Veja o resultado nos logs.
5. Se estiver certo, rode outra vez: escolha `apply` e digite **APLICAR** no campo `confirmar`.
6. Confira no Discord o que realmente foi criado. Retire a permissão de **Administrador** ou remova o bot quando terminar.

> Se a aba **Actions** não mostrar o fluxo, talvez seja preciso habilitar ações nas configurações do repositório. O fluxo só é executado quando você iniciar manualmente.

## Anti-raid — limites
O AutoMod do Discord ajuda a bloquear spam e excesso de menções. Uma execução pontual **não é um monitor anti-raid 24h**, não faz verificação CAPTCHA de membros e não garante proteção total. Revise no Discord a verificação dos membros, a proteção nativa contra raids, alertas, permissões dos cargos e exigência de 2FA para moderação.

**Mantenha este repositório privado.** Nunca registre token em arquivos, logs, commits ou mensagens. Mesmo um Secret pode ser usado por um workflow malicioso se alguém conseguir editar e executar código com acesso a ele. O acesso de escrita ao repositório deve ficar restrito, e a conta GitHub deve usar autenticação de dois fatores.

O ID do servidor é um identificador, **não uma senha**. O código atual usa uma impressão digital SHA-256 para impedir execução num servidor diferente sem publicar o ID em texto puro; isso **não é criptografia nem substitui os Secrets**. O ID também pode permanecer visível em commits antigos, caso a pessoa tenha tido acesso ao histórico público.

O workflow foi endurecido: **somente execução manual**, **somente branch `main`**, **somente o proprietário**, `GITHUB_TOKEN` com leitura limitada, checkout sem credenciais persistentes e dependências fixadas por hash. Estas medidas reduzem riscos, mas não substituem a proteção da conta e do repositório.

### Depois de configurar o servidor
1. Tire a permissão **Administrador** do bot no Discord ou expulse o bot, se não vai mais usá-lo.
2. Se não pretende rodar o montador outra vez, em **GitHub → Settings → Secrets and variables → Actions**, apague `DISCORD_BOT_TOKEN`. Para revogar de verdade o token que já existiu, use **Reset Token** no portal do Discord; será preciso cadastrar o novo token como Secret caso queira usar o bot outra vez.
3. Em **GitHub → Settings → General → Danger Zone → Change repository visibility**, torne o repositório **Private**. Confira quem tem acesso de escrita.
4. Ative 2FA/passkey na conta do GitHub e evite publicar capturas de tela com credenciais.

**Secrets não podem ser consultados em texto puro** pelo GitHub depois de cadastrados. Não tente “decodificar” ou ofuscar o token: a segurança vem de limitar quem pode utilizá-lo e de revogá-lo quando não for mais necessário.

## Permissões
O bot precisa ter as permissões necessárias para administrar categorias, cargos, AutoMod e configurações; Administrador **somente temporariamente**. O código não faz vigilância contínua.

**Importante:** não cole o token no campo `confirmar`. Nele vai só a palavra `APLICAR`.
