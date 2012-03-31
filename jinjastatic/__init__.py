import os
import sys
import argparse
import logging
import shutil

import yaml
import jinja2
import logging
import jinjatag
import datetime


from utils import is_updated
import staticlib
from watcher import setup_watch
from dependencies import Dependencies

logger = logging.getLogger('jinjastatic')

def run():
    configure_logging()

    p = argparse.ArgumentParser(description="Compile static templates")
    p.add_argument('-s', '--source', required=True,
                   help="Source file or directory.")
    p.add_argument('-d', '--dest',
                   help="Destination file or directory.")
    p.add_argument('-w', '--watch', action="store_true", default=False,
                   help="Watch for changed files.")
    p.add_argument('-f', '--full', action="store_true", default=False,
                   help="Do not perform an incremental compilation, and do everything.")
    p.add_argument('-p', '--production', action="store_true", default=False,
                   help="Minify and compile static files for use in production.")
    p.add_argument('-c', '--config', default='config.yml',
                   help='Name of config file with settings.')
    p.add_argument('-q', '--quiet', action="store_true", default=False,
                   help='Suppress output')
    p.add_argument('-x', '--compiledir', default=None,
                   help='Default directory to house compiled files.')
    args = p.parse_args()

    if args.quiet:
        logger.setLevel(logging.ERROR)

    if args.production:
        if args.compiledir:
            compiledir = args.compiledir
        else:
            compiledir = os.path.join(args.dest, 'compiled')


        if not os.path.exists(compiledir):
            os.makedirs(compiledir)
    else:
        compiledir = None

    config = {}
    if os.path.exists(args.config):
        with open(args.config) as f:
            config = yaml.load(f.read())

    env, loader = get_jinja_env(args.source)
    dependencies = Dependencies(args.source, env, loader)
    dependencies.load_graph()

    if args.watch:
        compile_jinja(args.source, args.dest, config, True, True, compiledir, dependencies)
        setup_watch(args.source,
                    FileHandler(args.source, args.dest, config, dependencies),
                    ['.*', '*#*', '*~'],
                    )
        return

    compile_jinja(args.source, args.dest, config, not args.full and not args.production, not args.production, compiledir, dependencies)


def compile_jinja(source, dest, config, incremental, debug, compiledir, dependencies):
    env = get_jinja_env(source)[0]

    staticlib.clear_data()

    staticlib.set_config(debug, config, source)

    if incremental:
        changed = walk_for_changed(source, dest, dependencies)
    else:
        changed = ()

    if not debug:
        walk_and_compile(env, source, dest, incremental, False, changed)
        staticlib.compile(source, compiledir, dest)
    walk_and_compile(env, source, dest, incremental, True, changed)

def walk_and_compile(env, source, dest, incremental, save, changed):
    for dirpath, dirnames, filenames in os.walk(source, followlinks=True):
        reldir = dirpath[len(source):].lstrip('/')
        for filename in filenames:
            if not filename.lower().endswith('.html'):
                if save:
                    copy_file(os.path.join(source, reldir, filename),
                              os.path.join(dest, reldir, filename),
                              incremental)
                continue
            if save:
                target_file = os.path.join(dest, reldir, filename)
            else:
                target_file = None
            try:
                if not incremental or os.path.join(reldir, filename) in changed:
                    compile_file(env, os.path.join(reldir, filename),
                                 os.path.join(dirpath, filename), target_file, False)
            except Exception as e:
                logger.error("   In file {0}: {1}".format(os.path.join(reldir, filename),
                                                        str(e)), exc_info=True)

def walk_for_changed(source, dest, dependencies):
    changed = set()
    for dirpath, dirnames, filenames in os.walk(source, followlinks=True):
        reldir = dirpath[len(source):].lstrip('/')
        for filename in filenames:
            if not filename.lower().endswith('.html'):
                continue
            name = os.path.join(reldir, filename)
            if is_updated(os.path.join(source, reldir, filename),
                          os.path.join(dest, reldir, filename)):
                changed.add(name)
                changed.update(dependencies.get_affected_files(name))
    return changed


class FileHandler(object):
    def __init__(self, source, dest, config, dependencies):
        self.source = source
        self.dest = dest
        self.config = config
        self.dependencies = dependencies

    def __call__(self, files):
        env = get_jinja_env(self.source)[0]
        for fname in files:
            self.dependencies.recompute_file(fname)
        total_changed = set()
        for fname in files:
            total_changed.add(fname)
            total_changed.update(self.dependencies.get_affected_files(fname))
        for fname in total_changed:
            if fname.lower().endswith('.html'):
                target_file = os.path.join(self.dest, fname)
                compile_file(env, fname, os.path.join(self.source, fname),
                             target_file, False)
            else:
                copy_file(os.path.join(self.source, fname),
                          os.path.join(self.dest, fname),
                          True)

def copy_file(source, dest, incremental):
    if not incremental or is_updated(source, dest):
        if not os.path.exists(os.path.dirname(dest)):
            os.makedirs(os.path.dirname(dest))
        shutil.copyfile(source, dest)

def compile_file(env, source_name, source_file, dest_file, incremental):
    if incremental and not is_updated(source_file, dest_file):
        return

    if dest_file:
        logger.debug("Compiling {0} -> {1}".format(source_file, dest_file))
    ctx = {
        'datetime': datetime,
        'env': EnvWrapper(),
        }
    try:
        result = env.get_template(source_name).render(ctx).encode('utf8')
    except Exception as e:
        logger.error("Error compiling {0}".format(source_name), exc_info=True)
        return
    if not dest_file:
        return
    with with_dir(open, dest_file, 'w+') as f:
        f.write(result)

def get_jinja_env(source):
    jinja_tag = jinjatag.JinjaTag()
    loader = jinja2.FileSystemLoader(source)
    env = jinja2.Environment(loader=loader, extensions=[jinja_tag])
    jinja_tag.init()
    return env, loader

def with_dir(callback, filename, *args, **kwargs):
    dirname = os.path.dirname(filename)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    return callback(filename, *args, **kwargs)

def configure_logging():
    logger.setLevel(logging.DEBUG)
    fh = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)


class EnvWrapper(object):
    def __getattr__(self, name):
        return os.environ.get(name, '')



if __name__ == '__main__':
    run()
