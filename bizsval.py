import biznesradar_scraper as br
import googlefinance_scraper as gf
import os
import json
from statistics import mean, stdev, variance, median
from glob import glob
from datetime import date
import csv

BLACKLIST = "data/blacklist.json"

def acint(string):
    '''Converts scraped financial report numerical strings to integers
    eg. "50 0000" to an integer = 50000 '''
    return int(string.replace(" ",""))

def sort_dict(dictionary):
    sorted_dict = dict(sorted(dictionary.items(), key = lambda item: item[1], reverse = True))
    return sorted_dict
       
class BrHandler:
    '''Converts data scraped from biznesradar.pl to standard attributes of Company objects'''
    def __init__(self, dir_):
        self.dir = dir_  
        
    def refine_financials(self, raw_financials):
        financials = {}
        financials['equity'] = raw_financials[br.EQUITY]
        financials['dividend'] = raw_financials[br.DIVIDEND]
        financials['net_income'] = raw_financials[br.NET_INCOME]
        financials['revenue'] = raw_financials[br.REVENUE]
        financials['assets'] = raw_financials["Aktywa razem"]
        financials['liabilities'] = [a - e for a, e in zip(financials['assets'], financials['equity'] )]
            
        return financials
    
    def get_financials(self, name, from_file):
        if from_file:
            S = (br.INCOME, br.BALANCE, br.CASH)
            temp_financials = {}
            for i in range (3):
                with open(f"{self.dir}/{name}-{S[i]}.json") as file:
                    data = json.load(file)
                    temp_financials.update(data)      
        return self.refine_financials(temp_financials)
    
    def get_market_cap(self, name, from_file):
        if not from_file:
            return acint(br.get_info(name)["Kapitalizacja:"])/1000
        
class GfHandler:
    '''Converts data scraped from Google Finance to standard attributes of Company objects'''
    def __init__(self, dir_):
        self.dir_ = dir_
        self.market_caps = {}
    
    def adjust_market_cap(self, pe, market_cap, income):
        """ adjusts market cap to currency of reports if pe is listed on googlefin"""
        synthetic_pe = market_cap / income[4]
        adjusted_cap = market_cap
        comp = synthetic_pe / pe
        if comp > 1.3 or comp < 0.7:
            adjusted_cap /= comp
        return adjusted_cap
                  
    def get_financials(self, name, from_file):
        fins = None
        if from_file:
            with open(f"{self.dir_}/{name}.json") as file:
                fins = json.load(file)
        else:
            fins = gf.get_financials(name, dir_ = self.dir_)
        if not fins['pe'] == "NaN":
            self.market_caps[name] = self.adjust_market_cap(fins['pe'], fins['market_cap'], fins["net_income"])
        return fins
    
    def get_market_cap(self, name, from_file):
        cap = None
        if not from_file:
            try:
                cap = self.market_caps[name]
            except:
                #cap = gf.get_financials(name, dir_ = self.dir_)['market_cap']
                return 0
            return cap

class EquityError(Exception):
    def __init__(self, message):
       super().__init__(message)
       
    def __str__(self):
        return f"{self.__class__.__name__}"

class MarketCapError(Exception):
    def __init__(self, message):
       super().__init__(message)
       
    def __str__(self):
        return f"{self.__class__.__name__}"

class Company:
    '''Main class for representing companies to be evaluated, parameter "name" has to match the file
    in which data is stored, by default exchange ticker. Handler depends on the source of data. GfHandler 
    for companies sourced from Google Finance, BrHandler for biznesradar.pl'''
    def __init__(self, name, handler):
        self.name = name
        self.handler = handler
        self.financials = {
            "equity": [],
            "net_income": [],
            "dividend": [],
            "revenue": [],
            "assets": [],
            "liabilities": []
        }
        self.market_cap = 0
        self.known_years = 0
        self.roe = 0
        self.roe_deviation = 0
        self.margin = 0
        self.debt_to_equity = 0
        self.debt_to_assests = 0

    def chk_pos(self, element_of_financials, years_back=None, i1=None, i2=None): 
        '''Checks if all elements of a financial statement's section are positive'''
        if years_back:
            i2 = len(self.financials[element_of_financials])
            i1 = i2 - years_back
        if i1 is None or i2 is None:
            raise ValueError("i1 and i2 must be defined")
        return all(val > 0 for val in self.financials[element_of_financials][i1:i2])

    def mean_roe(self, years_back=None, i1=None, i2=None): 
        '''Calculates mean return on equity in given years'''
        roes = []
        if years_back:
            i2 = len(self.financials['net_income'])
            i1 = i2 - years_back
        if i1 is None or i2 is None:
            raise ValueError("i1 and i2 must be defined")
        for i in range(i1, i2):
            equity = self.financials["equity"]
            net_income = self.financials['net_income']
            if equity[i] <= 0:
                raise ValueError("negative equity")
            else:
                if net_income[i] == 0:
                    roes.append(0)
                else:
                    roes.append(net_income[i] / equity[i])
        self.roe = mean(roes)
        self.roe_deviation = stdev(roes) / self.roe
        return self.roe

    def mean_pr(self, years_back=None, i1=None, i2=None): 
        '''Calculates mean payout ratio in given years'''
        prs = []
        if years_back:
            i2 = len(self.financials['net_income'])
            i1 = i2 - years_back
        if i1 is None or i2 is None:
            raise ValueError("i1 and i2 must be defined")
        for i in range(i1, i2):
            inc = self.financials["net_income"][i - 1]
            div = self.financials["dividend"][i]
            if inc > 0:
                prs.append(div / inc)
        if len(prs) > 1:
            return mean(prs)
        else:
            return 0

    def estimate_growth(self, years_back=None, i1=None, i2=None):
        '''Default method to estimate earnings growth, assuming additions to capital
        based on mean dividend payout ratio and returns equal to mean ROE'''
        if years_back:
            i2 = len(self.financials['net_income'])
            i1 = i2 - years_back
        if i1 is None or i2 is None:
            raise ValueError("i1 and i2 must be defined")
        roe = self.mean_roe(i1=i1, i2=i2)
        pr = self.mean_pr(i1=i1, i2=i2)
        if pr < 0 or roe < 0 or pr > 1:
            print(f"{self.name} assuming no growth \n payout ratio : {pr}, roe : {roe}")
            return 0
        else:
            print(f"{self.name} estimated growth rate {roe * (1 - pr)}")
            return roe * (1 - pr)

    def calc_margin(self, years_back=None, i1=None, i2=None):
        '''Calculates mean net margin of a Company'''
        margins = []
        if years_back:
            i2 = len(self.financials['net_income'])
            i1 = i2 - years_back
        if i1 is None or i2 is None:
            raise ValueError("i1 and i2 must be defined")
        for i in range(i1, i2):
            margins.append(self.financials["net_income"][i] / self.financials['revenue'][i])
        self.margin = mean(margins)
        return mean(margins)
    
    def calc_debt_to_equity_current(self):
        self.debt_to_equity = self.financials['liabilities'][-1] / self.financials['equity'][-1]
        return self.debt_to_equity
        
    def calc_debt_to_assets_current(self):
        self.debt_to_assests = self.financials['liabilities'][-1] / self.financials['assets'][-1]
        return self.debt_to_assests
    
    def estimate_income_classic(self, projection_length, growth_cap, years_back=0, i1_=None, i2_=None):
        '''Default method of projecting future incomes, utilizing the estimate_growth function'''
        if years_back:
            i2_ = len(self.financials['net_income'])
            i1_ = i2_ - years_back
        if i1_ is None or i2_ is None:
            raise ValueError("i1_ and i2_ must be defined")
        gr = self.estimate_growth(i1=i1_, i2=i2_)
        if gr > growth_cap:
            gr = growth_cap
        income = mean(self.financials['net_income'][i1_:i2_])
        print(f"mean income {income}")
        print(f"growth rate {gr}")
        incomes = []
        for i in range(projection_length):
            income *= 1 + gr 
            incomes.append(income / (1 + ((i + 1) * 0.03)))
        print(f"projecetd incomes {incomes}")
        return incomes

    def estimate_income_nc(self, base_i0, base_i1, projection_length):
        '''Method for projecting future incomes for a "no growth" scenario, assumes repeated mean 
        income from years base_i0 to base_i1 for a number of years given as projection_length'''
        av_inc = mean(self.financials['net_income'][base_i0:base_i1])
        return [av_inc for i in range(projection_length)]

    def calc_iv(self, discount_rate, projected_income, terminal_growth):
        '''Default intrinsic value calculation, projected_income = list of predicted future incomes
        to be discounted, assumes growth into perpetuity at a rate marked by the parameter terminal_growth'''
        discounted_incomes = []    
        len_ = len(projected_income)
        range_ = range(1, len_ + 1)
        for i in range_:
            discounted_incomes.append(projected_income[i - 1] / ((1 + discount_rate) ** i))
        terminal_value = projected_income[len_ - 1] / (discount_rate - terminal_growth)
        iv = sum(discounted_incomes) + terminal_value 
        return iv 

    def calc_iv2(self): 
        print(f"calculating iv for {self.name}")
        l = len(self.financials["net_income"])
        if self.roe == 0:
            self.mean_roe(years_back=l)
        roe = self.roe 
        if roe > 0.25: 
            roe = 0.25
        pr = self.mean_pr(years_back=l)
        equity = self.financials["equity"][l - 1]
        if pr < 0 or equity < 0 or roe < 0:
            return 0, 0
        else:
            gr = roe * (1 - pr)
            print(f"assumed growth rate {gr}")
            inc = 0
            for i in range(1, 11):
                temp = equity * roe
                equity += (temp * (1 - pr)) / 1.1 ** i
                temp /= 1.08 ** i
                inc += temp
            inc += temp / 0.1
            return inc, gr

    def calc_uvf(self, discount_rate, yearsBack): 
        '''Calculates the undervaluation factor - intrinsic value / market price'''
        if not self.financials['equity']:
            raise EquityError("Missing equity data")
        if self.market_cap == 0:
            raise MarketCapError('Missing equity data')
        iv = self.calc_iv(discount_rate, self.estimate_income_classic(5, 0.1, years_back=yearsBack), 0.02)
        return iv / self.market_cap

    def set_market_cap(self, from_file=0):
        self.market_cap = self.handler.get_market_cap(self.name, from_file)

    def set_financials(self, from_file=1):
        self.financials = self.handler.get_financials(self.name, from_file)

def load_gf_tickers():
    ticks = gf.default_tickers()
    tickers = []
    for t in ticks:
        tickers.append(t.replace(":","-"))
    return tickers
        
def load_blacklist(dir_):
    with open(dir_, 'r') as blacklist:
        return json.load(blacklist)

def add_to_blacklist(company, dir_):
    _list = load_blacklist(dir_)
    with open(dir_, 'w') as blacklist:
        if company not in _list: 
            _list.append(company)
        json.dump(_list, blacklist)

def prep_companies(handler, tickers, blacklist_dir, use_black_list=True):
    '''Initializes Company objects from saved data'''
    blacklist = []
    if use_black_list:
        blacklist = load_blacklist(blacklist_dir)

    companies = []
    for t in tickers:
        try:
            if t not in blacklist:
                temp = Company(t, handler)
                temp.set_financials()
                companies.append(temp)
            else:
                print(f"Blacklisted ticker: {t} - initialization skipped")
        except Exception as e:
            print(f"An error occurred while initializing company: {t} : {e}")
            print("***************************")

    return companies

def eval_stocks(companies, save_dir, tag, margin_filter, roe_filter, roe_deviation_filter, filter_backyears, use_black_list, blacklist_dir):
    '''Runs the evaluation process for a list of company objects with filter parameters excluding
    those not matching the given thresholds from valuation'''
    
    results = []  # List to store company data
    for c in companies:
        try:
            exclusion = False
            while exclusion == False:
                if not c.chk_pos("net_income", years_back=5):
                    exclusion = True
                    print(f"{c.name} excluded from valuation, reason: negative earnings present")
                    break
                if margin_filter:
                    if c.calc_margin(years_back=filter_backyears) < margin_filter:
                        print(f"{c.name} excluded from valuation, reason: margin filter not passed")
                        exclusion = True
                        break
                if roe_filter:
                    if c.mean_roe(years_back=filter_backyears) < roe_filter:
                        exclusion = True
                        print(f"{c.name} excluded from valuation, reason: ROE filter not passed")
                if roe_deviation_filter:
                    if c.roe_deviation > roe_deviation_filter:
                        exclusion = True
                        print(f"{c.name} excluded from valuation, reason: ROE deviation filter not passed")
                        break
                
                break

            if not exclusion:
                c.set_market_cap()
                uvf = c.calc_uvf(discount_rate=0.065, yearsBack=5)  # Undervaluation factor
                roe = c.roe
                margin = c.margin
                deviation = c.roe_deviation
                debt_to_assets = c.calc_debt_to_assets_current()
                results.append({
                    "Name": c.name,
                    "Undervaluation Factor": uvf,
                    "ROE": roe,
                    "Margin": margin,
                    "ROE Deviation": deviation,
                    "Debt to Assets": debt_to_assets
                })
            br.time.sleep(1)
            print("***************************")
        except Exception as e:
            print(f"An error occurred while evaluating {c.name}: {e}")

    csv_filename = f"{save_dir}/{tag} {str(date.today())}.csv"
    with open(csv_filename, mode="w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["Name", "Undervaluation Factor", "ROE", "Margin", "ROE Deviation", "Debt to Assets"])
        writer.writeheader()
        writer.writerows(results)

    print(f"Results saved to {csv_filename}")

    
def eval_br():
    companies = prep_companies(BrHandler("data/gpw"), br.default_tickers(), BLACKLIST)
    eval_stocks(companies,"analyses", "gpw", 0.05, 0.08, 0.5, 5, 1, BLACKLIST)

def eval_gf():
    companies = prep_companies(GfHandler("data/gf"), load_gf_tickers(), GPW_BLACKLIST)
    eval_stocks(companies, "analyses", "gf", 0.05, 0.08, 0.8, 5, 1, GPW_BLACKLIST)


BRH = BrHandler("data/gpw")
GFH = GfHandler("data/gf")


