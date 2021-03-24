from datetime import datetime

units = {
	'second': 60,
	'minute': 3600,
	'hour': 86400,
	'day': 604800,
	'week': 2628002,
	'month': 31557600,
	'year': -1
}

def timeago(t, suffix='ago', plural=True, rounded=False):
	if isinstance(t, int) or isinstance(t, float):
		seconds = t
	else:
		td = datetime.now() - t
		seconds = td.total_seconds()
	prev = seconds
	for u in units:
		s = units[u]
		v = seconds / s
		if v < (0.5 if rounded else 1):
			# t = round(v) * s
			t = round(prev)
			if t == 1 or not plural:
				return f'{t} {u} {suffix}'
			else:
				return f'{t} {u}s {suffix}'
		prev = seconds / s
