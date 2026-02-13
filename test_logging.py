"""
Script de teste para verificar sistema de logging
"""
import os
import sys
import django

# Configurar Django
sys.path.append('/home/judbomfim/wchip')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

import logging
from datetime import datetime
from core.logging_utils import (
    get_logger,
    log_task_start,
    log_task_end,
    log_error,
    log_api_call,
    log_database_operation
)

def test_logging():
    """Testa o sistema de logging"""
    
    print("🧪 Testando sistema de logging...\n")
    
    # Teste 1: Logger básico
    print("✓ Teste 1: Logger básico")
    logger = get_logger('apps.sims')
    date_now = datetime.now()
    logger.info(f'[{date_now}] Teste de logging básico - Sistema funcionando!')
    
    # Teste 2: Diferentes níveis
    print("✓ Teste 2: Diferentes níveis de log")
    logger.debug(f'[{date_now}] Teste DEBUG')
    logger.info(f'[{date_now}] Teste INFO')
    logger.warning(f'[{date_now}] Teste WARNING')
    logger.error(f'[{date_now}] Teste ERROR')
    
    # Teste 3: Utilitários
    print("✓ Teste 3: Utilitários de logging")
    log_task_start(logger, 'teste_task', test_id=123)
    log_task_end(logger, 'teste_task', status='sucesso', items_processed=10)
    
    # Teste 4: Log de API
    print("✓ Teste 4: Log de chamada de API")
    log_api_call(logger, 'ApiTC', '/test/endpoint', method='POST', param1='valor1')
    
    # Teste 5: Log de banco de dados
    print("✓ Teste 5: Log de operação de banco")
    log_database_operation(logger, 'UPDATE', 'Orders', order_id=123, status='AA')
    
    # Teste 6: Log de erro
    print("✓ Teste 6: Log de erro")
    try:
        raise ValueError("Erro de teste proposital")
    except Exception as e:
        log_error(logger, e, context='Teste de erro', test_param='valor')
    
    print("\n✅ Todos os testes concluídos!")
    print(f"\n📂 Verifique os logs em: /home/judbomfim/wchip/logs/")
    print("   - app.log (logs gerais)")
    print("   - sims.log (logs do módulo sims)")
    print("   - error.log (apenas erros)")

if __name__ == '__main__':
    test_logging()
