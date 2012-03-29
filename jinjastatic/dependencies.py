import os
import jinja2
from jinja2 import meta
import networkx as nx
import logging

logger = logging.getLogger('jinjastatic')

class Dependencies(object):
    def __init__(self, source, env, loader):
        self.env = env
        self.loader = loader
        self.source = source
        self.dependency_graph = nx.DiGraph()

    def get_affected_files(self, template, acc=None):
        if not acc:
            acc = set()
        if template in self.dependency_graph:
            for child in self.dependency_graph.successors(template):
                acc.add(child)
                self.get_affected_files(child, acc)
        return list(acc)

    def load_graph(self):
        self.depencency_graph = nx.DiGraph()
        for relpath, dirnames, filenames in os.walk(self.source):
            for filename in filenames:
                if not filename.endswith('.html'):
                    continue
                path = os.path.join(relpath, filename)
                name = path[len(self.source):].lstrip('/')
                requirements = self._get_requirements(name)
                for requirement in requirements:
                    if requirement:
                        self.dependency_graph.add_edge(requirement, name)

    def recompute_file(self, template):
        old_attached = []
        if not template.endswith('.html'):
            return
        if template in self.dependency_graph:
            old_attached = list(self.dependency_graph.successors(template))
            self.dependency_graph.remove_node(template)
        for requirement in self._get_requirements(template):
            if requirement:
                self.dependency_graph.add_edge(requirement, template)
        for old_name in old_attached:
            self.dependency_graph.add_edge(template, old_name)

    def _get_requirements(self, template_name):
        try:
            return list(meta.find_referenced_templates(self.env.parse(self.loader.get_source(self.env, template_name))))
        except Exception as e:
            logger.error("Error analyzing {0}".format(template_name), exc_info=True)
        return []

