import setup
import aiohttp
import database as db
from aiohttp import web
import jinja2
from jinja2 import Environment, select_autoescape
import json
import re
import os
from datetime import datetime
import asyncio
import markdown

class CachingFileSystemLoader(jinja2.BaseLoader):
	def __init__(self):
		self.file_cache = {}
		self.template_list = None

	def get_source(self, environment, template):
		filename = 'templates/' + template
		if filename in self.file_cache:
			contents = self.file_cache[filename]
		else:
			print('Opening', filename)
			with open(filename, 'r') as f:
				contents = f.read()
			self.file_cache[filename] = contents

		return contents, filename, lambda: False

	def list_templates(self):
		if self.template_list: return self.template_list
		found = set()
		for searchpath in self.searchpath:
			walk_dir = os.walk(searchpath, followlinks=self.followlinks)
			for dirpath, _, filenames in walk_dir:
				for filename in filenames:
					template = (
						os.path.join(dirpath, filename)[len(searchpath) :]
						.strip(os.path.sep)
						.replace(os.path.sep, "/")
					)
					if template[:2] == "./":
						template = template[2:]
					if template not in found:
						found.add(template)
		found = sorted(found)
		self.template_list = found
		return found


jinja_env = Environment(
	loader=CachingFileSystemLoader(),
	autoescape=select_autoescape(['html', 'xml']),
	enable_async=True,
	extensions=[],
	lstrip_blocks=True,
	trim_blocks=True,
	auto_reload=False,
)

jinja_env.globals['escape'] = jinja2.escape
jinja_env.globals['year'] = datetime.now().year
jinja_env.globals['image'] = markdown.create_responsive_image


class templates:
	template_dict = {}
	cached_responses = {}

async def load_template(filename, url=None, static=False, **kwargs):
	if filename in templates.template_dict:
		t = templates.template_dict[filename]
		r = await t.render_async(**kwargs)
	else:
		print(f'Loading template {filename} for the first time')
		t = jinja_env.get_template(filename)
		templates.template_dict[filename] = t
		r = await t.render_async(**kwargs)
	return r

routes = web.RouteTableDef()



@routes.get('/')
async def index(request):
	return await load_template('index.html', static=True)

projects_dict = json.loads(open('website/projects.json', 'r').read())

#@routes.get('/projects')
#async def projects(request):
#	return web.Response(text='<h1>Coming soon</h1>', content_type='text/html')

@routes.get('/projects')
async def projects(request):
	return await load_template('projects.html', projects=projects_dict)

sitemap_dict = {
	'/': {
		'priority': 1.0,
		'lastmod': datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%I:%SZ')
	},
	'/projects': {
		'priority': 0.8,
		'lastmod': datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%I:%SZ')

	},
	'/blog': {
		'priority': 0.7,
		'lastmod': '2019-03-09T17:37:29Z'
	}
}

@routes.get('/sitemap.xml')
async def sitemap(request):
	return await load_template('sitemap.xml', sitemap=sitemap_dict)

# @routes.get('/blog')
# async def blog_soon(request):
# 	return await load_template('soon.html')

async def get_username(request):
	cookies = request.cookies
	sid = cookies.get('sid')
	username = await db.get_session(sid)
	return username

async def check_admin(request):
	username = await get_username(request)
	return username is not None

@routes.get('/blog')
async def blog(request):
	is_admin = await check_admin(request)
	posts = await db.get_blog_posts(limit=10, get_hidden=is_admin)
	return await load_template('blog.html', posts=posts, is_admin=is_admin)

@routes.get('/rss')
async def blog_rss(request):
	posts = await db.get_blog_posts(get_html=True)
	return await load_template('blog.xml', posts=posts)

@routes.get('/blog/new')
async def blog_new(request):
	username = await get_username(request)
	if username is None:
		return web.HTTPTemporaryRedirect('/blog/login')
	return await load_template('editpost.html', username=username, new=True)


@routes.post('/blog/new')
async def blog_post_new(request):
	form = await request.post()
	username = await get_username(request)
	if username is None:
		return web.HTTPTemporaryRedirect('/blog/login')
	body = form['body']
	title = form['title']
	print(form)
	unlisted = form.get('unlisted', 'off') == 'on'
	r = await db.new_blog_post(title, body, username, unlisted=unlisted)
	print(r)
	return web.HTTPFound(f'/blog/post/{r}')

@routes.post('/blog/edit')
async def blog_post_edit(request):
	form = await request.post()
	username = await get_username(request)
	if username is None:
		return web.HTTPTemporaryRedirect('/blog/login')
	body = form['body']
	title = form['title']
	slug = form['slug']
	unlisted = form.get('unlisted', 'off') == 'on'
	slug = await db.edit_blog_post(title, body, username, slug=slug, unlisted=unlisted)
	print('Unlisted:', unlisted)
	if unlisted:
		return web.HTTPFound(f'/blog/edit/{slug}')
	else:
		return web.HTTPFound(f'/blog/post/{slug}')


@routes.post('/blog/preview')
async def blog_post_preview(request):
	form = await request.post()
	username = await get_username(request)
	if username is None:
		return web.HTTPTemporaryRedirect('/blog/login')
	body = form['body']
	title = form['title']
	post = db.get_blog_post_dict(title, body, username)
	post = await db.convert_post(post, get_html=True)
	return await load_template('blogpost.html', p=post, is_admin=False, is_preview=True)

@routes.get('/blog/login')
async def blog_login(request):
	return await load_template('login.html')

@routes.get('/blog/post/{slug}')
async def view_post(request):
	post = await db.get_blog_post(request.match_info['slug'])
	if post is None:
		raise web.HTTPNotFound()
	is_admin = await check_admin(request)
	return await load_template('blogpost.html', p=post, is_admin=is_admin)

@routes.get('/blog/edit/{slug}')
async def edit_post(request):
	post = await db.get_blog_post(request.match_info['slug'])
	return await load_template('editpost.html', p=post, new=False)

@routes.post('/blog/login')
async def blog_login_post(request):
	form = await request.post()
	async with aiohttp.ClientSession() as s:
		r = await s.post(
			'https://www.google.com/recaptcha/api/siteverify',
			data={
				'secret': os.getenv('recaptchasecret'),
				'response': form['g-recaptcha-response'],
				'remoteip': request.headers['Cf-Connecting-Ip']
			}
		)
		r = await r.json()
	if not r['success']:
		return await load_template('login.html')
	else:
		if form['username'] == os.getenv('adminuser') and form['password'] == os.getenv('adminpassword'):
			# ref = request.headers.get('Referer')
			# if ref is None:
			# 	ref = '/blog'
			# ref = ref.lstrip('https://matdoes.dev')
			# if ref[0] != '/' or ref == '/blog/login':
			# 	ref = '/blog'
			ref = form.get('ref', '/blog')
			ref = ref.lstrip('https://matdoes.dev')
			if ref in {'', '/blog/login'}:
				ref = '/blog'
			r = web.HTTPFound(ref)
			sid = await db.new_session(form['username'])
			r.set_cookie('sid', sid, max_age=31557600) # seconds in a year
			print('good', ref)
			return r
	print('lol wrong password')
	return await load_template('login.html')


@web.middleware
async def error_middleware(request, handler):
	try:
		r = await handler(request)
		if str(r.status)[0] not in {'4', '5'}:
			return r
		message, status = r.message, r.status
	except web.HTTPException as ex:
		if str(ex.status)[0] not in {'4', '5'}:
			raise
		message, status = ex.reason, ex.status
	r = web.Response(
		text=await load_template(
			'error.html', status=status, message=message),
		content_type='text/html',
		status=status
	)
	r = await custom_replace(r, request)
	return r

class cache:
	htmlcache = {}

async def custom_replace(r, request):
	newtext = r.text.replace('<< url >>', str(request.url))
	
	for url in list(re.finditer('<< loadurl (.+){1,} >>', newtext))[::-1]:
		raw_url = url.group(1)
		span = url.span()
		if raw_url in cache.htmlcache:
			while cache.htmlcache[raw_url] is None:
				await asyncio.sleep(0)
			content = cache.htmlcache[raw_url]
		else:	
			print('getting cache for', raw_url)
			async with aiohttp.ClientSession() as s:
				cache.htmlcache[raw_url] = None
				async with s.get(raw_url) as resp:
					content = await resp.text()
					if resp.status == 200:
						cache.htmlcache[raw_url] = content
					else:
						print(resp.status)
					print('gotten', raw_url)
		newtext = newtext[:span[0]] + content + newtext[span[1]:]
	r.text = newtext
	return r


@web.middleware
async def middleware(request, handler):
	path = request.url.path
	if len(path) > 100:
		return web.HTTPTemporaryRedirect('/nou')
	if request.url.path[-1] == '/' and request.url.path != '/':
		stripped_url = request.url.path.rstrip('/')
		return web.HTTPPermanentRedirect(stripped_url)
	r = await handler(request)
	if isinstance(r, str):
		r = web.Response(
			text=r,
			headers={
				'content-type': 'text/html'
			}
		)
	content_types = {
		'css': 'text/css',
		'js': 'text/javascript',
		'html': 'text/html',
		'json': 'application/json',
		'xml': 'application/xml',
		'rss': 'application/rss+xml',
		'png': 'image/png'
	}
	# if r.content_type == 'application/octet-stream':
	parts = request.url.parts
	last_path = parts[-1]
	ext = last_path.rsplit('.', 1)[-1]
	if ext in content_types:
		r.content_type = content_types[ext]
	else:
		if r.content_type == 'application/octet-stream':
			r.content_type = 'text/plain'
	if path.startswith('/.well-known'):
		r.headers['Access-Control-Allow-Origin'] = '*'
	try:
		r = await custom_replace(r, request)
	except AttributeError:
		pass
	return r

async def cloudflare_disable_caching():
	return
	api_endpoint = os.getenv('cloudflare_endpoint')
	api_key = os.getenv('cloudflare_key')
	api_email = os.getenv('cloudflare_email')
	async with aiohttp.ClientSession() as s:
		await s.patch(
			api_endpoint,
			headers={
				'X-Auth-Email': api_email,
				'X-Auth-Key': api_key
			},
			json={'value': 'on'}
		)
		print('Disabled CloudFlare caching temporarily')

async def sitemap_blog_posts():
	for b in await db.get_blog_posts():
		sitemap_dict['/blog/post/' + b['slug']] = {
			'priority': 0.6,
			'lastmod': datetime.strftime(b['datetime'], '%Y-%m-%dT%H:%I:%SZ')
		}

asyncio.ensure_future(cloudflare_disable_caching())
asyncio.ensure_future(sitemap_blog_posts())
app = web.Application(middlewares=[error_middleware, middleware])
app.add_routes(routes)
app.add_routes([web.static('/', 'website')])
web.run_app(app)