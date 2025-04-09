This is my private tool for pulling and analyzing stock data. Created because common stock screening tools failed to satisfy me. I am aware of its shortcomings, but it is enough for me. It is public because of... reasons.
Works best for the Warsaw Stock Exchange, because of plentiful free data provided by biznesradar. If you're an investor non-native to Poland and somehow ended up here, this might help you to hunt for single-digit P/E, double-digit ROE bargains. Just don't tell anybody.

Modules:

bizval - main module of the project, contains functionality for preliminary valuation of stocks based on data from multiple years to save one from browsing companies filtered by last year or TTM results, as commonly seen on stock screening websites

biznesradar_scraper - pulls financial data from biznesradar.pl

googlefinance_scraper - pulls financial data from Google Finance, the unwanted child of this project, came to be as i expanded into foreign markets

