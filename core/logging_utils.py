"""
Utilitários para logging centralizado
"""
import logging
from datetime import datetime
from functools import wraps
from typing import Any, Callable


def get_logger(name: str) -> logging.Logger:
    """
    Retorna um logger configurado
    
    Args:
        name: Nome do módulo (ex: 'apps.sims', 'apps.orders')
    
    Returns:
        Logger configurado
    """
    return logging.getLogger(name)


def log_execution_time(logger: logging.Logger):
    """
    Decorator para logar tempo de execução de funções
    
    Uso:
        @log_execution_time(logger)
        def minha_funcao():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = datetime.now()
            logger.info(f'Iniciando {func.__name__} às {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
            
            try:
                result = func(*args, **kwargs)
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                logger.info(f'Finalizando {func.__name__} - Duração: {duration:.2f}s')
                return result
            except Exception as e:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                logger.error(f'Erro em {func.__name__} após {duration:.2f}s: {str(e)}', exc_info=True)
                raise
        
        return wrapper
    return decorator


def log_task_start(logger: logging.Logger, task_name: str, **context):
    """
    Loga início de uma task com contexto
    
    Args:
        logger: Logger a ser usado
        task_name: Nome da task
        **context: Contexto adicional (ex: order_id=123)
    """
    date_now = datetime.now()
    context_str = ', '.join([f'{k}={v}' for k, v in context.items()])
    logger.info(f'[{date_now.strftime("%Y-%m-%d %H:%M:%S")}] Iniciando {task_name} | {context_str}')


def log_task_end(logger: logging.Logger, task_name: str, status: str = 'sucesso', **context):
    """
    Loga fim de uma task com status
    
    Args:
        logger: Logger a ser usado
        task_name: Nome da task
        status: Status da execução (sucesso, erro, etc)
        **context: Contexto adicional
    """
    date_now = datetime.now()
    context_str = ', '.join([f'{k}={v}' for k, v in context.items()])
    logger.info(f'[{date_now.strftime("%Y-%m-%d %H:%M:%S")}] Finalizando {task_name} - Status: {status} | {context_str}')


def log_error(logger: logging.Logger, error: Exception, context: str = '', **extra):
    """
    Loga erros de forma padronizada
    
    Args:
        logger: Logger a ser usado
        error: Exceção capturada
        context: Contexto onde o erro ocorreu
        **extra: Informações adicionais
    """
    date_now = datetime.now()
    extra_str = ', '.join([f'{k}={v}' for k, v in extra.items()])
    logger.error(
        f'[{date_now.strftime("%Y-%m-%d %H:%M:%S")}] ERRO: {type(error).__name__} - {str(error)} | '
        f'Contexto: {context} | {extra_str}',
        exc_info=True
    )


def log_api_call(logger: logging.Logger, api_name: str, endpoint: str, method: str = 'GET', **params):
    """
    Loga chamadas de API
    
    Args:
        logger: Logger a ser usado
        api_name: Nome da API (ex: 'ApiTC', 'ApiCM')
        endpoint: Endpoint chamado
        method: Método HTTP
        **params: Parâmetros da chamada
    """
    date_now = datetime.now()
    params_str = ', '.join([f'{k}={v}' for k, v in params.items()])
    logger.info(f'[{date_now.strftime("%Y-%m-%d %H:%M:%S")}] API {api_name} - {method} {endpoint} | {params_str}')


def log_database_operation(logger: logging.Logger, operation: str, model: str, **details):
    """
    Loga operações de banco de dados
    
    Args:
        logger: Logger a ser usado
        operation: Tipo de operação (CREATE, UPDATE, DELETE)
        model: Nome do modelo
        **details: Detalhes da operação
    """
    date_now = datetime.now()
    details_str = ', '.join([f'{k}={v}' for k, v in details.items()])
    logger.info(f'[{date_now.strftime("%Y-%m-%d %H:%M:%S")}] DB {operation} - {model} | {details_str}')


# Níveis de log disponíveis:
# logger.debug()    - Informações detalhadas para diagnóstico
# logger.info()     - Informações gerais sobre a execução
# logger.warning()  - Alertas sobre possíveis problemas
# logger.error()    - Erros que não impedem a execução
# logger.critical() - Erros críticos que impedem a execução
