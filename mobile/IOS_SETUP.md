# JR Family — iPhone com Apple ID pessoal

O repositório Flutter contém Android e o fluxo de **geração do projeto iOS** em macOS.
Nenhum IPA assinado ou TestFlight está disponível nesta etapa.

## Validação automática no GitHub

Abra **Actions → Validar JR Family iOS**. A automação:
1. Instala Flutter 3.47.7 em um runner macOS.
2. Gera ios/ com `flutter create --platforms=ios --org com.jrfamily --project-name jr_family .`.
3. Executa `python3 tools/prepare_ios.py` para adicionar permissões iOS e configurar o bundle ID `com.jrfamily.app`.
4. Executa análise, testes Flutter e build de **simulador** sem assinatura.

**A compilação de simulador não instala no iPhone real.** O fluxo não gera IPA instalável nem prova que a execução em segundo plano está correta.

## Instalar em um iPhone real sem pagar Apple Developer Program

Você precisa de um **Mac com Xcode**, iPhone conectado ao Mac (cabo ou pareamento suportado) e um Apple ID comum. O GitHub Actions não instala diretamente no seu iPhone.

No Mac, clone o projeto, instale Flutter e as dependências iOS e execute:

```bash
cd JR-Family/mobile
flutter create --platforms=ios --org com.jrfamily --project-name jr_family .
python3 tools/prepare_ios.py
flutter pub get
open ios/Runner.xcworkspace
```

No Xcode, selecione **Runner → Signing & Capabilities**, ative **Automatically manage signing**, escolha sua equipe **Personal Team** e configure um identificador exclusivo se `com.jrfamily.app` não estiver disponível para sua conta. Se necessário, sincronize o Bundle Identifier em todos os targets. Selecione seu iPhone como destino e execute o aplicativo pelo Xcode. A assinatura gratuita tem limitações, incluindo necessidade de renovar o app periodicamente. Confira as instruções atuais do Xcode.

No campo de servidor do app use:
`https://jr-family-api-production.up.railway.app`

## Segurança e funcionalidades ainda não validadas

- O compartilhamento exige ação explícita, permissões oficiais e indicador visível de localização.
- Testar no aparelho os estados `Ao Usar`, `Sempre`, aplicativo em segundo plano, reinício e interrupção do compartilhamento; não afirmar suporte em segundo plano sem testes físicos.
- Notificações push iOS dependem de configurar Firebase/APNs e credenciais adequadas. Não publicar os arquivos de segredos no GitHub.
- TestFlight e distribuição pública precisam da participação no Apple Developer Program. Um Apple ID pessoal não basta para TestFlight.
- O fluxo atual configura o código iOS durante o build; para distribuição regular, futuramente será necessário versionar a estrutura iOS gerada e revisar suas configurações.

