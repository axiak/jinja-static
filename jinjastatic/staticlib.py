import os
import glob
import time
import random
import hashlib
import collections
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

import envoy
import jinjatagext

extensions = {
    'text/css': 'css',
    'text/javascript': 'js',
}

g = {
    'debug': False,
    ('text/css', False): {},
    ('text/javascript', False): {},
    ('text/css', True): {},
    ('text/javascript', True): {},
    'config': {},
    'compiled': {},
    'compsheets': {},
    'minified': {},
}

def _handle_tag(format, type_, ctx, src, **kwargs):
    kwargs.setdefault('type', type_)
    inHead = kwargs.pop('head', False)
    if g['debug']:
        return format.format(
            src,
            u' '.join('{0}={1!r}'.format(k, _force_str(v)) for k, v in kwargs.items()))
    key = (type_, inHead)
    ctxname = ctx.name
    min_dict = g['minified'].setdefault(ctxname, {})
    script_list = g[key]
    if min_dict.get(key):
        return ''
    elif ctxname in script_list and g['compiled']:
        files = OrderedDict([(g['compiled'][orig], 1)
                             for orig in script_list[ctxname]]).keys()
        min_dict[key] = True
        return u'\n'.join(format.format(src, 'type="{0}"'.format(type_))
                          for src in files)
    elif ctxname in script_list:
        script_list[ctxname].append(src)
    else:
        script_list[ctxname] = [src]
    return '**FIRSTPASS**'

@jinjatagext.simple_context_tag
def script(ctx, src, **kwargs):
    return _handle_tag(u'<script src="{0}" {1}></script>', u'text/javascript', ctx,
                       src, **kwargs)


@jinjatagext.simple_context_tag
def style(ctx, href, **kwargs):
    return _handle_tag(u'<link rel="stylesheet" href="{0}" {1}>',
                       u'text/css', ctx, href, **kwargs)


def clear_data():
    g.update({
            ('text/css', False): {},
            ('text/javascript', False): {},
            ('text/css', True): {},
            ('text/javascript', True): {},
            'compiled': {},
            'minified': {},
            })

def set_config(debug, config):
    g['debug'] = debug
    mapper = config.get('map', {})
    config['map'] = {}
    for k, v in mapper.items():
        for f in v:
            config['map'][f] = k
    g['config'] = config

def compile(base_dir, output_dir, dest_dir):
    config = g['config']
    _remove_old_files(output_dir)
    command = {
        'text/javascript': 'uglifyjs {0}',
        'text/css': 'uglifycss {0}',
        }

    rel_output = '/' + output_dir[len(dest_dir):].lstrip('/')

    for key in g:
        if not isinstance(key, tuple):
            continue
        unique_key = _gen_key()
        filemap = g[key]
        ext = extensions[key[0]]
        files = OrderedDict((filename, 1) for template in filemap for filename in filemap[template]).keys()
        file_comp = collections.defaultdict(list)
        for filename in files:
            aggregate = _decorate_key(config['map'].get(filename, 'maincompiled.' + ext), unique_key)
            file_comp[aggregate].append(filename)
        for target, filelist in file_comp.items():
            abstarget = os.path.join(output_dir, target)
            absfilelist = [os.path.join(base_dir, filename.lstrip('/')) for filename in filelist]
            output = envoy.run(command[key[0]].format(' '.join(absfilelist)))
            if output.status_code:
                raise RuntimeError(output.std_err)
            with open(abstarget, 'wb+') as f:
                f.write(output.std_out)
            target = os.path.join(rel_output, target)
            g['compiled'].update(dict((filename, target) for filename in filelist))

def _remove_old_files(output_dir):
    for fname in glob.glob(os.path.join(output_dir, '*_min*')):
        os.unlink(fname)

def _decorate_key(filename, key):
    first, second = filename.rsplit('.', 1)
    return first + '-' + key + '.' + second

def _gen_key():
    return hashlib.md5(str(time.time() + random.random())).hexdigest()[:10] + '_min'


def _force_str(obj):
    if isinstance(obj, unicode):
        return obj.encode('utf8')
    return str(obj)
