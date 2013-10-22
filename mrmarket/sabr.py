

import pandas as pd
from bisect import bisect_left
from numpy import sqrt, log, exp, power
from exchange import Computus, XSpec
from arachne import impliedvol, impliedvolbn
from scipy import optimize


__all__ = ['SABR', 'fit']

EXCH_MONTHS = 'FGHJKMNQUVXZ'

def _impliedvol(cp, forward, strike, maturity, discount, premium):
	return impliedvol(cp, forward, strike, maturity, 0.0, 0.0, premium/discount)

class SABR(object):
    def __init__(self, f, alpha, beta, rho, nu):
        self.f = f
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.nu = nu
    
    def __call__(self, K, texp, logmoneyness=False):
        K = K * 1.0
        
        if logmoneyness:
            x = K
            K = self.f / exp(x)
        else:
            x = log(self.f/K)
            
        sigma1 = power(self.f*K,self.beta-1.0)*self.alpha*self.alpha*(self.beta-1.0)*(self.beta-1.0)/24.0 \
            + pow(self.f*K,0.5*(self.beta-1.0))*self.alpha*self.beta*self.nu*self.rho/4.0 \
            + self.nu*self.nu*(2.0-3.0*self.rho*self.rho)/24.0
            
        if abs(x)<1.0e-15:
            sigma0 = self.alpha * power(K, self.beta-1)
            return sigma0*(1.0+sigma1*texp)
            
        if self.beta == 1.0:
            z = self.nu * x / self.alpha
        else:
            z = self.nu * (power(self.f,1-self.beta)-power(K,1-self.beta)) / self.alpha / (1-self.beta)
             
        if self.nu == 0.0:
			sigma0 = x*self.alpha*(1-self.beta) / (power(self.f,1-self.beta) - power(K,1-self.beta))
        else:
            sigma0 = self.nu * x  / log((sqrt(1.0-2*self.rho*z+z*z)+z-self.rho)/(1-self.rho))

        return sigma0*(1.0 + sigma1*texp)


class SABR_Fitter(object):
	def __init__(self, fwd, beta, tau, opts):
		"""opts should be a list of (strike, mid vol) tuples. Deal with bid / asks later"""
		self.fwd = fwd
		self.beta = beta
		self.tau = tau
		self.opts = opts
		
		self.alpha = 0.0
		self.rho = 0.0
		self.nu = 0.0
		
	def _vol(self, K):
		K = K * 1.0
		x = log(self.fwd/K)
            
		sigma1 = power(self.fwd*K,self.beta-1.0)*self.alpha*self.alpha*(self.beta-1.0)*(self.beta-1.0)/24.0 \
            + pow(self.fwd*K,0.5*(self.beta-1.0))*self.alpha*self.beta*self.nu*self.rho/4.0 \
            + self.nu*self.nu*(2.0-3.0*self.rho*self.rho)/24.0
            
		if abs(x)<1.0e-15:
			sigma0 = self.alpha * power(K, self.beta-1)
			return sigma0*(1.0 + sigma1*self.tau)
            
		if self.beta == 1.0:
			z = self.nu * x / self.alpha
		else:
			z = self.nu * (power(self.fwd,1-self.beta)-power(K,1-self.beta)) / self.alpha / (1-self.beta)
			 
		if self.nu == 0.0:
			sigma0 = x*self.alpha*(1-self.beta) / (power(self.fwd,1-self.beta) - power(K,1-self.beta))
		else:
			sigma0 = self.nu * x  / log((sqrt(1.0-2*self.rho*z+z*z)+z-self.rho)/(1-self.rho))

		return sigma0*(1.0 + sigma1*self.tau)
		
		
	def target(self, xval):
		self.alpha = xval[0]
		self.rho = xval[1]
		self.nu = xval[2]
		
		err = []
		
		for opt in self.opts:
			kvol = self._vol(opt[0])
			err.append(kvol-opt[1])
		
		return err


		
def fit(product, snap_date, fopt, ffut, beta=None, x0=None):
	"""Fit SABR parameters to a snapshot. 
	
	Arguments:
	fopt -- dataframe of option priecs multi-indexed by ('month','strike') 
			Either a single column of mid or settlement prices, or columns
			names 'BID' and 'ASK'.
	ffut -- dataframe of futures prices (single) indexed by month, columns
			as per the options. 
	
	'month' here refers to an exchange month code like 'Z3'. 
	Returns a dataframe of SABR parameters indexed by month
	"""
	_computus = Computus()
	_spec = XSpec()
	
	xs = _spec.spec(product)
	cdr = _computus.make(xs.computus)
	
		
	if xs.model == 'normal':
		if beta is None:
			beta = 0.0
		ivolfn = impliedvolbn
	else:
		if beta is None:
			beta = 1.0
		ivolfn = _impliedvol
	
	if not 'month' in fopt.index.names:
		raise Exception('Unable to index fopts by month')
		
	snap_base =  10*(snap_date.year/10)
	
	if 'BID' in fopt.columns and 'ASK' in fopt.columns:
		to_tuples = lambda x: x[['BID', 'ASK']].to_records()
	else:
		to_tuples = lambda x: x.to_records()
		
	df = pd.DataFrame(index = fopt.index.levels[fopt.index.names.index('month')], \
			columns = ['fwd', 't', 'beta', 'alpha', 'rho', 'nu'], \
			dtype = float)
	
	for month in ['U3']: #fopt.index.levels[fopt.index.names.index('month')]:
		if len(month) == 4:	# ie midcurve TODO
			continue 
			
		mm,yy = EXCH_MONTHS.index(month[0]) + 1, + snap_base + int(month[1])
		umon = xs.undlMonths[bisect_left(xs.undlMonths, month[0])]
		if umon < EXCH_MONTHS[mm-1]:
			umon += str((yy+1)%10)
		else:
			umon += str(yy%10)
			
		fwd = (ffut.ix[umon]['BID'] + ffut.ix[umon]['ASK']) / 2.0
		expiry = cdr.opt_expiry(mm, yy)
		act365 = (expiry - snap_date).days / 365.0 \
			+ (expiry - snap_date).seconds / 31536000.0	
		if act365 < 0.0:
			continue
			
		mopts = fopt.ix[month]
		tuples = []
		for k in mopts.index:
			mid = (mopts['BID'][k] + mopts['ASK'][k]) / 2.0
			#print 'CP'[k<fwd], fwd, k, act365, 1.0, mid
			tuples.append((k, ivolfn('CP'[k<fwd], fwd, k, act365, 1.0, mid)))
			
		pp = _fit(fwd, act365, beta, tuples, x0)
		
		print tuples
		print pp[0], [fwd, act365, beta]
		
		df.ix[month] = [fwd, act365, beta, pp[0][0], pp[0][1], pp[0][2]]
		
	return df
	

def _fit(fwd, act365, beta, strip, x0=None):
	sf = SABR_Fitter(fwd, beta, act365, strip)
	
	tfunc = sf.target
	if x0 is None:
		x0 = [0.2, 0.1, 0.05]
	
	return optimize.leastsq(tfunc, x0)
	

