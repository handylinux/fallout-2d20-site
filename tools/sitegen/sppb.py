"""
SP Page Builder 5 layout renderer.

Input : a layout (list of sections) from jos_sppagebuilder (`content` or `text` field).
Output: HTML + CSS, following the markup/CSS that SPPB 5 itself emits
        (classes sppb-section / sppb-row-container / sppb-row-column / sppb-addon-wrapper,
         per-element CSS keyed by #section-id-…, #column-id-…, #column-wrap-id-…, #sppb-addon-…).

Breakpoints used by SPPB 5 (Bootstrap 5):
    xl >=1200   lg 992–1199   md 768–991   sm 576–767   xs <576
    media queries: (max-width:1199.98px) (max-width:991.98px) (max-width:767.98px) (max-width:575.98px)
"""
import html
import json
import re

BP = ('xl', 'lg', 'md', 'sm', 'xs')

# подменяется генератором: путь картинки из дампа → путь в статике
MAP_IMG = lambda x: x  # noqa: E731
BP_MAX = {'lg': '1199.98px', 'md': '991.98px', 'sm': '767.98px', 'xs': '575.98px'}

# settings that carry no meaning for us and must not be copied anywhere
DROP = {
    'icon', 'acl', 'admin_label', 'while_scroll_view', 'mouse_movement', 'collapse',
    'instFormId', 'background_gradient', 'gradient_overlay', 'global_background_gradient',
    'global_gradient_overlay', 'pattern_overlay', 'global_pattern_overlay',
    'overlay_pattern_color', 'global_overlay_pattern_color',
    'background_parallax', 'external_background_video', 'video_loop',
    'background_position_custom_x', 'background_position_custom_y',
    'background_size_custom', 'shape_name', 'shape_color', 'shape_width', 'shape_height',
    'shape_flip', 'shape_invert', 'shape_to_front', 'bottom_shape_name', 'bottom_shape_color',
    'bottom_shape_width', 'bottom_shape_height', 'bottom_shape_flip', 'bottom_shape_invert',
    'bottom_shape_to_front', 'global_seclect_position', 'global_custom_position',
    'global_use_animation', 'global_animationduration', 'global_animationdelay',
    'enable_animation', 'animationduration', 'animationdelay', 'blend_mode',
    'transform', 'use_global_width', 'global_user_border', 'global_border_width',
    'global_boxshadow', 'boxshadow', 'row_boxshadow', 'row_border_style', 'row_border',
    'global_use_overlay', 'title_position', 'title_icon_position', 'custom_letterspacing',
    'heading_selector_row',
}


# --------------------------------------------------------------------------- helpers
def esc(s):
    return html.escape(str(s), quote=True)


def tr(v):
    """json value -> html-safe text"""
    return esc(v).replace('\n', '<br>')


def clean(obj):
    """Strip empty/default junk so the resulting JSON is readable."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in DROP:
                continue
            c = clean(v)
            if c is None or c == '' or c == [] or c == {} or c is False:
                continue
            if isinstance(c, dict) and (not c or set(c) <= {'unit'}):
                continue
            out[k.strip()] = c
        return out
    if isinstance(obj, list):
        return [clean(x) for x in obj if x is not None]
    if isinstance(obj, str):
        return obj.strip()
    return obj


def px(v):
    """'125' -> '125px' (SPPB stores unitless numbers in some fields)"""
    if v is None:
        return ''
    v = str(v).strip()
    if not v or v == 'px':
        return ''
    if re.fullmatch(r'-?\d+(\.\d+)?px', v):
        return v
    if re.fullmatch(r'-?\d+(\.\d+)?', v):
        return v + 'px'
    return v


# --------------------------------------------------------------------------- layout index
class Layout:
    def __init__(self, rows):
        self.rows = rows or []
        self.by_id = {}
        self.consumed = set()
        self._index(self.rows)

    def _index(self, nodes):
        for n in nodes:
            nid = str(n.get('id'))
            self.by_id[nid] = n
            for c in n.get('columns', []):
                self._index([c])
                for a in c.get('addons', []):
                    self._index([a])
            for a in n.get('addons', []):
                pass

    def take(self, rid):
        """Pop a nested row that lives in the flat list but belongs to an addon item."""
        node = self.by_id.get(str(rid))
        if node is not None:
            self.consumed.add(str(rid))
        return node

    def top_level(self):
        return [r for r in self.rows if str(r.get('id')) not in self.consumed]


def parent_of(node):
    p = node.get('parent')
    if isinstance(p, dict):
        return p
    return None


# --------------------------------------------------------------------------- layout сетки
def layout_ratios(layout, count):
    """'3+3+3+3' / '4,8' / '6.0+6.0' → [25.0, 25.0, 25.0, 25.0] (проценты ширины колонки)."""
    if not layout or not count:
        return []
    parts = [p for p in str(layout).replace(',', '+').split('+') if p.strip()]
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return []
    if len(nums) != count:
        return []
    total = sum(nums)
    if total <= 0:
        return []
    return [round(n / total * 100, 6) for n in nums]


def col_class(pct):
    """25.0 → 'sppb-col-md-3' (сетка SPPB 12 колонок)."""
    if pct is None:
        return ''
    n = int(round(pct / 100 * 12))
    if n < 1 or n > 12:
        return ''
    return 'sppb-col-md-%d' % n


# --------------------------------------------------------------------------- CSS utils
def spacing_decl(prop, value, important=False):
    """'15px 0px 15px 0px' -> 'padding-top:15px;padding-right:0px;…'"""
    if not value:
        return ''
    parts = [p for p in str(value).replace('  ', ' ').split(' ') if p.strip() != ''] or []
    parts = [px(p) for p in parts]
    if not parts:
        return ''
    if len(parts) == 1:
        parts = parts * 4
    elif len(parts) == 2:
        parts = [parts[0], parts[1], parts[0], parts[1]]
    elif len(parts) == 3:
        parts = [parts[0], parts[1], parts[2], parts[1]]
    names = ('top', 'right', 'bottom', 'left')
    return ''.join('%s-%s:%s%s;' % (prop, n, v, ' !important' if important else '')
                   for n, v in zip(names, parts) if v)


def responsive(base_sel, css_base, per_bp):
    """per_bp: {'lg': 'decls', 'md': …, 'sm': …, 'xs': …}"""
    out = css_base
    for bp in ('lg', 'md', 'sm', 'xs'):
        d = per_bp.get(bp)
        if d:
            out += '@media (max-width:%s){%s{%s}}' % (BP_MAX[bp], base_sel, d)
    return out


def spacing_responsive(sel, prop, value_obj):
    """value_obj = {'xl': '15px 0px', 'md': '0px'} — xl is the base, the rest are media queries."""
    if not isinstance(value_obj, dict):
        return spacing_decl(prop, value_obj) and sel + '{' + spacing_decl(prop, value_obj) + '}' or ''
    base = spacing_decl(prop, value_obj.get('xl'))
    out = sel + '{' + base + '}' if base else ''
    for bp in ('lg', 'md', 'sm', 'xs'):
        d = spacing_decl(prop, value_obj.get(bp))
        if d:
            out += '@media (max-width:%s){%s{%s}}' % (BP_MAX[bp], sel, d)
    return out


def size_responsive(sel, prop, value_obj, unit='px'):
    """{'xl': {'value': '19', 'unit': 'px'}, 'sm': {...}}"""
    if not isinstance(value_obj, dict):
        return ''
    def decl(v):
        if isinstance(v, dict):
            val = (v.get('value') or '').strip()
            u = v.get('unit') or unit
            return ('%s:%s%s;' % (prop, val, u)) if val else ''
        val = str(v).strip()
        return ('%s:%s%s;' % (prop, val, unit)) if val else ''
    out = decl(value_obj.get('xl'))
    css = sel + '{' + out + '}' if out else ''
    for bp in ('lg', 'md', 'sm', 'xs'):
        d = decl(value_obj.get(bp))
        if d:
            css += '@media (max-width:%s){%s{%s}}' % (BP_MAX[bp], sel, d)
    return css


def num_responsive(sel, prop, value_obj, unit='px'):
    if not isinstance(value_obj, dict):
        return ('%s{%s:%s%s;}' % (sel, prop, px(value_obj), unit)) if value_obj not in (None, '') else ''
    def decl(v):
        v = str(v).strip() if v is not None else ''
        if not v:
            return ''
        return '%s:%s%s;' % (prop, v, '' if v.endswith(('px', '%', 'em', 'rem', 'vh', 'vw')) else unit)
    out = decl(value_obj.get('xl'))
    css = sel + '{' + out + '}' if out else ''
    for bp in ('lg', 'md', 'sm', 'xs'):
        d = decl(value_obj.get(bp))
        if d:
            css += '@media (max-width:%s){%s{%s}}' % (BP_MAX[bp], sel, d)
    return css


def align_class(alignment, prefix='sppb-text'):
    """{'xl': 'center'} / 'sppb-text-left' -> bootstrap-ish class handled in CSS"""
    if isinstance(alignment, dict):
        return (alignment.get('xl') or '').strip()
    return str(alignment or '').strip()


def gradient_css(g):
    if not isinstance(g, dict):
        return ''
    c1, c2 = g.get('color'), g.get('color2')
    if not c1:
        return ''
    if g.get('type') == 'radial':
        return 'background-image:radial-gradient(at %s, %s, %s);' % (
            g.get('radialPos', 'center center'), c1, c2 or c1)
    return 'background-image:linear-gradient(%sdeg, %s, %s);' % (g.get('deg', 45), c1, c2 or c1)


def bg_decls(settings, prefix=''):
    """background / overlay declarations shared by sections, columns and addons."""
    p = prefix
    t = settings.get(p + 'background_type') or 'none'
    out = ''
    if t == 'color':
        c = settings.get(p + 'background_color')
        if c:
            out += 'background-color:%s;' % c
    elif t == 'image':
        i = settings.get(p + 'background_image')
        src = i.get('src') if isinstance(i, dict) else i
        if src:
            out += 'background-image:url(%s);' % MAP_IMG(src)
            out += 'background-repeat:%s;' % (settings.get(p + 'background_repeat') or 'no-repeat')
            size = settings.get(p + 'background_size') or 'cover'
            out += 'background-size:%s;' % size
            att = settings.get(p + 'background_attachment')
            if att:
                out += 'background-attachment:%s;' % att
            pos = settings.get(p + 'background_position')
            if pos:
                out += 'background-position:%s;' % pos
    elif t == 'gradient':
        out += gradient_css(settings.get(p + 'background_gradient'))
    ov = settings.get('overlay') or settings.get(p + 'overlay')
    if ov and ov != 'overlay_none':
        out += 'position:relative;'
    return out


def overlay_html(settings, cls='sppb-addon-overlayer'):
    t = settings.get('overlay_type') or settings.get('global_overlay_type') or ''
    if t == 'overlay_color':
        g = settings.get('gradient_overlay') or settings.get('global_gradient_overlay') or {}
        if g.get('color'):
            return '<div class="%s" style="background-color:%s;"></div>' % (cls, g['color'])
    elif t == 'overlay_gradient':
        g = settings.get('gradient_overlay') or settings.get('global_gradient_overlay') or {}
        if g.get('color'):
            return '<div class="%s" style="%s"></div>' % (cls, gradient_css(g))
    return ''


# --------------------------------------------------------------------------- renderer
class Renderer:
    def __init__(self, layout_rows, ctx):
        self.L = Layout(layout_rows)
        self.ctx = ctx          # {'link': fn(url, kind), 'img': fn(src)}
        self.css = []

    # ---------------------------------------------------------------- sections
    def render(self):
        out = []
        for row in self.L.top_level():
            if isinstance(parent_of(row), dict):
                continue
            out.append(self.section(row))
            self.css.append(self.section_css(row))
        return '\n'.join(x for x in out if x)

    def section(self, row):
        s = row.get('settings') or {}
        sid = row.get('id')
        classes = ['sppb-section']
        for bp, suf in (('xl', ''), ('lg', '-lg'), ('md', '-md'), ('sm', '-sm'), ('xs', '-xs')):
            if str(s.get('hidden_' + bp, '')).strip() in ('1', 'true'):
                classes.append('sppb-hidden' + suf)
        if str(s.get('fullscreen', 0)) in ('1', 'true'):
            classes.append('sppb-section-fullscreen')
        extra = (s.get('class') or '')
        if extra:
            classes.append(extra)
        body = self.row_inner(row)
        head = ''
        if s.get('show_top_shape'):
            head += '<div class="sppb-shape-container sppb-top-shape"></div>'
        if s.get('show_bottom_shape'):
            head += '<div class="sppb-shape-container sppb-bottom-shape"></div>'
        return ('<section id="section-id-%s" class="%s">%s<div class="sppb-row-container">%s</div></section>'
                % (esc(sid), ' '.join(classes), head, body))

    def row_inner(self, row):
        s = row.get('settings') or {}
        rclasses = ['sppb-row']
        if str(s.get('no_gutter', 0)) in ('1', 'true'):
            rclasses.append('sppb-no-gutter')
        if str(s.get('columns_align_center', 0)) in ('1', 'true'):
            rclasses.append('sppb-row-align-center')
        cols = []
        ratios = layout_ratios(row.get('layout'), len(row.get('columns') or []))
        for i, col in enumerate(row.get('columns', [])):
            cols.append(self.column(col, ratios[i] if i < len(ratios) else None))
        return '<div class="%s">%s</div>' % (' '.join(rclasses), ''.join(cols))

    def column(self, col, pct=None):
        cid = col.get('id')
        addons = []
        for a in col.get('addons', []):
            addons.append(self.addon(a))
        inner = ''.join(addons)
        classes = 'sppb-row-column sppb-col' + (' ' + col_class(pct) if col_class(pct) else '')
        return ('<div id="column-wrap-id-%s" class="%s">'
                '<div id="column-id-%s" class="sppb-column"><div class="sppb-column-addons">%s</div></div></div>'
                % (esc(cid), classes, esc(cid), inner))

    def addon(self, addon):
        name = addon.get('name')
        s = addon.get('settings') or {}
        aid = addon.get('id')
        fn = getattr(self, 'addon_' + name, None)
        if fn is None:
            inner = '<!-- addon %s is not implemented yet -->' % esc(name)
        else:
            inner = fn(addon, s)
        if not inner:
            return ''
        classes = 'clearfix sppb-addon sppb-addon-%s' % name.replace('_', '-')
        if s.get('class'):
            classes += ' ' + s['class']
        hidden = ''
        for bp, suf in (('xl', ''), ('lg', '-lg'), ('md', '-md'), ('sm', '-sm'), ('xs', '-xs')):
            if str(s.get('hidden_' + bp, '')).strip() in ('1', 'true'):
                classes += ' sppb-hidden' + suf
        return ('<div id="sppb-addon-wrapper-%s" class="sppb-addon-wrapper">'
                '<div id="sppb-addon-%s" class="%s">%s</div></div>'
                % (esc(aid), esc(aid), classes, inner))

    # ---------------------------------------------------------------- CSS
    def section_css(self, row):
        s = row.get('settings') or {}
        sid = '#section-id-%s' % row.get('id')
        css = ''
        bg = bg_decls(s)
        if bg:
            css += '.sp-page-builder .page-content %s{%s}' % (sid, bg)
        sp = spacing_responsive('.sp-page-builder .page-content ' + sid, 'padding', s.get('padding'))
        css += sp if sp else ''
        mg = spacing_responsive('.sp-page-builder .page-content ' + sid, 'margin', s.get('margin'))
        css += mg if mg else ''
        if s.get('section_height'):
            css += num_responsive(sid, 'min-height', s.get('section_height'))
        if s.get('row_max_width'):
            css += num_responsive(sid + '>.sppb-row-container', 'max-width', s.get('row_max_width'))
        if s.get('row_min_width'):
            css += num_responsive(sid + '>.sppb-row-container', 'min-width', s.get('row_min_width'))
        if s.get('columns_content_alignment'):
            css += '%s .sppb-column-addons{justify-content:%s;}' % (sid, s['columns_content_alignment'])
        ratios = layout_ratios(row.get('layout'), len(row.get('columns') or []))
        cols_css = ''.join(self.column_css(c, ratios[i] if i < len(ratios) else None)
                           for i, c in enumerate(row.get('columns', [])))
        addons_css = ''.join(self.addon_css(a) for c in row.get('columns', [])
                             for a in c.get('addons', []))
        return css + cols_css + addons_css

    def column_css(self, col, pct=None):
        s = col.get('settings') or {}
        cid = col.get('id')
        sel = '#column-id-%s' % cid
        wrap = '#column-wrap-id-%s' % cid
        css = ''
        bg = bg_decls(s)
        if bg:
            css += sel + '{' + bg + '}'
        w = s.get('width') or {}
        if isinstance(w, dict):
            base = w.get('xl')
            if base in ('0%', '', None) and pct:
                # SPPB хранит ширину строкой layout секции, а в колонке — нули
                base = '%s%%' % (round(pct, 6))
            if base and base not in ('0%', ''):
                css += '%s{max-width:%s;flex-basis:%s;}' % (wrap, base, base)
            for bp in ('lg', 'md', 'sm', 'xs'):
                v = w.get(bp)
                if v and v != base:
                    css += '@media (max-width:%s){%s{max-width:%s;flex-basis:%s;}}' % (BP_MAX[bp], wrap, v, v)
        css += spacing_responsive(sel, 'padding', s.get('padding'))
        css += spacing_responsive(sel, 'margin', s.get('margin'))
        if s.get('items_content_alignment'):
            css += '%s .sppb-addon-wrapper{text-align:%s;}' % (sel, s['items_content_alignment'])
        if str(s.get('items_align_center', 0)) in ('1', 'true'):
            css += '%s .sppb-column-addons{align-items:center;}' % sel
        if s.get('border_radius') not in (None, '', 0, '0'):
            css += num_responsive(sel, 'border-radius', s.get('border_radius'))
        bs = s.get('boxshadow')
        if isinstance(bs, dict) and bs.get('enabled'):
            css += '%s{box-shadow:%s %s %s %s %s;}' % (
                sel, px(bs.get('ho') or 0), px(bs.get('vo') or 0), px(bs.get('blur') or 0),
                px(bs.get('spread') or 0), bs.get('color') or '#000')
        custom = s.get('custom_css')
        if custom:
            css += custom
        return css

    def addon_css(self, addon):
        s = addon.get('settings') or {}
        aid = addon.get('id')
        sel = '#sppb-addon-%s' % aid
        wrap = '#sppb-addon-wrapper-%s' % aid
        css = ''
        bg = bg_decls(s, prefix='global_')
        if s.get('global_background_type') not in (None, '', 'none'):
            css += sel + '{' + bg + '}'
        css += spacing_responsive(sel, 'padding',
                                  s.get('global_padding') or s.get('global_padding'))
        m = s.get('global_margin')
        if m:
            css += spacing_responsive(wrap, 'margin', m)
        if s.get('global_text_color'):
            css += sel + '{color:%s;}' % s['global_text_color']
        if s.get('global_link_color'):
            css += '%s a{color:%s;}' % (sel, s['global_link_color'])
        if s.get('global_link_hover_color'):
            css += '%s a:hover,%s a:focus,%s a:active{color:%s;}' % (
                sel, sel, sel, s['global_link_hover_color'])
        br = s.get('global_border_radius')
        if br not in (None, '', 0, '0', {}):
            css += num_responsive(sel, 'border-radius', br)
        if s.get('global_custom_css'):
            css += s['global_custom_css']
        css += getattr(self, '_css_' + addon.get('name'), lambda a, s: '')(addon, s)
        return css

    # ---------------------------------------------------------------- addons: content
    def addon_heading(self, addon, s):
        title = s.get('title') or ''
        if not title:
            return ''
        tag = s.get('heading_selector') or 'h2'
        align = align_class(s.get('alignment'))
        cls = 'sppb-addon sppb-addon-header' + (' ' + align if align else '')
        link = s.get('title_link') if isinstance(s.get('title_link'), dict) else {}
        url = self.ctx['link'](link) if link else ''
        inner = '<%s class="sppb-addon-title">%s</%s>' % (tag, tr(title), tag)
        if url:
            target = ' target="_blank" rel="noopener noreferrer"' if link.get('new_tab') else ''
            inner = '<a href="%s"%s>%s</a>' % (esc(url), target, inner)
        return '<div class="%s">%s</div>' % (cls, inner)

    def _css_heading(self, addon, s):
        sel = '#sppb-addon-%s' % addon.get('id')
        css = ''
        align = align_class(s.get('alignment'))
        if align:
            css += '%s .sppb-addon-header{text-align:%s;}' % (sel, align)
        t = sel + ' .sppb-addon-header .sppb-addon-title'
        typ = s.get('heading_typography') or {}
        decls = ''
        if typ.get('weight'):
            decls += 'font-weight:%s;' % typ['weight']
        if typ.get('uppercase'):
            decls += 'text-transform:uppercase;'
        if typ.get('italic'):
            decls += 'font-style:italic;'
        if typ.get('underline'):
            decls += 'text-decoration:underline;'
        if typ.get('font'):
            decls += 'font-family:%s;' % typ['font']
        if decls:
            css += t + '{' + decls + '}'
        css += size_responsive(t, 'font-size', typ.get('size') or {})
        css += size_responsive(t, 'line-height', typ.get('line_height') or {})
        css += size_responsive(t, 'letter-spacing', typ.get('letter_spacing') or {})
        ts = s.get('title_text_shadow')
        if isinstance(ts, dict) and ts.get('enabled'):
            css += '%s{text-shadow:%s %s %s %s;}' % (
                t, px(ts.get('ho') or 0), px(ts.get('vo') or 0), px(ts.get('blur') or 0),
                ts.get('color') or '')
        elif isinstance(ts, str) and ts not in ('', '0 0 0 #ffffff'):
            css += '%s{text-shadow:%s;}' % (t, ts)
        col = s.get('title_color')
        if isinstance(col, dict) and col.get('color'):
            css += t + '{color:%s;}' % col['color']
        elif isinstance(col, str) and col:
            css += t + '{color:%s;}' % col
        css += spacing_responsive(t, 'margin', s.get('title_margin') or {})
        css += spacing_responsive(t, 'padding', s.get('title_padding') or {})
        return css

    def addon_text_block(self, addon, s):
        title = s.get('title') or ''
        tag = s.get('heading_selector') or 'h3'
        align = align_class(s.get('alignment'))
        cls = 'sppb-addon sppb-addon-text-block'
        if align:
            cls += ' ' + align
        if str(s.get('dropcap', 0)) in ('1', 'true'):
            cls += ' sppb-dropcap'
        text = self.ctx['text'](s.get('text') or '')
        h = '<div class="%s">' % cls
        if title:
            h += '<%s class="sppb-addon-title">%s</%s>' % (tag, tr(title), tag)
        h += '<div class="sppb-addon-content">%s</div></div>' % text
        return h

    def _css_text_block(self, addon, s):
        sel = '#sppb-addon-%s' % addon.get('id')
        css = ''
        align = align_class(s.get('alignment'))
        if align and align.startswith('sppb-') is False and align in BP_ALIGN:
            css += '%s .sppb-addon-text-block{text-align:%s;}' % (sel, align)
        typ = s.get('text_typography') or {}
        if typ.get('uppercase'):
            css += '%s .sppb-addon-content{text-transform:uppercase;}' % sel
        css += size_responsive(sel + ' .sppb-addon-content', 'font-size', typ.get('size') or {})
        css += size_responsive(sel + ' .sppb-addon-content', 'line-height', typ.get('line_height') or {})
        if s.get('text_fontsize'):
            css += '%s{font-size:%s;}' % (sel, px(s['text_fontsize']))
        if s.get('text_fontweight'):
            css += '%s{font-weight:%s;}' % (sel, s['text_fontweight'])
        if s.get('text_lineheight'):
            css += '%s{line-height:%s;}' % (sel, px(s['text_lineheight']))
        if s.get('title_text_color'):
            css += '%s .sppb-addon-title{color:%s;}' % (sel, s['title_text_color'])
        if s.get('title_font_style', {}) and isinstance(s.get('title_font_style'), dict):
            if s['title_font_style'].get('uppercase'):
                css += '%s .sppb-addon-title{text-transform:uppercase;}' % sel
        return css

    def addon_image(self, addon, s):
        img = s.get('image') or {}
        src = img.get('src') if isinstance(img, dict) else img
        if not src:
            return ''
        alt = s.get('alt_text') or ''
        pos = align_class(s.get('position'))
        cls = 'sppb-addon sppb-addon-single-image' + (' ' + pos if pos else '')
        url = ''
        link = s.get('link')
        if isinstance(link, dict):
            url = self.ctx['link'](link)
        elif isinstance(link, str) and link:
            url = self.ctx['raw_link'](link)
        pic = '<img class="sppb-img-responsive" src="%s" alt="%s" loading="lazy">' % (
            esc(self.ctx['img'](src)), esc(alt))
        if url:
            pic = '<a href="%s">%s</a>' % (esc(url), pic)
        return ('<div class="%s"><div class="sppb-addon-content">'
                '<div class="sppb-addon-single-image-container">%s</div></div></div>' % (cls, pic))

    def _css_image(self, addon, s):
        sel = '#sppb-addon-%s' % addon.get('id')
        css = ''
        pos = align_class(s.get('position'))
        if pos:
            css += '%s .sppb-addon-single-image-container{text-align:%s;}' % (sel, pos)
        w = s.get('image_width') or {}
        if isinstance(w, dict):
            for bp, key in (('xl', ''), ('lg', None), ('md', None), ('sm', None), ('xs', None)):
                pass
            css += num_responsive('%s .sppb-addon-single-image-container img' % sel, 'width', w)
        h = s.get('image_height') or {}
        if isinstance(h, dict) and any(str(v).strip() for v in h.values()):
            css += num_responsive('%s .sppb-addon-single-image-container img' % sel, 'height', h)
            css += '%s .sppb-addon-single-image-container img{object-fit:cover;}' % sel
        if s.get('border_radius') not in (None, '', 0, '0'):
            css += num_responsive('%s .sppb-addon-single-image-container img' % sel,
                                  'border-radius', s.get('border_radius'))
        return css

    def addon_raw_html(self, addon, s):
        body = s.get('html') or ''
        if not body:
            return ''
        title = s.get('title') or ''
        tag = s.get('heading_selector') or 'h3'
        h = '<div class="sppb-addon sppb-addon-raw-html">'
        if title:
            h += '<%s class="sppb-addon-title">%s</%s>' % (tag, tr(title), tag)
        h += '<div class="sppb-addon-content">%s</div></div>' % body
        return h

    def addon_empty_space(self, addon, s):
        return '<div class="sppb-addon sppb-addon-empty-space"><div class="sppb-empty-space"></div></div>'

    def _css_empty_space(self, addon, s):
        gap = s.get('gap') or {}
        if not isinstance(gap, dict):
            return ''
        return num_responsive('#sppb-addon-%s .sppb-empty-space' % addon.get('id'), 'height', gap)

    def addon_divider(self, addon, s):
        t = s.get('divider_type') or 'border'
        if t != 'border':
            return ''
        w = s.get('container_div_width') or {}
        style = 'border-top:%s %s %s;' % (
            px(s.get('border_width') or 1), s.get('border_style') or 'solid',
            s.get('border_color') or '#ccc')
        return ('<div class="sppb-addon sppb-addon-divider"><div class="sppb-divider" style="%s"></div></div>'
                % style)

    def _css_divider(self, addon, s):
        sel = '#sppb-addon-%s .sppb-divider' % addon.get('id')
        css = num_responsive(sel, 'width', s.get('container_div_width') or {})
        css += num_responsive(sel, 'margin-top', s.get('margin_top') or {})
        css += num_responsive(sel, 'margin-bottom', s.get('margin_bottom') or {})
        return css

    # ---------------------------------------------------------------- addons: repeatable
    def addon_accordion(self, addon, s):
        items = s.get('sp_accordion_item') or []
        if not items:
            return '<div class="sppb-addon sppb-addon-accordion"></div>'
        aid = addon.get('id')
        acc_id = 'sppb-acc-%s' % aid
        html_out = ['<div class="sppb-addon sppb-addon-accordion">',
                    '<div class="sppb-accordion" id="%s">' % acc_id]
        for i, item in enumerate(items):
            title = item.get('title') or ''
            content_html = self.item_content(item)
            open_cls = ' show' if (s.get('openitem') == 'show' and i == 0) else ''
            coll = '' if (s.get('openitem') == 'show' and i == 0) else ' collapsed'
            exp = 'true' if open_cls else 'false'
            html_out.append(
                '<div class="sppb-accordion-item">'
                '<div class="sppb-accordion-item-header">'
                '<a class="sppb-accordion-item-title%s" data-bs-toggle="collapse" href="#%s-item-%d" '
                'aria-expanded="%s">%s</a></div>'
                '<div id="%s-item-%d" class="sppb-accordion-item-body collapse%s">'
                '<div class="sppb-accordion-item-content">%s</div></div></div>'
                % (coll, acc_id, i, exp, tr(title), acc_id, i, open_cls, content_html))
        html_out.append('</div></div>')
        return ''.join(html_out)

    def _css_accordion(self, addon, s):
        sel = '#sppb-addon-%s' % addon.get('id')
        css = ''
        if s.get('item_bg'):
            css += '%s .sppb-accordion-item{background-color:%s;}' % (sel, s['item_bg'])
        bw = s.get('item_border_width')
        if bw not in (None, '', '0'):
            css += '%s .sppb-accordion-item{border:%s solid %s;}' % (
                sel, px(bw), s.get('item_border_color') or '#ddd')
        if s.get('item_border_radius'):
            css += num_responsive(sel + ' .sppb-accordion-item', 'border-radius', s.get('item_border_radius'))
        if s.get('item_spacing'):
            css += num_responsive(sel + ' .sppb-accordion-item', 'margin-bottom', s.get('item_spacing'))
        if s.get('item_title_bg_color'):
            css += '%s .sppb-accordion-item-title{background-color:%s;}' % (sel, s['item_title_bg_color'])
        css += spacing_responsive(sel + ' .sppb-accordion-item-title', 'padding', s.get('item_title_padding') or {})
        css += spacing_responsive(sel + ' .sppb-accordion-item-content', 'padding', s.get('item_content_padding') or {})
        typ = s.get('item_title_typography') or {}
        if typ.get('uppercase'):
            css += '%s .sppb-accordion-item-title{text-transform:uppercase;}' % sel
        css += size_responsive(sel + ' .sppb-accordion-item-title', 'font-size', typ.get('size') or {})
        return css

    def addon_tab(self, addon, s):
        items = s.get('sp_tab_item') or []
        if not items:
            return '<div class="sppb-addon sppb-addon-tab"></div>'
        aid = addon.get('id')
        tid = 'sppb-tab-%s' % aid
        nav_position = s.get('nav_position') or 'top'
        h = ['<div class="sppb-addon sppb-addon-tab"><div class="sppb-tab sppb-tab-%s" id="%s">' % (nav_position, tid),
             '<ul class="sppb-nav sppb-nav-tabs"%s role="tablist">' % (
                 ' style="justify-content:center"' if s.get('nav_justified') else '')]
        for i, item in enumerate(items):
            active = ' active' if i == 0 else ''
            h.append('<li class="sppb-nav-item"><a class="sppb-nav-link%s" id="%s-tab-%d" data-bs-toggle="tab" '
                     'href="#%s-pane-%d" role="tab" aria-selected="%s">%s</a></li>'
                     % (active, tid, i, tid, i, 'true' if i == 0 else 'false', tr(item.get('title') or '')))
        h.append('</ul><div class="sppb-tab-content">')
        for i, item in enumerate(items):
            active = ' show active' if i == 0 else ''
            h.append('<div class="sppb-tab-pane%s" id="%s-pane-%d" role="tabpanel">%s</div>'
                     % (active, tid, i, self.item_content(item)))
        h.append('</div></div></div>')
        return ''.join(h)

    def _css_tab(self, addon, s):
        sel = '#sppb-addon-%s' % addon.get('id')
        css = ''
        if s.get('active_tab_bg'):
            css += '%s .sppb-nav-link.active{background-color:%s;}' % (sel, s['active_tab_bg'])
        if s.get('active_tab_color'):
            css += '%s .sppb-nav-link.active{color:%s;}' % (sel, s['active_tab_color'])
        if s.get('nav_color'):
            css += '%s .sppb-nav-link{color:%s;}' % (sel, s['nav_color'])
        if s.get('nav_bg_color'):
            css += '%s .sppb-nav-link{background-color:%s;}' % (sel, s['nav_bg_color'])
        if s.get('content_padding'):
            css += spacing_responsive(sel + ' .sppb-tab-content', 'padding', s.get('content_padding'))
        return css

    def addon_table_advanced(self, addon, s):
        heads = s.get('sp_table_advanced_item') or []
        rows = s.get('table_advanced_item') or []
        if not heads and not rows:
            return ''
        aid = addon.get('id')
        h = ['<div class="sppb-addon sppb-addon-table-advanced">',
             '<div class="sppb-addon-content">',
             '<div class="sppb-addon-table-main" id="sppb-table-%s">' % aid,
             '<table class="sppb-table"><thead><tr>']
        for cell in heads:
            h.append('<th>%s</th>' % self.cell_html(cell))
        h.append('</tr></thead><tbody>')
        for row in rows:
            cells = row.get('table_advanced_item') if isinstance(row, dict) else None
            if cells is None:
                cells = row if isinstance(row, list) else []
            h.append('<tr>')
            for cell in cells:
                h.append('<td>%s</td>' % self.cell_html(cell))
            h.append('</tr>')
        h.append('</tbody></table></div></div></div>')
        return ''.join(h)

    def _css_table_advanced(self, addon, s):
        sel = '#sppb-addon-%s' % addon.get('id')
        css = ''
        if s.get('header_bg_color'):
            css += '%s .sppb-table th{background:%s;}' % (sel, s['header_bg_color'])
        if s.get('header_color'):
            css += '%s .sppb-table th{color:%s;}' % (sel, s['header_color'])
        if s.get('tr_bg_color'):
            css += '%s .sppb-table tbody tr{background:%s;}' % (sel, s['tr_bg_color'])
        if s.get('table_text_alignment'):
            css += '%s .sppb-table{%s}' % (sel, 'text-align:%s;' % s['table_text_alignment'])
        css += spacing_responsive(sel + ' .sppb-table td', 'padding', s.get('td_padding') or {})
        if s.get('global_width'):
            css += num_responsive(sel + ' .sppb-addon-table-main', 'width', s.get('global_width'))
        return css

    def addon_feature(self, addon, s):
        title = s.get('title') or ''
        text = self.ctx['text'](s.get('text') or '')
        icon = s.get('icon_name') or ''
        h = ['<div class="sppb-addon sppb-addon-feature %s">' % (s.get('alignment') or '')]
        if icon:
            h.append('<div class="sppb-icon"><span class="%s" aria-hidden="true"></span></div>' % esc(icon))
        if title:
            h.append('<%s class="sppb-addon-title">%s</%s>' % (s.get('heading_selector') or 'h3', tr(title),
                                                              s.get('heading_selector') or 'h3'))
        if text:
            h.append('<div class="sppb-addon-content">%s</div>' % text)
        h.append('</div>')
        return ''.join(h)

    def addon_gallery(self, addon, s):
        items = s.get('sp_gallery_item') or []
        if not items:
            return ''
        h = ['<div class="sppb-addon sppb-addon-gallery"><ul class="sppb-gallery gallery-item-%s">'
             % (s.get('item_alignment') or 'left')]
        for it in items:
            src = it.get('thumb') or it.get('image') or ''
            h.append('<li><a href="%s"><img class="sppb-img-responsive" src="%s" alt="%s" loading="lazy"></a></li>'
                     % (esc(self.ctx['img'](src)), esc(self.ctx['img'](src)), esc(it.get('title') or '')))
        h.append('</ul></div>')
        return ''.join(h)

    def addon_articles(self, addon, s):
        return ('<div class="sppb-addon sppb-addon-articles">'
                '<!-- модуль статей: подставляется генератором страниц --></div>')

    def addon_module(self, addon, s):
        t = s.get('module_type') or 'module'
        if t == 'position':
            return ('<div class="sppb-addon sppb-addon-module">'
                    '<!-- позиция модуля: %s --></div>' % esc(s.get('position') or ''))
        mod_id = s.get('id') or s.get('module_id') or ''
        render = self.ctx.get('module') if isinstance(self.ctx, dict) else None
        inner = render(mod_id) if (render and mod_id) else ''
        return '<div class="sppb-addon sppb-addon-module">%s</div>' % (inner or '')

    def addon_navigation(self, addon, s):
        items = s.get('sp_link_list_item') or []
        if len(items) <= 1:
            return ''
        h = ['<div class="sppb-addon sppb-addon-navigation"><ul class="sppb-nav-links">']
        for it in items:
            url = ''
            u = it.get('url')
            if isinstance(u, dict):
                url = self.ctx['link'](u)
            elif isinstance(u, str):
                url = self.ctx['raw_link'](u)
            h.append('<li><a href="%s">%s</a></li>' % (esc(url or '#'), tr(it.get('title') or '')))
        h.append('</ul></div>')
        return ''.join(h)

    # ---------------------------------------------------------------- nested content
    def item_content(self, item):
        """content of an accordion/tab item: list of references to nested rows, or inline addons"""
        out = []
        for ref in item.get('content') or []:
            if not isinstance(ref, dict):
                continue
            rid = ref.get('id')
            if ref.get('type') in ('nested_row', 'row') or ref.get('name') == 'row':
                node = self.L.take(rid)
                if node:
                    out.append(self.nested_row(node))
            else:
                # inline addon (table cells, tab text, …)
                out.append(self.addon(ref))
        return ''.join(out)

    def nested_row(self, row):
        s = row.get('settings') or {}
        rclasses = ['sppb-row']
        if str(s.get('no_gutter', 0)) in ('1', 'true'):
            rclasses.append('sppb-no-gutter')
        cols = ''.join(self.column(c) for c in row.get('columns', []))
        # nested rows also need their generated CSS; keep it inline next to the markup
        css = self.nested_css(row)
        return '<div class="sppb-nested-row"><div class="%s">%s</div>%s</div>' % (
            ' '.join(rclasses), cols, css)

    def nested_css(self, row):
        s = row.get('settings') or {}
        css = ''
        sel = '#section-id-%s' % row.get('id')
        sp = spacing_responsive('.sp-page-builder .page-content ' + sel, 'padding', s.get('padding'))
        css += sp
        bg = bg_decls(s)
        if bg:
            css += '.sp-page-builder .page-content %s{%s}' % (sel, bg)
        css += ''.join(self.column_css(c) for c in row.get('columns', []))
        css += ''.join(self.addon_css(a) for c in row.get('columns', []) for a in c.get('addons', []))
        if not css:
            return ''
        css = css.replace('#section-id-' + str(row.get('id')), '.sppb-nested-row[data-row="%s"]' % row.get('id'))
        return '<style>%s</style>' % css

    def cell_html(self, cell):
        out = []
        for c in cell.get('content') or []:
            if not isinstance(c, dict):
                continue
            nm = c.get('name')
            st = c.get('settings') or {}
            if nm == 'text_block':
                out.append(self.ctx['text'](st.get('text') or ''))
            elif nm == 'heading':
                out.append(tr(st.get('title') or ''))
            elif nm == 'image':
                src = (st.get('image') or {}).get('src') if isinstance(st.get('image'), dict) else st.get('image')
                if src:
                    out.append('<img class="sppb-img-responsive" src="%s" alt="" loading="lazy">'
                               % esc(self.ctx['img'](src)))
            elif nm == 'raw_html':
                out.append(st.get('html') or '')
            else:
                out.append(self.addon(c))
        return ''.join(out)


BP_ALIGN = {'left', 'center', 'right', 'justify', 'start', 'end'}
