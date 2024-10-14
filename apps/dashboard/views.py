from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.sims.models import Sims
from apps.orders.models import Orders
import json
from datetime import datetime, timedelta
import pandas as pd


# Create your views here.
@login_required(login_url='/login/')
def index(request):
    # Dates
    today = datetime.now()
    dateDay = today.date()
    
    # dateTomorrow = dateDay - timedelta(days=-1)
    # dateYesterday = dateDay - timedelta(days=1)
    # dateWeek = dateDay - timedelta(days=7)
    # dateMonth = dateDay - timedelta(days=30)
    # dateYear = dateDay - timedelta(days=365)   
    
    # # ACTIVATIONS
    # activationOrders = Orders.objects.filter(activation_date=dateTomorrow)
    # if activationOrders:
    #     activationTomorrow = activationOrders.count()    
    #     activList = pd.DataFrame(activationOrders.values('id_sim__operator')).rename(columns={'id_sim__operator': 'operator'})
    #     activList = activList.groupby(['operator']).size().reset_index(name='countActiv')
    # else:
    #     activationTomorrow = 0
    #     activList = pd.DataFrame({'operator': ['TM', 'CM', 'TC'], 'countActiv': [0, 0, 0]})
          
    # try: countActivTM = activList[activList['operator'] == 'TM']['countActiv'].values[0]
    # except: countActivTM = 0
    # try: countActivCM = activList[activList['operator'] == 'CM']['countActiv'].values[0]
    # except: countActivCM = 0
    # try: countActivTC = activList[activList['operator'] == 'TC']['countActiv'].values[0]
    # except: countActivTC = 0
    
    # # Queries
    # simsAll = Sims.objects.all()
    # # Use range queries for each date range
    # ordersWeek = Orders.objects.filter(order_date__range=(dateMonth, dateDay))
    # ordersMonth = Orders.objects.filter(order_date__range=(dateMonth, dateDay))
    # ordersYear = Orders.objects.filter(order_date__range=(dateYear, dateDay))     
    
    # # Convertendo a lista de dicionários em um DataFrame    
    # fields_df = ['order_id','order_date', 'id_sim__type_sim', 'id_sim__operator']
    # rename_df = {'id_sim__type_sim': 'type_sim', 'id_sim__operator': 'operator'}
    
    # # weekDf = pd.DataFrame(list(ordersWeek.values(*fields_df)))
    # weekDf = pd.DataFrame(list(ordersYear.values(*fields_df)))
    # weekDf = weekDf.rename(columns=rename_df)
    # weekDf['order_date'] = pd.to_datetime(weekDf['order_date'].dt.date)
    # # monthDf = pd.DataFrame(list(ordersMonth.values(*fields_df)))
    # monthDf = pd.DataFrame(list(ordersYear.values(*fields_df)))
    # monthDf = monthDf.rename(columns=rename_df)
    # monthDf['order_date'] = pd.to_datetime(monthDf['order_date'].dt.date)
    # yearDf = pd.DataFrame(list(ordersYear.values(*fields_df)))
    # yearDf = yearDf.rename(columns=rename_df)
    # yearDf['month'] = pd.to_datetime(yearDf['order_date'].dt.strftime('%Y-%m'))
    # yearDf['order_date'] = pd.to_datetime(yearDf['order_date'].dt.date)
    
    # # SALES
    # # --- Week
    # weekSalesDup = weekDf.drop_duplicates(subset='order_id')
    # weekSalesReport = weekSalesDup.groupby('order_date').size().reset_index(name='countSalesWeek')
    # weekSalesDates = weekSalesReport['order_date'].tolist()
    # weekSalesDays = [(dateSalesWeek).strftime('%Y-%m-%d') for dateSalesWeek in weekSalesDates]
    # weekSalesDays = json.dumps(weekSalesDays)
    # weekSalesValues = json.dumps(weekSalesReport['countSalesWeek'].tolist()) 
    # # --- Month
    # monthSalesDup = monthDf.drop_duplicates(subset='order_id')
    # monthSalesReport = monthSalesDup.groupby('order_date').size().reset_index(name='countSalesMonth')
    # monthSalesDays = monthSalesReport['order_date'].tolist()
    # monthSalesDays = [(dateSalesMonth).strftime('%Y-%m-%d') for dateSalesMonth in monthSalesDays]
    # monthSalesDays = json.dumps(monthSalesDays)
    # monthSalesValues = json.dumps(monthSalesReport['countSalesMonth'].tolist())
    # # --- Year
    # yearSalesDup = yearDf.drop_duplicates(subset='order_id')
    # yearSalesReport = yearSalesDup.groupby('month').size().reset_index(name='countSalesYear')   
    # yearSalesDates = yearSalesReport['month'].tolist()
    # yearSalesDates = [(dateSalesYear).strftime('%Y-%m') for dateSalesYear in yearSalesDates]
    # yearSalesDates = json.dumps(yearSalesDates)    
    # yearSalesValues = json.dumps(yearSalesReport['countSalesYear'].tolist())
    
    # # SIMs
    # # --- Week  
    # weekSimsReport = weekDf.groupby(['order_date','type_sim']).size().reset_index(name='countSimsWeek') 
    # weekSimsS = weekSimsReport[(weekSimsReport['type_sim'] == 'esim')]
    # weekSimsE = weekSimsReport[(weekSimsReport['type_sim'] == 'sim')]
    # weekSalesD = weekSalesReport['order_date'].tolist()
    # weekSimsDays = [(dateSimssWeek).strftime('%Y-%m-%d') for dateSimssWeek in weekSalesD]
    # weekSimsDays = json.dumps(weekSimsDays)
    # weekSimsValuesS = json.dumps(weekSimsS['countSimsWeek'].tolist())
    # weekSimsValuesE = json.dumps(weekSimsE['countSimsWeek'].tolist())   
    # # --- Month
    # monthSimsReport = monthDf.groupby(['order_date','type_sim']).size().reset_index(name='countSimsMonth')
    # monthSimsS = monthSimsReport[(monthSimsReport['type_sim'] == 'esim')]
    # monthSimsE = monthSimsReport[(monthSimsReport['type_sim'] == 'sim')]
    # monthSimsDays = monthSimsS['order_date'].tolist()
    # monthSimsDays = [(dateSimsMonth).strftime('%Y-%m-%d') for dateSimsMonth in monthSimsDays]
    # monthSimsDays = json.dumps(monthSimsDays)
    # monthSimsValuesS = json.dumps(monthSimsS['countSimsMonth'].tolist())
    # monthSimsValuesE = json.dumps(monthSimsE['countSimsMonth'].tolist())
    # # --- Year
    # try:
    #     yearSimsReport = yearDf.groupby(['month','type_sim']).size().reset_index(name='countSimsYear')
    #     yearSimsReport = yearSimsReport.pivot_table(index='month', columns='type_sim', values='countSimsYear', fill_value=0)
    #     yearSimsValuesS = json.dumps(yearSimsReport['esim'].tolist())
    #     yearSimsValuesE = json.dumps(yearSimsReport['sim'].tolist())
    #     yearSimsDates = json.dumps([month.strftime('%Y-%m') for month in yearSimsReport.index])
    # except Exception as e:
    #     yearSimsValuesS = json.dumps([0,0,0,0,0,0,0,0,0,0,0,0])
    #     yearSimsValuesE = json.dumps([0,0,0,0,0,0,0,0,0,0,0,0])
    #     yearSimsDates = json.dumps(['2021-01','2021-02','2021-03','2021-04','2021-05','2021-06','2021-07','2021-08','2021-09','2021-10','2021-11','2021-12'])
    
    
    # # OPERATOR
    # # --- Week
    # weekOperReport = weekDf.groupby(['order_date','operator']).size().reset_index(name='countOperWeek')
    # weekOperTM = weekOperReport[(weekOperReport['operator'] == 'TM')]
    # weekOperCM = weekOperReport[(weekOperReport['operator'] == 'CM')]
    # weekOperTC = weekOperReport[(weekOperReport['operator'] == 'TC')]
    # weekOperD = weekOperTM['order_date'].tolist()
    # weekOperDates = [(dateOperWeek).strftime('%Y-%m-%d') for dateOperWeek in weekOperD]
    # weekOperDates = json.dumps(weekOperDates)
    # weekOperValuesTM = json.dumps(weekOperTM['countOperWeek'].tolist())
    # weekOperValuesCM = json.dumps(weekOperCM['countOperWeek'].tolist())
    # weekOperValuesTC = json.dumps(weekOperTC['countOperWeek'].tolist())
    # # --- Month
    # monthOperReport = monthDf.groupby(['order_date','operator']).size().reset_index(name='countOperMonth')
    # monthOperTM = monthOperReport[(monthOperReport['operator'] == 'TM')]
    # monthOperCM = monthOperReport[(monthOperReport['operator'] == 'CM')]
    # monthOperTC = monthOperReport[(monthOperReport['operator'] == 'TC')]
    # monthOperDates = monthOperTM['order_date'].tolist()
    # monthOperDates = [(dateOperMonth).strftime('%Y-%m-%d') for dateOperMonth in monthOperDates]
    # monthOperDates = json.dumps(monthOperDates)
    # monthOperValuesTM = json.dumps(monthOperTM['countOperMonth'].tolist())
    # monthOperValuesCM = json.dumps(monthOperCM['countOperMonth'].tolist())
    # monthOperValuesTC = json.dumps(monthOperTC['countOperMonth'].tolist())    
    # # --- Year
    # try:
    #     yearOperReport = yearDf.groupby(['month','operator']).size().reset_index(name='countSimsYear')
    #     yearOperReport = yearOperReport.pivot_table(index='month', columns='operator', values='countSimsYear', fill_value=0)
    #     yearOperValuesTM = json.dumps(yearOperReport['TM'].tolist())
    #     yearOperValuesCM = json.dumps(yearOperReport['CM'].tolist())
    #     yearOperValuesTC = json.dumps(yearOperReport['TC'].tolist())
    #     yearOperDates = json.dumps([month.strftime('%Y-%m') for month in yearOperReport.index])
    # except Exception as e:
    #     yearOperValuesTM = json.dumps([0,0,0,0,0,0,0,0,0,0,0,0])
    #     yearOperValuesCM = json.dumps([0,0,0,0,0,0,0,0,0,0,0,0])
    #     yearOperValuesTC = json.dumps([0,0,0,0,0,0,0,0,0,0,0,0])
    #     yearOperDates = json.dumps(['2021-01','2021-02','2021-03','2021-04','2021-05','2021-06','2021-07','2021-08','2021-09','2021-10','2021-11','2021-12'])        

    # # Verificar estoque de operadoras
    # sim_tm = simsAll.filter(sim_status='DS',operator='TM', type_sim='sim').count()
    # esim_tm = simsAll.filter(sim_status='DS',operator='TM', type_sim='esim').count()
    # sim_cm = simsAll.filter(sim_status='DS',operator='CM', type_sim='sim').count()
    # esim_cm = simsAll.filter(sim_status='DS',operator='CM', type_sim='esim').count()
    # sim_tc = simsAll.filter(sim_status='DS',operator='TC', type_sim='sim').count()
    # esim_tc = simsAll.filter(sim_status='DS',operator='TC', type_sim='esim').count()

    # context= {
    #     'sims': simsAll,
    #     'sim_tm': sim_tm,
    #     'esim_tm': esim_tm,
    #     'sim_cm': sim_cm,
    #     'esim_cm': esim_cm,
    #     'sim_tc': sim_tc,
    #     'esim_tc': esim_tc,
    #     'dateDay': dateDay,
    #     'dateYesterday': dateYesterday,
    #     'dateWeek': dateWeek,
    #     'dateMonth': dateMonth,
    #     'dateYear': dateYear,
    #     'activationTomorrow': activationTomorrow,
    #     'countActivTM': countActivTM,
    #     'countActivCM': countActivCM,
    #     'countActivTC': countActivTC,
    #     'weekSalesDates': weekSalesDays,
    #     'weekSalesValues': weekSalesValues,
    #     'weekSimsDates': weekSimsDays,
    #     'weekSimsValuesS': weekSimsValuesS,
    #     'weekSimsValuesE': weekSimsValuesE,        
    #     'weekOperDates': weekOperDates,
    #     'weekOperValuesTM': weekOperValuesTM,
    #     'weekOperValuesCM': weekOperValuesCM,
    #     'weekOperValuesTC': weekOperValuesTC,        
    #     'monthSalesDates': monthSalesDays,
    #     'monthSalesValues': monthSalesValues,
    #     'monthSimsDays': monthSimsDays,
    #     'monthSimsValuesS': monthSimsValuesS,
    #     'monthSimsValuesE': monthSimsValuesE,
    #     'monthOperDates': monthOperDates,
    #     'monthOperValuesTM': monthOperValuesTM,
    #     'monthOperValuesCM': monthOperValuesCM,
    #     'monthOperValuesTC': monthOperValuesTC,
    #     'yearSalesDates': yearSalesDates,
    #     'yearSalesValues': yearSalesValues,
    #     'yearSimsDates': yearSimsDates,
    #     'yearSimsValuesS': yearSimsValuesS,
    #     'yearSimsValuesE': yearSimsValuesE,
    #     'yearOperDates': yearOperDates,
    #     'yearOperValuesTM': yearOperValuesTM,
    #     'yearOperValuesCM': yearOperValuesCM,
    #     'yearOperValuesTC': yearOperValuesTC,        
    # }
    context= {
        'texto': 'Bem-vindo a área administariva do sistema de gestão de vendas de SIM Cards.'
    }
    
    
    return render(request, 'painel/dashboard/index.html', context)


@login_required(login_url='/login/')
def clear_cache(request):
    from django.core.cache import cache
    cache.clear()
    return HttpResponse("Cache cleared")