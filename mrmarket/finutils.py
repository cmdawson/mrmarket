from numpy import sqrt, exp
from scipy.stats import norm

__all__ = ['svi_var', 'delta_implied_strike', 'delta_implied_strike_bn']

	
def delta_implied_strike(fwd, delta, vol, texp, dfac, otype):
	"""Given a delta in (-1,1), returns the strike that would product said delta"""
	vtau = vol * sqrt(texp)
	phi = 1 if otype.upper()[0] == 'C' else -1
	dx = norm.ppf(phi*delta/dfac);
	return fwd * exp(-phi*vtau*dx + 0.5*vtau*vtau);
	
	
def delta_implied_strike_bn(fwd, delta, vol, texp, dfac, otype):
	"""Given a delta in (-1,1), returns the strike that would product said delta
	(Black-Normal model)"""
	vtau = vol * sqrt(texp)
	phi = 1 if otype.upper()[0] == 'C' else -1
	dx = norm.ppf(phi*delta/dfac)
	return -phi * dx * vtau + fwd
	
	
def svi_var(p, k):
	"""Gatheral's SVI variance. 'k' is the log-strike relative to the forward"""
	return p[0] + p[1]*(p[3]*(k-p[4]) + sqrt((k-p[4])*(k-p[4]) + p[2]*p[2]))
