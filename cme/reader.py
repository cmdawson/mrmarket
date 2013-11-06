import re, pandas as pd
from datetime import date
from math import modf

__all__ = ['Reader']

# Fixed width indices for settlement files
fields = {'ID':(0,5), 'OPEN':(6,15), 'HIGH':(16,25), \
        'LOW':(26,35), 'LAST':(36,45), 'SETT': (46,55), 'CHG':(55,63), \
        'VOL': (63,75), 'PSETT':(75,86), 'PVOL':(86,98), 'OPENINT':(98,110) }

# Quote conventions (not exhaustive - definately some ags required here)
# need to refactor this, should have some lookup table of product spefications
# that tells you what the quote unit is. Than can just have a parse_quote
# function with a member that takes the denominator 0.08, 0.32, 0.64, ... 1.0
quoteED = ['ED','ZE','E5','E4','E3','E2','E0']
quote8 = ['C', 'W', 'KEF','MWE','YW', 'CDF','PY','OKE','OMW','WZC','WDF','WZ']
quote32 = ['TU','FV','TY','US','UL']
quote64 = ['TUC','FP','FV1','FV2','FV3','TC','TY1','TY2','TY3','OUL','UL1','UL2','UL3','CG','US1','US2','US3']

columns = ['product','month','type','strike','open','high','low','last','settle', 'prev_settle', 'volume','prev_volume', 'openint']
monthmap = {'JAN':'F','FEB':'G','MAR':'H','APR':'J','MAY':'K','JUN':'M','JLY':'N','AUG':'Q','SEP':'U','OCT':'V','NOV':'X','DEC':'Z'}
monthre = re.compile(r'([A-Z]{3})\s?(\d{2})')
strikere = re.compile('^-?\d+(\.\d+)?')

def parse_quote(quote):
    frac,pt = modf(float(quote.replace("'",".")))
    return pt + frac/parse_quote.unit
parse_quote.unit = 1.0


class Reader:

    def __init__(self, filename):
	fp = open(filename)
	self.data = []
	self.index = []
	md = re.search(r'(\d{2})/(\d{2})/(\d{2})', fp.readline())
	self.settle_date = date(2000+int(md.group(3)), int(md.group(1)), int(md.group(2)))
	fp.readline()
	fp.readline()

	while self.setNextProduct(fp):
	    self.parseSection(fp)
	fp.close()

	self.df = pd.DataFrame(self.data, columns=columns, index=self.index)


    def __getitem__(self,pcode):
	"""Return DataFrame of settlement data for given product code"""
	return self.df.ix[pcode]


    def setNextProduct(self, fp):
	"""Return next product code and position fp on first line of data"""
	line = fp.readline()
	while line:
	    # by process of elimination ...
	    line = line.rstrip()
	    if line[:5] == 'TOTAL':
		line = fp.readline()
		continue
	    elif monthre.match(line[:5]):
		line = fp.readline()
		continue
	    elif strikere.match(line[:5]):
		line = fp.readline()
		continue

	    self.pcode = line.split(' ',1)[0]

	    if line[-3:].upper() == 'PUT':
		self.otype = 'P'
		mm = monthre.search(line)
		if not mm:
		    raise Exception("Unable to parse option header")
		self.omonth = '%d%s' % (int(mm.group(2))%10,monthmap[mm.group(1)])

	    elif line[-4:].upper() == 'CALL':
		self.otype = 'C'
		mm = monthre.search(line)
		if not mm:
		    print line
		    raise Exception("Unable to parse option header")
		self.omonth = '%d%s' % (int(mm.group(2))%10,monthmap[mm.group(1)])

	    else:
		self.otype = None
		self.omonth = None

	    return self.pcode

	return None


    def parseSection(self, fp):
	if self.pcode in quoteED:
	    strike_parse = lambda x: 0.01*int(x)
	    parse_quote.unit = 1.0
	elif self.pcode in quote8:
	    strike_parse = float
	    parse_quote.unit = 0.8
	elif self.pcode in quote32:
	    strike_parse = float
	    parse_quote.unit = 0.32
	elif self.pcode in quote64:
	    strike_parse = lambda x: 0.01*int(x)
	    parse_quote.unit = 0.64
	else:
	    strike_parse = float
	    parse_quote.unit = 1.0

	fpos = fp.tell()
	line = fp.readline()
	while line:
	    try:
		self.parseLine(line.rstrip(), strike_parse)
	    except Exception as e:
		#print e
		fp.seek(fpos,0)	
		return

	    fpos = fp.tell()
	    line = fp.readline()


    def parseLine(self, line, strike_parse):
	raw =  { fi:line[fields[fi][0]:fields[fi][1]].strip() for fi in fields \
	    if fields[fi][1] <= len(line) }

	mm = monthre.match(raw['ID'])
	mk = strikere.match(raw['ID'])
	if not (mm or mk):
	    raise Exception("not settlement data")

	# Ignore if there is no open interest
	try:
	    openint = int(raw['OPENINT'])
	except:
	    return

	row = [None] * len(columns)
	row[0] = self.pcode

	if self.otype:
	    row[1] = self.omonth
	    row[2] = self.otype
	    row[3] = strike_parse(raw['ID'])
	else:
	    row[1] = '%d%s' % (int(mm.group(2))%10, monthmap[mm.group(1)])

	row[-1] = openint

	# And all the other stuff
	ii = 4
	for ff in ['OPEN','HIGH','LOW','LAST','SETT','PSETT']:
	    try:
		row[ii] = parse_quote(raw[ff])
	    except:
		pass
	    ii = ii + 1

	for ff in ['VOL','PVOL']:
	    try:
		row[ii] = int(raw[ff])
	    except:
		row[ii] = 0
	    ii = ii + 1

	self.data.append(row)
	self.index.append(row[0])


if __name__ == '__main__':

    cme = Reader('../data/tmp/20131105/stlcomex')
    print cme['OG'][:30]
	




    
