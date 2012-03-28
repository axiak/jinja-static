import os
import sys
import argparse
import logging
import shutil

import yaml
import jinja2
import logging
import jinjatag


from utils import is_updated
import staticlib
from watcher import setup_watch

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

    if args.watch:
        compile_jinja(args.source, args.dest, config, True, True, compiledir)
        setup_watch(args.source, FileHandler(args.source, args.dest, config))
        return

    compile_jinja(args.source, args.dest, config, not args.full and not args.production, not args.production, compiledir)


def compile_jinja(source, dest, config, incremental, debug, compiledir):
    env = get_jinja_env(source)

    staticlib.clear_data()

    staticlib.set_config(debug, config, source)
    if not debug:
        walk_and_compile(env, source, dest, incremental, save=False)
        staticlib.compile(source, compiledir, dest)
    walk_and_compile(env, source, dest, incremental, save=True)

def walk_and_compile(env, source, dest, incremental, save=True):
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
                if filename.startswith('_'):
                    logger.debug("Skipping {0}".format(filename))
                    continue
            else:
                target_file = None
            try:
                compile_file(env, os.path.join(reldir, filename),
                             os.path.join(dirpath, filename), target_file, incremental)
            except Exception as e:
                logger.error("   In file {0}: {1}".format(os.path.join(reldir, filename),
                                                        str(e)), exc_info=True)

class FileHandler(object):
    def __init__(self, source, dest, config):
        self.source = source
        self.dest = dest
        self.config = config

    def __call__(self, files):
        env = get_jinja_env(self.source)
        for fname in files:
            if fname.lower().endswith('.html'):
                target_file = os.path.join(self.dest, fname)
                if fname.startswith('_'):
                    logger.debug("Skipping {0}".format(fname))
                    continue
                compile_file(env, fname, os.path.join(self.source, fname),
                             target_file, True)
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
    result = env.get_template(source_name).render().encode('utf8')
    if not dest_file:
        return
    with with_dir(open, dest_file, 'w+') as f:
        f.write(result)

def get_jinja_env(source):
    jinja_tag = jinjatag.JinjaTag()
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(source), extensions=[jinja_tag])
    jinja_tag.init()
    return env

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


if __name__ == '__main__':
    run()
