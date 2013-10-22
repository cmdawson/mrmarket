

from datecalc import *
from datetime import date, datetime, timedelta
from dateutil.relativedelta import *
"""TODO: Should functions accept string descriptions of the contract month 'M3' etc?
Issue with knowing whether 'M3' means Jun03 or Jun13, which should probably be determined
at a higher level. 

Add a first_notice function.

Include times in the fut_last_trade, opt_expiry
"""

__all__ = ['TBond', 'TNote', 'EuroDollar', 'EuroDollarMC', 'FedFunds', 'Metal', 'WTI', 'FX', 'Soft']

class TBond:
	"""Date calculations for the longer dated CME UST futures (10y and above).
	TODO: times in UTC"""
	def __init__(self, holidays):
		self.holidays = holidays

	def fut_last_trade(self, month, year):
		"""7th business day preceeding the last business day of delivery month. (12:01 NY?)"""
		next1st = date(year+month/12, 1+month%12, 1)
		return business_day(next1st, -8, self.holidays)
		
	def fut_first_notice(self, month, year):
		pass

	def fut_delivery(self, month, year):	
		"""Any time between the first and last days of the delivery month (London timezone)."""
		the1st = date(year, month, 1)
		return (business_day(the1st, 0, self.holidays), end_of_month(the1st, self.holidays))

	def opt_expiry(self, month, year):
		"""Last Friday preceding by at least two business days the last business day of the month
		preceding the option month (19:00 NY). Got that?"""
		eopm3 = business_day(date(year, month, 1), -3, self.holidays)
		return eopm3 + relativedelta(weekday=FR(-1)) 
		 
		

class TNote:
	"""Date calculations for the shorter CME UST futures (FV and TU) (London timezone). """
	def __init__(self, holidays, toffset=0):
		self.holidays = holidays

	def fut_last_trade(self, month, year):
		"""Last business day of the calendar month (12:01 NY?)."""
		next1st = date(year + month/12, 1+month%12, 1)
		return business_day(next1st, -1, self.holidays)

	def fut_delivery(self, month, year):	
		"""Third business day following the last trading day."""
		return business_day(self.fut_last_trade(month,year),3,self.holidays)

	def opt_expiry(self, month, year):
		"""Last Friday preceding by at least two business days the last business day of the month
		preceding the option month."""
		eopm3 = business_day(date(year, month, 1), -3, self.holidays)
		return eopm3 + relativedelta(weekday=FR(-1)) 



class EuroDollar:
	"""Date calculations for CME eurodollar futures and options. (London time)"""
	def __init__(self, holidays):
		self.holidays = holidays

	def fut_last_trade(self, month, year):
		"""The second London bank business day prior to the third Wednesday of the contract
		expiry month (11:00 LDN)."""
		return business_day(date(year,month,1)+relativedelta(weekday=WE(3)), -2, self.holidays)

	def fut_delivery(self, month, year):	
		"""N/A"""
		return (False, False)

	def opt_expiry(self, month, year):
		"""For qtrly options, the second London bank business day prior to the third Wednesday
		of the contract expiry month. For serial options, the Friday immediately preceding the
		third Wednesday of the contract month"""
		if (month%3 == 0):
			return self.fut_last_trade(month, year)		
		else:
			return (datetime(year,month,1) + relativedelta(weekday=WE(3))) + relativedelta(weekday=FR(-1))	
			
	def mc_expiry(self, month, year):
		"""Midcurve options follow the same rules as serial options"""
		return (datetime(year,month,1) + relativedelta(weekday=WE(3))) + relativedelta(weekday=FR(-1))	


class FedFunds:
	"""Date calculations for CME Fed Funds futures and options (London time). """
	def __init__(self, holidays):
		self.holidays = holidays

	def fut_last_trade(self, month, year):
		"""Last business day of the delivery month"""
		return end_of_month(date(year,month,1), self.holidays)

	def fut_delivery(self, month, year):	
		return (False, False)

	def opt_expiry(self, month, year):
		"""Last business day of the delivery month"""
		return self.fut_last_trade(month, year)



class Metal:
	"""Date calculations for varios CME metal futures and options (London time)."""
	def __init__(self, holidays):
		self.holidays = holidays

	def fut_last_trade(self, month, year):
		"""3rd Last business day of the delivery month"""
		return business_day(end_of_month(date(year,month,1), self.holidays), -2, self.holidays)

	def fut_delivery(self, month, year):	
		"""Any time between the first and last days of the delivery month."""
		the1st = date(year, month, 1)
		return (business_day(the1st, 0, self.holidays), end_of_month(the1st, self.holidays))

	def opt_expiry(self, month, year):
		"""4 business days prior to the end of the month preceding the option contract month.
		(I think this means '4th last business day of the month preceding the ... '). If the 
		expiration day falls on a Friday or immediately prior to an Exchange holiday, 
		expiration will occur on the previous business day."""
		eopm = business_day(date(year, month, 1), -4, self.holidays)
		nextday = eopm + timedelta(days=1)
		
		if (nextday.weekday() > 4) or (nextday in self.holidays):
			return business_day(eopm, -1, self.holidays)
		else:
			return eopm



class WTI:
	"""Date calculations for CME WTI Crude oil futures and options (London time)."""
	def __init__(self, holidays):
		self.holidays = holidays
		self.hh, self.mm = 22, 15

	def fut_last_trade(self, month, year):
		"""Trading in the current delivery month shall cease on the third business day prior
		to the 25th calendar day of the month preceding the delivery month. If the 25th
		calendar day of the month is a non-business day, trading shall cease on the third 
		business day prior to the last business day preceding the 25th calendar day."""
		the25th = datetime(year-1/month, 1+(month-2)%12, 25)
		if the25th in self.holidays or the25th.weekday() > 4:
			return business_day(the25th, -4, self.holidays)
		else:
			return business_day(the25th, -3, self.holidays)
	

	def fut_delivery(self, month, year):	
		"""Any time between the first and last calendar days of the delivery month."""
		return (date(year, month, 1), date(year, 1+month%12, 1) + timedelta(days=-1))

	def opt_expiry(self, month, year):
		"""Trading ends three business days before the termination of trading in the underlying
		futures contract."""
		the25th = datetime(year-1/month, 1+(month-2)%12, 25)
		if the25th in self.holidays or the25th.weekday() > 4:
			return business_day(the25th, -7, self.holidays)
		else:
			return business_day(the25th, -6, self.holidays)



class FX:
	"""Date calculations for CME fx futures and options.
	'spot' is 2 days by default. For CAD futures it should be set to 1."""
	def __init__(self, holidays, spot=2):
		self.holidays = holidays
		self.spot = spot
		self.hh = 22

	def fut_last_trade(self, month, year):
		"""'spot' business days before the 3rd Wednesday of the contract month (9:16 CT)."""
		return business_day(self.fut_delivery(month, year)[0], -self.spot, self.holidays)

	def fut_delivery(self, month, year):	
		"""3rd Wednesday of the contract month"""
		return (datetime(year,month,1) + relativedelta(weekday=WE(3)),)*2

	def opt_expiry(self, month, year):
		"""2nd Friday immediately preceding the third Wednesday of the contract month (2pm CT)."""
		return (datetime(year, month, 1, self.hh) + relativedelta(weekday=WE(3)) + relativedelta(weekday=FR(-2)))



class Soft:
	"""Date calculations for CME Agricultural futures and options."""
	def __init__(self, holidays):
		self.holidays = holidays
		self.hh, self.mm = 19, 15

	def fut_last_trade(self, month, year):
		"""Business day prior to the 15th calendar day of the contract month."""
		return business_day(date(year, month, 15), -1, self.holidays)

	def fut_delivery(self, month, year):
		"""Between the first business day of the delivery month and the 2nd business day 
		following the last trading day."""	
		return (business_day(date(year,month,1),0,self.holidays), \
			business_day(self.fut_last_trade(year, month), 2, self.holidays))

	def opt_expiry(self, month, year):
		"""The last Friday which precedes by at least two business days the last business day of
		the calendar month preceding such option's named expiry month. If such Friday is not a
		business day, then the last day of trading in such option shall be the business day prior
		to such Friday."""
		lastfri = business_day(date(year,1+(month-1)%12,1, self.hh, self.mm), -3, self.holidays) \
			+ relativedelta(weekday=FR(-1))

		if (lastfri.weekday() > 4) or (lastfri in self.holidays):
			return business_day(lastfri, -1, self.holidays)
		else:
			return lastfri
		
				




