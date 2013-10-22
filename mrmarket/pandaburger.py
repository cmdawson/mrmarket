

import pandas as pd
import bloomburger
from datetime import datetime, timedelta

# recall that if you want weekly / month historical data then use periodicity property

class PandaBurger(bloomburger.bb):
	def __init__(self):
		super(PandaBurger, self).__init__()
		
	def connect(self, server='localhost', port=8194):
		super(PandaBurger, self).connect(server, port)
	
	def fetch(self, securities, fields, d0=False, d1=False, interval=0):
		"""Fetch realtime, historical, or historical intraday Bloomberg data.
		Returns pandas data structure.
		Attempts to provide some flexiblity, but possibly to the point of ambiguity."""
		
		#if type(securities) == str:
		#	securities = [securities]
		#elif type(securities) != list: 	
			# hack because bloomburger requires a list. Would be better if it accepted any 
			# iterable object, but nobody's perfect. 
		#	securities = [ss for ss in securities]
			
		#if type(fields) == str:
		#	fields = [fields]
		#elif type(fields) != list:
		#	fields = [ff for ff in fields]
		
		if interval == 0:
			if not d0 and not d1:
				bdata = super(PandaBurger, self).fetch(securities, fields)
				pdata = [dict(bdata[s]) for s in securities]
				return pd.DataFrame(pdata, index=securities) #, columns=fields)
			elif not d1:
				# better to just return a dataframe for the single date?
				# (really wish i'd had bloomburger do the same)
				bdata = super(PandaBurger, self).fetch(securities, fields, d0, d0)
				securities = [s for s in securities if s in bdata and bdata[s]]
				pdata = [dict([fi for fi in bdata[s][0] if fi[0]!='date']) for s in securities]
				return pd.DataFrame(pdata, index=securities) #, columns=fields)
				
			bdata = super(PandaBurger, self).fetch(securities, fields, d0, d1)
			return pd.Panel({sec: pd.DataFrame([dict(rr) for rr in bdata[sec]]).set_index('date') \
				for sec in bdata if bdata[sec]})
			
		
		else:
			# bloomburger will only do intraday tick requests one security at a time, (not clear
			# if the API allows any different). fields[0] should be an event like 'TRADE'
			if not d1:
				d1 = datetime.now()
			if not d0:
				d0 = datetime(d1.year, d1.month, d1.day)
				
			prepanel = {}			
			for sec in securities:
				bdata = super(PandaBurger, self).fetch(sec, fields[0], d0, d1, interval)
				if bdata[sec]:
					prepanel[sec] = [dict(rr) for rr in bdata[sec]]
					
			# if there were no events for a particular security in any of the intervals, then
			# it will not appear at all in the panel. Prefer all NaN, not sure how to do it. 
			return pd.Panel({kk: pd.DataFrame(prepanel[kk]).set_index('time') for kk in prepanel})
			
			
	def dump(self, securities, fields, d0=None):
		if not d0:
			return bloomburger.bb.fetch(self, securities, fields)
		else:
			return bloomburger.bb.fetch(self, securities, fields, d0, d0)
			
		

