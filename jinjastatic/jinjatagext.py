from jinja2 import nodes
try:
    from jinjatag import simple_context_tag
except ImportError:
    from jinjatag import decorators
    @decorators.create_extension_decorator
    class simple_context_tag(decorators.BaseTag):
        def parse_attrs(self, parser, add_id=True, with_context=False):
            attrs = {}
            while parser.stream.current.type != 'block_end':
                node = parser.parse_assign_target(with_tuple=False)

                if parser.stream.skip_if('assign'):
                    attrs[node.name] = parser.parse_expression()
                else:
                    attrs[node.name] = nodes.Const(node.name)
            if with_context:
                attrs['ctx'] = nodes.ContextReference()
            return nodes.Dict([nodes.Pair(nodes.Const(k), v) for k,v in attrs.items()])

        def parse(self, parser):
            tag = parser.stream.next()
            attrs = self.parse_attrs(parser, with_context=True)
            return nodes.Output([self.call_method('_call_simple_tag', args=[attrs])])

        def _call_simple_tag(self, attrs):
            return self.call_tag_func(**attrs)
