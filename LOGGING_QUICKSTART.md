# 📊 Sistema de Logging Instalado - Início Rápido

## ✅ Status da Instalação

O sistema de logging foi instalado com sucesso! 

### Arquivos Criados:
- ✅ `/home/judbomfim/wchip/core/settings.py` - Configuração de logging
- ✅ `/home/judbomfim/wchip/logs/` - Diretório de logs
- ✅ `/home/judbomfim/wchip/core/logging_utils.py` - Utilitários de logging
- ✅ `/home/judbomfim/wchip/LOGGING_GUIDE.md` - Documentação completa
- ✅ `/home/judbomfim/wchip/apps/sims/tasks.py` - Logger configurado
- ✅ `/home/judbomfim/wchip/apps/orders/tasks.py` - Logger configurado

### Arquivos de Log Disponíveis:
- 📄 `logs/app.log` - Logs gerais
- 📄 `logs/error.log` - Apenas erros
- 📄 `logs/celery.log` - Logs do Celery
- 📄 `logs/sims.log` - Logs do módulo sims
- 📄 `logs/orders.log` - Logs do módulo orders

---

## 🚀 Uso Rápido (Copy & Paste)

### 1️⃣ Em qualquer arquivo .py do projeto:

```python
import logging
from datetime import datetime

# Obter logger (escolha o módulo correto)
logger = logging.getLogger('apps.sims')      # Para módulo sims
# logger = logging.getLogger('apps.orders')  # Para módulo orders
# logger = logging.getLogger('apps.send_email')  # Para módulo send_email

# Usar com data/hora
date_now = datetime.now()
logger.info(f'[{date_now}] Sua mensagem aqui')
```

### 2️⃣ Exemplo em uma função/task:

```python
@shared_task
def minha_task():
    date_now = datetime.now()
    logger = logging.getLogger('apps.sims')
    
    logger.info(f'[{date_now}] Iniciando minha_task')
    
    try:
        # seu código aqui
        resultado = processar_algo()
        logger.info(f'[{date_now}] Task concluída com sucesso')
        return resultado
        
    except Exception as e:
        logger.error(f'[{date_now}] Erro na task: {str(e)}', exc_info=True)
        raise
```

### 3️⃣ Usando utilitários prontos:

```python
from core.logging_utils import get_logger, log_task_start, log_task_end, log_error

logger = get_logger('apps.sims')

@shared_task
def processar():
    log_task_start(logger, 'processar', item_id=123)
    
    try:
        # processar
        log_task_end(logger, 'processar', status='sucesso', total=10)
    except Exception as e:
        log_error(logger, e, context='Processamento', item_id=123)
```

---

## 📺 Ver Logs em Tempo Real

```bash
# Ver logs gerais
tail -f /home/judbomfim/wchip/logs/app.log

# Ver logs de erros
tail -f /home/judbomfim/wchip/logs/error.log

# Ver logs do módulo sims
tail -f /home/judbomfim/wchip/logs/sims.log

# Ver logs do Celery
tail -f /home/judbomfim/wchip/logs/celery.log
```

---

## 🎯 Passo a Passo de Implementação

### ✅ PASSO 1: Configuração (CONCLUÍDO)
- [x] Logging configurado no `settings.py`
- [x] Diretório `/logs` criado
- [x] Arquivos de log inicializados

### ✅ PASSO 2: Aplicar em módulos existentes (CONCLUÍDO)
- [x] Logger adicionado em `apps/sims/tasks.py`
- [x] Logger adicionado em `apps/orders/tasks.py`
- [x] Utilitários criados em `core/logging_utils.py`

### 📋 PASSO 3: Adicionar em outros arquivos (PRÓXIMO)

Para adicionar logging em outros arquivos, siga este modelo:

#### Em views.py:
```python
import logging
from datetime import datetime

logger = logging.getLogger('apps.sims')  # ou 'apps.orders', etc

def sua_view(request):
    date_now = datetime.now()
    logger.info(f'[{date_now}] View acessada: {request.path}')
    
    try:
        # seu código
        return render(request, 'template.html')
    except Exception as e:
        logger.error(f'[{date_now}] Erro na view: {str(e)}', exc_info=True)
        raise
```

#### Em classes.py:
```python
import logging
from datetime import datetime

logger = logging.getLogger('apps.sims')

class MinhaClasse:
    def processar(self):
        date_now = datetime.now()
        logger.info(f'[{date_now}] Processando...')
        # seu código
```

---

## 🔍 Testar o Sistema

Execute o script de teste:

```bash
/home/judbomfim/wchip/.venv/bin/python /home/judbomfim/wchip/test_logging.py
```

Depois verifique os logs criados:

```bash
ls -lh /home/judbomfim/wchip/logs/
cat /home/judbomfim/wchip/logs/sims.log
```

---

## 📚 Documentação Completa

Para mais detalhes, exemplos e configurações avançadas, consulte:

👉 **[LOGGING_GUIDE.md](/home/judbomfim/wchip/LOGGING_GUIDE.md)**

---

## 💡 Dicas Importantes

1. **Sempre use `date_now = datetime.now()`** para incluir timestamp
2. **Use `exc_info=True`** em `logger.error()` para ver o traceback completo
3. **Escolha o logger correto** para cada módulo
4. **Em produção**, considere mudar nível para WARNING ou ERROR

---

## 📊 Níveis de Log Disponíveis

```python
logger.debug(...)     # Desenvolvimento/Debug
logger.info(...)      # Informações gerais ✅ Mais usado
logger.warning(...)   # Alertas
logger.error(...)     # Erros ✅ Muito importante
logger.critical(...)  # Erros críticos
```

---

## ✅ Sistema Pronto!

O logging está instalado e funcional. Agora você pode:

1. ✅ Logar informações em qualquer parte do código
2. ✅ Monitorar erros em tempo real
3. ✅ Auditar operações do sistema
4. ✅ Debugar problemas de produção

**Próximo passo:** Adicione logging em suas views, classes e outros tasks seguindo os exemplos acima!
