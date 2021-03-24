from datetime import datetime
import motor.motor_asyncio
import uuid
import os
import re
import markdown
import struct
import aiohttp
import asyncio
from timeago import timeago
import urllib.parse

dbuser = os.getenv('dbuser')
dbpassword = os.getenv('dbpassword')
# dbpassword = urllib.parse.quote_plus(dbpassword)

#connection_uri = f'srv+mongodb://{dbuser}:{dbpassword}@ds163905.mlab.com:63905/matdoesdev'
connection_uri = f'mongodb+srv://{dbuser}:{dbpassword}@cluster0-eu9e0.mongodb.net/matdoesdev?retryWrites=true&w=majority'



client = motor.motor_asyncio.AsyncIOMotorClient(connection_uri)

db = client.matdoesdev

blog_posts = db.posts
sessions_db = db.sessions

sessions = {}
cached_image_sizes = {}


base_url = 'https://matdoes.dev'

async def get_image_size(url):
	if url[0] == '/':
		url = base_url + url
	async with aiohttp.ClientSession() as s:
		r = await s.get(url)
		data = await r.read()
	w, h = struct.unpack('>LL', data[16:24])
	width = int(w)
	height = int(h)
	return width, height

async def save_image_size(url):
	width, height = await get_image_size(url)
	cached_image_sizes[url] = (width, height)


def get_image_size_cached(url):
	if url in cached_image_sizes:
		return cached_image_sizes[url]
	asyncio.ensure_future(save_image_size(url))
	return (320, 480)
	

def get_blog_post_dict(title, content, author, unlisted=False, tags=[]):
	post_id = uuid.uuid4().hex
	print('post id:',post_id)
	first_im = markdown.find_first_image(content)
	images = markdown.find_images(content)
	slug = generate_slug(title)
	if first_im is not None:
		get_image_size_cached(first_im['url'])
	document = {
		'_id': post_id,
		'content': content,
		'title': title,
		'datetime': datetime.now(),
		'edited_time': datetime.now(),
		'author': author,
		'slug': slug,
		'tags': tags,
		'image': first_im,
		'comments': [],
		'images': images,
		'hidden': unlisted
	}
	return document



async def new_blog_post(title, content, author, unlisted=False, tags=[]):
	print('creating new blog post')
	document = get_blog_post_dict(title, content, author, unlisted=unlisted, tags=tags)
	print(document)
	await blog_posts.insert_one(document)
	print('done')
	return document['slug']

async def edit_blog_post(title, content, author, tags=[], slug=None, unlisted=False):
	print('editing blog post')
	document = get_blog_post_dict(title, content, author, tags=tags, unlisted=unlisted)
	await get_blog_post_from_id(document['_id'])

	if slug is None:
		slug = document['slug']
	else:
		del document['slug']
	del document['_id']
	del document['datetime']
	await blog_posts.update_one({'slug': slug}, {'$set': document})
	print('done')
	return slug

async def get_blog_post(slug):
	post = await blog_posts.find_one({'slug': slug})
	if post is None:
		return None
	post = await convert_post(post, get_html=True)
	return post

async def get_blog_post_from_id(post_id):
	post = await blog_posts.find_one({'_id': post_id})
	if post is None:
		return None
	post = await convert_post(post, get_html=True)
	return post
	
	
async def new_session(username):
	global sessions
	sid = str(uuid.uuid4())
	print('Creating new session')
	await sessions_db.insert_one({
		'_id': sid,
		'username': username
	})
	print('done')
	sessions[sid] = username
	return sid
	
async def get_session(sid):
	if sid is None:
		return None
	global sessions
	print('sessions:', sessions)
	if sid in sessions:
		return sessions[sid]
	session_data = await sessions_db.find_one({
		'_id': sid
	})
	if session_data is None:
		sessions[sid] = None
		return None
	return session_data['username']

def generate_slug(title):
	slug = re.sub(r'[\W_]+', '-', title.lower())
	slug.replace('--', '-').replace('--', '-')
	slug = slug.strip('-')
	return slug


async def convert_post(post, get_html=False):
	desc_length = 160
	
	no_markdown = markdown.remove_markdown(post['content'])

	no_markdown = no_markdown.replace('&emsp;', ' ')
	no_markdown = no_markdown.replace('\n', ' ')
	no_markdown = no_markdown.replace('  ', ' ')
	description = no_markdown[:desc_length]
	 
	description = description.strip()
	if '.' in description:
		description, _ = description.rsplit('.', 1)
		description += '.'
	
	if 'slug' in post:
		slug = post['slug']
	else:
		slug = generate_slug(post['title'])

	if get_html:
		post_html = markdown.parse_markdown(post['content'], nofollow=False)
	else:
		post_html = None

	image = post.get('image')
	if image is not None:
		im_size = get_image_size_cached(image['url'])
		image['size'] = im_size

	read_time = 0
	images = post.get('images', [])
	read_time += len(no_markdown.split()) * 0.25
	for i in range(len(images)):
		read_time += max(12 - i, 3)
	read_time += len(post['content'].split('\n')) * 0.2
	print(read_time)
	read_time_str = timeago(read_time, 'read', False, True)


	return {
		'title': post['title'],
		'text': no_markdown,
		'slug': slug,
		'time': post['datetime'],
		'author': post['author'],
		'timeago': timeago(post['datetime']),
		'content': post['content'],
		'html': post_html,
		'datetime': post['datetime'],
		'image': image,
		'description': description,
		'readtime': read_time_str,
		'images': images,
		'hidden': post.get('hidden', False)
	}

async def get_blog_posts(limit=-1, get_html=False, get_hidden=False):
	#cursor = blogs.find({})
	#cursor.sort('datetime', -1).limit(limit)
	print('getting blog posts')
	posts = []
	async for post in blog_posts.find({}):
		post_data = await convert_post(post, get_html=get_html)
		if post_data.get('hidden', False) and not get_hidden:
			continue
		posts.append(post_data)
	return posts
	