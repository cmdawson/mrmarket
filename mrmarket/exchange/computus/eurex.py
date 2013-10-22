

from datecalc import *
from datetime import date, timedelta, datetime
from dateutil.relativedelta import *
"""TODO: expiration and last trade times, fut_first_notice functions"""

__all__ = ['Bund']

class Bund:
	"""Date calculations for Eurex Bund and other EU govt bond futures and options (London TZ)."""
	def __init__(self, holidays):
		self.holidays = holidays
		self.hh = 18

	def fut_last_trade(self, month, year):
		"""Two exchange days prior to the delivery day of the relevant maturity month"""
		return business_day(self.fut_delivery(month, year), -2, self.holidays)

	def fut_first_notice(self, month, year):
		pass

	def fut_delivery(self, month, year):	
		"""The first exchange day on or following the 10th calendar day of the contract month."""
		return business_day(date(year, month, 10), 0, self.holidays)

	def opt_expiry(self, month, year):
		"""Last Friday prior to the first calendar day of the option expiration month, followed
		by at least two exchange days prior to the first calendar day of the option expiration
		month. Exception: If this Friday is not an exchange day, or if this Friday is not an
		exchange day and followed by only one exchange day prior to the first calendar day of
		the option expiration month then the exchange day immediately preceding that Friday is
		the Last Trading Day. An exchange day within the meaning of this exception is a day,
		which is both an exchange day at Eurex and a Federal workday in the US.
	
		I've ignored the bit about "Federal workdays" since the only federal holiday that
		could be relevant is xmas and it's Eurex holiday anyway.""" 
		bom = datetime(year,month,1, self.hh)
		bom3p = business_day(bom,-3,self.holidays)

		fri1 = bom + relativedelta(weekday=FR(-1))
		fri2 = bom3p + relativedelta(weekday=FR(-1))

		if is_holiday(fri1, self.holidays) and business_day(fri1, 1, self.holidays) < bom:
			return business_day(fri1, -1, self.holidays)

		elif is_holiday(fri2, self.holidays):
			return business_day(fri2, -1, self.holidays)

		else:
			return fri2
	



