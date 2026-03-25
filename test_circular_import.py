#!/usr/bin/env python
"""
Teste simples para validar que o ciclo de importação foi resolvido.
"""
import sys
import os

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(__file__))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

try:
    import django
    django.setup()
    
    print("✓ Django setup OK")
    
    # Testar importações que causavam ciclo
    from apps.sims import tasks as sims_tasks
    print("✓ apps.sims.tasks importado com sucesso")
    
    from apps.orders import tasks as orders_tasks
    print("✓ apps.orders.tasks importado com sucesso")
    
    # Verificar que as funções estão disponíveis
    assert hasattr(sims_tasks, 'sims_in_orders'), "sims_in_orders não encontrada"
    assert hasattr(sims_tasks, 'simActivateTC'), "simActivateTC não encontrada"
    assert hasattr(sims_tasks, 'simDeactivateTC'), "simDeactivateTC não encontrada"
    print("✓ Funções de sims disponíveis")
    
    assert hasattr(orders_tasks, 'order_import'), "order_import não encontrada"
    assert hasattr(orders_tasks, 'orders_up_status'), "orders_up_status não encontrada"
    print("✓ Funções de orders disponíveis")
    
    print("\n✅ SUCESSO: Ciclo de importação resolvido!")
    sys.exit(0)
    
except ImportError as e:
    print(f"❌ ERRO de importação: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
    
except Exception as e:
    print(f"❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
