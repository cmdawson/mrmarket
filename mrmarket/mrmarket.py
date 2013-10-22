

from fograbber import *
import sqlite3, datetime
from exchange.computus import business_day
from dateutil.relativedelta import relativedelta
from pandas.io import sql
from pandas.lib import Timestamp

__all__ = ['MrMarket']

class MrMarket(FOGrabber):

	def __init__(self, datadir):
		super(MrMarket, self).__init__()
		self.DATA = datadir
		dnow = datetime.datetime.now()
		self._today = datetime.datetime(dnow.year, dnow.month, dnow.day)
		self.product = None
		
	@staticmethod
	def valid_database(db, cur):
		cur.execute('SELECT name FROM %s WHERE type="table"' % (db) )
		tables = [str(rr[0]) for rr in cur.fetchall()]
		return 'options' in tables and 'futures' in tables
		
	@staticmethod
	def last_update(cur, table):
		cur.execute('SELECT MAX(timestamp) as "[timestamp]" FROM %s' % table)
		return cur.fetchone()
		
	
	def snap(self, product):
		"""Snap live data and bring settlement data up to date"""
		self.save_settle_data(product)	# settlement data up-to-date. N.B. also calls reset()
		
		dnow = datetime.datetime.now()
		flive = self.DATA + 'live/' + product.lower() + '.sql'
		conn = sqlite3.connect(flive)
		cur = conn.cursor()
		
		futf, optf = self.snap_by_delta(product, dnow)
		del futf['ticker']
		del futf['last_trade']
		optf['timestamp'] = dnow
		futf['timestamp'] = dnow
		optf.reset_index(inplace=True)
		futf.reset_index(inplace=True)
		sql.write_frame(optf, name='options', con=conn, if_exists='append') 
		sql.write_frame(futf, name='futures', con=conn, if_exists='append')
			
		conn.close()

	def load_recent(self, product, **kwargs):
		"""Wrapper to load below that takes some simple keywords like bdays=3 and traslates it for
		load() below. Also understands days, weeks, months or combinations of the three."""
		self.reset(product, self._today)
		itbegins = self._today
		
		if 'bdays' in kwargs:
			itbegins = business_day(itbegins, -int(kwargs.get('bdays')), self.cal.holidays)
			self.load(product, start=itbegins)
			return
		
		if 'days' in kwargs:
			itbegins -= timdelta(days=int(kwargs.get('days')))
		if 'weeks' in kwargs:
			itbegins -= timdelta(days=7*int(kwargs.get('weeks')))
		if 'months' in kwargs:
			itbegins -= relativedelta(months=int(kwargs.get('months')))
		
		itbegins = business_day(itbegins, 0, self.cal.holidays)
		self.load(product, start=itbegins)
		
	
	def load(self, product, **kwargs):
		dnow = datetime.datetime.now()
		fsettle = self.DATA + 'settle/' + product.lower() + '.sql'
		flive = self.DATA + 'live/' + product.lower() + '.sql'
		
		conn = sqlite3.connect(fsettle, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
		cur = conn.cursor()
		cur.execute('ATTACH \"%s\" AS live' % (flive))
		
		# build the basic query
		#query = 'SELECT timestamp as "[timestamp]" FROM %s'
		query = 'SELECT * FROM %s'
		conj = ' WHERE '
		if 'start' in kwargs:
			query += (conj + 'timestamp >= "%s"' % kwargs.get('start'))
			conj = ' AND '
		if 'end' in kwargs:
			query += (conj + 'timestamp < "%s"' % kwargs.get('end'))
			conj = ' AND '
		query += ' ORDER BY timestamp'
		
		self.opt_settle = sql.read_frame(query % 'options', conn)
		self.opt_settle['timestamp'] = self.opt_settle['timestamp'].apply(Timestamp)
		self.opt_settle['month'] = self.opt_settle['month'].apply(str)
		self.opt_settle.set_index(['timestamp', 'month', 'strike'], inplace=True)
		
		self.fut_settle = sql.read_frame(query % 'futures', conn)
		self.fut_settle['timestamp'] = self.fut_settle['timestamp'].apply(Timestamp)
		# how you multi-index depends on how you are going to use it. For a timeseries of ERM4 you want
		# to index by ['mon', 'timestamp'], while for looking at the evolution of the curve it would be
		# timestamp month. Note the need-for-sortedness too. 
		self.fut_settle.set_index(['mon', 'timestamp'], inplace=True)	
		self.fut_settle.sortlevel(0, inplace=True) # Do we need this? would have been better to do it when snapping. 
		
		if not self.valid_database('live.sqlite_master', cur):
			self.opt_live = None
			self.fut_live = None
			return
		
		self.fut_live = sql.read_frame(query % 'live.futures', conn)
		self.fut_live['timestamp'] = self.fut_live['timestamp'].apply(Timestamp)
		self.fut_live.set_index(['mon', 'timestamp'], inplace=True)	
		self.fut_live.sortlevel(0, inplace=True) 
		
		self.opt_live = sql.read_frame(query % 'live.options', conn)
		self.opt_live['timestamp'] = self.opt_live['timestamp'].apply(Timestamp)
		self.opt_live['month'] = self.opt_live['month'].apply(str)
		self.opt_live.set_index(['timestamp', 'month', 'strike'], inplace=True)
		
		conn.close()
		
	def save_settle_data(self, product, start=None):
		"""Like it says. If the datafile already exists it will bring it up to date, otherwise it will 
		begin from 'start' which defaults to 6 months."""
		self.product = product
		self.reset(product, self._today)
		
		fsettle = self.DATA + 'settle/' + product.lower() + '.sql'
		conn = sqlite3.connect(fsettle, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
		cur = conn.cursor()
		
		try:
			cur.execute('SELECT timestamp FROM options AS "[timestamp]" GROUP BY timestamp ' \
				'ORDER BY timestamp')
			rows = cur.fetchall()
		except:
			rows = []
		
		if not rows:
			if start is None:
				start = self._today + relativedelta(months=-6)
		else:
			start = business_day(rows[-1][0], 1, self.cal.holidays)
			
		while start < self._today:
			if not start in rows:
				print "Saving settle data for " + str(start)
				try:
					futf, optf = self.snap_by_delta(product, start)
					del futf['ticker']
					del futf['last_trade']
					optf['timestamp'] = start
					futf['timestamp'] = start
					optf.reset_index(inplace=True)
					futf.reset_index(inplace=True)
					sql.write_frame(optf, name='options', con=conn, if_exists='append') 
					sql.write_frame(futf, name='futures', con=conn, if_exists='append')
				except Exception as e:
					print e
	
			start = business_day(start, 1, self.cal.holidays)
			
		conn.close()
			
				



