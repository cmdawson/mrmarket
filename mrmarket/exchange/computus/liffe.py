

from datecalc import *
from datetime import date, timedelta
from dateutil.relativedelta import *
"""TODO: expiration and last trade times, fut_first_notice functions"""

__all__ = ['ShortSterling', 'Euribor']

class ShortSterling:
	"""Date calculations for Liffe Short Sterling futures and options. If only
	they were all this simple. """
	def __init__(self, holidays):
		self.holidays = holidays
		self.mc_expiry = self.opt_expiry

	def fut_last_trade(self, month, year):
		"""Third wednesday of the contract monthi (11am LDN)"""
		return date(year, month, 1) + relativedelta(weekday=WE(3))

	def fut_delivery(self, month, year):	
		return (False, False)

	def opt_expiry(self, month, year):
		"""Third wednesday of the contract monthi (11am LDN)"""
		return date(year, month, 1) + relativedelta(weekday=WE(3))
		

class Euribor:
	"""Date Calculations for Eurex Euribor futures and options. """
	def __init__(self, holidays):
		self.holidays = holidays
		self.mc_expiry = self.opt_expiry

	def fut_last_trade(self, month, year):
		"""Final Settlement Day (also last trade) is two exchange days prior to the third
		Wednesday of the respective maturity month, provided there's a fixing; otherwise,
		the exchange day immediately preceding that day (11am CET)
		As far as I can tell the Liffe calendar is the same as the TARGET one, so fixings
		are available on every exchange day baring disruptions."""
		return business_day(date(year, month, 1) + relativedelta(weekday=WE(3)), -2, self.holidays)

	def fut_delivery(self, month, year):	
		return (False, False)

	def opt_expiry(self, month, year, midcurve=False):
		"""Two exchange days prior to the third Wednesday of the respective expiration
		month (guess same rule if there's no fixing on that date"""
		return business_day(date(year, month, 1) + relativedelta(weekday=WE(3)), -2, self.holidays)



