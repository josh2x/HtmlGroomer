"""

HTMLGroomer

Groom html to standarize it and make it pretty

Usage:
    groomer = HtmlGroomer(settings, html)
    groomed = groomer.getGroomed()

TODO:
    * &#8209; type entity bug
    * is_inline closing tags
    * Outloook CSS width:100% overwrite with px val from html width
    * Closing tags for v: reduce indent
    * Strip empty attribues which are not boolean eg href="href"

"""

import string
import re
import logging
from html.parser import HTMLParser
from collections import OrderedDict
try:
    from urllib.parse import urlparse
except ImportError:
     from urlparse import urlparse

logging.basicConfig(level=logging.WARNING, format='%(name)s: %(funcName)s: %(message)s') #%(module)s: %(levelname)s:

def sortedDict(old=OrderedDict(), order=[]):
    # singleton utility function
    new = OrderedDict()
    for key in order:
        if key in old.keys():
            new[key] = old[key]
            del old[key]
    # everything else
    for key in sorted(old):
        new[key] = old[key]
    return new


class HtmlGroomer():

    def __init__(self, settings, raw_content):
        self.settings = settings
        self.logger = logging.getLogger('HtmlGroomer')
        self.logger.setLevel(logging.WARNING)
        content = raw_content
        if self.settings.get('indent_conditionals'):
            content = self.hideConditionals(content)
        self.parser = HGParser(self.settings, content)

    def getGroomed(self):
        content = self.parser.stack.groomed_html
        content = self.formatHexColors(content)
        if self.settings.get('indent_conditionals'):
            content = self.revealConditionals(content)
        content = self.customCorrections(content)
        return content

    def formatHexColors(self, content):
        matches = re.compile(self.settings.get('hexcolor_pat'))
        replace = self.formatHexColor
        return matches.sub(replace, content)

    def formatHexColor(self, pat):
        if (len(pat.group(2)) == 3) and self.settings.get('expand_hexcolors'):
            return pat.group(1) + pat.group(2).upper() + pat.group(2).upper() + pat.group(3)
        else:
            return pat.group(1) + pat.group(2).upper() + pat.group(3)

    def hideConditionals(self, content):
        content = re.sub(r'(<!--\[if [^!][^\]]+\])>', r'\1-->', content)
        content = re.sub(r'<(\!\[endif\]-->)', r'<!--\1', content)
        return content

    def revealConditionals(self, content):
        content = re.sub(r'(<!--\[if [^!][^\]]+\])-->', r'\1>', content)
        content = re.sub(r'<!--(!\[endif\]-->)', r'<\1', content)
        return content

    def customCorrections(self, content):
        for key, val in self.settings.get('custom_corrections').items():
            content = content.replace(key, val)
        return content


class HGParser(HTMLParser):

    """
    Feed HTML content and get back an HGStack object containing HGElement objects
    Usage:
        parser = HGParser(settings, html)
        stack = parser.stack
    """

    strict = False
    convert_charrefs = True

    def __init__(self, settings, raw_content):
        super().__init__()
        self.reset()
        self.settings = settings
        self.logger = logging.getLogger('HGParser')
        self.logger.setLevel(logging.WARNING)
        self.stack = HGStack(self.settings, raw_content)
        self._data = ''
        super().feed(raw_content)
        super().close()

    def handle_starttag(self, name, attrs):
        self._feed_data()
        if name in self.settings.get('delete_tags') and not attrs:
            pass
        else:
            if name in self.settings.get('startendtags'):
                self.handle_startendtag(name, attrs)
            else:
                self.stack.feedElement(is_xhtml=self.stack.is_xhtml, kind='starttag', name=name, attrs=attrs)

    def handle_endtag(self, name):
        self._feed_data()
        if name in self.settings.get('delete_tags') and name != self.stack.getLastElement().parent.name:
            pass
        else:
            self.stack.feedElement(kind='endtag', name=name)

    def handle_startendtag(self, name, attrs):
        self._feed_data()
        if name in self.settings.get('delete_tags') and not attrs:
            pass
        else:
            self.stack.feedElement(is_xhtml=self.stack.is_xhtml, kind='startendtag', name=name, attrs=attrs)

    def handle_comment(self, content):
        self._feed_data()
        if re.search(self.settings.get('conditional_pat'), content, re.MULTILINE | re.IGNORECASE):
            name = 'conditional'
        elif re.search(self.settings.get('ampscript_pat'), content, re.MULTILINE | re.IGNORECASE):
            name = 'ampscript'
        else:
            name = 'plain'
        if not name in self.settings.get('delete_tags'):
            self.stack.feedElement(kind='comment', name=name, content=content)

    def handle_decl(self, content):
        self._feed_data()
        name = 'doctype'
        self.stack.feedElement(kind='declaration', name=name, content=content)

    def handle_entityref(self, name):
        self.handle_data('&{};'.format(name))

    def handle_data(self, content):
        last_e = self.stack.getLastElement()
        if (last_e.kind == 'starttag') and last_e.name in self.settings.get('keep_inner_whitespace'):
            name = last_e.name
            content = self.stack.removeBaseIndent(content)
            for line in content.splitlines():
                self.stack.feedElement(kind='data', name=name, content=line)
        else:
            self._data += content

    def _feed_data(self):
        if self._data:
            name = 'text'
            # treat whitespace like a browser, and collapse runs of space
            content = re.sub(r'\s+', ' ', self._data)
            if self.stack.getLastElement().is_not_inline:
                content = content.lstrip()
            if content:
                self.stack.feedElement(kind='data', name=name, content=content)
            self._data = ''


class HGStack():

    """
    HGStack represents an HTML document as an ordered and
    indexed list of HGElement objects. It's not a DOM tree.
    """

    def __init__(self, settings, raw_content):
        self.settings = settings
        self._raw_content = raw_content
        self.logger = logging.getLogger('HGStack')
        self.logger.setLevel(logging.WARNING)
        self.ancestors = []
        self.elements = []
        # self.is_xhtml
        if self.settings.get('force_xhtml'):
            self._is_xhtml = True
        elif re.search(self.settings.get('xhtml_pat'), self._raw_content, re.IGNORECASE):
            self._is_xhtml = True
        else:
            self._is_xhtml = False
        self._break_unit = self.settings.get('break_unit')
        self.tab_size = self.settings.get('tab_size')
        self.use_native_indent = self.settings.get('use_native_indent')
        if self.native_indent != '\t':
            self.indent_tabs = False
            self.native_tab_size = len(self.native_indent)
        else:
            self.indent_tabs = True
            self.native_tab_size = 0
        if self.use_native_indent:
            self._indent_unit = self.native_indent
            self.convert_indent = False
        else:
            self._indent_unit = self.settings.get('indent_unit')
            self.convert_indent = True
        self.logger.info('force_xhtml: {!s}'.format(self.settings.get('force_xhtml')))
        self.logger.info('is_xhtml: {!s}'.format(self.is_xhtml))
        self.logger.info('native_indent: {!r}'.format(self.native_indent))
        self.logger.info('native_tab_size: {}'.format(self.native_tab_size))
        self.logger.info('use_native_indent: {!s}'.format(self.use_native_indent))
        self.logger.info('indent_tabs: {!s}'.format(self.indent_tabs))
        self.logger.info('convert_indent: {!s}'.format(self.convert_indent))
        self.logger.info('indent_unit: {!s}'.format(self.indent_unit))

    @property
    def break_unit(self):
        return self._break_unit

    @property
    def indent_unit(self):
        return self._indent_unit

    @property
    def is_xhtml(self):
        return self._is_xhtml

    @property
    def native_indent(self):
        tabs = []
        spaces = []
        tabs_pat = re.compile(r'^(\t+)', re.MULTILINE)
        spaces_pat = re.compile(r'^( +)', re.MULTILINE)
        for match in tabs_pat.finditer(self._raw_content):
            tabs.append(match.groups())
        for match in spaces_pat.finditer(self._raw_content):
            spaces.append(match.groups())
        if len(tabs) == len(spaces):
            return self.settings.get('indent_unit')
        elif len(tabs) > len(spaces):
            return tabs[0][0]
        else:
            return spaces[0][0]

    @property
    def groomed_html(self):
        elements = self.elements
        spaced_elements = []
        spaced = ''
        for this_e in elements:
            next_e = self.getNextElement(this_e.index)
            last_e = self.getPreviousElement(this_e.index)
            breaks_before = 0
            this_indent = this_e.indent
            # starttag
            if this_e.kind == 'starttag':
                if this_e.is_inline:
                    # this is_not_inline if a child is_not_inline
                    child = next_e
                    while child.name != this_e.name:
                        if child.is_not_inline:
                            this_e.is_inline = False
                        child = self.getNextElement(child.index)
                if last_e.is_inline and this_e.is_inline:
                    this_indent = 0
            # endtag
            elif this_e.kind == 'endtag':
                if last_e.is_inline and this_e.is_inline:
                    this_indent = 0
                else:
                    # find our starttag in prior_e
                    prior_e = last_e
                    while (prior_e.kind != 'starttag') and (prior_e.name != this_e.name):
                        prior_e = self.getPreviousElement(prior_e.index)
                    # if our starttag is_not_inline because something inside is_not_inline neither is this
                    if prior_e.is_not_inline: this_e.is_inline = False
            # text
            elif (this_e.name == 'text') and (this_e.kind == 'data'):
                if last_e.is_inline:
                    this_indent = 0
                    if last_e.kind == 'starttag':
                        # last element was inline start tag
                        this_e.content = this_e.content.lstrip()
                if last_e.is_not_inline:
                    # last element was not inline so strip left
                    this_e.content = this_e.content.lstrip()
                if next_e.is_not_inline:
                    this_e.content = this_e.content.rstrip()
                elif next_e.kind == 'endtag':
                    # next element is inline end tag
                    this_e.content = this_e.content.rstrip()
                if not this_e.content:
                    # skip this_e, it was just whitespace we don't need
                    continue
            # line breaks
            if this_e.index == 0:
                breaks_before = 0
            elif (
                    (this_e.name == 'text') and
                    (this_e.kind == 'data') and
                    (this_e.content == '&nbsp;') and
                    (last_e.kind == 'starttag') and
                    (next_e.kind == 'endtag')
                ):
                # collapse semi-empty containers
                this_indent = 0
                breaks_before = 0
                next_e.is_collapsed = True
            elif this_e.is_collapsed:
                this_indent = 0
                breaks_before = 0
            elif (
                    (last_e.name == this_e.name) and
                    (last_e.kind == 'starttag') and
                    (this_e.kind == 'endtag')
                ):
                # collapse empty containers
                this_indent = 0
                breaks_before = 0
            elif (this_e.name == 'br') and (last_e.name == 'br'):
                # multiple br on the same line
                this_indent = 0
                breaks_before = 0
            elif (last_e.name == 'br') and (this_e.name != 'br'):
                breaks_before += 1
                if last_e.name in self.settings.get('double_break_after'):
                    breaks_before += 1
            elif this_e.is_not_inline or last_e.is_not_inline:
                breaks_before += 1
            # append it
            spaced += self.break_unit * breaks_before
            spaced += self.indent_unit * this_indent
            spaced += this_e.html
            this_e.debug({'breaks_before':breaks_before, 'this_indent': this_indent,})
        return spaced

    def getElement(self, e=None):
        try:
            return self.elements[e]
        except IndexError:
            return HGElement(settings=self.settings)

    def getPreviousElement(self, e):
        return self.getElement(e - 1)

    def getNextElement(self, e):
        return self.getElement(e + 1)

    def getLastElement(self):
        return self.getElement(-1)

    def feedElement(self, is_xhtml=False, kind=None, name=None, content=None, attrs=[]):
        if kind == 'endtag':
            try:
                self.ancestors.pop()
            except IndexError:
                self.logger.warning('*** Extra closing tag. No ancestors to pop.')
        element = HGElement(
            settings=self.settings,
            index=len(self.elements),
            ancestors=list(self.ancestors),
            is_xhtml=is_xhtml,
            kind=kind,
            name=name,
            content=content,
            attrs=attrs,
            )
        self.elements.append(element)
        if kind == 'starttag':
            self.ancestors.append(element)

    def removeBaseIndent(self, content):
        base_pat = '^({})+'.format(self.indent_unit)
        indent_pat = ''
        cleaned = []
        lines = content.splitlines()
        for l, line in enumerate(lines):
            self.logger.debug('{}: {!r}'.format(l, line))
            if line.strip():
                # Is this still needed if sublime handles the conversion?
                if self.convert_indent:
                    line = re.sub(self.native_indent, self.indent_unit, line)
                if not indent_pat:
                    try:
                        base_indent = re.search(base_pat, line).group(0)
                    except AttributeError:
                        base_indent = ''
                    base_count = len(re.findall(self.indent_unit, base_indent))
                    indent_pat = '^{}'.format(self.indent_unit * base_count)
                line = re.sub(indent_pat, '', line, 1)
                cleaned.append(line)
        return self.break_unit.join(cleaned)

    def debugElements(self):
        for this_e in self.elements:
            this_e.debug()


class HGElement():

    """
    HGElement represents one element of an HTML document
    """

    def __init__(self, settings, index=None, ancestors=None, is_xhtml=False, is_collapsed=False, kind=None, name=None, content=None, attrs={}, is_inline=False):
        self.logger = logging.getLogger('HGElement')
        self.logger.setLevel(logging.DEBUG)
        self.settings = settings
        self._index = index
        self._ancestors = ancestors
        self._is_xhtml = is_xhtml
        self._is_collapsed = is_collapsed
        self._kind = kind
        self._name = name
        self._content = content
        self._attributes = {}
        for attr in attrs:
            """
            HtmlParser will return attrs as a list of tuples:
                attr[0] is the attribute name
                attr[1] is the value
                boolean attributes have a value of None
            Interate the list and build a dictionary so we can get()
            """
            self._attributes[attr[0]] = attr[1]
        # inline styles and settings can impact is_inline
        styles = self._attributes.get('style')
        if styles:
            if re.search(r'display:\s*block', styles, re.IGNORECASE):
                self._is_inline = False
            elif re.search(r'display:\s*inline-block', styles, re.IGNORECASE):
                self._is_inline = False
            elif re.search(r'display:\s*none', styles, re.IGNORECASE):
                self._is_inline = False
            elif re.search(r'display:\s*inline', styles, re.IGNORECASE):
                self._is_inline = True
            elif is_inline:
                self._is_inline = True
            else:
                self._is_inline = self.name in self.settings.get('inline_elements')
        else:
            self._is_inline = self.name in self.settings.get('inline_elements')
        self.debug()

    def __repr__(self):
        return self.name

    @property
    def is_xhtml(self):
        return self._is_xhtml

    @property
    def is_text(self):
        if self.kind == 'data' and self.name == 'text':
            return True
        else:
            return False

    @property
    def is_inline(self):
        return self._is_inline

    @is_inline.setter
    def is_inline(self, value):
        self._is_inline = value

    @property
    def is_not_inline(self):
        # "if element.is_not_inline:" reads better than "if not element.is_inline:"
        if self._is_inline:
            return False
        else:
            return True

    @property
    def is_collapsed(self):
        return self._is_collapsed

    @is_collapsed.setter
    def is_collapsed(self, value):
        self._is_collapsed = value

    @property
    def index(self):
        return self._index

    @property
    def attributes(self):
        return self._attributes

    @property
    def ancestors(self):
        return self._ancestors

    @property
    def parent(self):
        try:
            return self.ancestors[-1]
        except IndexError:
            return None

    @property
    def kind(self):
        return self._kind

    @property
    def name(self):
        return self._name

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, value):
        self._content = value

    @property
    def indent(self):
        ancestors = self.ancestors
        try:
            depth = len(ancestors)
        except TypeError:
            return 0
        indent = 0
        for ancestor in ancestors:
            if ancestor.name in self.settings.get('dont_increase_indent'):
                pass
            elif ancestor.is_inline:
                pass
            else:
                indent += 1
        return indent

    @property
    def html(self):
        if self.kind == 'data':
            element = self.content
        elif self.kind == 'declaration':
            element = '<!{}>'.format(self.content)
        elif self.kind == 'entity':
            element = '&{};'.format(self.name)
        elif self.kind == 'comment':
            element = '<!--{}-->'.format(self.content)
        elif self.kind == 'starttag':
            element = "<{}>".format(self.tag_inner)
        elif self.kind == 'startendtag':
            if self.is_xhtml:
                if self.settings.get('never_xhtml') and (self.settings.get('never_xhtml').count(self.name) > 0):
                    element = "<{}>".format(self.tag_inner)
                else:
                    element = "<{} />".format(self.tag_inner)
            else:
                element = "<{}>".format(self.tag_inner)
        elif self.kind == 'endtag':
            element = '</{}>'.format(self.tag_inner)
        return element

    @property
    def tag_inner(self):
        if not self.attributes:
            return self.name
        else:
            attributes = self.attributes
            merged_styles = {}
            # urls
            if attributes.get('href'):
                attributes['href'] = self.fixUrl(attributes['href'])
            # html height and width attributes should not have px
            if attributes.get('height', '').endswith('px'):
                 attributes['height'] = attributes['height'][:-2]
            if attributes.get('width', '').endswith('px'):
                attributes['width'] = attributes['width'][:-2]
            # html emails
            if 'html_email' == self.settings.get('groomer_type'):
                # images
                if self.name == 'img':
                    # Default Movable Ink alt text
                    mi_pat = self.settings.get('movable_ink_pat')
                    if attributes.get('src') and re.search(mi_pat, attributes['src'], re.IGNORECASE):
                        if not attributes.get('alt'):
                            attributes['alt'] = self.settings.get('movable_ink_alt')
                    # always have alt on img
                    if not attributes.get('alt'):
                        attributes['alt'] = ''
                    # always have border on img, default=0
                    if not attributes.get('border'):
                        attributes['border'] = '0'
                # outlook 120dpi fix: add inline css width where html width exists
                if attributes.get('width'):
                    if attributes['width'].endswith('%'):
                        if self.settings.get('merge_percent_width') :
                            merged_styles['width'] = attributes['width']
                    else:
                        merged_styles['width'] = attributes['width'] + 'px'
                    if merged_styles.get('width') and not attributes.get('style'):
                        attributes['style'] = 'width:' + merged_styles['width']
            # format inline css
            if attributes.get('style') and self.settings.get('format_css'):
                attributes['style'] = self.formatCssProps(attributes['style'], merged_styles)
            # sort and flatten attributes
            flat_attrs = []
            for key, val in sortedDict(attributes, self.settings.get('html_attrs_sort_order')).items():
                if val:
                    # standard: <tag key="value" ...
                    flat_attrs.append('{}="{}"'.format(key.strip(), val.strip()))
                elif key == 'alt':
                    # allow empty alt: <tag alt="" ...
                    flat_attrs.append('{}="{}"'.format(key.strip(), val.strip()))
                elif self.is_xhtml:
                    # xhmtl spec: <tag boolattr="boolattr" ...
                    flat_attrs.append('{}="{}"'.format(key.strip(), key.strip()))
                else:
                    # html spec: <tag boolattr ...
                    flat_attrs.append(key.strip())
            return '{} {}'.format(self.name, ' '.join(flat_attrs))

    def formatCssProps(self, content, merge={}):
        # get a list of all css parts and remove empty elements
        parts = re.split(r'([^;"]+);? ?', content)
        parts = list(filter(None, parts))
        # split into dict overriding prop dupes with last one
        properties = {}
        for part in parts:
            try:
                key, val = part.split(':',1)
                properties[key.strip()] = val.strip()
            except ValueError:
                continue
        # expand
        for key, val in self.settings.get('css_props_expanded').items():
            if properties.get(key) and properties[key]:
                properties[key] = val
        # merge in any properties passed
        for key, val in merge.items():
            properties[key] = val
        # reassemble in sorted order stripping leading/trailing spaces
        parts = []
        for key, val in sortedDict(properties, self.settings.get('css_props_sort_order')).items():
            parts.append('{}:{}'.format(key.strip(), val.strip()))
        # flatten parts ensuring ; on the last one
        styles = '; '.join(parts)
        return styles + ';'

    def fixUrl(self, u):
        #TODO fix missing protocol
        url = urlparse(u.strip())
        return url.geturl()

    def debug(self, metadata={}):
        if self.index == 0:
            self.logger.debug('===== =========== =========== = = = =============================================')
            self.logger.debug('   n: kind        name        i x c i = is_inline; x = is_xhtml; c = is_collapsed')
            self.logger.debug('===== =========== =========== = = = =============================================')
        if self.index != None:
            self.logger.debug(
                '{:4}: {:12}{:11}{:2}{:2}{:2}{}{}{}{}'.format(
                    self._index if self._index != None else '',
                    self.kind,
                    self.name,
                    ' i' if self.is_inline else '',
                    ' x' if self.is_xhtml else '',
                    ' c' if self.is_collapsed else '',
                    ' {!r}'.format(metadata) if metadata else '',
                    ' ancestors({}){!r}'.format(len(self.ancestors), self.ancestors) if self.ancestors else ' ancestors(0)',
                    ' attributes{!r}'.format(self.attributes) if self.attributes else '',
                    ' content:{!r}'.format(self.content) if self.content else '',
                    )
                )