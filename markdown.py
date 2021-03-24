import re
import struct

'''
matdoes.dev markdown:


Relative anchor: [matdoesdev](/blog)


External anchor: [matdoesdev](https://matdoes.dev)
  External anchors have target=_blank so they open in new pages


Normal links: https://matdoes.dev
  Normal links in the text are converted to anchors


Code block: ```lang
code
```
  If a language is specified, it is highlighted with hljs


Inline code: `code`


Block quote:
> text


Italic: *text*
Bold: **text**


||text||
  Centers text horizontally


Titles:
# h2
## h3
### h4
#### h5
##### h6
###### h6


Horizontal rule:
---


Image:
[description](https://image)
Left image:
,[description](https://image)
Right image:
.[description](https://image)

'''

img_pattern = r'!\[(.{1,}?)\]\(([\w\-.\/:?=#]+)\)'
img_left_pattern = ',' + img_pattern
img_right_pattern = '.' + img_pattern


def get_image_size(data):
	w, h = struct.unpack('>LL', data[16:24])
	width = int(w)
	height = int(h)
	return width, height

base_url = 'https://matdoes.dev'

def find_images(content):
	images = re.findall(img_pattern, content)
	return images

def find_first_image(content):
	images = find_images(content)
	if len(images) == 0:
		first_im = None
	else:
		im_alt, im_url = images[0]
		if im_url[0] == '/':
			im_url = base_url + im_url
		first_im = {
			'url': im_url,
			'alt': im_alt
		}
	return first_im



def create_responsive_image(src='\\2', alt='\\1', classes=[]):
	responsive_class_list = ['lazy'] + classes
	rclass_str = ' '.join(responsive_class_list)
	nclass_str = ' '.join(classes)
	nclass_str = f' class="{nclass_str}"'
	responsive = f'<img data-src="{src}" alt="{alt}" class="{rclass_str}" onload="this.classList.remove(\'lazy\')">'
	noscript = f'<noscript><img src="{src}" alt="{alt}"{nclass_str}></noscript>'
	return responsive + noscript

def hl_codeblock(m):
	hl_type = m.group(1) or 'no-highlight'
	hl_text = m.group(2)
	return f'<pre><code class="hljs {hl_type}">{hl_text}</code></pre>'

def parse_markdown(content, nofollow=True):
	content = content.replace('&', '&amp;')
	content = content.replace('"', '&quot;')
	content = content.replace('\r\n', '\n')
	content = content.replace('<', '&lt;')
	content = content.replace('>', '&gt;')

	content = content.replace(r'\[', '&#91;')
	content = content.replace(r'\]', '&#93;')
	content = content.replace(r'\(', '&#40;')
	content = content.replace(r'\)', '&#41;')
	content = content.replace(r'\\', '&#92;')
	content = content.replace(r'\/', '&#47;')
	content = content.replace(r'\`', '&#96;')
	content = content.replace(r'\#', '&#35;')
	content = content.replace(r'\|', '&#124;')
	content = content.replace(r'\-', '&#45;')
	content = content.replace(r'\*', '&#42;')
	content = content.replace(r'\.', '&#46;')
	content = content.replace(r'\,', '&#44;')


	# inline hyperlinks
	content = re.sub(r'(?<!\]\()\b(https?:\/\/[\w\-.]{1,}\.[a-z]+)\b', r'<a href="\1">\1</a>', content)

	# left images
	content = re.sub(
		img_left_pattern,
		create_responsive_image(classes=['float-left']),
		content
	)

	# right images
	content = re.sub(
		img_right_pattern,
		create_responsive_image(classes=['float-right']),
		content
	)

	# images
	content = re.sub(
		img_pattern,
		create_responsive_image(),
		content
	)

	# external anchors
	content = re.sub(
		r'\[(.{1,}?)\]\((https?:\/\/[\w\-.\/:?=#]+)\)',
		r'<a href="\2" target="_blank" rel="noreferrer">\1</a>',
		content
	)

	# relative anchors
	content = re.sub(
		r'\[(.{1,}?)\]\(([\w\-.\/:?=#]+)\)',
		r'<a href="\2" target="_blank" aria-label="\1">\1</a>',
		content
	)

	# code block
	content = re.sub(r'```(\w+|)\n?([\0-\255]+)```', hl_codeblock, content)

	# inline code block
	content = re.sub(r'`(.{1,}?)`', r'<code>\1</code>', content)

	# block quote
	content = re.sub(r'^&gt; (.{1,}?)\n', r'<blockquote>\1</blockquote>', content, flags=re.MULTILINE)

	# bold
	content = re.sub(r'\*\*(.{1,}?)\*\*', r'<b>\1</b>', content)

	# italic
	content = re.sub(r'\*(.{1,}?)\*', r'<i>\1</i>', content)

	# center
	content = re.sub(r'\|\|(.{1,}?)\|\|', r'<span class="center">\1</span>', content)

	# titles
	content = re.sub(r'^###### (.+)\n', r'<h6>\1</h6>\n', content, flags=re.MULTILINE)
	content = re.sub(r'^##### (.+)\n', r'<h6>\1</h6>\n', content, flags=re.MULTILINE)
	content = re.sub(r'^#### (.+)\n', r'<h5>\1</h5>\n', content, flags=re.MULTILINE)
	content = re.sub(r'^### (.+)\n', r'<h4>\1</h4>\n', content, flags=re.MULTILINE)
	content = re.sub(r'^## (.+)\n', r'<h3>\1</h3>\n', content, flags=re.MULTILINE)
	content = re.sub(r'^# (.+)\n', r'<h2>\1</h2>\n', content, flags=re.MULTILINE)

	# horizontal rule
	content = re.sub(r'\n([-_*])\1{2,}\n', '<hr>\n', content)


	content = content.replace('\n', '<br>')
	content = content.replace('\t', '&emsp;')
	return content

def remove_markdown(content):
	content = parse_markdown(content)
	content = content.replace('<br>', '\n')
	content = content.replace('<hr>', ' ')
	content = re.sub(r'<.{1,}?>', '', content)
	return content
