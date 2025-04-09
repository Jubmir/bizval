from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import json

def remove_suffix(string):
    M = {"bln":10**9,
        "mld": 10**6,
         "mln": 10**3,
         "tys": 1}

    l = len(string)
    m = string[l-3:l]
    refined = float(string[:l-3].replace(",", "."))
    return refined * M[m]

def virtual_dividend(net_incomes, equity):
    e = equity
    i = net_incomes
    e.reverse()
    i.reverse()
    l = len(e)
    x = 0
    dividends = [0]
    while x < l-1:
        dividends.append(i[x+1] - (e[x] - e[x+1]))
        x += 1
    return dividends

def get_market_cap(company):
    URL = "https://www.google.com/finance/quote/"
    driver = webdriver.Edge()
    driver.get(f"{URL}{company}")
    list_ = driver.find_elements(By.CLASS_NAME, "VfPpkd-vQzf8d")

    for element in list_:  # FINDING REJECT BTN
        if element.text == "Odrzuć wszystko":
            element.click()
            break
        
    cap = driver.find_elements(By.CLASS_NAME, 'P6K39c')[3].text
    cap = remove_suffix((cap[:len(cap)-4]))
     
    return cap

def get_financials(company, save = True, dir_ = "data/gf"):       
    URL = "https://www.google.com/finance/quote/"
    driver = webdriver.Edge()
    driver.get(f"{URL}{company}")
    list_ = driver.find_elements(By.XPATH, '//*[@jsname="tWT92d"]')
    list_[0].click()

    annual_btn = driver.find_element(
        By.XPATH, '//*[@id="annual2"]/span[2]')
    annual_btn.click()
    time.sleep(1)
    x = driver.find_elements(By.CLASS_NAME, 'gjKCb')
    x[1].click()
    vals = {"revenue": [],
            "net_income": [],
            "equity": [],
            "assets":[],
            "liabilities":[],
            "market_cap": 0}
    time.sleep(1)
    for i in range(5):
        year = driver.find_elements(
            By.XPATH, f'//*[@id="option-{i}"]/span')
        for x in year[:2]:
            x.click()
        list_ = driver.find_elements(By.CLASS_NAME, "QXDnM")
        temp = []
        for element in list_:
            try:
                temp.append(element.text)
            except:
                pass
        print(temp)
        vals["revenue"].append(remove_suffix((temp[0])))
        vals["net_income"].append(remove_suffix((temp[2])))
        vals["equity"].append(remove_suffix((temp[10])))
        vals["assets"].append(remove_suffix((temp[8])))
        vals["liabilities"].append(remove_suffix((temp[9])))
    
    list0 = driver.find_elements(By.CLASS_NAME, 'P6K39c')
    c = list0[3].text
    c = remove_suffix((c[:len(c)-4]))
  
    pe = list0[5].text
    try:
        vals["pe"] = float(pe.replace(",","."))
    except:
            vals["pe"] = "NaN"
    vals["market_cap"] = c
    vals["dividend"] = virtual_dividend(vals['net_income'], vals['equity'])

    
    if save:
        c = company.replace(':','-')
        with open(f"{dir_}/{c}.json", 'w') as file:
            json.dump(vals, file)
    
    return vals


def default_tickers():
    ticks = []        
    
    with open("data/gf_tickers.json") as file:
        ticks = json.load(file)
       
    return ticks

def bulk_download(tickers):
    for t in tickers:
        try:
            get_financials(t, dir_ = "data/gf")
        except:
            pass
    
def test_financials(company, save = True, dir_ = "data/gf"):       
    URL = "https://www.google.com/finance/quote/"
    driver = webdriver.Edge()
    driver.get(f"{URL}{company}")

    list_ = driver.find_elements(By.XPATH, '//*[@jsname="tWT92d"]')
    list_[0].click()
    
    return list_
        
     
                
    
