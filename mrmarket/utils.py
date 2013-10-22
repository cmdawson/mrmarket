import sqlite3, datetime
import pandas as pd
from exchange import XSpec
from exchange.computus import Computus, business_day
from mrmarket import MrMarket
from pandaburger import PandaBurger
from pandas.io import sql
from pandas.lib import Timestamp
import datetime
from dateutil.relativedelta import relativedelta

import matplotlib.pyplot as plt

__all__ = ['DATA', 'vol_change', 'futures_curve', 'bbget']

DATA = 'H:/data/exchange/'
EXCH_MONTHS = 'FGHJKMNQUVXZ'

def vol_change(mrmkt, month=None, trail=None, midcurve=None):
	"""Plot some smiles
	Generically pick 4 expires to display, probably by highest volume, but take some
	keyword arguments to let user override them. And maybe you want to look at more
	than just a comparison with yesterday. Evolution over a period (shaded smiles)?
	Comparison with arbitrary date? ...  """
	isettle = mrmkt.opt_settle.index.levels[0]
	last_settle = mrmkt.opt_settle.ix[isettle[-1]]
	
	isnap = mrmkt.opt_live.index.levels[0]
	last_snap = mrmkt.opt_live.ix[isnap[-1]]
	year = isnap[-1].year
	
	if month is not None:
		margs = month.split(',')
	else:
		df = last_settle.groupby(level='month')
		sumv = df['VOLUME'].sum().order(ascending=False)
		if midcurve is not None and mrmkt.has_midcurves():
			ii = [q for q in sumv.index if q[0] == str(midcurve)]
		else:
			ii = [q for q in sumv.index if len(q) == 2]
		margs = sumv[ii][:4].index #sorted(sumv[ii], key=lambda x: x[-1]+x[-2])
		
	months = [x for x in margs if x in last_snap.index.levels[0]]
	ii, rows = 1, int(len(months)/2)+1
	
	axes = {}
	
	for mm in months:
		ax = plt.subplot(rows,2,ii, axisbg=(0.97,0.97,0.985))
		axes[mm] = ax
		ssmile = last_settle.ix[mm] 
		
		#fut_settle = mrmkt.fut_settle[mm, isettle[-1]]
		#fut_live = mrmkt

		ax.plot(ssmile.index, ssmile['SETTLE_VOL'], 'r', label=isettle[-1].strftime('%d %b'));
		lsmile = last_snap.ix[mm]
		lsmile['MID_VOL'] = (lsmile['BID_VOL']+lsmile['ASK_VOL'])/2.0
		ax.plot(lsmile.index, lsmile['BID_VOL'], 'g^', label=isnap[-1].strftime('%H:%M'));
		ax.plot(lsmile.index, lsmile['ASK_VOL'], 'bv') #marker=r'$\clubsuit$', alpha=0.5);
		ax.grid();
		ax.legend();
		
		if len(mm) == 4:
			cmon, cyr = EXCH_MONTHS.index(mm[2])+1, year+(int(mm[3])-(year%10)+10)%10
			expdate = mrmkt.cal.mc_expiry(cmon, cyr)
			ax.set_title(mm + " (" + expdate.strftime('%d-%b-%Y') + ")")
		else:
			cmon, cyr = EXCH_MONTHS.index(mm[0])+1, year+(int(mm[1])-(year%10)+10)%10
			expdate = mrmkt.cal.opt_expiry(cmon, cyr)
			ax.set_title(mrmkt.product + mm + " (" + expdate.strftime('%d-%b-%Y') + ")")

		ii += 1
		
	if trail is not None:
		nn = min(len(isettle), trail)
		alpha = 0.2
		for dd in isettle[-nn:-1]:
			fsettle = mrmkt.opt_settle.ix[dd]
			for mm, ax in axes.iteritems():
				ssmile = fsettle.ix[mm]
				ax.plot(ssmile.index, ssmile['SETTLE_VOL'], 'r--', alpha=alpha) #, label=dd.strftime('%d %b'));

			alpha = alpha + 0.3/nn
		
def futures_curve(mrmkt, **kwargs):
	"""Simple plot of the futures curve and how it's evolved over the past 4 days"""
	isettle = mrmkt.fut_settle.index.levels[1]
	fsettle = mrmkt.fut_settle.xs(isettle[-1], level='timestamp')
	isnap = mrmkt.fut_live.index.levels[1]
	fsnap = mrmkt.fut_live.xs(isnap[-1], level='timestamp')
	
	year = isettle[-1].year
	
	fsettle['mid'] = (fsnap.ASK + fsnap.BID)/2
	fsettle['month'] = fsettle.index.values
	fsettle['lasttrade'] = fsettle['month'].apply(lambda x: \
		mrmkt.cal.fut_last_trade(EXCH_MONTHS.index(x[0])+1, year+(int(x[1])-(year%10)+10)%10))
		
	fprev = mrmkt.fut_settle.xs(isettle[-2], level='timestamp')
	fsettle['T_2'] = fprev['PX_SETTLE']
	
	fprev = mrmkt.fut_settle.xs(isettle[-3], level='timestamp')
	fsettle['T_3'] = fprev['PX_SETTLE']
		
	fsettle.index = fsettle['lasttrade']
	fsettle.sort(inplace=True)
	
	ax = plt.subplot(1,1,1)
		
	ax.plot(fsettle.index, fsettle['mid'], color='blue', label=isnap[-1].strftime('%H:%M'));
	ax.plot(fsettle.index, fsettle['PX_SETTLE'], color='crimson', label=isettle[-1].strftime('%d %b'));
	ax.plot(fsettle.index, fsettle['T_2'], color='crimson', alpha=0.4, label=isettle[-2].strftime('%d %b'));
	ax.plot(fsettle.index, fsettle['T_3'], color='crimson', alpha=0.2, label=isettle[-3].strftime('%d %b'));
	ax.set_xticks(fsettle.index);
	ax.set_xticklabels(fsettle['month']);
	ax.grid();
	ax.legend();
	
	#print fsettle
	
	
def bbget(tickers, fields="PX_LAST", start=None, end=None, period=None, dates=None):
	"""Convenience function for downloading Bloomberg data.
	
	Args:
		tickers: iterable of Bloomberg tickers
		period: Either (i) 'DAILY' (default), 'WEEKLY', 'MONTHLY', ...
		        or (ii) Number of minutes for intraday ticks
		fields: iterable of fields, defaults to 'PX_LAST'
		EITHER
			start: Start date for historical data, default tries to do something
					sensible depending on the end date and the period.
			end: End date for historical data, defaults to now. 
		OR
			dates: Array of dates 
		
	Returns a pandas panel for multiple fields, a dataframe for a single field.
	"""
	
	pb = PandaBurger()
	pb.connect('localhost', 8194)
	interval = 0
	
	if start is None and end is None and dates is None:
		data = pb.fetch(tickers, fields))
	
	if not dates is None:
		data = {} # have no idea why you cant' assign directly to a panel
		for di in dates:
			datum = pb.fetch(tickers, fields, di, di)
			if di in datum.major_axis:
				data[di] = datum.major_xs(di)	
		return pd.Panel(data) 
		
	if end is None:
		end = datetime.datetime.now()

	if period is None or period == 'DAILY':
		_start = end + relativedelta(months=-1)
	elif period == 'WEEKLY':
		pb.periodicity = period
		_start = end + relativedelta(months=-3)
	elif period == 'MONTHLY':
		pb.periodicity = period
		_start = end + relativedelta(years=-2)
	elif period == 'QUARTERLY':
		pb.periodicity = period
		_start = end + relativedelta(years=-4)
	else: # Must be an intraday interval in minutes
		interval += period
		_start = end + relativedelta(weeks=-1)
		
	if start is None:
		start = _start
			
	
	data = pb.fetch(tickers, fields, start, end, interval)
	
	# force timestamp?
	
	if len(data.minor_axis) == 1:
		return data.minor_xs(data.minor_axis[0])
	else:
		return data
	
	# really need a pandaburger.disconnect (or want, probably don't need it)
	
	
def stir_conditional_curve(mrmkt, **kwargs):
	pass
	
	
def multi_plot(df, shared=False):
	"""Multiple plots on a shared x-axis"""
	ax = plt.subplot(1,1,1)
	
	col = df.columns[0]
	ax.plot(df.index, df[col], label=col)
	
	for col in df.columns[1:]:
		bx = ax.twinx()
		



	

	

