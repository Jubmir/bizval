import requests
from bs4 import BeautifulSoup
import json
import time

CASH = "przeplywy-pieniezne"
INCOME = "rachunek-zyskow-i-strat"
BALANCE = "bilans"
EQUITY = "Kapitał własny akcjonariuszy jednostki dominującej"
NET_INCOME = "Zysk netto akcjonariuszy jednostki dominującej"
REVENUE = "Przychody ze sprzedaży"
SALES_INC = "Zysk ze sprzedaży"
DIVIDEND = "Dywidenda"

def cook_soup(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    return soup

def get_tickers():
    ''' returns a list of tickers of WSE listed companies'''
    soup = cook_soup("https://infostrefa.com/infostrefa/pl/spolki")
    tables = soup.find_all("table")
    rows = tables[1].find_all('tr')
    tickers = []
    for row in rows:
        s = row.find_all("td")[2].string
        if s:
            tickers.append(s)
    return tickers

def extract_info(soup):
    box = soup.find(class_="box-left")
    data = {}
    for i in box.find_all('tr'):
        temp = i.find("td").string
        if temp:
            data[i.find("th").string] = temp
        else:
            temp = i.find("td").find("a")
            if temp:
                data[i.find("th").string] = temp.string
    return data

def get_info(ticker):
    ''' gets you current market cap and misc info provided by biznesradar.pl'''
    URL = f"https://www.biznesradar.pl/raporty-finansowe-bilans/{ticker}"
    response = requests.get(URL)
    soup = BeautifulSoup(response.text, "html.parser")
    print(f"getting info for {ticker}")
    return extract_info(soup)
      
def get_statement(ticker, statement, with_info = 0):
    '''scrape financial statement from biznesradar.pl'''
    print(f"getting {statement} for {ticker}")
    soup = cook_soup(f"https://www.biznesradar.pl/raporty-finansowe-{statement}/{ticker}")
    inf = {}
    if with_info:
        inf = extract_info(soup)
    table = soup.find(class_="report-table")
    rows = table.find_all("tr")
    data = {}
    for row in rows:
        temp = []
        try:
            for i in row.find_all(class_="value"):
                temp.append(int(i.string.replace(" ", "")))
                data[row.find("td").string] = temp
        except:
            pass
    return data, inf

def default_tickers():
    tickers = json.load(open("data/gpw_tickers.json"))
    return tickers

def bulk_download(save_dir, ticker_list, statements_to_get = [INCOME, BALANCE, CASH], with_info = 0, request_delay = 1):
    s = statements_to_get
    for ticker in ticker_list:
        try:
            inf = None
            for statement in s:
                if not inf and with_info:
                    temp = get_statement(ticker, statement, with_info = 1)
                    statement_ =  temp[0]
                    inf = temp[1]
                else:
                    statement_ = get_statement(ticker, statement, with_info = 1)[0]
                with open(f"{save_dir}/{ticker}-{statement}.json", 'w') as f:
                    json.dump(statement_, f)
            
            if inf:
                with open(f"{save_dir}/{ticker}-info.json", 'w') as f:
                    json.dump(inf, f)
            
            time.sleep(request_delay)
        except:
            print(f"failed to save financial statements for {ticker}")

def get_all_statements(ticker):
    return (get_statement(ticker, INCOME),
            get_statement(ticker, BALANCE),
            get_statement(ticker, CASH))
