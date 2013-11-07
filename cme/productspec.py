import pandas as pd
from collections import namedtuple

__all__ = ['ProductSpec','ProductSpecLoader']

ProductSpec = namedtuple('ProductSpec','quoteUnit,strikeFactor,computus,underlying')

class ProductSpecLoader(object):
    """Encapsulation of various exchange product conventions
    Specifically quoteUnit, strikeFactor, computus
    """
    def __init__(self, specfile):
	self.specfile = specfile

	# Pandas does a good job of figuring out the type ... but not if there
	# are missing values
	self._df = pd.read_csv(specfile, index_col=0, comment='#').dropna(how='all')
	self._defaultspec = ProductSpec(1.0,1.0,None,None)
	    
    def knows(self, product):
	return product in self._df.index

    def spec(self, product):
	"""Returns namedtuple of product specification"""
	if self.knows(product):
	    return ProductSpec(*self._df.ix[product])
	else:
	    return self._defaultspec
		
if __name__ == '__main__':
    xs = ProductSpecLoader('cme.spec')

    foo = xs.spec('TUC')

    print foo.quoteUnit, type(foo.quoteUnit)
    print foo.strikeFactor, type(foo.strikeFactor)
    print foo.computus, type(foo.computus)
    print foo.underlying, type(foo.underlying)
    print foo._fields

	
	
	


