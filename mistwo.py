# coding: utf-8
"""
    mistune
    ~~~~~~~

    The fastest markdown parser in pure Python with renderer feature.

    :copyright: (c) 2014 - 2016 by Hsiaoming Yang.
"""

import re
import inspect

__version__ = '0.7.3'
__author__ = 'Hsiaoming Yang <me@lepture.com>'
__all__ = [
    'BlockGrammar', 'BlockLexer',
    'InlineGrammar', 'InlineLexer',
    'Renderer', 'Markdown',
    'markdown', 'escape',
]


_key_pattern = re.compile(r'\s+')
_nonalpha_pattern = re.compile(r'\W')
_escape_pattern = re.compile(r'&(?!#?\w+;)')
_newline_pattern = re.compile(r'\r\n|\r')
_block_quote_leading_pattern = re.compile(r'^ *> ?', flags=re.M)
_inline_tags = [
    'a', 'em', 'strong', 'small', 's', 'cite', 'q', 'dfn', 'abbr', 'data',
    'time', 'code', 'var', 'samp', 'kbd', 'sub', 'sup', 'i', 'b', 'u', 'mark',
    'ruby', 'rt', 'rp', 'bdi', 'bdo', 'span', 'br', 'wbr', 'ins', 'del',
    'img', 'font',
]
_pre_tags = ['pre', 'script', 'style']
_valid_end = r'(?!:/|[^\w\s@]*@)\b'
_valid_attr = r'''\s*[a-zA-Z\-](?:\=(?:"[^"]*"|'[^']*'|\d+))*'''
_block_tag = r'(?!(?:%s)\b)\w+%s' % ('|'.join(_inline_tags), _valid_end)
_scheme_blacklist = ('javascript:', 'vbscript:')


def _pure_pattern(regex):
    pattern = regex.pattern
    if pattern.startswith('^'):
        pattern = pattern[1:]
    return pattern


def _keyify(key):
    return _key_pattern.sub(' ', key.lower())


def escape(text, quote=False, smart_amp=True):
    """Replace special characters "&", "<" and ">" to HTML-safe sequences.

    The original cgi.escape will always escape "&", but you can control
    this one for a smart escape amp.

    :param quote: if set to True, " and ' will be escaped.
    :param smart_amp: if set to False, & will always be escaped.
    """
    if smart_amp:
        text = _escape_pattern.sub('&amp;', text)
    else:
        text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    if quote:
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#39;')
    return text


def escape_link(url):
    """Remove dangerous URL schemes like javascript: and escape afterwards."""
    lower_url = url.lower().strip('\x00\x1a \n\r\t')
    for scheme in _scheme_blacklist:
        if lower_url.startswith(scheme):
            return ''
    return escape(url, quote=True, smart_amp=False)


def preprocessing(text, tab=4):
    text = _newline_pattern.sub('\n', text)
    text = text.expandtabs(tab)
    text = text.replace('\u00a0', ' ')
    text = text.replace('\u2424', '\n')
    pattern = re.compile(r'^ +$', re.M)
    return pattern.sub('', text)


class BlockGrammar(object):
    """Grammars for block level tokens."""

    newline = re.compile(r'^\n+')
    block_code = re.compile(r'^``\n([^\n]+(\n[^\n]+)*\n*)+')
    fences = re.compile(
        r'^ *(`{3,}|~{3,}) *(\S+)? *\n'  # ```lang
        r'([\s\S]+?)\s*'
        r'\1 *(?:\n+|$)'  # ```
    )
    hrule = re.compile(r'^ {0,3}[-*_](?: *[-*_]){2,} *(?:\n+|$)')
    heading = re.compile(r'^ *(#{1,6}) *([^\n]+?) *#* *(?:\n+|$)')
    lheading = re.compile(r'^([^\n]+)\n *(=|-)+ *(?:\n+|$)')
    title = re.compile(r'^ *#! *([^\n]+?) *(?:\n+|$)')
    image = re.compile(
        r'^!\[('
        r'(?:\[[^^\]]*\]|[^\[\]]|\](?=[^\[]*\]))*'
        r')\]\('
        r'''\s*(<)?([\s\S]*?)(?(2)>)\s*'''
        r'\)'
    )
    block_quote = re.compile(r'^( *>[^\n]+(\n[^\n]+)*\n*)+')
    list_block = re.compile(
        r'^( *)([*+-]|\d+\.) [\s\S]+?'
        r'(?:'
        r'\n+(?=\1?(?:[-*_] *){3,}(?:\n+|$))'  # hrule
        r'|\n{2,}'
        r'(?! )'
        r'(?!\1(?:[*+-]|\d+\.) )\n*'
        r'|'
        r'\s*$)'    )
    list_item = re.compile(
        r'^(( *)(?:[*+-]|\d+\.) [^\n]*'
        r'(?:\n(?!\2(?:[*+-]|\d+\.) )[^\n]*)*)',
        flags=re.M
    )
    list_bullet = re.compile(r'^ *(?:[*+-]|\d+\.) +')
    paragraph = re.compile(
        r'^((?:[^\n]+\n?(?!'
        r'%s|%s|%s|%s|%s|%s|%s'
        r'))+)\n*' % (
            _pure_pattern(fences).replace(r'\1', r'\2'),
            _pure_pattern(list_block).replace(r'\1', r'\3'),
            _pure_pattern(hrule),
            _pure_pattern(heading),
            _pure_pattern(lheading),
            _pure_pattern(block_quote),
            '<' + _block_tag,
        )
    )
    table = re.compile(
        r'^ *\|(.+)\n *\|( *[-:]+[-| :]*)\n((?: *\|.*(?:\n|$))*)\n*'
    )
    nptable = re.compile(
        r'^ *(\S.*\|.*)\n *([-:]+ *\|[-| :]*)\n((?:.*\|.*(?:\n|$))*)\n*'
    )
    text = re.compile(r'^[^\n]+')
    equation = re.compile(r'^\$\$ *(\[[^\]*]\])?([^\n]*(?:\n[^\n]*)*\n*)')


class BlockLexer(object):
    """Block level lexer for block grammars."""
    grammar_class = BlockGrammar

    default_rules = [
        'newline', 'hrule', 'block_code', 'fences', 'title', 'image',
        'heading', 'nptable', 'lheading', 'block_quote', 'equation',
        'list_block', 'table', 'paragraph', 'text'
    ]

    list_rules = (
        'newline', 'block_code', 'fences', 'lheading', 'hrule',
        'block_quote', 'list_block', 'text',
    )

    footnote_rules = (
        'newline', 'block_code', 'fences', 'heading',
        'nptable', 'lheading', 'hrule', 'block_quote',
        'list_block', 'table', 'paragraph', 'text'
    )

    def __init__(self, rules=None, **kwargs):
        self.tokens = []

        if not rules:
            rules = self.grammar_class()

        self.rules = rules

    def __call__(self, text, rules=None):
        return self.parse(text, rules)

    def parse(self, text, rules=None):
        text = text.rstrip('\n')

        if not rules:
            rules = self.default_rules

        def manipulate(text):
            for key in rules:
                rule = getattr(self.rules, key)
                m = rule.match(text)
                if not m:
                    continue
                getattr(self, 'parse_%s' % key)(m)
                return m
            return False  # pragma: no cover

        while text:
            m = manipulate(text)
            if m is not False:
                text = text[len(m.group(0)):]
                continue
            if text:  # pragma: no cover
                raise RuntimeError('Infinite loop at: %s' % text)
        return self.tokens

    def parse_newline(self, m):
        length = len(m.group(0))
        if length > 1:
            self.tokens.append({'type': 'newline'})

    def parse_block_code(self, m):
        # clean leading whitespace
        code = m.group(1)
        self.tokens.append({
            'type': 'code',
            'lang': None,
            'text': code,
        })

    def parse_fences(self, m):
        self.tokens.append({
            'type': 'code',
            'lang': m.group(2),
            'text': m.group(3),
        })

    def parse_heading(self, m):
        self.tokens.append({
            'type': 'heading',
            'level': len(m.group(1)),
            'text': m.group(2),
        })

    def parse_lheading(self, m):
        """Parse setext heading."""
        self.tokens.append({
            'type': 'heading',
            'level': 1 if m.group(2) == '=' else 2,
            'text': m.group(1),
        })

    def parse_hrule(self, m):
        self.tokens.append({'type': 'hrule'})

    def parse_list_block(self, m):
        bull = m.group(2)
        self.tokens.append({
            'type': 'list_start',
            'ordered': '.' in bull,
        })
        cap = m.group(0)
        self._process_list_item(cap, bull)
        self.tokens.append({'type': 'list_end'})

    def _process_list_item(self, cap, bull):
        cap = self.rules.list_item.findall(cap)

        _next = False
        length = len(cap)

        for i in range(length):
            item = cap[i][0]

            # remove the bullet
            space = len(item)
            item = self.rules.list_bullet.sub('', item)

            # outdent
            if '\n ' in item:
                space = space - len(item)
                pattern = re.compile(r'^ {1,%d}' % space, flags=re.M)
                item = pattern.sub('', item)

            # determine whether item is loose or not
            loose = _next
            if not loose and re.search(r'\n\n(?!\s*$)', item):
                loose = True

            rest = len(item)
            if i != length - 1 and rest:
                _next = item[rest-1] == '\n'
                if not loose:
                    loose = _next

            if loose:
                t = 'loose_item_start'
            else:
                t = 'list_item_start'

            self.tokens.append({'type': t})
            # recurse
            self.parse(item, self.list_rules)
            self.tokens.append({'type': 'list_item_end'})

    def parse_block_quote(self, m):
        self.tokens.append({'type': 'block_quote_start'})
        # clean leading >
        cap = _block_quote_leading_pattern.sub('', m.group(0))
        self.parse(cap)
        self.tokens.append({'type': 'block_quote_end'})

    def parse_table(self, m):
        item = self._process_table(m)

        cells = re.sub(r'(?: *\| *)?\n$', '', m.group(3))
        cells = cells.split('\n')
        for i, v in enumerate(cells):
            v = re.sub(r'^ *\| *| *\| *$', '', v)
            cells[i] = re.split(r' *\| *', v)

        item['cells'] = cells
        self.tokens.append(item)

    def parse_nptable(self, m):
        item = self._process_table(m)

        cells = re.sub(r'\n$', '', m.group(3))
        cells = cells.split('\n')
        for i, v in enumerate(cells):
            cells[i] = re.split(r' *\| *', v)

        item['cells'] = cells
        self.tokens.append(item)

    def _process_table(self, m):
        header = re.sub(r'^ *| *\| *$', '', m.group(1))
        header = re.split(r' *\| *', header)
        align = re.sub(r' *|\| *$', '', m.group(2))
        align = re.split(r' *\| *', align)

        for i, v in enumerate(align):
            if re.search(r'^ *-+: *$', v):
                align[i] = 'right'
            elif re.search(r'^ *:-+: *$', v):
                align[i] = 'center'
            elif re.search(r'^ *:-+ *$', v):
                align[i] = 'left'
            else:
                align[i] = None

        item = {
            'type': 'table',
            'header': header,
            'align': align,
        }
        return item

    def parse_paragraph(self, m):
        text = m.group(1).rstrip('\n')
        self.tokens.append({'type': 'paragraph', 'text': text})

    def parse_text(self, m):
        text = m.group(0)
        self.tokens.append({'type': 'text', 'text': text})

    def parse_equation(self, m):
        tag = m.group(1)
        tex = m.group(2)
        self.tokens.append({'type': 'equation', 'tag': tag, 'tex': tex})

    def parse_title(self, m):
        text = m.group(1)
        self.tokens.append({'type': 'title', 'text': text})

    def parse_image(self, m):
        title = m.group(1)
        link = m.group(3)
        self.tokens.append({
            'type': 'image',
            'title': title,
            'link': link,
        })

class InlineGrammar(object):
    """Grammars for inline level tokens."""

    escape = re.compile(r'^\\([\\`*{}\[\]()#+\-.!_>~|\$])')  # \* \+ \! ....
    link = re.compile(
        r'\[('
        r'(?:\[[^^\]]*\]|[^\[\]]|\](?=[^\[]*\]))*'
        r')\]\('
        r'''\s*(<)?([\s\S]*?)(?(2)>)(?:\s+['"]([\s\S]*?)['"])?\s*'''
        r'\)'
    )
    reflink = re.compile(r'^@([^\]]+)@')
    double_emphasis = re.compile(
        r'^_{2}([\s\S]+?)_{2}(?!_)'  # __word__
        r'|'
        r'^\*{2}([\s\S]+?)\*{2}(?!\*)'  # **word**
    )
    emphasis = re.compile(
        r'^\b_((?:__|[^_])+?)_\b'  # _word_
        r'|'
        r'^\*((?:\*\*|[^\*])+?)\*(?!\*)'  # *word*
    )
    code = re.compile(r'^`\s*([\s\S]*?[^`])\s*`(?!`)')  # `code`
    linebreak = re.compile(r'^ {2,}\n(?!\s*$)')
    strikethrough = re.compile(r'^~~(?=\S)([\s\S]*?\S)~~')  # ~~word~~
    footnote = re.compile(r'^\^\[([^\]]+)\]')
    text = re.compile(r'^[\s\S]+?(?=[\\<!\[_*`~@\$\^]|https?://| {2,}\n|$)')
    math = re.compile(r'^\$([^\$]+?)\$')

    def hard_wrap(self):
        """Grammar for hard wrap linebreak. You don't need to add two
        spaces at the end of a line.
        """
        self.linebreak = re.compile(r'^ *\n(?!\s*$)')
        self.text = re.compile(
            r'^[\s\S]+?(?=[\\<!\[_*`~]|https?://| *\n|$)'
        )


class InlineLexer(object):
    """Inline level lexer for inline grammars."""
    grammar_class = InlineGrammar

    default_rules = [
        'escape', 'footnote', 'link', 'reflink', 'double_emphasis',
        'emphasis', 'code', 'linebreak', 'strikethrough', 'math', 'text',
    ]

    def __init__(self, renderer, rules=None, **kwargs):
        self.renderer = renderer

        if not rules:
            rules = self.grammar_class()

        kwargs.update(self.renderer.options)
        if kwargs.get('hard_wrap'):
            rules.hard_wrap()

        self.rules = rules

        self._in_link = False
        self._in_footnote = False

    def __call__(self, text, rules=None):
        return self.output(text, rules)

    def setup(self):
        pass

    def output(self, text, rules=None):
        text = text.rstrip('\n')
        if not rules:
            rules = list(self.default_rules)

        if self._in_footnote and 'footnote' in rules:
            rules.remove('footnote')

        output = self.renderer.placeholder()

        def manipulate(text):
            for key in rules:
                pattern = getattr(self.rules, key)
                m = pattern.match(text)
                if not m:
                    continue
                self.line_match = m
                # print(key)
                out = getattr(self, 'output_%s' % key)(m)
                if out is not None:
                    return m, out
            return False  # pragma: no cover

        self.line_started = False
        while text:
            ret = manipulate(text)
            self.line_started = True
            if ret is not False:
                m, out = ret
                output += out
                text = text[len(m.group(0)):]
                continue
            if text:  # pragma: no cover
                raise RuntimeError('Infinite loop at: %s' % text)

        return output

    def output_escape(self, m):
        text = m.group(1)
        return self.renderer.escape(text)

    def output_footnote(self, m):
        text = m.group(1)
        text = self.output(text)
        return self.renderer.footnote(text)

    def output_link(self, m):
        line = m.group(0)
        text = m.group(1)
        link = m.group(3)
        title = m.group(4)

        self._in_link = True
        text = self.output(text)
        self._in_link = False
        return self.renderer.link(link, title, text)

    def output_reflink(self, m):
        tag = m.group(1)
        return self.renderer.reflink(tag)

    def output_double_emphasis(self, m):
        text = m.group(2) or m.group(1)
        text = self.output(text)
        return self.renderer.double_emphasis(text)

    def output_emphasis(self, m):
        text = m.group(2) or m.group(1)
        text = self.output(text)
        return self.renderer.emphasis(text)

    def output_code(self, m):
        text = m.group(1)
        return self.renderer.codespan(text)

    def output_linebreak(self, m):
        return self.renderer.linebreak()

    def output_strikethrough(self, m):
        text = self.output(m.group(1))
        return self.renderer.strikethrough(text)

    def output_text(self, m):
        text = m.group(0)
        return self.renderer.text(text)

    def output_math(self, m):
        tex = m.group(1)
        return self.renderer.math(tex)


class Renderer(object):
    """The default HTML renderer for rendering Markdown.
    """

    def __init__(self, **kwargs):
        self.options = kwargs

    def placeholder(self):
        """Returns the default, empty output value for the renderer.

        All renderer methods use the '+=' operator to append to this value.
        Default is a string so rendering HTML can build up a result string with
        the rendered Markdown.

        Can be overridden by Renderer subclasses to be types like an empty
        list, allowing the renderer to create a tree-like structure to
        represent the document (which can then be reprocessed later into a
        separate format like docx or pdf).
        """
        return ''

    def block_code(self, code, lang=None):
        """Rendering block level code. ``pre > code``.

        :param code: text content of the code block.
        :param lang: language of the given code.
        """
        code = code.rstrip('\n')
        if not lang:
            code = escape(code, smart_amp=False)
            return '<pre><code>%s\n</code></pre>\n' % code
        code = escape(code, quote=True, smart_amp=False)
        return '<pre><code class="lang-%s">%s\n</code></pre>\n' % (lang, code)

    def block_quote(self, text):
        """Rendering <blockquote> with the given text.

        :param text: text content of the blockquote.
        """
        return '<blockquote>%s\n</blockquote>\n' % text.rstrip('\n')

    def block_html(self, html):
        """Rendering block level pure html content.

        :param html: text content of the html snippet.
        """
        if self.options.get('skip_style') and \
           html.lower().startswith('<style'):
            return ''
        if self.options.get('escape'):
            return escape(html)
        return html

    def header(self, text, level, raw=None):
        """Rendering header/heading tags like ``<h1>`` ``<h2>``.

        :param text: rendered text content for the header.
        :param level: a number for the header level, for example: 1.
        :param raw: raw text content of the header.
        """
        return '<div class="sec-title sec-lvl-%d">%s</div>\n' % (level, text)

    def hrule(self):
        """Rendering method for ``<hr>`` tag."""
        if self.options.get('use_xhtml'):
            return '<hr />\n'
        return '<hr>\n'

    def list(self, body, ordered=True):
        """Rendering list tags like ``<ul>`` and ``<ol>``.

        :param body: body contents of the list.
        :param ordered: whether this list is ordered or not.
        """
        tag = 'ul'
        if ordered:
            tag = 'ol'
        return '<%s>\n%s</%s>\n' % (tag, body, tag)

    def list_item(self, text):
        """Rendering list item snippet. Like ``<li>``."""
        return '<li>%s</li>\n' % text

    def paragraph(self, text):
        """Rendering paragraph tags. Like ``<p>``."""
        return '<p>%s</p>\n' % text.strip(' ')

    def table(self, header, body):
        """Rendering table element. Wrap header and body in it.

        :param header: header part of the table.
        :param body: body part of the table.
        """
        return (
            '<table>\n<thead>%s</thead>\n'
            '<tbody>\n%s</tbody>\n</table>\n'
        ) % (header, body)

    def table_row(self, content):
        """Rendering a table row. Like ``<tr>``.

        :param content: content of current table row.
        """
        return '<tr>\n%s</tr>\n' % content

    def table_cell(self, content, **flags):
        """Rendering a table cell. Like ``<th>`` ``<td>``.

        :param content: content of current table cell.
        :param header: whether this is header or not.
        :param align: align of current table cell.
        """
        if flags['header']:
            tag = 'th'
        else:
            tag = 'td'
        align = flags['align']
        if not align:
            return '<%s>%s</%s>\n' % (tag, content, tag)
        return '<%s style="text-align:%s">%s</%s>\n' % (
            tag, align, content, tag
        )

    def double_emphasis(self, text):
        """Rendering **strong** text.

        :param text: text content for emphasis.
        """
        return '<strong>%s</strong>' % text

    def emphasis(self, text):
        """Rendering *emphasis* text.

        :param text: text content for emphasis.
        """
        return '<em>%s</em>' % text

    def codespan(self, text):
        """Rendering inline `code` text.

        :param text: text content for inline code.
        """
        text = escape(text.rstrip(), smart_amp=False)
        return '<code>%s</code>' % text

    def linebreak(self):
        """Rendering line break like ``<br>``."""
        if self.options.get('use_xhtml'):
            return '<br />\n'
        return '<br>\n'

    def strikethrough(self, text):
        """Rendering ~~strikethrough~~ text.

        :param text: text content for strikethrough.
        """
        return '<del>%s</del>' % text

    def text(self, text):
        """Rendering unformatted text.

        :param text: text content.
        """
        if self.options.get('parse_block_html'):
            return text
        return escape(text)

    def escape(self, text):
        """Rendering escape sequence.

        :param text: text content.
        """
        return escape(text)

    def link(self, link, title, text):
        """Rendering a given link with content and title.

        :param link: href link for ``<a>`` tag.
        :param title: title content for `title` attribute.
        :param text: text content for description.
        """
        link = escape_link(link)
        if not title:
            return '<a href="%s">%s</a>' % (link, text)
        title = escape(title, quote=True)
        return '<a href="%s" title="%s">%s</a>' % (link, title, text)

    def image(self, src, title):
        """Rendering a image with title and text.

        :param src: source link of the image.
        :param title: caption text of the image.
        """
        src = escape_link(src)
        if title:
            title = escape(title, quote=True)
            html = '<figure><img src="%s"><figcaption>%s</figcaption></figure>\n' % (src, title)
        else:
            html = '<figure><img src="%s"></figure>\n' % src
        return html

    def reflink(self, tag):
        """Rendering an in document reference.

        :param tag: tag to target.
        """
        html = '<span class="reference" target="%s"></span>'
        return html % tag

    def newline(self):
        """Rendering newline element."""
        return ''

    def footnote(self, text):
        """Rendering the ref anchor of a footnote.

        :param key: identity key for the footnote.
        :param index: the index count of current footnote.
        """
        html = '<span class="footnote">%s</span>'
        return html % text

    def equation(self, tex, tag):
        """Render display math.

        :param tex: tex specification.
        """
        if tag:
            html = '<div class="equation numbered" id="%s">%s</div>\n' % (tag, tex)
        else:
            html = '<div class="equation">%s</div>\n' % tex
        return html

    def math(self, tex):
        """Render inline math.

        :param tex: tex specification.
        """
        html = '<span class="latex">%s</span>'
        return html % tex

    def title(self, text):
        """Render page title.

        :param text: title text.
        """
        html = '<div class="doc-title">%s</div>\n'
        return html % text


class Markdown(object):
    """The Markdown parser.

    :param renderer: An instance of ``Renderer``.
    :param inline: An inline lexer class or instance.
    :param block: A block lexer class or instance.
    """
    def __init__(self, renderer=None, inline=None, block=None, **kwargs):
        if not renderer:
            renderer = Renderer(**kwargs)
        else:
            kwargs.update(renderer.options)

        self.renderer = renderer

        if inline and inspect.isclass(inline):
            inline = inline(renderer, **kwargs)
        if block and inspect.isclass(block):
            block = block(**kwargs)

        if inline:
            self.inline = inline
        else:
            self.inline = InlineLexer(renderer, **kwargs)

        self.block = block or BlockLexer(BlockGrammar())

        # detect if it should parse text in block html
        self._parse_block_html = kwargs.get('parse_block_html')

    def __call__(self, text):
        return self.parse(text)

    def render(self, text):
        """Render the Markdown text.

        :param text: markdown formatted text content.
        """
        return self.parse(text)

    def parse(self, text):
        out = self.output(preprocessing(text))
        return out

    def pop(self):
        if not self.tokens:
            return None
        self.token = self.tokens.pop()
        return self.token

    def peek(self):
        if self.tokens:
            return self.tokens[-1]
        return None  # pragma: no cover

    def output(self, text, rules=None):
        self.tokens = self.block(text, rules)
        self.tokens.reverse()

        self.inline.setup()

        out = self.renderer.placeholder()
        while self.pop():
            out += self.tok()
        return out

    def tok(self):
        t = self.token['type']

        # sepcial cases
        if t.endswith('_start'):
            t = t[:-6]

        return getattr(self, 'output_%s' % t)()

    def tok_text(self):
        text = self.token['text']
        while self.peek()['type'] == 'text':
            text += '\n' + self.pop()['text']
        return self.inline(text)

    def output_newline(self):
        return self.renderer.newline()

    def output_hrule(self):
        return self.renderer.hrule()

    def output_heading(self):
        return self.renderer.header(
            self.inline(self.token['text']),
            self.token['level'],
            self.token['text'],
        )

    def output_code(self):
        return self.renderer.block_code(
            self.token['text'], self.token['lang']
        )

    def output_table(self):
        aligns = self.token['align']
        aligns_length = len(aligns)
        cell = self.renderer.placeholder()

        # header part
        header = self.renderer.placeholder()
        for i, value in enumerate(self.token['header']):
            align = aligns[i] if i < aligns_length else None
            flags = {'header': True, 'align': align}
            cell += self.renderer.table_cell(self.inline(value), **flags)

        header += self.renderer.table_row(cell)

        # body part
        body = self.renderer.placeholder()
        for i, row in enumerate(self.token['cells']):
            cell = self.renderer.placeholder()
            for j, value in enumerate(row):
                align = aligns[j] if j < aligns_length else None
                flags = {'header': False, 'align': align}
                cell += self.renderer.table_cell(self.inline(value), **flags)
            body += self.renderer.table_row(cell)

        return self.renderer.table(header, body)

    def output_block_quote(self):
        body = self.renderer.placeholder()
        while self.pop()['type'] != 'block_quote_end':
            body += self.tok()
        return self.renderer.block_quote(body)

    def output_list(self):
        ordered = self.token['ordered']
        body = self.renderer.placeholder()
        while self.pop()['type'] != 'list_end':
            body += self.tok()
        return self.renderer.list(body, ordered)

    def output_list_item(self):
        body = self.renderer.placeholder()
        while self.pop()['type'] != 'list_item_end':
            if self.token['type'] == 'text':
                body += self.tok_text()
            else:
                body += self.tok()

        return self.renderer.list_item(body)

    def output_loose_item(self):
        body = self.renderer.placeholder()
        while self.pop()['type'] != 'list_item_end':
            body += self.tok()
        return self.renderer.list_item(body)

    def output_paragraph(self):
        return self.renderer.paragraph(self.inline(self.token['text']))

    def output_text(self):
        return self.renderer.paragraph(self.tok_text())

    def output_equation(self):
        return self.renderer.equation(self.token['tex'], self.token['tag'])

    def output_title(self):
        return self.renderer.title(self.inline(self.token['text']))

    def output_image(self):
        return self.renderer.image(self.token['link'], self.inline(self.token['title']))

def markdown(text, escape=True, **kwargs):
    """Render markdown formatted text to html.

    :param text: markdown formatted text content.
    :param escape: if set to False, all html tags will not be escaped.
    :param use_xhtml: output with xhtml tags.
    :param hard_wrap: if set to True, it will use the GFM line breaks feature.
    :param parse_block_html: parse text only in block level html.
    :param parse_inline_html: parse text only in inline level html.
    """
    return Markdown(escape=escape, **kwargs)(text)
