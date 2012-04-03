# jinja-static

Jinja-static is a static template compilation system kind of like Jekyll designed to be used
with real sites that serve all of their html statically. Its design goals are:

 - To be instantaneous in development
 - To have all javscript/css minification happen as would be required for production
 - To be extensible

## Design

Right now there's a single command, `jinja-static` which will run everything for you with a few options.

The static templates are built up in jinja2 with a few added tags for asset management.


## Asset Management

The tags provided for asset management are:

 - `script`
 - `style`
 - `coffee`
 - `less`

For `script` and `coffee`, the keyword argument `src` is expected, while the keyword argument `href` for style and less is expected.

Here's an example of it in use:

```jinja
<html>
  <head>
    {% script src="/js/jquery.js" head=True %}
    {% script src="/js/other-js.js" head=True %}
    {% style href="/css/mycss.css" head=True %}
  </head>
  <body>
    ...
    {% coffee src="/coffee/mycoffee.coffee" %}
  </body>
</html>
```




## License

The project is released under the MIT license