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

In development mode, one would expect the rendered HTML to look like:

```html
<html>
  <head>
    <script src="/js/jquery.js" type="text/javascript"></script>
    <script src="/js/other-js.js" type="text/javascript"></script>
    <link rel="stylesheet" type="text/css" href="/css/mycss.css">
  </head>
  <body>
    ...
    <script src="/coffee/mycoffee.js" type="text/javascript"></script>
  </body>
</html>
```

Whereas in production the generated HTML would look closer to this:

```html
<html>
  <head>
    <script src="/compiled/main-424e3efg212_min.js" type="text/javascript"></script>
    <link rel="stylesheet" type="text/css" href="/compiled/main-2ef32ac2a3_min.css">
  </head>
  <body>
    ...
    <script src="/compiled/main-323ce23ae3e_min.js" type="text/javascript"></script>
  </body>
</html>
```

Note that all media files in the same block of code are combined automatically (the grouping is done on whether or not you specify `head=True`).


## License

The project is released under the MIT license