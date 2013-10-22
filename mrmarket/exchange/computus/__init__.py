

import cme, eurex, liffe
from datecalc import *

__all__ = ['Computus', 'business_day']

class Computus:
	"""Factory for creating objects responsible for exchange date calculations. Each object
	implements the following methods:
		obj.fut_last_trade(month, year)
		obj.fut_first_notice(month, year)
		obj.fut_delivery(month, year)
		obj.opt_expiry(month, year)
	and is created by calling the make('label') function below, where 'label' refers to some
	canonical set of rules and is one of cbt-bond, cbt-note, cme-ed, cme-ed-mc, cme-ff,
	cme-metal, cme-wti, cme-fx, cme-soft, eurex-bund, liffe-ebor, liffe-stg

	Computus is also responsible for dealing with exchange holiday calendars and passing them
	to the datecalc objects above. Default rrulesets are defined for cme, target, eurex, and 
	bba, but note these don't include special holidays like jubilee's etc. You can override
	these default rrulesets in the make function.
	
	N.B. It gets CLZ2 wrong for some reason, unsure what the deal is there. Bit worrying."""

	def __init__(self):
		self.cme_cal = rruleset(cache=True)
		self.target_cal = rruleset(cache=True)
		self.eurex_cal = rruleset(cache=True)
		self.bba_cal = rruleset(cache=True)

		self.cme_cal.rrule(adj_new_year())
		self.cme_cal.rrule(martin_luther_king_day())
		self.cme_cal.rrule(presidents_day())
		self.cme_cal.rrule(good_friday())
		self.cme_cal.rrule(last_monday_may())	# memorial day
		self.cme_cal.rrule(independence_day())	# adjusted 4th July
		self.cme_cal.rrule(labour_day())	
		self.cme_cal.rrule(thanksgiving())	
		self.cme_cal.rrule(adj_xmas())	

		self.eurex_cal.rrule(adj_new_year())
		self.eurex_cal.rrule(good_friday())
		self.eurex_cal.rrule(easter_monday())
		self.eurex_cal.rrule(may1st())
		self.eurex_cal.rrule(adj_xmas_box())
		
		self.bba_cal.rrule(adj_new_year())
		self.bba_cal.rrule(good_friday())
		self.bba_cal.rrule(easter_monday())
		self.bba_cal.rrule(first_monday_may())
		self.bba_cal.rrule(last_monday_may())
		self.bba_cal.rrule(last_monday_aug())
		self.bba_cal.rrule(adj_xmas_box())

	def make(self, label, holidays=None):
		"""Construct the desired computus."""

		if label == 'cbot-bond':
			return cme.TBond(holidays if holidays else self.cme_cal)

		elif label == 'cbot-note':
			return cme.TNote(holidays if holidays else self.cme_cal)

		elif label == 'cme-ed':
			return cme.EuroDollar(holidays if holidays else self.cme_cal)
			
		elif label == 'cme-ed-mc':
			return cme.EuroDollarMC(holidays if holidays else self.cme_cal)

		elif label == 'cme-ff':
			return cme.FedFunds(holidays if holidays else self.cme_cal)
				
		elif label == 'cme-metal':
			return cme.Metal(holidays if holidays else self.cme_cal)

		elif label == 'cme-wti':
			return cme.WTI(holidays if holidays else self.cme_cal)

		elif label == 'cme-fx': 
			return cme.FX(holidays if holidays else self.cme_cal)

		elif label == 'cme-soft': 
			return cme.Soft(holidays if holidays else self.cme_cal)

		elif label == 'eurex-bund': 
			return eurex.Bund(holidays if holidays else self.eurex_cal)

		elif label == 'liffe-ebor': 
			return liffe.Euribor(holidays if holidays else self.bba_cal)

		elif label == 'liffe-stg':
			return liffe.ShortSterling(holidays if holidays else self.bba_cal)

		else:
			raise ValueError(label)


