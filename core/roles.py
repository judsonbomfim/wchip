from rolepermissions.roles import AbstractUserRole

class Atendente(AbstractUserRole):
    available_permissions = {
        'view_orders': True,
        'edit_orders': True,
        'send_esims_but': True,
    }
class Gerente(AbstractUserRole):
    available_permissions = {
        'view_statistics': True,
        'view_orders': True,
        'edit_orders': True,
        'import_orders': True,
        'view_sims': True,
        'add_sims': True,
        'add_esims': True,
        'edit_sims': True,
        'add_ord_sims': True,
        'send_esims_but': True,
        'list_activations': True,
        'export_activations': True,
        'list_number': True,
    }