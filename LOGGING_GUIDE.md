# Sistema de Logging - Guia de Uso

## 📋 Configuração Instalada

O sistema de logging foi configurado com sucesso no projeto. Ele inclui:

### Arquivos de Log
- **app.log** - Log geral da aplicação (INFO)
- **error.log** - Erros da aplicação (ERROR)
- **celery.log** - Logs específicos do Celery
- **sims.log** - Logs do módulo sims
- **orders.log** - Logs do módulo orders

Todos os logs estão em: `/home/judbomfim/wchip/logs/`

---

## 🚀 Como Usar

### 1. Importar o logger no seu módulo

```python
import logging
from datetime import datetime

# Para módulo sims
logger = logging.getLogger('apps.sims')

# Para módulo orders
logger = logging.getLogger('apps.orders')

# Para módulo send_email
logger = logging.getLogger('apps.send_email')

# Para módulo users
logger = logging.getLogger('apps.users')
```

### 2. Usar o logger com data/hora

```python
from datetime import datetime

date_now = datetime.now()

# Informação geral
logger.info(f'[{date_now}] Iniciando processamento')

# Erro
logger.error(f'[{date_now}] Erro ao processar: {erro}')

# Aviso
logger.warning(f'[{date_now}] Atenção: recurso limitado')

# Debug (desenvolvimento)
logger.debug(f'[{date_now}] Variável X = {valor}')
```

### 3. Logar exceções completas

```python
try:
    # código
    resultado = funcao_perigosa()
except Exception as e:
    date_now = datetime.now()
    logger.error(f'[{date_now}] Erro na função: {str(e)}', exc_info=True)
    # exc_info=True inclui o traceback completo
```

### 4. Usar utilitários prontos

```python
from core.logging_utils import (
    get_logger,
    log_task_start,
    log_task_end,
    log_error,
    log_api_call,
    log_database_operation,
    log_execution_time
)

# Obter logger
logger = get_logger('apps.sims')

# Logar início de task
log_task_start(logger, 'processar_sims', order_id=123, product='chip-x')

# Logar fim de task
log_task_end(logger, 'processar_sims', status='sucesso', total=10)

# Logar erro
try:
    # código
except Exception as e:
    log_error(logger, e, context='Processando order 123', order_id=123)

# Logar chamada de API
log_api_call(logger, 'ApiTC', '/activate', method='POST', iccid='123456')

# Logar operação de banco
log_database_operation(logger, 'UPDATE', 'Orders', order_id=123, status='AA')
```

### 5. Decorator para tempo de execução

```python
from core.logging_utils import get_logger, log_execution_time

logger = get_logger('apps.sims')

@shared_task
@log_execution_time(logger)
def minha_task_longa():
    # Automaticamente loga início, fim e duração
    processar_dados()
    return resultado
```

---

## 📊 Níveis de Log

| Nível | Quando usar | Exemplo |
|-------|-------------|---------|
| `DEBUG` | Informações detalhadas para desenvolvimento | `logger.debug('Variável x = 10')` |
| `INFO` | Fluxo normal da aplicação | `logger.info('Task iniciada')` |
| `WARNING` | Alertas, mas não impedem execução | `logger.warning('Memória em 80%')` |
| `ERROR` | Erros que afetam funcionalidade | `logger.error('Falha na API')` |
| `CRITICAL` | Erros graves que param o sistema | `logger.critical('DB inacessível')` |

---

## 💡 Exemplos Práticos

### Exemplo 1: Task com logging completo

```python
import logging
from datetime import datetime
from celery import shared_task

logger = logging.getLogger('apps.sims')

@shared_task
def processar_sims():
    date_now = datetime.now()
    logger.info(f'[{date_now}] Iniciando processamento de SIMs')
    
    try:
        sims = Sims.objects.filter(status='pending')
        logger.info(f'[{date_now}] Encontrados {sims.count()} SIMs para processar')
        
        for sim in sims:
            try:
                resultado = processar_sim(sim)
                logger.info(f'[{date_now}] SIM {sim.id} processado com sucesso')
            except Exception as e:
                logger.error(f'[{date_now}] Erro ao processar SIM {sim.id}: {str(e)}', exc_info=True)
        
        logger.info(f'[{date_now}] Processamento concluído')
        
    except Exception as e:
        logger.critical(f'[{date_now}] Erro crítico: {str(e)}', exc_info=True)
        raise
```

### Exemplo 2: Logging de API calls

```python
date_now = datetime.now()
logger.info(f'[{date_now}] Chamando API TC - Endpoint: /activate')

try:
    response = api_tc.activate(iccid)
    if response.status_code == 200:
        logger.info(f'[{date_now}] API TC - Sucesso: ICCID {iccid} ativado')
    else:
        logger.error(f'[{date_now}] API TC - Erro {response.status_code}: {response.text}')
except Exception as e:
    logger.error(f'[{date_now}] API TC - Exceção: {str(e)}', exc_info=True)
```

### Exemplo 3: Logging de operações de banco

```python
date_now = datetime.now()

try:
    order = Orders.objects.get(pk=order_id)
    logger.info(f'[{date_now}] Order {order_id} recuperado do banco')
    
    order.status = 'AA'
    order.save()
    logger.info(f'[{date_now}] Order {order_id} atualizado - status=AA')
    
except Orders.DoesNotExist:
    logger.error(f'[{date_now}] Order {order_id} não encontrado')
except Exception as e:
    logger.error(f'[{date_now}] Erro ao atualizar order {order_id}: {str(e)}', exc_info=True)
```

---

## 🔧 Configuração Avançada

### Alterar nível de log (settings.py)

Para mudar o nível de log em produção/desenvolvimento:

```python
# Em settings.py
LOGGING['loggers']['apps.sims']['level'] = 'DEBUG'  # Mais detalhado
LOGGING['loggers']['apps.sims']['level'] = 'WARNING'  # Menos detalhado
```

### Desabilitar logs no console

```python
# Em settings.py, remover 'console' dos handlers
LOGGING['loggers']['apps.sims']['handlers'] = ['sims_file', 'file_error']
```

### Aumentar tamanho dos arquivos de log

```python
# Em settings.py
LOGGING['handlers']['file']['maxBytes'] = 1024 * 1024 * 50  # 50MB
LOGGING['handlers']['file']['backupCount'] = 20  # 20 arquivos de backup
```

---

## 📁 Rotação de Logs

Os logs são automaticamente rotacionados quando atingem 15MB:
- Mantém 10 backups
- Formato: `app.log`, `app.log.1`, `app.log.2`, etc.

---

## 🔍 Visualizar Logs

### Via terminal

```bash
# Ver logs em tempo real
tail -f logs/app.log

# Ver últimas 100 linhas
tail -n 100 logs/app.log

# Buscar por erro específico
grep "ERROR" logs/app.log

# Buscar por data específica
grep "2026-02-04" logs/app.log

# Ver logs de erro
tail -f logs/error.log

# Ver logs do Celery
tail -f logs/celery.log
```

### Filtrar por módulo

```bash
# Ver logs do módulo sims
tail -f logs/sims.log

# Ver logs do módulo orders
tail -f logs/orders.log
```

---

## ✅ Checklist de Implementação

- [x] Configuração de logging no settings.py
- [x] Criação do diretório /logs
- [x] Arquivo .gitignore para logs
- [x] Logger configurado em apps/sims/tasks.py
- [x] Logger configurado em apps/orders/tasks.py
- [x] Utilitários de logging criados (logging_utils.py)
- [x] Documentação de uso

---

## 🎯 Próximos Passos

1. **Adicionar logs em outros módulos**: Siga o mesmo padrão em `views.py`, `classes.py`, etc.

2. **Monitoramento**: Considere ferramentas como:
   - Sentry (erros em produção)
   - ELK Stack (centralização de logs)
   - Grafana (visualização)

3. **Alertas**: Configure alertas para logs críticos via email/Slack

---

## 📞 Suporte

Se tiver dúvidas sobre logging, consulte:
- [Documentação Django Logging](https://docs.djangoproject.com/en/4.2/topics/logging/)
- [Python Logging Tutorial](https://docs.python.org/3/howto/logging.html)
- Arquivo: `/home/judbomfim/wchip/core/logging_utils.py`
