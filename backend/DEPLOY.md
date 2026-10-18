# Publicação JR Family

Estado: código preparado; servidor ainda não publicado.

Use a pasta backend como raiz do serviço Docker. O contêiner executa as migrações e escuta na variável PORT (padrão 8000). Configure PostgreSQL persistente e as variáveis abaixo exclusivamente no provedor, nunca no GitHub:

- ENVIRONMENT=production
- DATABASE_URL: conexão privada do PostgreSQL; aceita postgres://, postgresql:// ou postgresql+psycopg://
- JWT_SECRET: segredo aleatório de pelo menos 32 caracteres
- CORS_ORIGINS: origem HTTPS exata do painel, sem barra final
- FIREBASE_ENABLED=false até configurar credenciais

Saúde: GET /health. Validar cadastro, login e isolamento entre famílias após publicar.

Firebase: habilitar Cloud Messaging, registrar Android com applicationId com.jrfamily.app, configurar google-services.json no build e credenciais de serviço no backend por secret file/GOOGLE_APPLICATION_CREDENTIALS. Nunca publicar chave privada no repositório. Depois habilitar FIREBASE_ENABLED=true e FIREBASE_PROJECT_ID.

O aplicativo deve apontar para a URL HTTPS real do serviço. Validar notificações e localização em aparelhos físicos com permissões concedidas.
