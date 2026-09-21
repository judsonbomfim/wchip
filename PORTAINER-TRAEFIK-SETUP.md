# Instalação no Portainer com Traefik

Este guia mostra como instalar a aplicação wchip no Portainer usando Traefik como reverse proxy.

## Pré-requisitos

1. **Traefik instalado e configurado** no seu ambiente Docker/Portainer
2. **Rede `public` criada**:
   ```bash
   docker network create public
   ```
3. **Portainer instalado e acessível**

## Configuração do Traefik

Certifique-se que seu Traefik está configurado com:
- Entrypoints `web` (porta 80) e `websecure` (porta 443)
- Certificate resolver `leresolver` configurado (Let's Encrypt)
- Rede `public` conectada

Exemplo de configuração no docker-compose do Traefik:
```yaml
services:
  traefik:
    image: "traefik:latest"
    command:
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --providers.docker.network=public
      - --certificatesresolvers.leresolver.acme.httpchallenge=true
      - --certificatesresolvers.leresolver.acme.email=seu-email@example.com
      - --certificatesresolvers.leresolver.acme.storage=/acme.json
      - --certificatesresolvers.leresolver.acme.httpchallenge.entrypoint=web
    networks:
      - public
```

## Instalação no Portainer

### Passo 1: Preparar arquivo .env

1. Copie o arquivo `.env.portainer.example` para `.env`
2. Edite o arquivo `.env` e configure:
   - `DOMAIN`: seu domínio (ex: wchip.seudominio.com)
   - `SECRET_KEY`: gere uma chave secreta Django única
   - `ALLOWED_HOSTS`: adicione seu domínio
   - Configure banco de dados, email e outras variáveis necessárias

### Passo 2: Criar Stack no Portainer

1. Acesse o Portainer
2. Vá em **Stacks** → **Add stack**
3. Nomeie a stack (ex: `wchip`)
4. Escolha uma das opções:

#### Opção A: Upload do arquivo docker-compose
- Selecione **Upload**
- Faça upload do arquivo `docker-compose.portainer.yml`

#### Opção B: Repositório Git
- Selecione **Repository**
- Configure o repositório Git
- Caminho do compose: `docker-compose.portainer.yml`

#### Opção C: Web editor
- Selecione **Web editor**
- Cole o conteúdo do arquivo `docker-compose.portainer.yml`

### Passo 3: Configurar variáveis de ambiente

Na seção **Environment variables** do Portainer, adicione:

```
DOMAIN=wchip.seudominio.com
SECRET_KEY=sua-chave-secreta-aqui
DEBUG=False
ALLOWED_HOSTS=wchip.seudominio.com,localhost
```

Ou faça upload do arquivo `.env` na opção **Load variables from .env file**

### Passo 4: Deploy

1. Clique em **Deploy the stack**
2. Aguarde o Portainer fazer o build e iniciar os containers
3. Verifique os logs dos containers para confirmar que estão rodando corretamente

## Verificação

Após o deploy:

1. Acesse seu domínio: `https://wchip.seudominio.com`
2. Verifique se o redirecionamento HTTP → HTTPS está funcionando
3. Confira o certificado SSL

## Comandos úteis

### Ver logs pelo Portainer
- Acesse a stack → clique no container → Logs

### Executar comandos Django

No Portainer, acesse o container `djangoapp` → Console e execute:

```bash
# Migrar banco de dados
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser

# Coletar arquivos estáticos
python manage.py collectstatic --noinput
```

## Estrutura da Stack

A stack inclui:

- **web (djangoapp)**: Aplicação Django principal
  - Exposta via Traefik na porta 8000
  - Conectada às redes `public` e `internal`
  - Routers: `django-http` e `django-https`
  
- **redis**: Cache e broker para Celery
  - Apenas na rede `internal` (não exposto externamente)

## Redes

- **public**: Rede externa compartilhada com Traefik
- **internal**: Rede interna para comunicação entre containers

## Customização

### Alterar domínio
Edite a variável `DOMAIN` nas variáveis de ambiente da stack.

### Adicionar subdomínios ou múltiplos domínios
Modifique os labels do Traefik:
```yaml
- "traefik.http.routers.django-https.rule=Host(`wchip.com`) || Host(`www.wchip.com`)"
```

### Desabilitar HTTPS (não recomendado)
Remova os labels relacionados a HTTPS e mantenha apenas o router HTTP.

### Adicionar middleware de autenticação
```yaml
- "traefik.http.middlewares.auth.basicauth.users=user:$$apr1$$..."
- "traefik.http.routers.django-https.middlewares=auth"
```

## Troubleshooting

### Container não inicia
- Verifique os logs no Portainer
- Confirme que o arquivo `.env` está configurado corretamente
- Verifique se as dependências (Redis, banco de dados) estão rodando

### Traefik não roteia corretamente
- Confirme que a rede `public` existe e o Traefik está conectado nela
- Verifique se o domínio aponta para o servidor
- Confira os labels do Traefik nos logs do container Traefik

### Erro de certificado SSL
- Verifique se o certificateResolver `leresolver` está configurado no Traefik
- Confirme que as portas 80 e 443 estão abertas e acessíveis
- Aguarde alguns minutos para o Let's Encrypt emitir o certificado
- Verifique os logs do Traefik para erros relacionados ao ACME

### Redis não conecta
- Verifique se o container Redis está rodando
- Confirme que ambos os containers estão na mesma rede `internal`
- Verifique as variáveis `REDIS_HOST` e `REDIS_PORT`

## Segurança

- ✅ Use sempre HTTPS em produção
- ✅ Configure `DEBUG=False` em produção
- ✅ Use senhas fortes para SECRET_KEY e banco de dados
- ✅ Mantenha o Redis apenas na rede interna
- ✅ Configure ALLOWED_HOSTS corretamente
- ✅ Mantenha as imagens Docker atualizadas

## Backup

Faça backup regularmente:
- Volume `redis-data`
- Banco de dados (se externo)
- Arquivo `.env`
- Arquivos de mídia e estáticos

## Suporte

Para mais informações sobre:
- Traefik: https://doc.traefik.io/traefik/
- Portainer: https://docs.portainer.io/
- Django: https://docs.djangoproject.com/
