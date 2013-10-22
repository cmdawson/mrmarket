

import pandas as pd
from collections import namedtuple
import os

__all__ = ['XSpec']

class XSpec(object):
	"""Encapsulation of various exchange product conventions"""
	def __init__(self, specfile=None):
		"""Read table of exchange product specifications from CSV file"""
		if specfile is None:
			specfile = os.path.dirname(__file__)+'\\generic.xspec'
		
		self.specfile = specfile
	
		# Pandas does a good job of figuring out the type ...
		self._df = pd.read_csv(specfile, index_col=0)
		self._spec = namedtuple('spec', self._df.columns)
		
		# but not if there are missing entries. You can do this, but probably
		# better to ensure the specfile is better formed. 
		self._df.numOpts = self._df.numOpts.fillna(0).astype(int)
		self._df.numSerialOpts = self._df.numSerialOpts.fillna(0).astype(int)
		self._df.numFuts = self._df.numFuts.fillna(0).astype(int)
		self._df.numSerialFuts = self._df.numSerialFuts.fillna(0).astype(int)
		#self._df.strikeStep = self._df.strikeStep.fillna(0).astype(float)

	def knows(self, product):
		return product in self._df['name']

	def spec(self, product):
		"""Returns namedtuple of product specification"""
		if self.knows(product):
			return self._spec._make(self._df.loc[product])
		else:
			raise ValueError('Unknown exchange symbol: ' + product)
			
			
if __name__ == '__main__':
	xs = XSpec('generic.xspec')

	foo = xs.spec('ER')

	print foo.strikeStep, type(foo.strikeStep)
	print foo.computus, type(foo.computus)
	print foo._fields

	
	
	


