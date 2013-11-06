import re, os, pandas as pd
from products import products
from datetime import date
__all__ = ['products', 'columns', 'get_date', 'extract']

# Fixed width indices for settlement files
ffields = {'ID':(0,5), 'OPEN':(6,15), 'HIGH':(16,25), \
	'LOW':(26,35), 'LAST':(36,45), 'SETT': (46,55), 'CHG':(55,63), \
	'VOL': (63,75), 'PSETT':(75,86), 'PVOL':(86,98), 'OPENINT':(98,110) }

_eurodollars = ['ED']
_treasuries = ['FV','TU','TY','TB','UL','US']


columns = ['mon', 'strike', 'type', 'open', 'high', 'low', 'last', 'settle', \
    'volume', 'openint']


_datere = re.compile(r'(\d{2})/(\d{2})/(\d{2})')
_monre = re.compile(r'([A-Z]{3})(\d{2})')
_strikere = re.compile('^\d+(\.\d+)?')

_monmap = {'JAN':'F', 'FEB':'G', 'MAR':'H', 'APR':'J', 'MAY':'K', 'JUN':'M', \
    'JLY':'N', 'AUG':'Q', 'SEP':'U', 'OCT':'V', 'NOV':'X', 'DEC':'Z'}

def get_date(dfile):
    fp = open(dfile)
    top = fp.next()
    fp.close()
    
    md = _datere.search(top)
    if not md:
	raise Exception("unable to establish date of settlement data")

    return date(2000+int(md.group(3)), int(md.group(1)), int(md.group(2)))
    

def next_product(fp):
    for line in fp:
	pcode = line.split(' ',1)[0]
	if pcode in products:
	    return line
    return None


def get_table(code, fp):
    pinfo = products[code]
    if code in _eurodollars or pinfo[3] in _eurodollars:
	parse = unpack_eurodollar
    elif code in _treasuries or pinfo[3] in _treasuries:
	parse = unpack_treasury
    else:
	parse = unpack_line

    data = []
    try:
	fpos = fp.tell()
	for line in fp:
	    dd = parse(line)
	    if 'OPENINT' in dd:
		data.append(dd)
    except:
	fp.seek(fpos)

    return data


def extract(code, datafile):
    if not hasattr(code,"__contains__"):
	code = [code]

    rdata= {}
    fp = open(datafile)
    while True:
	pline = next_product(fp)
	if not pline:
	    break

	pline = pline.rstrip()
	prod = pline.split(' ',1)[0]

	if not prod in code:
	    continue

	if not prod in rdata:
	    rdata[prod] = []

	if pline[-4:] == 'CALL' or pline[-3:] == 'PUT':
	    otype = 'C' if pline[-4:] == 'CALL' else 'P'
	    mm = _monre.search(pline)
	    month = '%d%s' % (int(mm.group(2))%10,_monmap[mm.group(1)])
	    tbl = get_table(prod, fp)
	    for row in tbl:
		rdata[prod].append([month, row['ID'], otype, row['OPEN'], \
		    row['HIGH'], row['LOW'], row['LAST'], row['SETT'], \
		    row['VOL'], row['OPENINT']])
	else:
	    tbl = get_table(prod, fp)
	    for row in tbl:
		rdata[prod].append([row['ID'], row['OPEN'], row['HIGH'], \
		    row['LOW'], row['LAST'], row['SETT'], row['VOL'], \
		    row['OPENINT']])

    fp.close()
    return rdata


def _unpack_raw(line):
    return { fi:line[ffields[fi][0]:ffields[fi][1]] for fi in ffields \
	if ffields[fi][1] <= len(line) }


def unpack_line(line):
    raw = _unpack_raw(line)
    mm = _monre.match(raw['ID'])
    mk = _strikere.match(raw['ID'])
    if not (mm or mk):
	raise Exception("not settlement data")
    for kk in raw:
	if kk == 'ID':
	    if mm:
		raw['ID'] = '%d%s' % (int(mm.group(2))%10,_monmap[mm.group(1)])
	    else:
		raw['ID'] = int(raw['ID'])
	elif kk=='VOL' or kk=='PVOL' or kk=='OPENINT':
	    try:
		raw[kk] = int(raw[kk])
	    except:
		raw[kk] = 0
	else:
	    try:
		raw[kk] = float(raw[kk])
	    except:
		raw[kk] = 0.0
    return raw
    

def unpack_eurodollar(line):
    """Need to round up the strike to 1/8th"""
    raw = _unpack_raw(line)
    mm = _monre.match(raw['ID'])
    mk = _strikere.match(raw['ID'])
    if not (mm or mk):
	raise Exception("not settlement data")
    for kk in raw:
	if kk == 'ID':
	    if mm:
		raw['ID'] = '%d%s' % (int(mm.group(2))%10,_monmap[mm.group(1)])
	    else:
		# strikes will appear like 9912, 10087 etc
		ik = int(raw['ID'])
		raw['ID'] = ik/100 + int(0.5+(ik%100)*0.08)/8.0
	elif kk=='VOL' or kk=='PVOL' or kk=='OPENINT':
	    try:
		raw[kk] = int(raw[kk])
	    except:
		raw[kk] = 0
	else:
	    try:
		raw[kk] = float(raw[kk])
	    except:
		raw[kk] = 0.0
    return raw 


def unpack_treasury(line):
    """Futures will be 32nds or 64ths"""
    raw = _unpack_raw(line)
    mm = _monre.match(raw['ID'])
    mk = _strikere.match(raw['ID'])
    if not (mm or mk):
	raise Exception("not settlement data")

    for kk in raw:
	if kk == 'ID':
	    if mm:
		raw['ID'] = '%d%s' % (int(mm.group(2))%10,_monmap[mm.group(1)])
	    else:
		ik = int(raw['ID'])
		raw['ID'] = ik/100 + int(0.5+(ik%100)*0.08)/8.0
	elif kk=='VOL' or kk=='PVOL' or kk=='OPENINT':
	    try:
		raw[kk] = int(raw[kk])
	    except:
		raw[kk] = 0
	else:
	    # Futures quoted in 32nds, options in 64ths
	    parts = [x for x in raw[kk].split('\'')]
	    try:
		raw[kk] = int(parts[0])
	    except:
		raw[kk] = 0.0
	    try:
		frac = int(parts[1])
		raw[kk] += (int(frac*0.4+0.5)*25)/100.0/(32.0 if mm else 64.0)
	    except:
		raw[kk] = 0.0
	    if parts[0].find('-') != -1:
		raw[kk] *= -1
    return raw 

