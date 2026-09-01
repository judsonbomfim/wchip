from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.sims.models import Sims
from apps.orders.models import Orders
import json
from datetime import datetime, timedelta
from collections import Counter, defaultdict


@login_required(login_url='/login/')
def index(request):
    today = datetime.now()
    dateDay = today.date()

    dateTomorrow = dateDay + timedelta(days=1)
    dateYesterday = dateDay - timedelta(days=1)
    dateWeek = dateDay - timedelta(days=7)
    dateMonth = dateDay - timedelta(days=30)
    dateYear = dateDay - timedelta(days=365)

    orders_pending = Orders.objects.filter(
        activation_date__lte=dateDay
    ).exclude(
        order_status__in=['AT', 'CC', 'CN', 'DE', 'DA', 'ED', 'RB', 'RE']
    ).order_by('activation_date')

    activationOrders = Orders.objects.filter(activation_date=dateTomorrow)
    operator_counts = Counter(activationOrders.values_list('id_sim__operator', flat=True))

    countActivTM = operator_counts.get('TM', 0)
    countActivCM = operator_counts.get('CM', 0)
    countActivCMHK = operator_counts.get('CMHK', 0)
    countActivTC = operator_counts.get('TC', 0)
    countActivVR = operator_counts.get('VR', 0)

    # Vendas até o fim de hoje; exclui cancelados/reembolsos
    # DateTimeField + __range com date corta hoje à 00:00 — usar __lt=dateTomorrow
    simsAll = Sims.objects.all()
    non_sale_status = ['CC', 'RB', 'RE']
    chart_orders = Orders.objects.exclude(order_status__in=non_sale_status)
    ordersWeek = chart_orders.filter(order_date__gte=dateWeek, order_date__lt=dateTomorrow)
    ordersMonth = chart_orders.filter(order_date__gte=dateMonth, order_date__lt=dateTomorrow)
    ordersYear = chart_orders.filter(order_date__gte=dateYear, order_date__lt=dateTomorrow)

    # item_id = 1 linha de venda (loja ou manual). type_sim/oper_sim cobrem
    # pedidos manuais ainda sem id_sim ou com tipo/operadora só no pedido.
    fields = [
        'item_id',
        'order_id',
        'order_date',
        'type_sim',
        'oper_sim',
        'id_sim__type_sim',
        'id_sim__operator',
    ]

    def process_orders(orders_qs):
        processed = []
        for order in orders_qs.values(*fields):
            order_date = order['order_date']
            processed.append({
                'item_id': order['item_id'],
                'order_id': order['order_id'],
                'order_date': order_date.date() if hasattr(order_date, 'date') else order_date,
                'type_sim': order['id_sim__type_sim'] or order['type_sim'],
                'operator': order['id_sim__operator'] or order['oper_sim'],
            })
        return processed

    week_orders = process_orders(ordersWeek)
    month_orders = process_orders(ordersMonth)

    year_orders = []
    for order in ordersYear.values(*fields):
        order_date = order['order_date']
        order_date = order_date.date() if hasattr(order_date, 'date') else order_date
        year_orders.append({
            'item_id': order['item_id'],
            'order_id': order['order_id'],
            'order_date': order_date,
            'month': order_date.replace(day=1),
            'type_sim': order['id_sim__type_sim'] or order['type_sim'],
            'operator': order['id_sim__operator'] or order['oper_sim'],
        })

    # SIMs Vendidos: 1 ponto por item (inclui manuais e multi-item da loja)
    unique_week_sales = {sale['item_id']: sale for sale in week_orders}.values()
    sales_by_date_week = defaultdict(int)
    for sale in unique_week_sales:
        sales_by_date_week[sale['order_date']] += 1

    unique_month_sales = {sale['item_id']: sale for sale in month_orders}.values()
    sales_by_date_month = defaultdict(int)
    for sale in unique_month_sales:
        sales_by_date_month[sale['order_date']] += 1

    unique_year_sales = {sale['item_id']: sale for sale in year_orders}.values()
    sales_by_month_year = defaultdict(int)
    for sale in unique_year_sales:
        sales_by_month_year[sale['month']] += 1

    all_week_dates = [dateWeek + timedelta(days=i) for i in range((dateDay - dateWeek).days + 1)]
    all_month_dates = [dateMonth + timedelta(days=i) for i in range((dateDay - dateMonth).days + 1)]

    all_year_months = []
    current_month = dateYear.replace(day=1)
    while current_month <= dateDay.replace(day=1):
        all_year_months.append(current_month)
        next_month = current_month.replace(day=28) + timedelta(days=4)
        current_month = next_month.replace(day=1)

    sales_by_date_week = {d: sales_by_date_week.get(d, 0) for d in all_week_dates}
    sorted_sales_week = sorted(sales_by_date_week.items())
    sales_by_date_month = {d: sales_by_date_month.get(d, 0) for d in all_month_dates}
    sorted_sales_month = sorted(sales_by_date_month.items())
    sales_by_month_year = {m: sales_by_month_year.get(m, 0) for m in all_year_months}
    sorted_sales_year = sorted(sales_by_month_year.items())

    weekSalesDates = json.dumps([d.strftime('%Y-%m-%d') for d, v in sorted_sales_week])
    weekSalesValues = json.dumps([v for d, v in sorted_sales_week])
    monthSalesDates = json.dumps([d.strftime('%Y-%m-%d') for d, v in sorted_sales_month])
    monthSalesValues = json.dumps([v for d, v in sorted_sales_month])
    yearSalesDates = json.dumps([d.strftime('%Y-%m') for d, v in sorted_sales_year])
    yearSalesValues = json.dumps([v for d, v in sorted_sales_year])

    sims_by_date_type_week = defaultdict(lambda: defaultdict(int))
    for order in {o['item_id']: o for o in week_orders}.values():
        if order['type_sim'] in ('sim', 'esim'):
            sims_by_date_type_week[order['order_date']][order['type_sim']] += 1
    weekSimsDates = json.dumps([d.strftime('%Y-%m-%d') for d in all_week_dates])
    weekSimsValuesS = json.dumps([sims_by_date_type_week[d].get('sim', 0) for d in all_week_dates])
    weekSimsValuesE = json.dumps([sims_by_date_type_week[d].get('esim', 0) for d in all_week_dates])

    sims_by_date_type_month = defaultdict(lambda: defaultdict(int))
    for order in {o['item_id']: o for o in month_orders}.values():
        if order['type_sim'] in ('sim', 'esim'):
            sims_by_date_type_month[order['order_date']][order['type_sim']] += 1
    monthSimsDates = json.dumps([d.strftime('%Y-%m-%d') for d in all_month_dates])
    monthSimsValuesS = json.dumps([sims_by_date_type_month[d].get('sim', 0) for d in all_month_dates])
    monthSimsValuesE = json.dumps([sims_by_date_type_month[d].get('esim', 0) for d in all_month_dates])

    sims_by_month_type_year = defaultdict(lambda: defaultdict(int))
    for order in {o['item_id']: o for o in year_orders}.values():
        if order['type_sim'] in ('sim', 'esim'):
            sims_by_month_type_year[order['month']][order['type_sim']] += 1
    yearSimsDates = json.dumps([m.strftime('%Y-%m') for m in all_year_months])
    yearSimsValuesS = json.dumps([sims_by_month_type_year[m].get('sim', 0) for m in all_year_months])
    yearSimsValuesE = json.dumps([sims_by_month_type_year[m].get('esim', 0) for m in all_year_months])

    unique_week_oper = {order['item_id']: order for order in week_orders}.values()
    oper_by_date_week = defaultdict(lambda: defaultdict(int))
    for order in unique_week_oper:
        if order['operator']:
            oper_by_date_week[order['order_date']][order['operator']] += 1
    weekOperDates = json.dumps([d.strftime('%Y-%m-%d') for d in all_week_dates])
    weekOperValuesTM = json.dumps([oper_by_date_week[d].get('TM', 0) for d in all_week_dates])
    weekOperValuesCM = json.dumps([oper_by_date_week[d].get('CM', 0) for d in all_week_dates])
    weekOperValuesCMHK = json.dumps([oper_by_date_week[d].get('CMHK', 0) for d in all_week_dates])
    weekOperValuesTC = json.dumps([oper_by_date_week[d].get('TC', 0) for d in all_week_dates])
    weekOperValuesVR = json.dumps([oper_by_date_week[d].get('VR', 0) for d in all_week_dates])

    unique_month_oper = {order['item_id']: order for order in month_orders}.values()
    oper_by_date_month = defaultdict(lambda: defaultdict(int))
    for order in unique_month_oper:
        if order['operator']:
            oper_by_date_month[order['order_date']][order['operator']] += 1
    monthOperDates = json.dumps([d.strftime('%Y-%m-%d') for d in all_month_dates])
    monthOperValuesTM = json.dumps([oper_by_date_month[d].get('TM', 0) for d in all_month_dates])
    monthOperValuesCM = json.dumps([oper_by_date_month[d].get('CM', 0) for d in all_month_dates])
    monthOperValuesCMHK = json.dumps([oper_by_date_month[d].get('CMHK', 0) for d in all_month_dates])
    monthOperValuesTC = json.dumps([oper_by_date_month[d].get('TC', 0) for d in all_month_dates])
    monthOperValuesVR = json.dumps([oper_by_date_month[d].get('VR', 0) for d in all_month_dates])

    unique_year_oper = {order['item_id']: order for order in year_orders}.values()
    oper_by_month_year = defaultdict(lambda: defaultdict(int))
    for order in unique_year_oper:
        if order['operator']:
            oper_by_month_year[order['month']][order['operator']] += 1
    yearOperDates = json.dumps([m.strftime('%Y-%m') for m in all_year_months])
    yearOperValuesTM = json.dumps([oper_by_month_year[m].get('TM', 0) for m in all_year_months])
    yearOperValuesCM = json.dumps([oper_by_month_year[m].get('CM', 0) for m in all_year_months])
    yearOperValuesCMHK = json.dumps([oper_by_month_year[m].get('CMHK', 0) for m in all_year_months])
    yearOperValuesTC = json.dumps([oper_by_month_year[m].get('TC', 0) for m in all_year_months])
    yearOperValuesVR = json.dumps([oper_by_month_year[m].get('VR', 0) for m in all_year_months])

    sim_tm = simsAll.filter(sim_status='DS', operator='TM', type_sim='sim').count()
    esim_tm = simsAll.filter(sim_status='DS', operator='TM', type_sim='esim').count()
    sim_cm = simsAll.filter(sim_status='DS', operator='CM', type_sim='sim').count()
    esim_cm = simsAll.filter(sim_status='DS', operator='CM', type_sim='esim').count()
    sim_cmhk = simsAll.filter(sim_status='DS', operator='CMHK', type_sim='sim').count()
    esim_cmhk = simsAll.filter(sim_status='DS', operator='CMHK', type_sim='esim').count()
    sim_tc = simsAll.filter(sim_status='DS', operator='TC', type_sim='sim').count()
    esim_tc = simsAll.filter(sim_status='DS', operator='TC', type_sim='esim').count()
    sim_vr = simsAll.filter(sim_status='DS', operator='VR', type_sim='sim').count()
    esim_vr = simsAll.filter(sim_status='DS', operator='VR', type_sim='esim').count()

    context = {
        'texto': 'Bem-vindo a área administrativa do sistema de gestão de vendas de SIM Cards.',
        'sims': simsAll,
        'sim_tm': sim_tm,
        'esim_tm': esim_tm,
        'sim_cm': sim_cm,
        'esim_cm': esim_cm,
        'sim_cmhk': sim_cmhk,
        'esim_cmhk': esim_cmhk,
        'sim_tc': sim_tc,
        'esim_tc': esim_tc,
        'sim_vr': sim_vr,
        'esim_vr': esim_vr,
        'dateDay': dateDay,
        'dateYesterday': dateYesterday,
        'dateWeek': dateWeek,
        'dateMonth': dateMonth,
        'dateYear': dateYear,
        'orders_pending': orders_pending,
        'countActivTM': countActivTM,
        'countActivCM': countActivCM,
        'countActivCMHK': countActivCMHK,
        'countActivTC': countActivTC,
        'countActivVR': countActivVR,
        'weekSalesDates': weekSalesDates,
        'weekSalesValues': weekSalesValues,
        'weekSimsDates': weekSimsDates,
        'weekSimsValuesS': weekSimsValuesS,
        'weekSimsValuesE': weekSimsValuesE,
        'weekOperDates': weekOperDates,
        'weekOperValuesTM': weekOperValuesTM,
        'weekOperValuesCM': weekOperValuesCM,
        'weekOperValuesCMHK': weekOperValuesCMHK,
        'weekOperValuesTC': weekOperValuesTC,
        'weekOperValuesVR': weekOperValuesVR,
        'monthSalesDates': monthSalesDates,
        'monthSalesValues': monthSalesValues,
        'monthSimsDates': monthSimsDates,
        'monthSimsValuesS': monthSimsValuesS,
        'monthSimsValuesE': monthSimsValuesE,
        'monthOperDates': monthOperDates,
        'monthOperValuesTM': monthOperValuesTM,
        'monthOperValuesCM': monthOperValuesCM,
        'monthOperValuesCMHK': monthOperValuesCMHK,
        'monthOperValuesTC': monthOperValuesTC,
        'monthOperValuesVR': monthOperValuesVR,
        'yearSalesDates': yearSalesDates,
        'yearSalesValues': yearSalesValues,
        'yearSimsDates': yearSimsDates,
        'yearSimsValuesS': yearSimsValuesS,
        'yearSimsValuesE': yearSimsValuesE,
        'yearOperDates': yearOperDates,
        'yearOperValuesTM': yearOperValuesTM,
        'yearOperValuesCM': yearOperValuesCM,
        'yearOperValuesCMHK': yearOperValuesCMHK,
        'yearOperValuesTC': yearOperValuesTC,
        'yearOperValuesVR': yearOperValuesVR,
    }

    return render(request, 'painel/dashboard/dashboard.html', context)


@login_required(login_url='/login/')
def clear_cache(request):
    from django.core.cache import cache
    cache.clear()
    return HttpResponse("Cache cleared")
