# Instalação no Portainer com Traefik

Este guia mostra como instalar a aplicação wchip no Portainer usando Traefik como reverse proxy.

## Pré-requisitos

1. **Traefik instalado e configurado** no seu ambiente Docker/Portainer
2. **Rede `public` criada** (Traefik):
   ```bash
   docker network create public
   ```
3. **Rede `shared_backend` criada** (Postgres e outros serviços do host):
   ```bash
   docker network create shared_backend
   ```
4. **Portainer instalado e acessível**
5. Arquivo `.env` da aplicação **no host** (conteúdo de produção). No repo isso está em `.env.production` — o `.env` da raiz é só local.

## Configuração do Traefik

Certifique-se que seu Traefik está configurado com:
- Entrypoints `web` (porta 80) e `websecure` (porta 443)
- Certificate resolver `leresolver` configurado (Let's Encrypt)
- Rede `public` conectada
- `--providers.docker.exposedbydefault=false`

Exemplo de configuração no docker-compose do Traefik (stack separada):
```yaml
services:
  traefik:
    image: "traefik:v3.3"
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

Não use `traefik:latest` em produção. Pin a versão.

## Instalação no Portainer

### Passo 1: Preparar variáveis

Há **dois** arquivos de ambiente no repositório:

| Arquivo | Uso |
|---|---|
| `.env` | Somente desenvolvimento local. Não copiar para o servidor. |
| `.env.production` | Conteúdo de produção. No servidor o nome do arquivo é `.env`. |

1. Use [`.env.portainer.example`](.env.portainer.example) como checklist da **stack** (DOMAIN, REDIS_PASSWORD).
2. No host, publique o conteúdo de `.env.production` como `/home/sprdmntrdr/docker/django/.env` (ou o caminho em `ENV_FILE_PATH`). Troque `REDIS_PASSWORD=CHANGE_ME_SET_ON_SERVER` por uma senha real — a mesma da stack.
3. Na stack do Portainer, defina pelo menos:
   - `DOMAIN` — host Traefik (ex: `painel.worldchip.com.br`)
   - `REDIS_PASSWORD` — senha forte (obrigatória; o compose não sobe sem ela)
   - `ENV_FILE_PATH` — caminho do `.env` no host (default: `/home/sprdmntrdr/docker/django/.env`)
   - `DEBUG=False`
   - `IMAGE_NAME` (opcional, default `djangoweb:latest`)

`DEBUG` agora é lido por `core/settings.py`. `DEBUG=False` no Portainer **vale**.

### Passo 2: Criar Stack no Portainer

1. Acesse o Portainer
2. Vá em **Stacks** → **Add stack**
3. Nomeie a stack (ex: `wchip`)
4. Escolha uma das opções:

#### Opção A: Upload do arquivo docker-compose
- Selecione **Upload**
- Faça upload do arquivo `docker-compose.yml`

#### Opção B: Repositório Git
- Selecione **Repository**
- Configure o repositório Git
- Caminho do compose: `docker-compose.yml`

#### Opção C: Web editor
- Selecione **Web editor**
- Cole o conteúdo do arquivo `docker-compose.yml`

### Passo 3: Configurar variáveis de ambiente

Na seção **Environment variables** do Portainer:

```
DOMAIN=painel.worldchip.com.br
REDIS_PASSWORD=senha-longa-aleatoria
ENV_FILE_PATH=/home/sprdmntrdr/docker/django/.env
DEBUG=False
IMAGE_NAME=djangoweb:latest
COLLECTSTATIC_ON_STARTUP=false
```

Ou **Load variables from .env file** a partir de uma cópia local do `.env.portainer.example` (nunca commitar senhas).

O bind-mount `${ENV_FILE_PATH}:/djangoweb/.env:ro` continua sendo a fonte das secrets do Django. `REDIS_PASSWORD` da stack é injetado no Redis (`--requirepass`) e nas URLs Celery.

### Passo 4: Deploy

1. Clique em **Deploy the stack**
2. Aguarde o Portainer fazer o build e iniciar os containers
3. Confira healthchecks: `wchip-web` só fica healthy depois de migrate + Gunicorn; Celery/Beat esperam isso
4. Verifique os logs dos containers

## Rotação de secrets (imagens antigas)

O `.dockerignore` agora exclui `.env`. Se alguma imagem `djangoweb:latest` foi buildada **antes** desta correção, as layers podem ter gravado SECRET_KEY, senha do banco, AWS e APIs.

1. Rebuild da imagem (`djangoweb:latest` novo)
2. Remova imagens antigas no host (`docker image prune` / delete da tag antiga)
3. **Rotacione** SECRET_KEY, senha do Postgres, AWS, SMTP e todas as `API*` keys
4. Atualize o `.env` do host (a partir de `.env.production`) e a senha do Redis (`REDIS_PASSWORD`) — a mesma na stack e no arquivo

## Checklist: stack já existe no Portainer

Não é instalação nova. **Não** crie outra stack, **não** apague a stack, **não** crie redes novas. Atualize a stack atual e o `.env` que o host já monta.

Haverá downtime curto: os `container_name` mudam (`djangoapp` → `wchip-web`, etc.) e o Redis passa a exigir senha.

### O que muda vs o guia de instalação

| Item | Instalação nova | Vocês (já no Portainer) |
|---|---|---|
| Stack | Add stack | **Editor / Git da stack existente → Update** |
| Redes `public` / `shared_backend` | criar se faltar | **já existem — só conferir** |
| `wchip_internal` | compose cria | compose cria no Update |
| `.env` no host | criar | **editar o que já está em** `/home/sprdmntrdr/docker/django/.env` |
| `redis.conf` | garantir na pasta | **Git: vem no pull.** Upload só do YAML: copiar o arquivo |
| `docker rm -f` | às vezes | **só se o Update falhar** por nome em uso |
| Volumes `redis-data` / `logs` | novos | **permanecem** se o nome da stack for o mesmo |

### 1. Conferir redes (não criar)

No host:

```bash
docker network ls | grep -E 'public|shared_backend'
```

As duas têm que existir. Não rode `docker network create`. Não crie `wchip_internal`.

### 2. Atualizar o `.env` do host (já existe)

O bind-mount continua o mesmo caminho. **Não** substitua pelo `.env` local do notebook.

No servidor, edite `/home/sprdmntrdr/docker/django/.env` e **acrescente/ajuste** (mesmos valores que em `.env.production`):

```
DEBUG=False
USE_S3=True
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<senha-nova-forte>
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

`URL_PAINEL` e `CSRF_TRUSTED_ORIGINS` com `https://` e o host do painel.

```bash
ENV_FILE=/home/sprdmntrdr/docker/django/.env
chmod 600 "$ENV_FILE"
grep -E '^(DEBUG|REDIS_PASSWORD|USE_S3|URL_PAINEL|CSRF_TRUSTED_ORIGINS|CELERY_BROKER_URL)=' "$ENV_FILE"
```

`REDIS_PASSWORD` não pode ser `CHANGE_ME_SET_ON_SERVER`.

### 3. `redis.conf`

- **Repository (Git):** no Update o Portainer puxa o `redis.conf` da raiz. Nada a copiar no host.
- **Web editor / upload só do compose:** o bind `./redis.conf` quebra. Cole o compose **e** deixe `redis.conf` no mesmo diretório que o Portainer usa para a stack (ou mude a stack para Git).

### 4. Variáveis da stack no Portainer

Stacks → a stack do wchip → **Editor** → **Environment variables**. **Some** (não apague as que já funcionam):

```
DOMAIN=painel.worldchip.com.br
REDIS_PASSWORD=<igual ao REDIS_PASSWORD do .env do host>
ENV_FILE_PATH=/home/sprdmntrdr/docker/django/.env
DEBUG=False
IMAGE_NAME=djangoweb:latest
COLLECTSTATIC_ON_STARTUP=false
```

Sem `REDIS_PASSWORD` o Update falha (`REDIS_PASSWORD is required`).

### 5. Atualizar o compose e fazer Update

1. Commit/push deste repo **ou** cole o `docker-compose.yml` novo no editor da stack.
2. Caminho do compose continua `docker-compose.yml` (não existe `docker-compose.portainer.yml`).
3. Marque **Re-pull image** / rebuild se a opção existir.
4. **Update the stack** (não Remove, não Add stack).

O Portainer recria `web` / `celery` / `celery_beat` / `redis` com os nomes `wchip-*`. Volumes da stack permanecem.

Se o Update falhar com *The container name "djangoapp" is already in use* (ou `redis` / `celery`):

```bash
docker rm -f djangoapp celery celery_beat redis
```

Aí **Update** de novo. Não apague a stack no Portainer.

### 6. Depois do Update

No host, depois que o Portainer terminar o pull/build:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep wchip
```

Esperado: `wchip-web`, `wchip-celery`, `wchip-celery-beat`, `wchip-redis` **Up**.  
`wchip-web` pode ficar **starting** até ~90s (migrate + Gunicorn).

```bash
docker inspect -f '{{.Name}} {{.State.Health.Status}}' wchip-web wchip-redis
```

Esperado: `healthy` nos dois. Celery/beat não precisam de HTTP; o healthcheck da imagem trata ausência da porta 8000 como ok.

### 7. Conferências rápidas no host

```bash
# Usuário não-root
docker exec wchip-web id -u    # 10001

# Redis exige senha (deve FALHAR sem AUTH)
docker exec wchip-redis redis-cli ping && echo 'ERRO: redis sem senha' || echo 'REDIS_AUTH_OK'

# Redis com senha da stack (substitua ou exporte REDIS_PASSWORD no host)
docker exec -e REDISCLI_AUTH="$REDIS_PASSWORD" wchip-redis redis-cli ping   # PONG

# Health interno
docker exec wchip-web python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=4).read())"

# Redes do web
docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' wchip-web
# Esperado: public  shared_backend  e a rede interna do stack (wchip_internal / <stack>_wchip_internal)

# Redis NÃO pode estar em shared_backend / public
docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' wchip-redis
```

Não escale `wchip-celery-beat` (réplicas = 1).

### 8. Conferências no browser

- [ ] `http://painel.worldchip.com.br` redireciona para HTTPS
- [ ] `https://painel.worldchip.com.br/healthz/` responde `ok` (sem login)
- [ ] Certificado Let's Encrypt válido
- [ ] Login do painel (POST) — se 403 CSRF, `URL_PAINEL` / `CSRF_TRUSTED_ORIGINS` com `https://` e o mesmo host
- [ ] Dashboard carrega CSS/JS (S3)
- [ ] Cookie de sessão com flag **Secure** (DevTools → Application)

### 9. Imagem antiga com `.env` no build (só se já buildou `djangoweb:latest` antes deste hardening)

```bash
docker images djangoweb
# Depois do rebuild ok, remova dangling:
docker image prune -f
```

Aí rotacione SECRET_KEY, senha do Postgres, AWS, SMTP e `API*` no `.env` do host.

### 10. Rollback rápido

Portainer → stack → **Rollback** / redeploy do commit anterior.  
Os containers voltam aos nomes antigos só se o compose antigo for o que subir. Volumes `redis-data` e o `.env` do host permanecem.

## Comandos úteis

### Ver logs pelo Portainer
- Acesse a stack → clique no container → Logs

### Executar comandos Django

No Portainer, acesse o container `wchip-web` → Console:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

## Estrutura da Stack

- **wchip-web**: Django + Gunicorn (entrypoint `web`)
  - Redes: `public` (Traefik), `shared_backend` (Postgres), `wchip_internal` (Redis)
  - Porta 8000 só no overlay Docker — Traefik faz o TLS
- **wchip-celery**: worker (não escalar sem revisar locks)
- **wchip-celery-beat**: um único processo — não escalar
- **wchip-redis**: Redis 7.2.16 com senha, só em `wchip_internal`

## Redes

- **public**: externa, compartilhada com Traefik
- **shared_backend**: externa, Postgres e outros stacks do host
- **wchip_internal**: bridge interna do stack (`internal: true`) — só Redis + app

## Customização

### Alterar domínio
Edite `DOMAIN` nas variáveis da stack. Também atualize `ALLOWED_HOSTS`, `URL_PAINEL` e `CSRF_TRUSTED_ORIGINS` no `.env` do Django.

### Adicionar subdomínios
Modifique os labels do Traefik:
```yaml
- "traefik.http.routers.django-https.rule=Host(`wchip.com`) || Host(`www.wchip.com`)"
```

### collectstatic
`COLLECTSTATIC_ON_STARTUP=false` no serviço sempre ligado. Use `true` só num deploy que precise publicar CSS/JS no S3, ou rode `collectstatic` manualmente.

## Troubleshooting

### Container não inicia
- `REDIS_PASSWORD` ausente: o compose recusa interpolar (`REDIS_PASSWORD is required`)
- Confirme que `ENV_FILE_PATH` existe no host e está legível
- Confirme redes `public` e `shared_backend`

### Traefik não roteia
- Rede `public` existe e o Traefik está nela
- `DOMAIN` bate com o DNS
- Labels no container `wchip-web`

### Redis não conecta
- Celery/web devem estar em `wchip_internal` (não use mais o nome `internal` / Redis na `shared_backend`)
- `REDIS_PASSWORD` da stack igual em Redis e nos containers Django
- `CELERY_BROKER_URL=redis://redis:6379/0` — a senha é injetada pelo settings

### /healthz/ 400 DisallowedHost
- Não remova a inclusão automática de `127.0.0.1` em `ALLOWED_HOSTS`

### Login CSRF 403
- `URL_PAINEL` e `CSRF_TRUSTED_ORIGINS` com `https://` e o mesmo host de `DOMAIN`

## Segurança

- Use sempre HTTPS em produção (Traefik já redireciona)
- `DEBUG=False` em produção (agora respeitado)
- Redis com senha, só na rede `wchip_internal`
- Não publique 6379/8000 no host
- Se rebuildar depois de um `.env` ter ido para a imagem, rotacione as chaves
- Mantenha as imagens atualizadas

## Backup

- Volume `redis-data`
- Banco de dados (externo)
- Arquivo `.env` do host
- Arquivos de mídia e estáticos (S3)

## Suporte

- Traefik: https://doc.traefik.io/traefik/
- Portainer: https://docs.portainer.io/
- Django: https://docs.djangoproject.com/
