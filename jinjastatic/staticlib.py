import os
import sys
import glob
import time
import pipes
import shutil
import random
import tempfile
import traceback
import hashlib
import urlparse
import logging
import collections
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

import envoy
import jinjatagext

from utils import is_updated
import notify

try:
    notify.register("Jinja-Static")
except Exception as e:
    sys.stderr.write("Notifications not supported: {0}\n".format(traceback.format_exc()))

logger = logging.getLogger('jinjastatic')

extensions = {
    'text/css': 'css',
    'text/javascript': 'js',
    }

pre_compilers = {
                # compiler, new mime type, new ext, on-demand compilation
    'text/less': ('lessc %(input)s', 'text/css', 'css', False),
    'text/coffeescript': ('coffee --join %(output)s -c %(input)s', 'text/javascript', 'js', True),
    }

ext_mime = {
    'less': 'text/less',
    'coffee': 'text/coffeescript',
    'js': 'text/javascript',
    'css': 'text/css',
}

compilers = {
    'text/javascript': './runyui.sh --nomunge %(input)s',
    'text/css': 'uglifycss %(input)s',
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

def _handle_tag(type_, ctx, src, debug=False, head=False, **kwargs):
    kwargs.setdefault('type', type_)
    format = style_formats[type_]
    if g['debug']:
        if type_ in pre_compilers and pre_compilers[type_][3]:
            src = rename_ext(src, pre_compilers[type_][2])
            kwargs['type'] = pre_compilers[type_][1]
        return format.format(
            src,
            u' '.join('{0}={1!r}'.format(k, _force_str(v)) for k, v in kwargs.items()))
    elif debug:
        return u''
    key = (type_, head)
    compiled_key = (pre_compilers.get(type_, (None, type_))[1], head)
    format = style_formats[compiled_key[0]]
    ctxname = ctx.name
    min_dict = g['minified'].setdefault(ctxname, {})

    if min_dict.get(compiled_key):
        return ''
    elif ctxname in g.get(compiled_key, {}) and g['compiled']:
        files = OrderedDict([(g['compiled'][orig], 1)
                             for orig in g[compiled_key][ctxname]]).keys()
        min_dict[compiled_key] = True
        src = urlparse.urljoin(g['config'].get('static_root', ''), src)
        return u'\n'.join(format.format(urlparse.urljoin(g['config'].get('static_root', ''), src),
                                        'type="{0}"'.format(compiled_key[0]))
                          for src in files)
    elif type_ in pre_compilers:
        pre_compile(src, type_, head, ctxname)
        return u''
    else:
        g[key].setdefault(ctxname, []).append(src.lstrip('/'))
    return '**FIRSTPASS**'


style_formats = {
    'text/javascript': u'<script src="{0}" {1}></script>',
    'text/css': u'<link rel="stylesheet" href="{0}" {1}>',
    'text/less': u'<link rel="stylesheet/less" href="{0}" {1}>',
    'text/coffeescript': u'<script src="{0}" {1}></script>',
}


@jinjatagext.simple_context_tag
def script(ctx, src, **kwargs):
    return _handle_tag(u'text/javascript', ctx,
                       src, **kwargs)


@jinjatagext.simple_context_tag
def style(ctx, href, **kwargs):
    return _handle_tag(u'text/css', ctx, href, **kwargs)

@jinjatagext.simple_context_tag
def less(ctx, href, **kwargs):
    return _handle_tag(u'text/less', ctx, href, **kwargs)

@jinjatagext.simple_context_tag
def coffee(ctx, src, **kwargs):
    return _handle_tag(u'text/coffeescript', ctx,
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

    static_dirs = set()

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
            combined_file_obj = None
            if len(absfilelist) == 1:
                combined_file = absfilelist[0]
            else:
                combined_file_obj = _combine_files(absfilelist, ext)
                combined_file = combined_file_obj.name

            compiler_fmt = compilers[key[0]]
            if '%(input)s' in compiler_fmt:
                data = None
                cmd = compiler_fmt % {'input': combined_file}
            else:
                data = read_file_data([combined_file])
                cmd = compiler_fmt
            output = run_command(cmd, data=data)

            with open(abstarget, 'wb+') as f:
                f.write(output.std_out)
            target = os.path.join(rel_output, target)
            g['compiled'].update(dict((filename, target) for filename in filelist))

            if key[0] == 'text/css':
                static_dirs.update(os.path.dirname(filename) for filename in absfilelist)

    for d in static_dirs:
        for dirpath, dirnames, filenames in os.walk(d, followlinks=True):
            reldir = dirpath[len(d):].lstrip('/')
            target_dir = os.path.join(output_dir, reldir)
            for filepath in filenames:
                target_path = os.path.join(target_dir, filepath)
                filepath = os.path.join(dirpath, filepath)
                if is_updated(filepath, target_path):
                    new_dir = os.path.dirname(target_path)
                    if not os.path.exists(new_dir):
                        os.makedirs(new_dir)
                    shutil.copyfile(filepath, target_path)

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
    compiler, type_, ext = pre_compilers[type_][:3]
    key = (type_, head)
    script_list = g[key].setdefault(ctxname, [])
    old_file = os.path.join(g['base_dir'], src.lstrip('/'))
    new_name = os.path.join(os.path.dirname(src).strip('/'), 'compiled-' + hashlib.md5(src).hexdigest()) + "." + ext

    if new_name in script_list:
        return

    script_list.append(new_name)

    new_name = os.path.join(g['base_dir'], new_name.lstrip('/'))

    if not is_updated(old_file, new_name):
        return

    _run_precompile(old_file, new_name, compiler)


def _run_precompile(old_file, new_file, compiler):
    logger.info('Pre-compiling {0} -> {1}'.format(old_file, new_file))

    params = {'input': pipes.quote(old_file)}
    use_stdout = True

    if '%(output)s' in compiler:
        use_stdout = False
        params['output'] = pipes.quote(new_file)

    output = run_command(compiler % params)

    if not use_stdout:
        return
    with open(new_file, 'wb+') as f:
        f.write(output.std_out)
    return

def handle_precompile_file(source, dest, incremental=False):
    if '.' not in os.path.basename(source):
        return False
    ext = source.rsplit('.', 1)[1]
    if not (ext in ext_mime and ext_mime[ext] in pre_compilers):
        return False
    compiler, type_, new_ext, incremental = pre_compilers[ext_mime[ext]][:4]
    if not incremental:
        return
    dest = rename_ext(dest, new_ext)
    if incremental and not is_updated(source, dest):
        return False
    _run_precompile(source, dest, compiler)
    return True

def read_file_data(filelist):
    result = []
    for fname in filelist:
        with open(fname) as f:
            result.append(f.read())
    return ''.join(result)

def _remove_old_files(output_dir):
    for fname in glob.glob(os.path.join(output_dir, '*_min*')):
        os.unlink(fname)

def _combine_files(filelist, ext):
    tmp = tempfile.NamedTemporaryFile(suffix='.' + ext)
    for filename in filelist:
        with open(filename, 'rb') as f:
            shutil.copyfileobj(f, tmp)
        if ext.lower() == 'js':
            tmp.write(';')
    tmp.flush()
    return tmp

def _decorate_key(filename, key):
    first, second = filename.rsplit('.', 1)
    return first + '-' + key + '.' + second

def _gen_key():
    return hashlib.md5(str(time.time() + random.random())).hexdigest()[:10] + '_min'


def _force_str(obj):
    if isinstance(obj, unicode):
        return obj.encode('utf8')
    return str(obj)

def rename_ext(filename, new_ext):
    if '.' not in os.path.basename(filename):
        return filename + '.' + new_ext
    else:
        return filename.rsplit('.', 1)[0] + '.' + new_ext

def run_command(cmd, **kwargs):
    try:
        output = envoy.run(cmd, **kwargs)
        std_err = output.std_err
    except Exception as e:
        status_code = 1
        std_err = traceback.format_exc()
    else:
        status_code = output.status_code
    if status_code:
        notify.send("Failure in Jinja-Static command", cmd,
                    icon='gtk-dialog-critical', urgency='CRITICAL')
        sys.stderr.write("Error while running command: {0}\n".format(cmd))
        sys.exit(1)
    return output
