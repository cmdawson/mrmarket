

from pandaburger import PandaBurger
from exchange import *
import pandas as pd, arachne, re
from datetime import datetime, date
from bisect import bisect_left
from itertools import dropwhile, izip, ifilter
from collections import OrderedDict, namedtuple
from numpy import sqrt
import sqlite3

from finutils import *

__all__ = ['FOGrabber']

EXCH_MONTHS = 'FGHJKMNQUVXZ'

# wrapper for black-scholes implied vol function (so it matches signature of black-normal one and
# we can use function pointer thingies)
def _impliedvol(cp, forward, strike, maturity, discount, premium):
	return arachne.impliedvol(cp, forward, strike, maturity, 0.0, 0.0, premium/discount)
	
class _OptR(object):
	__slots__ = 'month', 'undl', 'expiry', 'act365', 'undlpx', 'atmk', 'atmv', 'data'
	def __init__(self, month, undl, expiry):
		setattr(self,'month',month)
		setattr(self,'undl',undl)
		setattr(self,'expiry',expiry)	
	def __str__(self):
		outp= '{'
		for ff in self.__slots__:
			if hasattr(self,ff):
				outp += (ff+': '+str(getattr(self,ff))+', ')
		return outp[:-2]+'}'
	def __eq__(self, other):
		assert isinstance(other, _OptR) 
		return self.month == other.month
	
	
class FOGrabber(object):
	"""Retrieves F&O data from Bloomberg and shoves them into a Pandas dataframe"""
	def __init__(self, specfile=None):
		self.computus = Computus()
		self.specs = XSpec(specfile)
		self.date = datetime.now()
		self.product = None
		self.livedata = True
		
		self.pb = PandaBurger()
		self.pb.connect('localhost', 8194)
	
	
	def reset(self, product, sdate, src=False):
		self.xs = self.specs.spec(product)
		self.product = product
		self.cal = self.computus.make(self.xs.computus)
		
		
		if self.xs.model == 'normal':
			self.ivolfn = arachne.impliedvolbn
			self.istrikefn = delta_implied_strike_bn
		else:
			self.ivolfn = _impliedvol
			self.istrikefn = delta_implied_strike
			
		dtoday = date.today()
		if date(sdate.year, sdate.month, sdate.day) == date.today():
			self.date = datetime.now()
			self.livedata = True
			if not src:
				src = 'ELEC'
			self.suffix = src + ' ' + self.xs.suffix
		else:
			# *assuming* expiration time is same as settlement time
			dexp = self.cal.opt_expiry(sdate.month, sdate.year)
			self.date = datetime(sdate.year, sdate.month, sdate.day, dexp.hour, dexp.minute, 0)
			self.livedata = False
			if not src:
				src = 'COMB'
				self.suffix = src + ' ' + self.xs.suffix
				
		self.optregex = re.compile('^' + self.product + \
			'(?P<mm>[FGHJKMNQUVXZ]\d{1})(?P<type>[PC])\s(?P<k>\d+(\.\d+)?) ' + self.suffix + '$')
			
			
	def make_pair(self, instr, mstring, ii):
		smod = len(mstring)
		mm,yy = EXCH_MONTHS.index(mstring[ii%smod]) + 1, self.date.year + ii//smod

		if instr == 'fut':
			return (EXCH_MONTHS[mm-1] + str(yy%10), self.cal.fut_last_trade(mm, yy))
		else:
			umon = self.xs.undlMonths[bisect_left(self.xs.undlMonths, EXCH_MONTHS[mm-1])]
			if umon < EXCH_MONTHS[mm-1]:
				umon += str((yy+1)%10)
			else:
				umon += str(yy%10)
			
			return (EXCH_MONTHS[mm-1] + str(yy%10), self.cal.opt_expiry(mm, yy), umon)
			
	
	def make_record(self, instrument, mstring, ii):
		smod = len(mstring)
		mm,yy = EXCH_MONTHS.index(mstring[ii%smod]) + 1, self.date.year + ii//smod

		if instrument == 'fut':
			return (EXCH_MONTHS[mm-1] + str(yy%10), self.cal.fut_last_trade(mm, yy))
		else:
			umon = self.xs.undlMonths[bisect_left(self.xs.undlMonths, EXCH_MONTHS[mm-1])]
			if umon < EXCH_MONTHS[mm-1]:
				umon += str((yy+1)%10)
			else:
				umon += str(yy%10)
				
			if instrument == 'mc':
				expiry = self.cal.mc_expiry(mm, yy)
			else:
				expiry = self.cal.opt_expiry(mm, yy)
				
			return _OptR(EXCH_MONTHS[mm-1] + str(yy%10), umon, expiry)	
			
	def futures_chain(self):
		if not self.product:
			raise RuntimeError("Please set an exchange product first")
			
		futures = []
		# generate all the serial futures (plus one extra - see below)
		if pd.notnull(self.xs.futSerialMonths) and self.xs.numSerialFuts > 0:
			sf0 = bisect_left(self.xs.futSerialMonths, EXCH_MONTHS[self.date.month - 1])
			futures += [self.make_pair('fut', self.xs.futSerialMonths, ff) \
				for ff in range(sf0, sf0 + self.xs.numSerialFuts)]
		
			# Remove and replace expired months
			sf0 += self.xs.numSerialFuts
			while self.date > futures[0][1]:
				futures.pop(0)
				futures.append(self.make_pair('fut', self.xs.futSerialMonths, sf0))
				sf0 += 1
	
		# Generate the remaining futures, filtering those already included 
		ff0 = bisect_left(self.xs.futMonths, EXCH_MONTHS[self.date.month-1])
		futures += dropwhile(lambda y: y in futures or self.date > y[1], \
			[self.make_pair('fut', self.xs.futMonths, ff) for ff in range(ff0, ff0 + self.xs.numFuts + 1)])
			
		return futures
			
	
	def options_chain(self):
		if not self.product:
			raise RuntimeError("Please set an exchange product first")
			
		exps = []
		
		if pd.notnull(self.xs.optSerialMonths):
			ee0 = bisect_left(self.xs.optSerialMonths, EXCH_MONTHS[self.date.month - 1])
			exps += [self.make_record('opt', self.xs.optSerialMonths, ee) \
				for ee in range(ee0, ee0 + self.xs.numSerialOpts)]
			# pop the first if it's past, otherwise pop the last
			#exps.pop(0 if (self.date > exps[0].expiry) else -1)
			# Remove and replace expired months
			ee0 += self.xs.numSerialOpts
			
			while self.date > exps[0].expiry:
				exps.pop(0)
				exps.append(self.make_record('opt', self.xs.optSerialMonths, ee0))
				ee0 += 1
				
		ee0 = bisect_left(self.xs.optMonths, EXCH_MONTHS[self.date.month-1])
		exps += dropwhile(lambda y: y in exps or self.date > y.expiry, \
			[self.make_record('opt', self.xs.optMonths, ff) for ff in range(ee0, ee0 + self.xs.numOpts + 1)])	
		
		#for ee in exps:
		#	print ee
		
		return {ee.month: ee for ee in exps}
	
	def midcurves_chain(self):
		if not self.product:
			raise Exception("Please set an exchange product first")
			
		optr = []
		mcsuffix = self.xs.midcurves[1]
		years = range(int(self.xs.midcurves[0])+1)
		years.remove(1)
		
		ee0 = bisect_left(self.xs.optSerialMonths, EXCH_MONTHS[self.date.month - 1])
		optr += [self.make_record('mc', self.xs.optSerialMonths, ee) \
			for ee in range(ee0, ee0 + self.xs.numSerialMC)]
			
		ee0 += self.xs.numSerialMC
		while self.date > optr[0].expiry:
				optr.pop(0)
				optr.append(self.make_record('mc', self.xs.optSerialMonths, ee0))
				ee0 += 1
		
		ee0 = bisect_left(self.xs.optMonths, EXCH_MONTHS[self.date.month-1])
		optr += dropwhile(lambda y: y in optr or self.date > y.expiry, \
			[self.make_record('mc', self.xs.optMonths, ff) for ff in range(ee0, ee0 + self.xs.numMC)])	
		
		midcurves = [_OptR(str(y)+mcsuffix+rr.month, rr.undl[0]+str(int(rr.undl[1])+y+1-(y>0)), rr.expiry) \
			for rr in optr for y in years]
			
		return {mc.month: mc for mc in midcurves}
		
		
		
	def calc_atm_vols(self, opts, undlpx, _product=None, _re=None):
		tickers = []
		
		if _product is None:
			_product = self.product
		if _re is None:
			_re = self.optregex
		
		#self.product, _re=self.optregex
		for rr in opts.values():
			rr.undlpx = undlpx[rr.undl]
			rr.atmk = self.xs.strikeStep * int(0.5 + rr.undlpx/self.xs.strikeStep)
			rr.atmv = False
			
			rr.act365 = (rr.expiry - self.date).days / 365.0 \
							+ (rr.expiry - self.date).seconds / 31536000.0	
			if rr.act365 < 1.0e-6:
				del opts[rr.month]
			else:
				tickers.append(_product + rr.month + 'C ' + str(rr.atmk) + ' ' + self.suffix)
				tickers.append(_product + rr.month + 'P ' + str(rr.atmk) + ' ' + self.suffix)
						
		if self.livedata:
			bdata = self.pb.dump(tickers, ['BID','ASK','BID_SIZE','ASK_SIZE'])
			#	'LAST_UPDATE_BID', 'LAST_UPDATE_ASK'])
		else:
			bdata = self.pb.dump(tickers, ['PX_SETTLE'], self.date)
		
		for tkr0, row0 in bdata.iteritems():
			mmatch = _re.match(tkr0)
			mm = mmatch.group('mm')
			otype0 = mmatch.group('type')
			strike = float(mmatch.group('k'))
			
			# skip if we've already failed or succeeded
			if not mm in opts or opts[mm].atmv:
				continue
			
			otype1 = 'P' if otype0 == 'C' else 'C'
			tkr1 = _product + mm + otype1 + ' ' + str(strike) + ' ' + self.suffix
			row1 = bdata[tkr1]
			
			if not row0 and not row1:
				del opts[mm]
				continue
			elif self.livedata:
				drow0 = dict(row0)
				drow1 = dict(row1)
			
				onbid0 = drow0['BID_SIZE'] if 'BID_SIZE' in drow0 else 0
				onbid1 = drow1['BID_SIZE'] if 'BID_SIZE' in drow1 else 0
				onask0 = drow0['ASK_SIZE'] if 'ASK_SIZE' in drow0 else 0
				onask1 = drow1['ASK_SIZE'] if 'ASK_SIZE' in drow1 else 0
				avg0 = sqrt(onbid0*onask0)
				avg1 = sqrt(onbid1*onask1)
				
				if avg0 > avg1:
					px = (drow0['BID'] + drow0['ASK']) / 2.0
					otype = otype0
				elif avg1 > avg0 or avg1 > 0:
					px = (drow1['BID'] + drow1['ASK']) / 2.0
					otype = otype1
				elif onbid0 > onbid1:
					px = drow0['BID']
					otype = otype0
				elif onbid1 > onbid0 or onbid1 > 0:
					px = drow1['BID']
					otype = otype1
				elif onask0 > onask1:
					px = drow0['ASK']
					otype = otype0
				elif onask1 > onbid0 or onask1 > 0:
					px = drow1['ASK']
					otype = otype1
				else:
					del opts[mm]
					continue	

			else:
				drow = dict(row0[0])
				px = drow['PX_SETTLE']
		
			try:
				# have to do this due to a bug in the implied vol solver
				if strike == opts[mm].undlpx:
					opts[mm].atmv = self.ivolfn(otype0, opts[mm].undlpx+1.0E-8, strike, opts[mm].act365, 1.0, px)
				else:				
					opts[mm].atmv = self.ivolfn(otype0, opts[mm].undlpx, strike, opts[mm].act365, 1.0, px)
					
				print "(", mm, otype0, opts[mm].undlpx, strike, opts[mm].act365, 1.0, px, ") = ", opts[mm].atmv
			except Exception, e:
				print e
				print "(", mm, otype0, opts[mm].undlpx, strike, opts[mm].act365, 1.0, px, ")"
				del opts[mm]
		
	
	def bulk_fetch(self, tickers, optr, _re=None):
		if self.livedata:
			bdata = self.pb.dump(tickers, ['BID','ASK','VOLUME','BID_SIZE','ASK_SIZE'])
		else:
			bdata = self.pb.dump(tickers, ['PX_SETTLE','VOLUME'], self.date)
			
		if _re is None:
			_re = self.optregex
			
		for tkr, row in bdata.iteritems():
			try:
				mmatch = _re.match(tkr)
				mm = mmatch.group('mm')
				otype = mmatch.group('type')
				strike = float(mmatch.group('k'))
				data = {}
			except:
				print tkr
				exit()	
			
			if not row:
				continue
			elif self.livedata:
				drow = dict(row)
				bid = drow['BID'] if 'BID' in drow else 0
				ask = drow['ASK'] if 'ASK' in drow else 0
				volume = drow['VOLUME'] if 'VOLUME' in drow else 0
				onbid = drow['BID_SIZE'] if 'BID_SIZE' in drow else 0
				onask = drow['ASK_SIZE'] if 'ASK_SIZE' in drow else 0
				
				bvol = float('nan')
				avol = float('nan')
				try:
					if bid > 0 and onbid > 0:	
						bvol = self.ivolfn(otype, optr[mm].undlpx, strike, optr[mm].act365, 1.0, bid)
					if ask > 0 and onask > 0:
						avol = self.ivolfn(otype, optr[mm].undlpx, strike, optr[mm].act365, 1.0, ask)
				except:
					print "Failed to calculate vol for ", tkr, 
					print optr[mm].undlpx, strike, optr[mm].act365, "("+str(bid)+"|"+str(ask)+")"
		
				optr[mm].data.append((strike, otype, bid, bvol, ask, avol, volume))
			else:
				drow = dict(row[0])
				px = drow['PX_SETTLE'] if 'PX_SETTLE' in drow else 0
				if px == 0:
					continue
				volume = drow['VOLUME'] if 'VOLUME' in drow else 0
				
				ivol = self.ivolfn(otype, optr[mm].undlpx, strike, optr[mm].act365, 1.0, px)
				optr[mm].data.append((strike, otype, px, ivol, volume))
	
	
	def get_options_by_delta(self, optr, deltas, _product=None, _re=None):
		"""tada"""
		if _product is None:
			_product = self.product
			_re = self.optregex
	
		kstep = self.xs.strikeStep
		tickers = set()
		
		for rr in optr.values():
			kcall = rr.atmk if rr.atmk > rr.undlpx else rr.atmk + kstep
			kput = kcall - kstep
			tickers.add(_product+rr.month+'P '+str(kput)+' '+ self.suffix)
			tickers.add(_product+rr.month+'C '+str(kcall)+' '+ self.suffix)
			
			for da in deltas:
				try:
					kput = kstep*int(self.istrikefn(rr.undlpx,-da,rr.atmv,rr.act365,1.0,'P')/kstep)
					kcall = kstep*int(1.0+self.istrikefn(rr.undlpx,da,rr.atmv,rr.act365,1.0,'C')/kstep)
				except:
					print rr.month, 
					print "failed with ", rr.undlpx, da, rr.atmv, rr.act365
					continue
			
				tickers.add(_product+rr.month+'P '+str(kput)+' '+ self.suffix)
				tickers.add(_product+rr.month+'C '+str(kcall)+' '+ self.suffix)
				
				rr.data = []
			
		#for tt in tickers:
		#	if tt[:4] == 'TYM3':
		#		print tt
			
		self.bulk_fetch(tickers, optr, _re)
		for rr in optr.values():
			rr.data.sort(lambda x,y: (x[0]>y[0]) - (x[0]<y[0]))
		
		
	def get_options_by_volume(self, optr, nn=10, mindelta=0.05, _product=None, _re=None):
		"""Gets price data for the n most traded strikes by volume for the given expiry.
		Can specify cutoffs either by mindelta (calculated using the ATM vols or (TODO) passing
		a strike range [lo,hi]"""
		if _product is None:
			_product = self.product
			_re = self.optregex
			
		kstep = self.xs.strikeStep
		tickers = []
		
		for rr in optr.values():
			klo = kstep*int(self.istrikefn(rr.undlpx,-mindelta,rr.atmv,rr.act365,1.0,'P')/kstep)
			khi = kstep*int(1+self.istrikefn(rr.undlpx,mindelta,rr.atmv,rr.act365,1.0,'C')/kstep)
			
			while klo <= khi:
				tickers.append(_product + rr.month + 'PC'[klo>rr.undlpx] + ' ' \
				+ str(klo) + ' ' + self.suffix)
				klo += kstep
				
			rr.data = []
				
		self.bulk_fetch(tickers, optr, _re)
		# keep the top n by volume (sorted by strike)
		for rr in optr.values():
			rr.data.sort(lambda x,y: (x[-1]>y[-1]) - (x[-1]<y[-1]))
			rr.data = rr.data[-nn:] #.sort(lambda x,y: (x[0]>y[0]) - (x[0]<y[0]))
			rr.data.sort(lambda x,y: (x[0]>y[0]) - (x[0]<y[0]))
		
	
	def snap_largest_volume(self, product, sdate, nn=10, midcurves=True):
		"""Snap options grid and get the 10 most traded by volume for each month.
		"""
		self.reset(product, sdate)
		
		if self.livedata:
			ffields = ['BID', 'ASK', 'VOLUME']
			_columns = ['BID', 'BID_VOL', 'ASK', 'ASK_VOL', 'VOLUME']
			
		else:
			ffields = ['PX_SETTLE', 'VOLUME']
			_columns = ['SETTLE', 'SETTLE_VOL', 'VOLUME']
		
		fdata = pd.DataFrame.from_records(self.futures_chain(), columns=['mon', 'last_trade'], index='mon')
		fdata.insert(0, 'ticker', [self.product+mm+' '+self.suffix for mm in fdata.index])
		fdata = pd.merge(fdata, self.pb.fetch(fdata.ticker, ffields, self.date), left_on='ticker', \
			right_index=True, how='outer')
			
		if not 'VOLUME' in fdata:
			raise Exception("No futures volume on " + sdate.strftime("%Y-%m-%d"))
			
		optr = self.options_chain()
		
		# discard months with no volume
		optr = {k:v for k,v in optr.iteritems() if pd.notnull(fdata.VOLUME[v.undl])}
		
		if self.livedata:
			self.calc_atm_vols(optr, 0.5*(fdata.BID+fdata.ASK))
		else:
			self.calc_atm_vols(optr, fdata.PX_SETTLE)
		
		self.get_options_by_volume(optr, nn)
		
		if pd.notnull(self.xs.midcurves) and midcurves:
			mcoptr = self.midcurves_chain()
			mcre = re.compile('^(?P<mm>\d' + self.xs.midcurves[1] + \
				'[FGHJKMNQUVXZ]\d{1})(?P<type>[PC])\s(?P<k>\d+(\.\d+)?) ' + self.suffix + '$')
			if self.livedata:
				mcoptr = {k:v for k,v in mcoptr.iteritems() if pd.notnull(fdata.BID[v.undl])
					and pd.notnull(fdata.ASK[v.undl])}
				self.calc_atm_vols(mcoptr, 0.5*(fdata.BID+fdata.ASK), '', mcre)
			else:
				mcoptr = {k:v for k,v in mcoptr.iteritems() if pd.notnull(fdata.VOLUME[v.undl])}
				self.calc_atm_vols(mcoptr, fdata.PX_SETTLE, '', mcre)
				
			self.get_options_by_volume(mcoptr, nn, 0.05, '', mcre)
		else:
			mcoptr = []
		
		idx = pd.MultiIndex.from_tuples( \
			[(mm,kk[0]) for mm in sorted(optr) for kk in optr[mm].data] \
				+ [(mc,kk[0]) for mc in sorted(mcoptr) for kk in mcoptr[mc].data], \
			names=['month', 'strike'])	
		odata = pd.DataFrame( \
			[list(x[2:]) for mm in sorted(optr) for x in optr[mm].data]
				+ [list(x[2:]) for mc in sorted(mcoptr) for x in mcoptr[mc].data], \
			columns = _columns, \
			index = idx)
			
		return fdata, odata
		
	
	def snap_by_delta(self, product, sdate, deltas=[0.05,0.1,0.25,0.4], midcurves=True):
		"""Snap live or settlement options prices by a list of deltas, whose implied
		strikes are determined using the ATM vol for simplicity."""
		self.reset(product, sdate)
		
		if self.livedata:
			ffields = ['BID', 'ASK', 'VOLUME']
			_columns = ['BID', 'BID_VOL', 'ASK', 'ASK_VOL', 'VOLUME']
		else:
			ffields = ['PX_SETTLE', 'VOLUME']
			_columns = ['SETTLE', 'SETTLE_VOL', 'VOLUME']
		
		fdata = pd.DataFrame.from_records(self.futures_chain(), columns=['mon', 'last_trade'], index='mon')
		fdata.insert(0, 'ticker', [self.product+mm+' '+self.suffix for mm in fdata.index])
		fdata = pd.merge(fdata, self.pb.fetch(fdata.ticker, ffields, self.date), left_on='ticker', \
			right_index=True, how='outer')
			
		if not 'VOLUME' in fdata:
			raise Exception("No futures volume on " + sdate.strftime("%Y-%m-%d"))
		
	
		optr = self.options_chain()
		
		# Calc ATM vols and ignore options whose futures are dead
		if self.livedata:
			optr = {k:v for k,v in optr.iteritems() if pd.notnull(fdata.BID[v.undl])
				and pd.notnull(fdata.ASK[v.undl])}
			self.calc_atm_vols(optr, 0.5*(fdata.BID+fdata.ASK))
		else:
			optr = {k:v for k,v in optr.iteritems() if pd.notnull(fdata.VOLUME[v.undl])} # what if no volume field ???
			self.calc_atm_vols(optr, fdata.PX_SETTLE)
			
		self.get_options_by_delta(optr, deltas)

		
		if pd.notnull(self.xs.midcurves) and midcurves:
			mcoptr = self.midcurves_chain()
			#print '^(?P<mm>\d' + self.xs.midcurves[1] + \
			#	'[FGHJKMNQUVXZ]\d{1})(?P<type>[PC])\s(?P<k>\d+(\.\d+)?) ' + self.xs.suffix + '$'
			mcre = re.compile('^(?P<mm>\d' + self.xs.midcurves[1] + \
				'[FGHJKMNQUVXZ]\d{1})(?P<type>[PC])\s(?P<k>\d+(\.\d+)?) ' + self.suffix + '$')
			if self.livedata:
				mcoptr = {k:v for k,v in mcoptr.iteritems() if pd.notnull(fdata.BID[v.undl])
					and pd.notnull(fdata.ASK[v.undl])}
				self.calc_atm_vols(mcoptr, 0.5*(fdata.BID+fdata.ASK), '', mcre)
			else:
				mcoptr = {k:v for k,v in mcoptr.iteritems() if pd.notnull(fdata.VOLUME[v.undl])}
				self.calc_atm_vols(mcoptr, fdata.PX_SETTLE, '', mcre)
				
			self.get_options_by_delta(mcoptr, deltas, '', mcre)
		else:
			mcoptr = []
				
		idx = pd.MultiIndex.from_tuples( \
			[(mm,kk[0]) for mm in sorted(optr) for kk in optr[mm].data] \
				+ [(mc,kk[0]) for mc in sorted(mcoptr) for kk in mcoptr[mc].data], \
			names=['month', 'strike'])	
		odata = pd.DataFrame( \
			[list(x[2:]) for mm in sorted(optr) for x in optr[mm].data]
				+ [list(x[2:]) for mc in sorted(mcoptr) for x in mcoptr[mc].data], \
			columns = _columns, \
			index = idx)
		
		return fdata, odata
		
	def has_midcurves(self):
		return pd.notnull(self.xs.midcurves)
		



