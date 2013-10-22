import sqlite3, re
from datetime import datetime
from pandas.io import sql
from pandas.lib import Timestamp
import pandas as pd
from utils import bbget
import dateutil.parser as parser
#from pandas.tseries.frequencies import infer_freq

__all__ = ['MrData']

class MrData(object):
	"""MrData: basic utility for creating and maintaining sqlite files of bb data, and 
	loading them into pandas dataframes or panels. Multiple tickers / single fields or
	single tickers / multiple fields are stored in single tables. If multiple tickers
	and fields are required (e.g. OHLC) then each ticker will be given its own table.
	
	"""
	def __init__(self, datadir):
		self.DATA = datadir
		self.suffix_re = re.compile('(_)(Comdty|Index|Equity|Curncy)$')
		
		self.intraday_re = re.compile('^(\d+)([HT])$')
		self.monthly_re = re.compile('^B?([MQA])S?(-[A-Z]{3})?$')
		#self.qtr_re = re.compile('^B?QS?(-[A-Z]3})$')
	

	def create(self, datafile, start, tickers, fields=['PX_LAST'], end=None, period=None):
		"""Create new datafile based on the given tickers, fields, and start date. Optionally pass
		periodicity (defaults to 'DAILY'), an end date (defaults to today). If an intraday period
		is passed the fields will be set to ['TRADE']."""
		try:
			open(self.DATA + datafile, 'r')
			raise Exception(self.DATA + datafile + ' already exists, please use update')
		except IOError:
			pass
		
		if type(period) is int:df
			fields = ['TRADE']
			
		# Note if period is an integer (minutes) fields needs to be ['TRADE'] or something
		dnow = datetime.now()
		df = bbget(tickers, fields, start, period=period)
		dims = df.shape
		
		conn = sqlite3.connect(self.DATA + datafile)
		cur = conn.cursor()
		
		# Sqlite doesn't have a seperate TIMESTAMP type, but instead lets you store them as TEXT, 
		# REAL (julian date), or INTEGER (unix epoch) and provides converter functions. Pandas 
		# uses TEXT cos everything goes into the insert statement via %s. Could slim things down
		# by using REAL but doesn't seem necessary. 
		if len(dims) == 3:
			for ii in df.items:
				safe_table = ii.replace(' ', '_').strip()
				iframe = df[ii].dropna(how='all')
				iframe['timestamp'] = iframe.index
	
				cur.execute(sql.get_schema(iframe, safe_table, 'sqlite', keys='timestamp'))
				safe_cols = [s.replace(' ', '_').strip() for s in iframe.columns]
				sql._write_sqlite(iframe, safe_table, safe_cols, cur)
				
		else:
			# Only going to be a dataframe if there is a single field, which becomes
			# the name of the table
			df['timestamp'] = df.index
			
			cur.execute(sql.get_schema(df, fields[0], 'sqlite', keys='timestamp'))
			cur.execute('CREATE INDEX ts_idx ON %s (timestamp);' % fields[0])

			safe_cols = [s.replace(' ', '_').strip() for s in df.columns]
			sql._write_sqlite(df.dropna(how='all'), fields[0], safe_cols, cur)

				
		conn.commit()
		conn.close()

	
	def update(self, datafile, start=None):
		"""Bring the given datafile up to date. If start is provided, also extend the datafile
		back to that date if necessary"""
		try:
			fp = open(self.DATA + datafile, 'r')
			fp.close()
		except IOError:
			raise Exception('Cannot find file ' + self.DATA + datafile)
			
		conn = sqlite3.connect(self.DATA + datafile)
		conn.text_factory = str
		cur = conn.cursor()
	
		cur.execute('SELECT name FROM sqlite_master WHERE type=\'table\'')
		tables = [t[0] for t in cur.fetchall()]
		
		for table in tables:
			cur.execute('SELECT DATETIME(timestamp) FROM %s ORDER BY DATETIME(timestamp)' \
				'DESC LIMIT 7' % table)
			tidx = [datetime.strptime(r[0], '%Y-%m-%d %H:%M:%S') for r in cur.fetchall()]
			# TODO: should do the sorting in _infer_period
			period = self._infer_period([ti for ti in reversed(tidx)]) 
			
			t0 = tidx[0]
			cur.execute('DELETE FROM %s WHERE DATETIME(timestamp) = \'%s\'' % (table, t0))
			cur.execute('SELECT * FROM %s LIMIT 1' % table)
			cols = [d[0] for d in cur.description]
			
			if type(period) is int:
				secs = [self.suffix_re.sub(' \\2', table)]
				fields = ['TRADE']
			elif self.suffix_re.search(table):
				secs = [self.suffix_re.sub(' \\2', table)]
				fields = [c for c in cols if c != 'timestamp']
				#fields.remove('timestamp')
			else:
				fields = [table]
				secs = [self.suffix_re.sub(' \\2', c) for c in cols]
				secs.remove('timestamp')
	
			df = bbget(secs, fields, t0, period=period)
			dims = df.shape
			
			if len(dims) == 3:
				df = df[secs[0]]
						
			df['timestamp'] = df.index
			sql._write_sqlite(df.dropna(how='all'), table, cols, cur)
					
		conn.commit()
		conn.close()
		

	def load(self, datafile, table=None):
		"""Load a datafile and return a dataframe. By default returns all tables which will
		produce a dataframe when appropriate, or generally a date,ticker,field panel. Or the
		optional table argument can be used"""
		try:
			fp = open(self.DATA + datafile, 'r')
			fp.close()
		except IOError:
			raise Exception('Cannot find file ' + self.DATA + datafile)
			
		conn = sqlite3.connect(self.DATA + datafile)
		cur = conn.cursor()
		
		cur.execute('SELECT name FROM sqlite_master WHERE type=\'table\'')
		tables = [t[0] for t in cur.fetchall()]
		
		if not tables:
			raise Exception('No tables in ' + datafile)
		
		pdict = {}
		cur.execute('SELECT * from %s' % tables[0])
		cols = [self.suffix_re.sub(' \\2',d[0]) for d in cur.description]
		
		titem = self.suffix_re.sub(' \\2', tables[0])
		pdict[titem] \
			= pd.DataFrame.from_records(cur.fetchall(), columns=cols, coerce_float=True)
		pdict[titem]['timestamp'] = pdict[titem]['timestamp'].apply(Timestamp)
		pdict[titem].set_index('timestamp', inplace=True)
		
		if len(tables) == 1:
			conn.close()
			return pdict[titem]
	
		for tt in tables[1:]:
			cur.execute('SELECT * from %s' % tt)
			titem = self.suffix_re.sub(' \\2', tt)
			pdict[titem] \
				= pd.DataFrame.from_records(cur.fetchall(), columns=cols, coerce_float=True)
			pdict[titem]['timestamp'] = pdict[titem]['timestamp'].apply(Timestamp)
			pdict[titem].set_index('timestamp', inplace=True)
		
		conn.close()
		return pd.Panel.from_dict(pdict)		
		
		
	def info(self, datafile):
		"""Returns a list of tables in the given datafile"""
		conn = sqlite3.connect(self.DATA + datafile)
		cur = conn.cursor()
		
		cur.execute('SELECT name FROM sqlite_master WHERE type=\'table\'')
		tables = [t[0] for t in cur.fetchall()]
				
		conn.close()
		
		return tables
		
	def _infer_period(self, tstamps):
		idx = pd.to_datetime(tstamps)
		freq = pd.tseries.frequencies.infer_freq(idx)
		
		if freq is None:
			freq = pd.tseries.frequencies.infer_freq(idx[:3])
		
		if freq is None: # still
			raise Exception('Unable to infer timeseries frequency')
			
		if freq == 'B' or freq == 'D':
			return "DAILY"
		elif freq[0] == 'W':
			return "WEEKLY"
		else: 
			mm = self.intraday_re.match(freq)
			if mm:
				gg = mm.groups()
				return int(gg[0]) * (1 if gg[1] == 'T' else 60)
			
			mm = self.monthly_re.match(freq)
			if mm:
				gg = mm.groups()
				if gg[0] == 'M':
					return 'MONTHLY'
				elif gg[0] == 'Q':
					return 'QUARTERLY'
				elif gg[0] == 'A':
					return 'ANNUAL'

			raise Exception('Unable to understand timeseries frequency ' + freq)

