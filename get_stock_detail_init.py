# -*- coding: utf-8 -*-
"""
Created on Thu May 19 11:52:17 2022

@author: Rich
"""

# ========= django setting required ===============
from dataclasses import dataclass
from time import time
from xxlimited import Str
from django.core.management.base import BaseCommand
from backend import settings
from django.utils import timezone
import threading

# ============ main code ===========================
import pandas as pd
from stock_name.models import StockDetail, StockName
import json
import requests


def get_stock(v1, v2):
    stock_list = StockName.objects.values('stock')[v1:v2]
    stock_list = pd.DataFrame(stock_list)
    stock_list = stock_list.iloc[:, 0].values.tolist()

    def updn(row) -> str:
        if row["股價"] != "-" and row["昨收"] != "-":
            return round(float(row["股價"]) - float(row["昨收"]), 2)
        return "-"

    def updn100(row) -> str:
        if row["漲跌"] != "-":
            return round(row["漲跌"]/float(row["昨收"]) * 100, 2)
        return "-"

    result = pd.DataFrame()

    for n in range(int(len(stock_list)/100)+1):
        l = list(map(lambda x: f"tse_{x}.tw", stock_list[n*100:(n+1)*100]))
        s = "|".join(l)

        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={s}&json=1&delay=0&_=1552123547443"
        res = requests.get(url)

        columns = ["c", "n", "z", "u", "w", "o", "y", "h", "l", "v"]
        df = pd.DataFrame(json.loads(res.text)['msgArray'], columns=columns)
        df.columns = ["代號", "簡稱", "股價", "漲跌",
                      "漲跌幅", "開盤", "昨收", "最高", "最低", "成交量"]
        # 轉換為小數點第二位

        # 計算漲跌幅的欄位
        df[df.iloc[:, 2:-1] != '-'] = df[df.iloc[:, 2:] != '-'].astype('float')
        df["漲跌"] = df.apply(updn, axis=1)
        df["漲跌幅"] = df.apply(updn100, axis=1)
        # 合併資料
        result = pd.concat([result, df], ignore_index=True)
        # ================== Start to sql ==============================
    result = result.to_dict('records')
    for stockDetail in result:
        StockDetail.objects.update_or_create(stock=StockName.objects.filter(stock=stockDetail['代號']).first(),
                                             defaults={'stock': StockName.objects.filter(stock=stockDetail['代號']).first(),
                                                       'price': stockDetail['股價'],
                                                       'ud': stockDetail['漲跌'],
                                                       'udpercent': stockDetail['漲跌幅'],
                                                       'open': stockDetail['開盤'],
                                                       'yesterday': stockDetail['昨收'],
                                                       'high': stockDetail['最高'],
                                                       'low': stockDetail['最低'],
                                                       'volumn': stockDetail['成交量'],
                                                       'updated': timezone.now()})
    print("執行完畢...")


class Command(BaseCommand):

    def handle(self, *args, **options):
        stock_list = StockName.objects.values('stock')
        stock_list = pd.DataFrame(stock_list)
        stock_list = stock_list.iloc[0:round(
            len(stock_list)), 0].values.tolist()
        step = 99
        totalStep = int(len(stock_list)/step)+1
        for i in range(totalStep):
            globals()['task' + str(i)] = threading.Thread(target=get_stock,
                                                          args=(step*i, step*(i+1)))
            globals()['task' + str(i)].start()
