

"""Miscellaneous date functions.

In particular routines for business day adjustments, and some helpful wrappers
for constructing an rrule (dateutil) given common holidays that appear in business
calendars. 

Most of the business day functions take a 'holidays' argument which defaults to an 
empty list, but can be any collection of datetimes that supports __contains__().
Note that's datetimes, not dates. For quick lookups you generally want a dictionary
with the holiday date(time)s as keys. Or a dateutil.rruleset but beware special 
holidays like the jubilee in 2012. 

Simple example of constructing UK bank holidays ruleset and getting a Eurodollar
option expiry date:

	from dateutil.rrule import rruleset, rrule
	from dateutil.relativedelta import relativedelta

	bankhols = rruleset(cache=True)

	bankhols.rrule(adj_new_year())
	bankhols.rrule(good_friday())
	bankhols.rrule(easter_monday())
	bankhols.rrule(first_monday_may())
	bankhols.rrule(last_monday_may())
	bankhols.rrule(last_monday_aug())
	bankhols.rrule(adj_xmas_box())

	expiry = date(2013,6,1) + relativedelta(weekday=WE(3)) 	
	expiry = business_day(expiry,-2,bankhols)"""
	
from datetime import datetime, date, timedelta
from dateutil.rrule import *
from dateutil.relativedelta import relativedelta

__all__ = ['rruleset', 'business_day', 'end_of_month', 'start_of_month', \
		'is_holiday', 'easter_monday', 'good_friday', 'adj_xmas', 'adj_xmas_box', \
		'first_monday_may', 'last_monday_may', 'last_monday_aug', 'adj_new_year', \
		'martin_luther_king_day', 'thanksgiving', 'labour_day', 'independence_day', \
		'presidents_day', 'dec31st', 'may1st', 'nth_wday_after'] 


_dref = datetime(1960,1,1)


def business_day(adate, n, holidays=[]):
	"""Return the nth business day after (or before if n < 0) the given date. 
	If n=0 it returns adate if that is a business day, otherwise same as n=1.
	"""
	if type(adate) == date:
		adate = datetime(adate.year, adate.month, adate.day) 

	if n > 0:
		inc = 1
	elif n < 0:
		inc = -1
	else:
		inc = 1
		n = 1
		adate += timedelta(days=-1)

	while n != 0:
		adate += timedelta(days=inc)
		if (adate.weekday() < 5) and (not adate in holidays):
			n -= inc

	return adate


def is_holiday(adate, holidays=[]):
	"""Like it says ... """
	return (adate.weekday() > 4) or (adate in holidays)	



def end_of_month(adate, holidays=[]):
	"""Return the last business day of the month."""
	next1st = date(adate.year+adate.month/12, 1+adate.month%12, 1)
	return business_day(next1st, -1, holidays)



def start_of_month(adate, holidays=[]):
	"""Return the first business day of the month."""
	the1st = date(adate.year, adate.month, 1)
	return business_day(the1st, 0, holidays)


def nth_wday_after(adate, weekday, n):
	"""Same as relativedelta(weekday=...) but less convenient. Might be
	worthwhile if optimization is needed."""
	return adate + timedelta(days=(weekday-adate.weekday()+7)%7+(n-1)*7)



def easter_monday(dref=_dref):
	"""Rule for all easter monday starting from dref (defaults to today)"""
	return rrule(YEARLY,byeaster=1, dtstart=dref)


def good_friday(dref=_dref):
	return rrule(YEARLY,byeaster=-2, dtstart=dref)


def first_monday_may(dref=_dref):
	return rrule(YEARLY, byweekday=MO(1), bymonth=5, dtstart=dref) 


def last_monday_may(dref=_dref):
	return rrule(YEARLY, byweekday=MO(-1), bymonth=5, dtstart=dref) 


def last_monday_aug(dref=_dref):
	return rrule(YEARLY, byweekday=MO(-1), bymonth=8, dtstart=dref) 


def adj_new_year(dref=_dref):
	"""Construct rule for New Year's day holidays starting from dref (default from
	today."""
	return rrule(YEARLY, bysetpos=1, byweekday=(MO,TU,WE,TH,FR), bymonthday=(1,2,3), \
		bymonth=1, dtstart=dref)


def adj_xmas(dref=_dref):
	return rrule(YEARLY, bysetpos=1, byweekday=(MO,TU,WE,TH,FR), \
		bymonthday=(25,26,27), bymonth=12, dtstart=dref)


def adj_xmas_box(dref=_dref):
	return rrule(YEARLY, bysetpos=(1,2), byweekday=(MO,TU,WE,TH,FR), \
		bymonthday=(25,26,27,28), bymonth=12, dtstart=dref)


def martin_luther_king_day(dref=_dref):
	return rrule(YEARLY, byweekday=MO(3), bymonth=1, dtstart=dref) 


def presidents_day(dref=_dref):
	return rrule(YEARLY, byweekday=MO(3), bymonth=2, dtstart=dref) 


def independence_day(dref=_dref):
	return rrule(YEARLY, bysetpos=1, byweekday=(MO,TU,WE,TH,FR), bymonthday=(4,5,6), \
		bymonth=7, dtstart=dref)


def labour_day(dref=_dref):
	return rrule(YEARLY, byweekday=MO(1), bymonth=9, dtstart=dref) 


def thanksgiving(dref=_dref):
	return rrule(YEARLY, byweekday=TH(4), bymonth=11, dtstart=dref) 


def may1st(dref=_dref):
	return rrule(YEARLY, bymonth=5, bymonthday=1, dtstart=dref)


def dec31st(dref=_dref):
	return rrule(YEARLY, bymonth=12, bymonthday=31, dtstart=dref)


if __name__ == "__main__":

	bankhols = rruleset(cache=True)

	bankhols.rrule(adj_new_year())
	bankhols.rrule(good_friday())
	bankhols.rrule(easter_sunday())
	bankhols.rrule(first_monday_may())
	bankhols.rrule(last_monday_may())
	bankhols.rrule(last_monday_aug())
	bankhols.rrule(adj_xmas_box())

	expiry = date(2013,6,1) + relativedelta(weekday=WE(3)) 	
	expiry = business_day(expiry,-2,bankhols) 

	print expiry.strftime('%a %d-%b-%Y')

	test = rruleset(cache=True)
	
	test.rrule(adj_new_year(date(1950,1,1)))
	print foo.strftime('%a %d-%b-%Y'), foo in test	




