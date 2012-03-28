import os
import glob
import time
import pipes
import shutil
import random
import tempfile
import hashlib
import logging
import collections
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

import envoy
import jinjatagext

logger = logging.getLogger('jinjastatic')

extensions = {
    'text/css': 'css',
    'text/javascript': 'js',
    }

pre_compilers = {
    'text/less': ('lessc %(input)s', 'text/css'),
    'text/coffeescript': ('coffee --join %(output)s -c %(input)s', 'text/javascript'),
    }

compilers = {
    'text/javascript': 'uglifyjs %s',
    'text/css': 'uglifycss %s',
    }


g = {
    'debug': False,
    ('text/css', False): {},
    ('text/javascript', False): {},
    ('text/css', True): {},
    ('text/javascript', True): {},
    'temp_dir': tempfile.mkdtemp(prefix='jinjastatic'),
    'config': {},
    'compiled': {},
    'compsheets': {},
    'minified': {},
}

def _handle_tag(format, type_, ctx, src, debug=False, head=False, **kwargs):
    kwargs.setdefault('type', type_)
    if g['debug']:
        return format.format(
            src,
            u' '.join('{0}={1!r}'.format(k, _force_str(v)) for k, v in kwargs.items()))
    elif debug:
        return u''
    key = (type_, head)
    ctxname = ctx.name
    min_dict = g['minified'].setdefault(ctxname, {})

    if min_dict.get(key):
        return ''
    elif ctxname in g.get(key, {}) and g['compiled']:
        files = OrderedDict([(g['compiled'][orig], 1)
                             for orig in g[key][ctxname]]).keys()
        min_dict[key] = True
        return u'\n'.join(format.format(src, 'type="{0}"'.format(type_))
                          for src in files)
    elif type_ in pre_compilers:
        pre_compile(src, type_, head, ctxname)
    else:
        g[key].setdefault(ctxname, []).append(src.lstrip('/'))
    return '**FIRSTPASS**'

@jinjatagext.simple_context_tag
def script(ctx, src, **kwargs):
    return _handle_tag(u'<script src="{0}" {1}></script>', u'text/javascript', ctx,
                       src, **kwargs)


@jinjatagext.simple_context_tag
def style(ctx, href, **kwargs):
    return _handle_tag(u'<link rel="stylesheet" href="{0}" {1}>',
                       u'text/css', ctx, href, **kwargs)

@jinjatagext.simple_context_tag
def less(ctx, href, **kwargs):
    return _handle_tag(u'<link rel="stylesheet/less" href="{0}" {1}>',
                       u'text/less', ctx, href, **kwargs)

@jinjatagext.simple_context_tag
def coffee(ctx, src, **kwargs):
    return _handle_tag(u'<script src="{0}" {1}></script>', u'text/coffeescript', ctx,
                       src, **kwargs)

def clear_data():
    try:
        shutil.rmtree(g['temp_dir'])
    except:
        pass
    g.update({
            ('text/css', False): {},
            ('text/javascript', False): {},
            ('text/css', True): {},
            ('text/javascript', True): {},
            'compiled': {},
            'temp_dir': tempfile.mkdtemp(prefix='jinjastatic'),
            'minified': {},
            })

def set_config(debug, config, base_dir):
    g['debug'] = debug
    g['base_dir'] = base_dir
    mapper = config.get('map', {})
    config['map'] = {}
    for k, v in mapper.items():
        for f in v:
            config['map'][f] = k
    g['config'] = config

def compile(base_dir, output_dir, dest_dir):
    config = g['config']
    _remove_old_files(output_dir)

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
            absfilelist = [os.path.join(base_dir, filename) for filename in filelist]
            logger.info('Compiling {0}'.format(abstarget))
            print compilers[key[0]] % ' '.join(pipes.quote(f) for f in absfilelist)
            output = envoy.run(compilers[key[0]] % ' '.join(pipes.quote(f) for f in absfilelist))
            if output.status_code:
                raise RuntimeError(output.std_err)
            with open(abstarget, 'wb+') as f:
                f.write(output.std_out)
            target = os.path.join(rel_output, target)
            g['compiled'].update(dict((filename, target) for filename in filelist))


g = {
    'debug': False,
    ('text/css', False): {},
    ('text/javascript', False): {},
    ('text/css', True): {},
    ('text/javascript', True): {},
    'temp_dir': tempfile.mkdtemp(prefix='jinjastatic'),
    'config': {},
    'compiled': {},
    'compsheets': {},
    'minified': {},
}

def pre_compile(src, type_, head, ctxname):
    compiler, type_ = pre_compilers[type_]
    key = (type_, head)
    script_list = g[key].setdefault(ctxname, [])
    new_name = os.path.join(g['temp_dir'], hashlib.md5(src).hexdigest())
    if new_name in script_list:
        return
    print new_name
    print os.path.exists(new_name)
    if os.path.exists(new_name):
        return

    old_file = os.path.join(g['base_dir'], src.lstrip('/'))

    logger.info('Pre-compiling {0} -> {1}'.format(old_file, new_name))

    params = {'input': pipes.quote(old_file)}
    use_stdout = True

    if '%(output)s' in compiler:
        use_stdout = False
        params['output'] = pipes.quote(new_name)

    output = envoy.run(compiler % params)
    if output.status_code:
        raise RuntimeError(output.std_err)
    script_list.append(new_name)
    if not use_stdout:
        return
    with open(new_name, 'wb+') as f:
        f.write(output.std_out)



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
